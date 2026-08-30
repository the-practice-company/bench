"""Слой «форма содержательно»: четыре наблюдения и одна молчаливая починка."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import zones
from scripts.maintain import structural
from tests.maintain_fixture import materialise

SCAFFOLD = Path(__file__).resolve().parent.parent / "scaffold"


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


def only(findings, cls):
    return [f for f in places(findings) if f[2] == cls]


def snapshot(root):
    """(байты файлов, множество каталогов) — всё дерево, кроме `.git/`.

    Каталоги берутся отдельно от файлов, а не выводятся из их путей:
    манифест волны 4 знает только непустые каталоги, а созданная пустая
    папка — тоже изменение дерева, и инвариант 2 волны про неё тоже.
    """
    files, dirs = {}, set()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        if path.is_dir():
            dirs.add(rel)
        else:
            files[rel] = path.read_bytes()
    return files, dirs


class TestSilentFix(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_zone_from_the_map_without_a_folder_is_created(self):
        """Аддитивно и без суждения: зон всегда восемь, и это фиксировано §9."""
        self.assertFalse((self.root / "knowledge").exists())
        created, _ = structural.run(self.root)
        self.assertEqual(created, ["knowledge", "knowledge/README.md"])
        self.assertTrue((self.root / "knowledge" / "README.md").exists())

    def test_the_created_readme_is_the_scaffold_byte_for_byte(self):
        """Взято из каркаса, а не сочинено: третьего определения формы нет."""
        structural.run(self.root)
        self.assertEqual(
            (self.root / "knowledge" / "README.md").read_bytes(),
            (SCAFFOLD / "knowledge" / "README.md").read_bytes())

    def test_all_eight_zones_exist_after_the_run(self):
        structural.run(self.root)
        present = {p.name for p in self.root.iterdir() if p.is_dir()}
        self.assertEqual(sorted(z for z in zones.ZONES if z not in present), [])


class TestReported(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)
        _, self.findings = structural.run(self.root)

    def test_a_top_level_folder_outside_the_map_is_reported_not_moved(self):
        """«Починка» была бы либо правкой фиксированной карты (§9), либо
        переездом содержимого (§1). Ни то ни другое плагину не принадлежит."""
        self.assertIn(("vault", 1, "map-tree-divergence",
                       "папка верхнего уровня, которой нет в карте зон"),
                      places(self.findings))
        self.assertTrue((self.root / "vault").exists())

    def test_a_direction_without_a_line_in_areas_readme_is_reported(self):
        self.assertIn(("areas/hiring", 1, "map-tree-divergence",
                       "направление без строки в areas/README.md"),
                      places(self.findings))

    def test_the_divergence_list_is_exact_and_the_listed_direction_is_absent(self):
        """`areas/work/` в перечислении направлений названо, и находки о нём
        быть не должно. Утверждение списком, а не одним `assertIn`: признак,
        не увидевший ни одной строки перечисления, красит все направления
        подряд и проходит проверку на одно посаженное."""
        self.assertEqual(
            only(self.findings, "map-tree-divergence"),
            [("areas/hiring", 1, "map-tree-divergence",
              "направление без строки в areas/README.md"),
             ("vault", 1, "map-tree-divergence",
              "папка верхнего уровня, которой нет в карте зон")])

    def test_the_archetype_mismatch_carries_numbers_not_a_verdict(self):
        """Честная половина требования §19: поведение вычислимо, значит
        показывается. Приведение отвергнуто — §20 относит выбор архетипа
        к суждению, а смена архетипа производит N ошибок гейта."""
        self.assertEqual(
            only(self.findings, "archetype-mismatch"),
            [("core/people", 1, "archetype-mismatch",
              "объявлен registry, записей со сменой status: 1 "
              "(правок после первого коммита: 1)")])

    def test_the_archetype_is_not_rewritten(self):
        text = (self.root / "core" / "people" / "README.md").read_text(encoding="utf-8")
        self.assertIn("archetype: registry", text)

    def test_an_ignored_binary_nobody_links_to_is_reported(self):
        """Предикат — не «сверх порога», а «игнорируется git и на него никто
        не сослался». Порога в байтах волна не заводит и не наследует."""
        self.assertEqual(
            only(self.findings, "unreferenced-ignored-binary"),
            [("sources/dump.bin", 1, "unreferenced-ignored-binary",
              "файл вне git, на него никто не сослался")])


class TestTheReferenceHalfOfThePredicate(unittest.TestCase):
    """Половина предиката «на него никто не сослался» — живая, а не украшение."""

    def test_a_referenced_ignored_file_is_not_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp)
            readme = root / "core" / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8")
                              + "\nВыгрузка лежит в `sources/dump.bin`.\n",
                              encoding="utf-8")
            _, findings = structural.run(root)
            self.assertEqual(only(findings, "unreferenced-ignored-binary"), [])


class TestTheSourceOfTheIgnoredList(unittest.TestCase):
    """Почему `ls-files`, а не `status --ignored`, и почему это проверяется.

    На фикстуре как она есть оба источника отвечают одинаково: `sources/`
    держит отслеженные файлы, поэтому git его не схлопывает, и подмена
    источника прошла бы зелёным прогоном. Схлопывание начинается там, где
    игнорируется **всё** содержимое каталога, — этот случай собирается
    здесь, и без него выбор источника нечем фальсифицировать.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def _ignore(self, line):
        path = self.root / ".gitignore"
        path.write_text(path.read_text(encoding="utf-8") + line + "\n",
                        encoding="utf-8")

    def test_a_file_in_a_wholly_ignored_directory_is_named(self):
        (self.root / "tmp" / "dumps").mkdir()
        (self.root / "tmp" / "dumps" / "a.bin").write_bytes(b"\x00\x01")
        self._ignore("tmp/dumps/")
        _, findings = structural.run(self.root)
        self.assertIn(("tmp/dumps/a.bin", 1, "unreferenced-ignored-binary",
                       "файл вне git, на него никто не сослался"),
                      places(findings))

    def test_an_ignored_nested_repository_is_not_a_binary(self):
        """Строка с косой на конце — вложенный репозиторий: это `foreign-repo`
        волны 4, а не файл, и находкой этого класса он быть не может."""
        nested = self.root / "tmp" / "nested"
        nested.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(nested), check=True)
        (nested / "a.md").write_text("x", encoding="utf-8")
        self._ignore("tmp/nested/")
        _, findings = structural.run(self.root)
        self.assertEqual([f for f in places(findings)
                          if f[0].startswith("tmp/nested")], [])


class TestReadOnlyExceptTheZone(unittest.TestCase):
    def test_nothing_but_the_missing_zone_appeared_on_disk(self):
        """Слой показывает; создаёт он ровно одно — недостающую зону."""
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp)
            files_before, dirs_before = snapshot(root)
            structural.run(root)
            files_after, dirs_after = snapshot(root)
            self.assertEqual(sorted(set(files_after) - set(files_before)),
                             ["knowledge/README.md"])
            self.assertEqual(sorted(set(dirs_after) - set(dirs_before)),
                             ["knowledge"])
            self.assertEqual(sorted(set(files_before) - set(files_after)), [])
            self.assertEqual(
                sorted(rel for rel, raw in files_before.items()
                       if files_after[rel] != raw), [])

    def test_a_second_run_changes_nothing(self):
        """Инвариант 2 волны: второй прогон не меняет ни байта."""
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp)
            structural.run(root)
            before = snapshot(root)
            created, findings = structural.run(root)
            self.assertEqual(created, [])
            self.assertEqual(snapshot(root), before)
            self.assertEqual(len(only(findings, "map-tree-divergence")), 2)


class TestGitFailureIsNotSilence(unittest.TestCase):
    """Незыблемое №4: не сумев спросить git, слой отказывает, а не молчит.

    Пустой список коммитов и пустой список игнорируемого выглядят как
    «ничего не нашлось» — то есть отсутствие находки. Отказ git прошёл бы
    зелёным прогоном, ничего не проверив."""

    def test_a_tree_without_git_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp)
            shutil.rmtree(root / ".git")
            with self.assertRaises(RuntimeError):
                structural.run(root)


if __name__ == "__main__":
    unittest.main()
