"""`init-tree`: дерево становится откатываемым, чужие репозитории — неприкасаемыми."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import init_tree, tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from tests.foreign import NESTED, committer, materialise, no_committer


def git_out(root, *args):
    return subprocess.run(["git", *args], cwd=str(root),
                          capture_output=True, text=True).stdout


class TestInit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=True)

    def test_it_creates_a_repository_and_the_as_found_commit(self):
        report, code = init_tree.run(self.root)
        self.assertEqual(code, EXIT_OK, report)
        self.assertTrue((self.root / ".git").is_dir())
        self.assertEqual(git_out(self.root, "log", "--format=%s").strip(),
                         "как было")

    def test_the_nested_repository_is_excluded_before_the_commit(self):
        """Измерено: без этого `git add -A` кладёт папку gitlink'ом, и клон
        теряет её содержимое целиком, а `revert` вернуть его не может."""
        init_tree.run(self.root)
        tracked = git_out(self.root, "ls-files").split("\n")
        self.assertEqual([t for t in tracked if t.startswith(NESTED + "/")], [])
        exclude = (self.root / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertIn(NESTED + "/", exclude)

    def test_no_gitlink_entered_the_index(self):
        """Прямая проверка того, чем поломка проявляется: режим 160000."""
        init_tree.run(self.root)
        self.assertNotIn("160000", git_out(self.root, "ls-files", "-s"))

    def test_the_base_commit_is_recorded_by_sha_not_by_message(self):
        """Опознавание коммита по тексту сообщения — правило без механизма:
        автор вправе написать что угодно, и `revert` встанет на этом молча."""
        init_tree.run(self.root)
        head = git_out(self.root, "rev-parse", "HEAD").strip()
        self.assertEqual(tree.read_base(self.root), head)

    def test_the_nested_repository_is_reported_not_touched(self):
        report, _ = init_tree.run(self.root)
        self.assertIn("foreign-repo", report)
        self.assertIn(NESTED, report)
        self.assertTrue((self.root / NESTED / ".git").is_dir())

    def test_running_twice_does_not_move_the_base(self):
        """Прерванный ADOPT на следующем запуске читает свой же план, а не
        объявляет новую точку отката."""
        init_tree.run(self.root)
        first = tree.read_base(self.root)
        (self.root / "новое.md").write_text("х", encoding="utf-8")
        report, code = init_tree.run(self.root)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(tree.read_base(self.root), first)

    def test_the_second_run_does_not_commit_what_the_turn_wrote(self):
        """Вторая половина того же: точка отката стоит на месте только если
        `add -A` второго прогона не втянул написанное после неё.

        `-z` здесь не украшение: без него git отдаёт русское имя в
        C-кавычках, и сравнивать пришлось бы с `"\\320\\275..."`.
        """
        init_tree.run(self.root)
        (self.root / "новое.md").write_text("х", encoding="utf-8")
        init_tree.run(self.root)
        self.assertEqual(
            [x for x in git_out(self.root, "status", "--porcelain", "-z").split("\0") if x],
            ["?? новое.md"])

    def test_the_exclusion_block_is_rewritten_not_appended(self):
        """Дописывание давало бы по строке на каждый повторный запуск, и
        `.git/info/exclude` рос бы дублями до бесконечности."""
        init_tree.run(self.root)
        init_tree.run(self.root)
        exclude = (self.root / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertEqual(exclude.count(NESTED + "/"), 1)
        self.assertEqual(exclude.count(init_tree.MARK), 1)


class TestNested(unittest.TestCase):
    """Единственный механически определяемый факт о чужом репозитории (§18)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=True)

    def test_it_names_the_repository_and_does_not_descend_into_it(self):
        """Спуск внутрь дал бы строку на каждый вложенный репозиторий чужого
        дерева — и `.git/info/exclude`, исключающий их поимённо вместо папки.

        Репозиторий в репозитории кладётся намеренно: без него утверждение
        «не спускаемся» нечем отличить от «спускаемся, но внутри пусто», и
        снятый `continue` проходит зелёным. Проверено — проходил.
        """
        inner = self.root / NESTED / "внутренний"
        inner.mkdir()
        (inner / "код.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=str(inner), check=True)
        self.assertEqual(tree.nested_repositories(self.root), [NESTED])


class TestInside(unittest.TestCase):
    """Предикат границы чужой; здесь проверяется, что его спросили правильно.

    Переставленные аргументы `boundary.outside` дают `inside` тождественно
    ложный: `revert` тогда отказывает по каждому пути, а отказ по пути вне
    корня проходит зелёным — то есть проверка границы выглядит работающей,
    ничего не проверяя.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)

    def test_a_path_in_the_root_is_inside(self):
        self.assertTrue(tree.inside(self.root, "README.md"))
        self.assertTrue(tree.inside(self.root, "journal/2026-01-04.md"))

    def test_a_path_above_the_root_is_not(self):
        self.assertFalse(tree.inside(self.root, "../соседний"))
        self.assertFalse(tree.inside(self.root, "journal/../../соседний"))

    def test_an_absolute_path_elsewhere_is_not(self):
        self.assertFalse(tree.inside(self.root, str(Path(self.tmp.name) / "чужое")))


class TestDeclined(unittest.TestCase):
    """Критерий 4: автор отказался заводить git."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)

    def test_no_git_means_nothing_is_created_and_nothing_is_changed(self):
        before = tree.manifest(self.root)
        report, code = init_tree.run(self.root, no_git=True)
        self.assertEqual(code, EXIT_OK, report)
        self.assertFalse((self.root / ".git").exists())
        self.assertEqual(tree.manifest(self.root), before)
        self.assertIn("git не заведён", report)


class TestIdentity(unittest.TestCase):
    def test_a_missing_git_identity_is_named_not_swallowed(self):
        """Коммит без `user.email` падает. Молчаливый отказ здесь означал бы
        дерево без точки отката при зелёном коде возврата.

        Личность снимается и из конфига, и из среды: переменные `GIT_*`
        старше конфига, и пустой `user.email` при выставленных переменных
        никакого отказа не даёт.
        """
        no_committer(self)
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp, git_root=False, nested=False)
            subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
            subprocess.run(["git", "config", "user.email", ""], cwd=str(root), check=True)
            subprocess.run(["git", "config", "user.name", ""], cwd=str(root), check=True)
            report, code = init_tree.run(root)
            self.assertEqual(code, EXIT_VIOLATION, report)
            self.assertIn("коммит «как было» не сделан", report)
            self.assertIsNone(tree.read_base(root))
