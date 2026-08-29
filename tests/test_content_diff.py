"""Критерий 1: чем доказывается, что содержимое не изменено."""

import tempfile
import unittest
from pathlib import Path

from scripts.maintain import content_diff, surface
from tests.maintain_fixture import materialise

# Пути фикстуры, на которых стоят правила сравнения. Названы здесь, а не
# по месту: переименование записи в фикстуре обязано ронять набор целиком,
# а не одну строку в середине.
RECORD = "areas/work/journal/items/2026-08-25.md"
DEAL = "projects/deals/items/one.md"
VIEW = "projects/deals/views.base"


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


class TestSurfaceIsStatic(unittest.TestCase):
    """Ловушка, ради которой поверхность объявлена, а не выведена."""

    def test_the_surface_is_a_literal_and_not_derived_from_a_run(self):
        """Выведенная из того, что прогон записал, проверка становится
        тавтологией: исключает ровно изменившееся и не краснеет никогда."""
        self.assertEqual(
            [entry.pattern for entry in surface.SURFACE],
            ["**/views.base",
             "**/README.md#frontmatter:archetype,values",
             ".claude/rules/*.md",
             "CLAUDE.md#section:Zone map,Placement rule",
             "areas/README.md#table",
             "*/README.md#absent",
             "**/items/*.md#frontmatter:absent-key",
             ".gitignore#append",
             ".claude/settings.json#merge:permissions.deny,claudeMdExcludes",
             ".twinkle-repo-builder#json:version",
             "OPEN-THREADS.md#append"])

    def test_the_surface_does_not_move_when_the_tree_does(self):
        """Перечисление литералом — утверждение, и утверждать его надо
        исполняемо. Совпадение списка выше держит только состав; что
        поверхность не смотрит на дерево, видно лишь так: тронуть дерево и
        спросить снова."""
        before = ([entry.pattern for entry in surface.SURFACE],
                  surface.covers(VIEW, "bytes"),
                  surface.covers(RECORD, "body"))
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp)
            (root / VIEW).write_text("переписан целиком\n", encoding="utf-8")
            (root / RECORD).write_text("переписан целиком\n", encoding="utf-8")
            after = ([entry.pattern for entry in surface.SURFACE],
                     surface.covers(VIEW, "bytes"),
                     surface.covers(RECORD, "body"))
        self.assertEqual(before, after)

    def test_the_body_of_a_record_is_not_on_the_surface(self):
        self.assertFalse(surface.covers(RECORD, "body"))

    def test_core_is_never_on_the_surface(self):
        for what in ("body", "frontmatter-value", "bytes"):
            self.assertFalse(surface.covers("core/me.md", what), what)

    def test_a_view_in_core_is_form_because_the_view_belongs_to_the_plugin(self):
        """§13 отдаёт `views.base` плагину целиком, и зона тут ни при чём:
        `core/people` — коллекция (наблюдение 4 фикстуры). Зоновый запрет
        поверх перечисления заставил бы MAINTAIN читать собственную законную
        починку как правку содержимого и откатывать себя на каждом прогоне."""
        self.assertTrue(surface.covers("core/people/views.base", "bytes"))

    def test_inside_a_knowledge_submodule_nothing_is_form(self):
        """Единственное зоновое исключение, и оно не про содержимое, а про
        чужой репозиторий: рецепт запрещает туда писать статически."""
        for what in ("bytes", "frontmatter-value", "create"):
            self.assertFalse(
                surface.covers("knowledge/чужое/views.base", what), what)
        self.assertTrue(surface.covers("knowledge/README.md", "create"))

    def test_a_star_does_not_cross_a_slash(self):
        """`fnmatch` здесь не годится: его `*` пересекает косую, и
        `*/README.md` совпал бы с `a/b/c/README.md` — поверхность стала бы
        шире отсуженной."""
        self.assertTrue(surface.covers("core/README.md", "create"))
        self.assertFalse(surface.covers("areas/work/journal/README.md", "create"))
        self.assertTrue(surface.covers("areas/work/journal/views.base", "bytes"))


class TestContentDiff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)
        self.before = content_diff.snapshot(self.root)

    def _diff(self, field_map=()):
        return content_diff.compare(self.before,
                                    content_diff.snapshot(self.root),
                                    field_map=field_map)

    def test_an_untouched_tree_produces_nothing(self):
        self.assertEqual(places(self._diff()), [])

    def test_rewriting_a_record_body_is_content_modified(self):
        path = self.root / RECORD
        path.write_text(path.read_text(encoding="utf-8") + "\nдописано\n",
                        encoding="utf-8")
        self.assertEqual(places(self._diff()), [
            (RECORD, 1, "content-modified", "тело markdown-файла изменилось")])

    def test_prose_of_claude_md_is_content_like_any_other_body(self):
        """Форм-секции `CLAUDE.md` на поверхности есть, описание домена —
        нет. Правка первого абзаца обязана краснеть."""
        path = self.root / "CLAUDE.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("Домен: работа студии",
                                     "Домен: переписан за автора"),
                        encoding="utf-8")
        self.assertEqual(places(self._diff()), [
            ("CLAUDE.md", 1, "content-modified", "тело markdown-файла изменилось")])

    def test_changing_an_existing_frontmatter_value_is_content_modified(self):
        path = self.root / DEAL
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("status: new", "status: decided"),
                        encoding="utf-8")
        self.assertEqual(places(self._diff()), [
            (DEAL, 1, "content-modified", "значение поля изменилось: status")])

    def test_removing_a_frontmatter_key_is_content_modified(self):
        path = self.root / DEAL
        text = path.read_text(encoding="utf-8")
        path.write_text("\n".join(l for l in text.split("\n")
                                  if not l.startswith("status:")),
                        encoding="utf-8")
        self.assertEqual(places(self._diff()), [
            (DEAL, 1, "content-modified", "ключ frontmatter исчез: status")])

    def test_rewriting_a_views_base_is_not_content_modified(self):
        """`views.base` целиком принадлежит плагину: §13 прямо об этом."""
        path = self.root / VIEW
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual(places(self._diff()), [])

    def test_a_new_frontmatter_key_is_legal_only_with_a_field_map_row(self):
        """Последняя строка правил сравнения — то, что делает `field-map`
        несущим: критерий 5 и критерий 1 держатся одним механизмом."""
        path = self.root / RECORD
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("---\n", "---\ncreated: 2026-08-25\n", 1),
                        encoding="utf-8")
        self.assertEqual(places(self._diff()), [
            (RECORD, 1, "content-modified", "поле появилось мимо field-map: created")])
        row = (RECORD, "created", "", "2026-08-25", "computed", "git-first-commit")
        self.assertEqual(places(self._diff(field_map=[row])), [])

    def test_a_field_map_row_with_a_different_value_does_not_excuse_it(self):
        """Иначе таблица оправдывала бы что угодно, назвав поле."""
        path = self.root / RECORD
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("---\n", "---\ncreated: 1999-01-01\n", 1),
                        encoding="utf-8")
        row = (RECORD, "created", "", "2026-08-25", "computed", "git-first-commit")
        self.assertEqual([f[2] for f in places(self._diff(field_map=[row]))],
                         ["content-modified"])

    def test_a_field_map_row_for_another_path_does_not_excuse_it(self):
        """Ключ оправдания — пара «путь и поле», а не одно поле: иначе одна
        строка накрывала бы то же поле во всём дереве."""
        path = self.root / RECORD
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("---\n", "---\ncreated: 2026-08-25\n", 1),
                        encoding="utf-8")
        row = (DEAL, "created", "", "2026-08-25", "computed", "git-first-commit")
        self.assertEqual([f[2] for f in places(self._diff(field_map=[row]))],
                         ["content-modified"])

    def test_a_field_map_row_does_not_excuse_an_existing_key(self):
        """Строка оправдывает **появление** ключа и ничего больше. Иначе
        достаточно было бы назвать поле, чтобы переписать под ним значение."""
        path = self.root / DEAL
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("status: new", "status: decided"),
                        encoding="utf-8")
        row = (DEAL, "status", "new", "decided", "computed", "какое-то-правило")
        self.assertEqual([f[2] for f in places(self._diff(field_map=[row]))],
                         ["content-modified"])

    def test_a_disappeared_file_is_content_modified(self):
        (self.root / "core" / "people" / "items" / "anna.md").unlink()
        self.assertEqual(places(self._diff()), [
            ("core/people/items/anna.md", 1, "content-modified", "файл исчез")])

    def test_a_changed_binary_outside_the_surface_is_content_modified(self):
        """Нетекстовый файл сравнивается байтами и никуда не деётся из
        сравнения: `sources/dump.bin` игнорируется git'ом, но лежит в дереве."""
        path = self.root / "sources" / "dump.bin"
        path.write_bytes(path.read_bytes() + b"\x00")
        self.assertEqual(places(self._diff()), [
            ("sources/dump.bin", 1, "content-modified", "байты файла изменились")])

    def test_an_empty_collection_removed_under_the_deletion_predicate_is_not(self):
        """Единственное удаление, которое MAINTAIN делает сам. Пустая
        коллекция не может содержать содержимого по определению."""
        for path in sorted((self.root / "projects" / "stale").rglob("*"),
                           reverse=True):
            if path.is_file():
                path.unlink()
        self.assertEqual(
            places(content_diff.compare(
                self.before, content_diff.snapshot(self.root),
                deleted=("projects/stale",))), [])

    def test_the_deletion_predicate_covers_the_named_path_and_nothing_beside_it(self):
        """`projects/stale` не оправдывает `projects/stale-2`: предикат
        сравнивает сегменты, а не префикс строки."""
        for path in sorted((self.root / "projects" / "deals").rglob("*"),
                           reverse=True):
            if path.is_file():
                path.unlink()
        findings = content_diff.compare(self.before,
                                        content_diff.snapshot(self.root),
                                        deleted=("projects/deal",))
        self.assertEqual(sorted({f[2] for f in places(findings)}),
                         ["content-modified"])
        self.assertEqual(len(places(findings)), 4)


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_the_git_directory_is_not_part_of_the_tree(self):
        """Иначе собственный коммит MAINTAIN прочитался бы как правка
        содержимого: `.git/` меняется от каждого хода git."""
        shot = content_diff.snapshot(self.root)
        self.assertEqual([rel for rel in shot if rel.startswith(".git")],
                         [".gitignore"])

    def test_ignored_and_untracked_files_are_in_the_snapshot(self):
        """Периметр снимка — дерево, а не индекс git. Игнорируемое сравнением
        не покрывалось бы вовсе, и правка туда прошла бы молча."""
        shot = content_diff.snapshot(self.root)
        self.assertEqual([rel for rel in shot if rel.endswith(".bin")],
                         ["sources/dump.bin"])
