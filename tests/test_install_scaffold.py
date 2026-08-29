"""Установщик каркаса: копия побайтово, слияние настроек, граница корня."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_frontmatter, check_links, install_scaffold, zones
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from tests.test_fixtures import places

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


def _blob_id(path, algorithm):
    """Идентификатор объекта git для файла, посчитанный локально.

    Формула самого git (`blob <длина>\\0<содержимое>`), поэтому подпроцесс на
    каждый файл не нужен, а сравнение остаётся сравнением хешей.

    Считается по байтам файла, а не через `git hash-object`: у последнего по
    умолчанию работают фильтры атрибутов, и включённый `core.autocrlf` дал бы
    одинаковые хеши при разном содержимом — то есть спрятал бы ровно ту
    поломку, ради которой это сравнение и заведено.
    """
    data = path.read_bytes()
    return hashlib.new(algorithm, b"blob %d\x00" % len(data) + data).hexdigest()


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


class TestFirstCommit(unittest.TestCase):
    """Критерий 2 волны. Коммит 1 — база рецепта: при обновлении версии
    `git diff` против него показывает, что автор изменил сам, а что приехало
    из пакета, и без побайтового равенства это неразличимо.

    Сравнение — по хешам объектов git, а не глазами: визуальный диф не
    отличает «одинаково» от «похоже».

    Коммит здесь собирается из списка, который вернул сам `install`, — ровно
    так его соберёт скилл задачи 9. Поэтому утверждается заодно и полнота
    отчёта: записанный, но не названный файл останется вне коммита и
    покраснеет в `test_the_working_tree_is_clean_after_the_commit`.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _new_repo(self.tmp.name)
        self.written = install_scaffold.install(SCAFFOLD, self.root)
        _git(self.root, "add", *self.written)
        _git(self.root, "commit", "-q", "-m", "scaffold")
        # Алгоритм спрашивается у git, а не предполагается. Репозиторий с
        # `objectFormat = sha256` дал бы двадцать три несовпадения разом и
        # обвинил бы в них установщик — красное не по своей причине.
        self.algorithm = _git(self.root, "rev-parse",
                              "--show-object-format").stdout.strip()

    def _tree(self):
        """Пути коммита и идентификаторы их объектов.

        `-z`, а не построчный разбор: git экранирует не-ASCII и кавычки в
        путях, и построчное чтение потребовало бы второго разборщика этого
        экранирования — с собственными ошибками.
        """
        listing = _git(self.root, "ls-tree", "-r", "-z", "HEAD").stdout
        out = {}
        for record in listing.split("\0"):
            if not record:
                continue
            meta, path = record.split("\t", 1)
            out[path] = meta.split()[2]
        return out

    def test_the_commit_carries_the_scaffold_blob_for_blob(self):
        """Расхождение по ключу значит, что файл не доехал; расхождение по
        значению — что доехал изменённым."""
        expected = {}
        for source in sorted(p for p in SCAFFOLD.rglob("*") if p.is_file()):
            rel = source.relative_to(SCAFFOLD).as_posix()
            if rel == FRAGMENT:
                continue
            expected[rel] = _blob_id(source, self.algorithm)
        actual = {path: blob for path, blob in self._tree().items()
                  if path != SETTINGS}
        self.assertEqual(actual, expected)

    def test_the_only_path_that_is_not_a_copy_is_the_merged_settings(self):
        """Исключение из побайтового равенства ровно одно и названо поимённо.

        Множество копий строится **без** фрагмента. Сверка с полным составом
        каркаса признала бы уехавший `settings-fragment.json` законной копией
        — то есть промолчала бы о единственном файле, которому в инстансе
        делать нечего.
        """
        copied = {p.relative_to(SCAFFOLD).as_posix()
                  for p in SCAFFOLD.rglob("*") if p.is_file()} - {FRAGMENT}
        self.assertEqual(set(self._tree()) - copied, {SETTINGS})

    def test_the_merged_settings_carry_the_fragment(self):
        """Читается объект коммита, а не файл на диске: утверждение всего
        класса — про коммит, и рабочее дерево здесь не свидетель."""
        self.assertEqual(
            json.loads(_git(self.root, "show", "HEAD:" + SETTINGS).stdout),
            json.loads((SCAFFOLD / FRAGMENT).read_text(encoding="utf-8")))

    def test_the_working_tree_is_clean_after_the_commit(self):
        """Ничего не осталось вне коммита: иначе «коммит 1 — каркас»
        неправда, и следующий Stop-хук найдёт незакоммиченное.

        `--porcelain` без `--ignored` — тот же вопрос и в той же форме, в
        какой его задаёт `hooks/summary.py`: файл, спрятанный от git строкой
        `.gitignore` каркаса, не увидит и хук.
        """
        self.assertEqual(_git(self.root, "status", "--porcelain").stdout, "")

    def test_both_gates_are_green_on_the_first_commit(self):
        """Красное здесь — дефект пакета, а не репозитория: каркас во всех
        инстансах один и тот же.

        Не повтор `tests/test_scaffold.py`: там гейты читают каркас, здесь —
        инстанс, где вместо `settings-fragment.json` лежит слитый
        `settings.json`, а рядом появился `.git/`. Глоб `settings*.json`
        разбирает оба имени, и промолчать гейт обязан на обоих.
        """
        self.assertEqual(places(check_links.scan(self.root)), [])
        self.assertEqual(places(check_frontmatter.scan(self.root)), [])

    def test_the_commit_creates_all_eight_zones(self):
        """Зона заводится всегда, даже пустой: пустая зона наблюдаема, а
        git пустых каталогов не хранит — держит зону её README, и утверждать
        надо именно его, иначе зона «есть» из-за любого случайного файла.
        """
        missing = sorted({"%s/README.md" % zone for zone in zones.ZONES}
                         - set(self._tree()))
        self.assertEqual(missing, [])

    def test_the_commit_creates_no_collection(self):
        """§17: коллекция без настоящей записи не заводится ни одна.

        Признаков два, как и у каркаса: вид и папка записей. Пустой `items/`
        в коммит не попадает по построению, но непустой — это уже
        сочинённая за автора запись, и молчать о ней нельзя.
        """
        stray = [path for path in sorted(self._tree())
                 if path.endswith("views.base") or "/items/" in path]
        self.assertEqual(stray, [])
