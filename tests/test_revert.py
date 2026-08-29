"""Критерий 1: `revert` возвращает дерево побайтово. И три фальсификатора."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import init_tree, revert, tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from tests.foreign import NESTED, committer, materialise

# Полный этап мутации в путях: донор переезда, его цель, правленый файл,
# удалённая папка, созданный файл и файл, у которого сменился режим.
STAGED = ["notes", "areas", "README.md", "archive", "OPEN-THREADS.md",
          "pipeline"]


def stage(root):
    """Переезд, правка ссылки, удаление, создание, смена режима.

    Смена режима здесь не для полноты списка: `git mv` режим сохраняет, а
    восстановление записью байтов — нет, и без этой мутации фальсификатор
    «содержимое вернули, режим нет» нечем отличить от честного отката.
    """
    (root / "areas" / "work").mkdir(parents=True)
    tree.git(root, "mv", "notes", "areas/work/notes")
    text = (root / "README.md").read_text(encoding="utf-8")
    (root / "README.md").write_text(text.replace("[[meeting]]",
                                                 "[[areas/work/notes/meeting]]"),
                                    encoding="utf-8")
    tree.git(root, "rm", "-r", "-q", "archive")
    (root / "OPEN-THREADS.md").write_text("# нити\n", encoding="utf-8")
    (root / "pipeline" / "build.py").chmod(0o755)
    return list(STAGED)


def porcelain(root):
    out = tree.git(root, "status", "--porcelain", "-z").stdout
    return [line for line in out.split("\0") if line]


class TestByteForByte(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=True)
        init_tree.run(self.root)

    def test_the_manifest_returns_to_what_it_was(self):
        before = tree.manifest(self.root)
        paths = stage(self.root)
        self.assertNotEqual(tree.manifest(self.root), before)
        report, code = revert.run(self.root, paths)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(tree.manifest(self.root), before)

    def test_the_tree_is_not_left_dirty(self):
        """Ход не заканчивается грязным деревом: разводка «незакоммиченное —
        значит здесь работал человек» несущая для `Stop`-хука волны 2.
        Индекс, снятый без выкладки, оставил бы дерево грязным при сошедшемся
        манифесте."""
        revert.run(self.root, stage(self.root))
        self.assertEqual(porcelain(self.root), [])

    def test_the_nested_repository_is_untouched_throughout(self):
        """Манифест берёт и его файлы — не потому, что `revert` их вернёт
        (он не может), а потому, что равенство доказывает: никто не дотянулся."""
        before = {k: v for k, v in tree.manifest(self.root)[0].items()
                  if k.startswith(NESTED + "/")}
        paths = stage(self.root)
        revert.run(self.root, paths)
        after = {k: v for k, v in tree.manifest(self.root)[0].items()
                 if k.startswith(NESTED + "/")}
        self.assertEqual(after, before)
        self.assertTrue((self.root / NESTED / ".git").is_dir())

    def test_the_emptied_directory_is_named_in_the_report(self):
        """Настоящий остаток: каталог, из которого `revert` вынул последний
        файл. Git пустых каталогов не знает и убрать его не может, поэтому он
        назван поимённо, а не замолчан."""
        report, _ = revert.run(self.root, stage(self.root))
        self.assertIn("опустевший каталог остался: areas/work/notes", report)

    def test_the_base_commit_is_not_uncommitted(self):
        base = tree.read_base(self.root)
        revert.run(self.root, stage(self.root))
        self.assertEqual(tree.head(self.root), base)


class TestSweep(unittest.TestCase):
    """Что подметание берёт и чего не берёт."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        init_tree.run(self.root)

    def test_a_non_ascii_name_created_by_the_turn_is_swept(self):
        """Без `-z` git отдаёт такое имя в C-кавычках, и удаление промахивается
        мимо файла: он остаётся в дереве, а `revert` падает
        `FileNotFoundError`. Чужие деревья здесь русские целиком."""
        (self.root / "заметки").mkdir()
        (self.root / "заметки" / "новое.md").write_text("х", encoding="utf-8")
        report, code = revert.run(self.root, ["заметки"])
        self.assertEqual(code, EXIT_OK, report)
        self.assertFalse((self.root / "заметки" / "новое.md").exists())

    def test_an_ignored_file_survives_the_sweep(self):
        """Подметание идёт через `git ls-files --others --exclude-standard`.
        Обходом файловой системы оно снесло бы игнорируемое безвозвратно.

        `.gitignore` стоит в списке **первым** намеренно: подметание,
        идущее по одному пути за раз, успевает удалить его и на следующем
        пути уже не видит, что `local/` игнорируется. Список берётся один
        раз на все пути — иначе смысл `revert` зависел бы от их порядка.
        """
        (self.root / ".gitignore").write_text("local/\n", encoding="utf-8")
        (self.root / "local").mkdir()
        (self.root / "local" / "заметка.md").write_text("моё", encoding="utf-8")
        report, code = revert.run(self.root, [".gitignore", "local", "README.md"])
        self.assertEqual(code, EXIT_OK, report)
        self.assertTrue((self.root / "local" / "заметка.md").exists())
        self.assertFalse((self.root / ".gitignore").exists())

    def test_a_repository_that_appeared_after_the_base_commit_is_not_deleted(self):
        """Наблюдено на живом git: неисключённый вложенный репозиторий
        приезжает из `ls-files --others` **каталогом** — `vendor/`. Удаление
        такой записи как файла роняет `revert` посреди отката, а «починка»
        рекурсивным удалением снесла бы чужой репозиторий целиком — ровно то,
        что откатить нельзя ничем.
        """
        vendor = self.root / "vendor"
        vendor.mkdir()
        (vendor / "lib.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=str(vendor), check=True)
        report, code = revert.run(self.root, ["vendor", "README.md"])
        self.assertEqual(code, EXIT_OK, report)
        self.assertTrue((vendor / "lib.py").exists())
        self.assertTrue((vendor / ".git").is_dir())
        self.assertIn("foreign-repo", report)
        self.assertIn("vendor", report)


class TestRefusals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)

    def test_a_path_outside_the_root_is_refused(self):
        """Незыблемое №6. `revert` зовут, когда доверия к происходящему
        меньше всего, и именно тогда он не имеет права выйти за корень."""
        init_tree.run(self.root)
        report, code = revert.run(self.root, ["../соседний"])
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("вне корня", report)

    def test_a_refused_path_stops_the_whole_call(self):
        """Отказ по одному пути не исполняет остальные: половина отката —
        состояние, которого не было ни до, ни после."""
        init_tree.run(self.root)
        before = tree.manifest(self.root)
        (self.root / "OPEN-THREADS.md").write_text("# нити\n", encoding="utf-8")
        revert.run(self.root, ["OPEN-THREADS.md", "../соседний"])
        self.assertNotEqual(tree.manifest(self.root), before)

    def test_without_a_head_there_is_nothing_to_return_to(self):
        report, code = revert.run(self.root, ["README.md"])
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("нет коммита", report)


class TestFalsifiers(unittest.TestCase):
    """Три реализации, обязанные покраснеть. Без них критерий 1 — обещание."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        init_tree.run(self.root)
        self.before = tree.manifest(self.root)
        self.paths = stage(self.root)

    def test_the_literal_command_from_the_spec_does_not_restore(self):
        """§18: «`revert <пути>` — `git checkout -- <пути>`». Восстанавливает
        из индекса, а `move` индекс уже изменил: на живом git `notes`,
        `archive` и `OPEN-THREADS.md` падают на pathspec, а остальные пути
        выкладываются из индекса, то есть не меняются."""
        for path in self.paths:
            tree.git(self.root, "checkout", "--", path)
        self.assertNotEqual(tree.manifest(self.root), self.before)

    def test_restoring_without_deleting_the_created_target_does_not_restore(self):
        for path in self.paths:
            tree.git(self.root, "checkout", "HEAD", "--", path)
        after = tree.manifest(self.root)
        self.assertNotEqual(after, self.before)
        self.assertEqual(sorted(set(after[0]) - set(self.before[0])),
                         ["OPEN-THREADS.md", "areas/work/notes/meeting.md"])

    def test_content_without_mode_does_not_restore(self):
        """Восстановление записью байтов вместо выкладки из `HEAD`: содержимое
        сходится всё, до последнего файла, — и манифест всё равно расходится,
        потому что режим остался тем, каким его сделала мутация."""
        for path in self.paths:
            tree.git(self.root, "reset", "-q", "HEAD", "--", path)
            for rel in tree.git_zlines(self.root, "ls-tree", "-r", "--name-only",
                                       "-z", "HEAD", "--", path):
                blob = subprocess.run(["git", "show", "HEAD:" + rel],
                                      cwd=str(self.root), capture_output=True)
                (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
                (self.root / rel).write_bytes(blob.stdout)
            for rel in tree.git_zlines(self.root, "ls-files", "--others",
                                       "--exclude-standard", "-z", "--", path):
                (self.root / rel).unlink()
        after = tree.manifest(self.root)
        self.assertNotEqual(after, self.before)
        self.assertEqual({k: v[0] for k, v in after[0].items()},
                         {k: v[0] for k, v in self.before[0].items()})
