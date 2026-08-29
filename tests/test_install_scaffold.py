"""Установщик каркаса: копия побайтово, слияние настроек, граница корня."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import install_scaffold
from scripts.findings import EXIT_OK, EXIT_VIOLATION

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "scaffold"
FRAGMENT = ".claude/settings-fragment.json"
SETTINGS = ".claude/settings.json"


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root),
                          capture_output=True, text=True, check=True)


def _new_repo(base, name="instance"):
    root = Path(base) / name
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "create@example.invalid")
    _git(root, "config", "user.name", "create")
    return root


def _tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


class TestCopy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _new_repo(self.tmp.name)

    def test_every_scaffold_file_lands_byte_for_byte(self):
        install_scaffold.install(SCAFFOLD, self.root)
        differing = []
        for source in sorted(p for p in SCAFFOLD.rglob("*") if p.is_file()):
            rel = source.relative_to(SCAFFOLD).as_posix()
            if rel == FRAGMENT:
                continue
            target = self.root / rel
            if not target.exists() or target.read_bytes() != source.read_bytes():
                differing.append(rel)
        self.assertEqual(differing, [])

    def test_the_fragment_itself_does_not_travel(self):
        """Файл существует ради слияния; в инстансе ему делать нечего."""
        install_scaffold.install(SCAFFOLD, self.root)
        self.assertFalse((self.root / FRAGMENT).exists())

    def test_it_reports_every_path_it_wrote(self):
        written = install_scaffold.install(SCAFFOLD, self.root)
        self.assertIn(SETTINGS, written)
        self.assertIn("CLAUDE.md", written)
        self.assertNotIn(FRAGMENT, written)
        self.assertEqual(written, sorted(written))

    def test_it_refuses_without_git(self):
        """`git init` — первое действие, до первой записи: иначе ничего
        из последующего не откатывается, а Stop-хук встречает каталог без git."""
        with tempfile.TemporaryDirectory() as bare:
            with self.assertRaises(install_scaffold.Refused) as caught:
                install_scaffold.install(SCAFFOLD, Path(bare))
            self.assertIn("git", str(caught.exception))
            self.assertEqual(list(Path(bare).iterdir()), [])

    def test_it_never_overwrites_what_is_already_there(self):
        (self.root / "CLAUDE.md").write_text("автор писал сюда сам\n",
                                             encoding="utf-8")
        with self.assertRaises(install_scaffold.Refused) as caught:
            install_scaffold.install(SCAFFOLD, self.root)
        self.assertIn("CLAUDE.md", str(caught.exception))
        self.assertEqual((self.root / "CLAUDE.md").read_text(encoding="utf-8"),
                         "автор писал сюда сам\n")

    def test_a_refusal_leaves_no_half_installed_scaffold(self):
        """Отказ — до первой записи, а не посреди неё.

        Утверждения о содержимом одного файла на это не хватает: в порядке
        обхода `CLAUDE.md` четырнадцатый, и установщик, пишущий по файлу за
        раз, оставил бы автору тринадцать чужих файлов и правил `.claude/`,
        которых он не заводил, — а тест остался бы зелёным.
        """
        (self.root / "CLAUDE.md").write_text("автор писал сюда сам\n",
                                             encoding="utf-8")
        with self.assertRaises(install_scaffold.Refused):
            install_scaffold.install(SCAFFOLD, self.root)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),
                         [".git", "CLAUDE.md"])

    def test_it_names_every_file_it_would_have_overwritten(self):
        """Список целиком, а не первый по алфавиту.

        Усыновление кладёт каркас в чужое дерево, где занято обычно не одно
        имя. Отказ по одному файлу за прогон превращает разбор в двадцать
        четыре прогона, и каждый следующий называет файл, о котором автор
        ещё не знал.
        """
        (self.root / "CLAUDE.md").write_text("своё\n", encoding="utf-8")
        (self.root / "core").mkdir()
        (self.root / "core" / "README.md").write_text("своё\n", encoding="utf-8")
        with self.assertRaises(install_scaffold.Refused) as caught:
            install_scaffold.install(SCAFFOLD, self.root)
        self.assertIn("CLAUDE.md", str(caught.exception))
        self.assertIn("core/README.md", str(caught.exception))

    def test_it_writes_nothing_outside_the_root(self):
        """Незыблемое №6: плагин не пишет ничего вне корня репозитория."""
        neighbour = Path(self.tmp.name) / "чужое-дерево"
        neighbour.mkdir()
        (neighbour / "заметка.md").write_text("чужое\n", encoding="utf-8")
        before = _tree_hash(neighbour)
        install_scaffold.install(SCAFFOLD, self.root)
        self.assertEqual(_tree_hash(neighbour), before)

    def test_a_symlink_inside_the_root_does_not_carry_the_scaffold_out(self):
        """Тот же запрет, но с посаженным способом его обойти.

        Соседний тест зелен и без единой проверки границы: писать наружу
        установщику просто неоткуда, все его цели склеены из корня. Дыра
        открывается симлинком внутри корня — а усыновление приходит именно
        в чужое дерево, где симлинк ставил не плагин. Без вопроса к
        `boundary.outside` одиннадцать правил и фрагмент уезжают в соседний
        каталог, и `mkdir(parents=True)` заводит там путь, которого не было.
        """
        neighbour = Path(self.tmp.name) / "чужое-дерево"
        neighbour.mkdir()
        (neighbour / "заметка.md").write_text("чужое\n", encoding="utf-8")
        before = _tree_hash(neighbour)
        (self.root / ".claude").symlink_to(neighbour, target_is_directory=True)
        with self.assertRaises(install_scaffold.Refused) as caught:
            install_scaffold.install(SCAFFOLD, self.root)
        self.assertIn(".claude/rules/areas.md", str(caught.exception))
        self.assertEqual(_tree_hash(neighbour), before)


class TestSettingsMerge(unittest.TestCase):
    """Слияние, а не копирование: `settings.json` уже существует, им включён
    плагин, и копия поверх выключила бы плагин первым же действием."""

    FRAGMENT_DATA = json.loads((SCAFFOLD / FRAGMENT).read_text(encoding="utf-8"))

    def test_an_absent_file_is_created_from_the_fragment(self):
        self.assertEqual(install_scaffold.merge_settings({}, self.FRAGMENT_DATA),
                         self.FRAGMENT_DATA)

    def test_existing_keys_survive(self):
        existing = {"enabledPlugins": {"twinkle-repo-builder": True}}
        merged = install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertEqual(merged["enabledPlugins"],
                         {"twinkle-repo-builder": True})

    def test_deny_is_extended_without_duplicates(self):
        existing = {"permissions": {"deny": ["Edit(./knowledge/*/**)",
                                             "Bash(rm:*)"]}}
        merged = install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertEqual(merged["permissions"]["deny"],
                         ["Edit(./knowledge/*/**)", "Bash(rm:*)",
                          "Write(./knowledge/*/**)"])

    def test_a_neighbouring_permission_key_is_untouched(self):
        existing = {"permissions": {"allow": ["Read(./core/**)"]}}
        merged = install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertEqual(merged["permissions"]["allow"], ["Read(./core/**)"])

    def test_excludes_are_extended_without_duplicates(self):
        existing = {"claudeMdExcludes": ["**/knowledge/**", "**/vendor/**"]}
        merged = install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertEqual(merged["claudeMdExcludes"],
                         ["**/knowledge/**", "**/vendor/**"])

    def test_merging_twice_changes_nothing(self):
        once = install_scaffold.merge_settings({}, self.FRAGMENT_DATA)
        self.assertEqual(install_scaffold.merge_settings(once, self.FRAGMENT_DATA),
                         once)

    def test_the_existing_object_is_not_mutated(self):
        """«Без потерь» проверяется и с той стороны, откуда читают повторно.

        Слияние поверх чужого списка на месте — та же потеря, только
        отложенная: вызвавший держит ссылку на разобранные настройки и
        увидит в них дописанное рецептом.
        """
        existing = {"permissions": {"deny": ["Bash(rm:*)"]}}
        install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertEqual(existing, {"permissions": {"deny": ["Bash(rm:*)"]}})

    def test_a_value_of_another_shape_is_never_reshaped(self):
        """Незыблемое №4: строку вместо списка не подгоняют молча.

        `list("**/knowledge/**")` рассыпает её на пятнадцать элементов, и
        настройки автора портятся без единой строки об этом. Форма чужого
        значения — повод отказаться, а не повод угадать.
        """
        existing = {"claudeMdExcludes": "**/knowledge/**"}
        with self.assertRaises(install_scaffold.Refused) as caught:
            install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertIn("claudeMdExcludes", str(caught.exception))
        self.assertEqual(existing["claudeMdExcludes"], "**/knowledge/**")

    def test_a_permissions_key_of_another_shape_is_refused(self):
        """То же самое этажом ниже: `permissions` списком — не объект.

        `dict(["Bash(rm:*)"])` роняет слияние `ValueError`'ом, то есть
        трассировкой и кодом возврата 1, которого в контракте
        `scripts/findings.py` нет вовсе.
        """
        existing = {"permissions": ["Bash(rm:*)"]}
        with self.assertRaises(install_scaffold.Refused) as caught:
            install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertIn("permissions", str(caught.exception))

    def test_broken_json_is_not_the_same_as_absent(self):
        """Файл есть — значит его писали. Затирать нельзя, молчать нельзя."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_repo(tmp)
            (root / ".claude").mkdir()
            (root / SETTINGS).write_text("{не json", encoding="utf-8")
            with self.assertRaises(install_scaffold.Refused) as caught:
                install_scaffold.install(SCAFFOLD, root)
            self.assertIn(SETTINGS, str(caught.exception))
            self.assertEqual((root / SETTINGS).read_text(encoding="utf-8"),
                             "{не json")

    def test_valid_json_that_is_not_an_object_is_refused_too(self):
        """Разобранный JSON бывает списком, строкой и `null`.

        Тот же факт, что и у битого файла: настройками это не читается, а
        файл писали. `dict([])` вдобавок отдаёт пустой объект — то есть
        путь, на котором чужое содержимое подменяется каркасным молча.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_repo(tmp)
            (root / ".claude").mkdir()
            (root / SETTINGS).write_text('["Bash(rm:*)"]', encoding="utf-8")
            with self.assertRaises(install_scaffold.Refused) as caught:
                install_scaffold.install(SCAFFOLD, root)
            self.assertIn(SETTINGS, str(caught.exception))
            self.assertEqual((root / SETTINGS).read_text(encoding="utf-8"),
                             '["Bash(rm:*)"]')

    def test_an_existing_settings_file_survives_the_install(self):
        """Слияние проверяется на диске, а не только на чистой функции.

        `enabledPlugins` — тот самый ключ, которым включён сам плагин:
        копия поверх выключила бы его первым же действием установки.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_repo(tmp)
            (root / ".claude").mkdir()
            (root / SETTINGS).write_text(
                json.dumps({"enabledPlugins": {"twinkle-repo-builder": True}}),
                encoding="utf-8")
            install_scaffold.install(SCAFFOLD, root)
            merged = json.loads((root / SETTINGS).read_text(encoding="utf-8"))
            self.assertEqual(merged["enabledPlugins"],
                             {"twinkle-repo-builder": True})
            self.assertEqual(merged["claudeMdExcludes"],
                             self.FRAGMENT_DATA["claudeMdExcludes"])


class TestCommandLine(unittest.TestCase):
    def test_exit_codes_follow_the_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_repo(tmp)
            ok = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "install_scaffold.py"),
                 str(root)], capture_output=True, text=True)
            self.assertEqual(ok.returncode, EXIT_OK)
            self.assertIn("CLAUDE.md", ok.stdout)

            again = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "install_scaffold.py"),
                 str(root)], capture_output=True, text=True)
            self.assertEqual(again.returncode, EXIT_VIOLATION)
            self.assertIn("CLAUDE.md", again.stderr)
