"""Форма коллекции: три архетипа, готовый вид, ни одной пустой единицы."""

import tempfile
import unittest
from pathlib import Path

from scripts import check_frontmatter, check_links
from scripts.basefile import parse_base
from scripts.frontmatter import parse as parse_frontmatter
from scripts.maintain import form_collection

RECORD = """\
---
type: deal
created: 2026-08-29
status: open
---

# Первая сделка

Настоящая запись, а не заглушка.
"""


class TestForm(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _make(self, archetype="pipeline"):
        return form_collection.create(
            self.root, "projects/deals", archetype,
            record_name="first.md", record_text=RECORD)

    def test_the_three_archetypes_are_a_closed_set(self):
        self.assertEqual(list(form_collection.ARCHETYPES),
                         ["journal", "pipeline", "registry"])

    def test_it_creates_readme_views_and_the_record(self):
        created = self._make()
        self.assertEqual(created, [
            "projects/deals",
            "projects/deals/README.md",
            "projects/deals/items",
            "projects/deals/items/first.md",
            "projects/deals/views.base",
        ])

    def test_the_record_reaches_the_disk_as_it_came(self):
        """Содержимое записи — авторское, и генератор его не трогает
        (незыблемое №1). Утверждается побайтово: «файл создан» о подмене
        текста молчит."""
        self._make()
        self.assertEqual(
            (self.root / "projects" / "deals" / "items" / "first.md")
            .read_text(encoding="utf-8"), RECORD)

    def test_without_a_record_nothing_reaches_the_disk(self):
        """Критерий 3. Развернуть скелет и откатить отвергнуто: оборванный
        прогон оставляет пустую коллекцию, а она не сигналит ничем."""
        with self.assertRaises(form_collection.NoContent):
            form_collection.create(self.root, "projects/deals", "pipeline",
                                   record_name=None, record_text=None)
        self.assertFalse((self.root / "projects").exists())

    def test_a_record_of_blank_text_is_no_record(self):
        """Пустая причина не считается причиной — то же правило, что у
        `_filled` гейта frontmatter. Иначе инвариант обходится пробелом."""
        with self.assertRaises(form_collection.NoContent):
            form_collection.create(self.root, "projects/deals", "pipeline",
                                   record_name="first.md", record_text="  \n")
        self.assertFalse((self.root / "projects").exists())

    def test_an_archetype_outside_the_set_creates_nothing(self):
        with self.assertRaises(ValueError):
            form_collection.create(self.root, "projects/deals", "дневничок",
                                   record_name="first.md", record_text=RECORD)
        self.assertFalse((self.root / "projects").exists())

    def test_a_taken_path_creates_nothing_and_keeps_what_was_there(self):
        """Второй вызов по тому же пути — отказ, а не дозапись поверх."""
        self._make()
        before = (self.root / "projects" / "deals" / "README.md").read_bytes()
        with self.assertRaises(ValueError):
            form_collection.create(self.root, "projects/deals", "journal",
                                   record_name="second.md", record_text=RECORD)
        self.assertEqual(
            (self.root / "projects" / "deals" / "README.md").read_bytes(),
            before)
        self.assertFalse(
            (self.root / "projects" / "deals" / "items" / "second.md").exists())

    def test_a_record_name_that_is_a_path_creates_nothing(self):
        """Незыблемое №6 у самого генератора. Имя записи приходит и из чужого
        дерева (этап 2 ADOPT), а `..` в нём выводит запись из коллекции —
        измерено: без проверки вызов кладёт файл в `projects/`."""
        with self.assertRaises(ValueError):
            form_collection.create(self.root, "projects/deals", "pipeline",
                                   record_name="../../first.md",
                                   record_text=RECORD)
        self.assertFalse((self.root / "projects").exists())

    def test_a_collection_path_that_escapes_the_root_creates_nothing(self):
        """Тот же примитив, что у гейта ссылок: второго прочтения пути в
        пакете нет.

        Корень — подкаталог временного, а не сам временный: утверждается,
        что **над** корнем не появилось ничего, и утверждение это обязано
        быть про свежий каталог. Проверено снятием проверки: без неё вызов
        кладёт коллекцию рядом с корнем, и она переживает прогон."""
        root = self.root / "repo"
        root.mkdir()
        with self.assertRaises(ValueError):
            form_collection.create(root, "../deals", "pipeline",
                                   record_name="first.md", record_text=RECORD)
        self.assertEqual([p.name for p in self.root.iterdir()], ["repo"])

    def test_the_readme_declares_the_archetype_and_the_pipeline_vocabulary(self):
        self._make("pipeline")
        fields = parse_frontmatter(
            (self.root / "projects" / "deals" / "README.md")
            .read_text(encoding="utf-8"))
        self.assertEqual(fields["archetype"], "pipeline")
        self.assertEqual(fields["values"]["status"], ["open", "decided", "revisited"])

    def test_a_journal_declares_no_vocabulary(self):
        """Словарь принадлежит конвейеру. У журнала статуса нет вовсе."""
        form_collection.create(self.root, "areas/work/journal", "journal",
                               record_name="a.md", record_text=RECORD)
        fields = parse_frontmatter(
            (self.root / "areas" / "work" / "journal" / "README.md")
            .read_text(encoding="utf-8"))
        self.assertNotIn("values", fields)

    def test_the_view_points_at_the_items_folder_of_this_collection(self):
        self._make()
        base = parse_base((self.root / "projects" / "deals" / "views.base")
                          .read_text(encoding="utf-8"))
        self.assertEqual(sorted(base.folders), ["projects/deals/items"])

    def test_the_view_requires_of_a_record_only_what_the_archetype_gives_it(self):
        """Контракт вида утверждается разбором, а не доверием к форме:
        поле, попавшее в `required` по ошибке (`sort:` с `property` и
        `direction` — разобранный случай), сделало бы гейт frontmatter
        красным на каждой свежей коллекции."""
        contract = {}
        for archetype in form_collection.ARCHETYPES:
            root = Path(self.tmp.name) / archetype
            form_collection.create(root, "projects/deals", archetype,
                                   record_name="first.md", record_text=RECORD)
            base = parse_base((root / "projects" / "deals" / "views.base")
                              .read_text(encoding="utf-8"))
            contract[archetype] = (sorted(base.required), sorted(base.known))
        self.assertEqual(contract, {
            "journal": (["created"], []),
            "pipeline": (["status"], ["created"]),
            "registry": (["type"], ["created"]),
        })

    def test_both_gates_are_silent_on_what_it_produced(self):
        """Форма, которую производит плагин, обязана проходить гейты плагина.
        Красное здесь — дефект пакета, а не инстанса."""
        self._make()
        self.assertEqual(
            [(f.path, f.line, f.cls, f.detail)
             for f in check_links.scan(self.root).findings], [])
        self.assertEqual(
            [(f.path, f.line, f.cls, f.detail)
             for f in check_frontmatter.scan(self.root).findings], [])


if __name__ == "__main__":
    unittest.main()
