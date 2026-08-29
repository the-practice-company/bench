"""Критерий 3: единица не заводится без содержимого. Три команды."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import check_frontmatter, check_links
from scripts.basefile import parse_base
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from scripts.maintain import demand, extend, structural
from tests.maintain_fixture import materialise
from tests.test_form_collection import RECORD

PEOPLE = "core/people/views.base"


def places(findings):
    return [(f.path, f.line, f.cls, f.detail) for f in findings]


class TestAddCollection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_with_a_record_the_collection_appears(self):
        report, code = extend.add_collection(
            self.root, "projects/leads", "pipeline",
            record_name="first.md", record_text=RECORD)
        self.assertEqual(code, EXIT_OK, report)
        self.assertTrue((self.root / "projects" / "leads" / "views.base").exists())
        # Отчёт называет созданное поимённо: «заведена» без списка — это
        # утверждение, которое нечем сверить с диском.
        self.assertEqual(report,
                         "заведена коллекция: projects/leads\n"
                         "создано: projects/leads, projects/leads/README.md, "
                         "projects/leads/items, projects/leads/items/first.md, "
                         "projects/leads/views.base\n")

    def test_an_aborted_run_leaves_no_half_of_the_unit_behind(self):
        """Критерий 3 целиком: не только сама единица, но и каталоги,
        созданные по дороге к ней. `mkdir(parents=True)` заводит их заодно,
        и оставленный `projects/deep/` — это ровно та пережившая откат
        половина, которой быть не должно. Каталог, бывший до команды,
        при этом остаётся."""
        def empty(root, collection, archetype, record_name, record_text):
            (Path(root) / collection / "items").mkdir(parents=True)
            return [collection]

        with mock.patch.object(extend.form_collection, "create", empty):
            _, code = extend.add_collection(
                self.root, "projects/deep/ghost", "pipeline",
                record_name="first.md", record_text=RECORD)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertFalse((self.root / "projects" / "deep").exists())
        self.assertTrue((self.root / "projects" / "deals").is_dir())

    def test_headless_without_a_record_creates_nothing_and_asks(self):
        """Критерий 3, и он проверяется отсутствием на диске, а не намерением."""
        report, code = extend.add_collection(
            self.root, "projects/leads", "pipeline",
            record_name=None, record_text=None)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertFalse((self.root / "projects" / "leads").exists())
        threads = (self.root / "OPEN-THREADS.md").read_text(encoding="utf-8")
        self.assertIn("projects/leads", threads)

    def test_the_question_is_asked_once_however_many_times_it_is_refused(self):
        """Нить дописывается по стабильному ключу: второй отказ по тому же
        пути не удваивает вопрос — иначе каждый прогон растил бы файл."""
        for _ in range(2):
            extend.add_collection(self.root, "projects/leads", "pipeline",
                                  record_name=None, record_text=None)
        threads = (self.root / "OPEN-THREADS.md").read_text(encoding="utf-8")
        self.assertEqual(threads.count("add-collection projects/leads"), 1)

    def test_the_post_condition_catches_a_unit_that_reached_the_disk_empty(self):
        """`structure-without-content` — постусловие команды, а не обход
        дерева. Обходом он ловил бы и пустые коллекции слоя спроса, у которых
        свой класс: `empty-collection` — наблюдение о дереве,
        `structure-without-content` — нарушенное обещание команды о себе.

        Проверяется подменённым генератором: команда обязана заметить, что
        то, что она создала, содержимого не несёт, и откатить."""
        def empty(root, collection, archetype, record_name, record_text):
            (Path(root) / collection / "items").mkdir(parents=True)
            return [collection, "%s/items" % collection]

        with mock.patch.object(extend.form_collection, "create", empty):
            report, code = extend.add_collection(
                self.root, "projects/ghost", "pipeline",
                record_name="first.md", record_text=RECORD)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("structure-without-content", report)
        self.assertFalse((self.root / "projects" / "ghost").exists())

    def test_an_empty_collection_of_the_fixture_is_not_this_class(self):
        """Разведение двух классов проверяется на дереве, а не декларируется.

        Обход дерева назвал бы `structure-without-content` обе пустые
        коллекции фикстуры. Утверждается ровно обратное: их видит слой
        спроса и зовёт `empty-collection`, а постусловие команды о них не
        говорит вовсе — оно про единицу, которую команда только что создала.
        """
        _, findings = demand.run(self.root, today="2026-08-29")
        self.assertEqual(
            [f for f in places(findings)
             if f[2] in ("empty-collection", "structure-without-content")],
            [("projects/fresh", 1, "empty-collection", "виды есть, записей ноль"),
             ("projects/stale", 1, "empty-collection", "виды есть, записей ноль")])
        report, code = extend.add_collection(
            self.root, "projects/leads", "pipeline",
            record_name="first.md", record_text=RECORD)
        self.assertEqual(code, EXIT_OK, report)
        self.assertNotIn("structure-without-content", report)

    def test_a_taken_path_is_refused_and_the_collection_stays_as_it_was(self):
        before = (self.root / "projects" / "deals" / "README.md").read_bytes()
        report, code = extend.add_collection(
            self.root, "projects/deals", "journal",
            record_name="first.md", record_text=RECORD)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("путь уже занят", report)
        self.assertEqual(
            (self.root / "projects" / "deals" / "README.md").read_bytes(), before)


class TestAddArea(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def listing(self):
        return (self.root / "areas" / "README.md").read_text(encoding="utf-8")

    def test_a_direction_with_a_purpose_gets_a_folder_and_a_row(self):
        """§4 требует от README зоны `areas` перечисления с фразой назначения.
        Не обновлять его — завести источник дрейфа по построению."""
        report, code = extend.add_area(self.root, "sales", "Продажи и сделки.")
        self.assertEqual(code, EXIT_OK, report)
        self.assertTrue((self.root / "areas" / "sales" / "README.md").exists())
        listing = self.listing()
        self.assertIn("Продажи и сделки.", listing)
        self.assertLess(listing.index("## Directions"),
                        listing.index("Продажи и сделки."))

    def test_the_row_lands_after_the_rows_the_author_wrote(self):
        """Порядок перечисления — авторский. Новое направление дописывается
        в конец списка, а не выше того, что уже написано."""
        extend.add_area(self.root, "sales", "Продажи и сделки.")
        listing = self.listing()
        self.assertLess(listing.index("`areas/work/`"),
                        listing.index("Продажи и сделки."))
        self.assertLess(listing.index("Продажи и сделки."),
                        listing.index("**By threshold.**"))

    def test_the_row_names_the_direction_the_way_the_tree_is_read(self):
        """Строка обязана быть той самой, которую ищет слой «форма
        содержательно»: направление без строки в `areas/README.md` — его
        находка, и заводить направление, тут же становящееся находкой,
        значит производить дрейф, а не снимать его."""
        extend.add_area(self.root, "sales", "Продажи и сделки.")
        self.assertIn("sales", structural._listed_directions(self.root))

    def test_without_a_purpose_neither_the_folder_nor_the_row_appears(self):
        """Содержимое у направления при заведении и есть его назначение."""
        report, code = extend.add_area(self.root, "sales", "")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertFalse((self.root / "areas" / "sales").exists())
        self.assertNotIn("sales", self.listing())
        threads = (self.root / "OPEN-THREADS.md").read_text(encoding="utf-8")
        self.assertIn("add-area sales", threads)

    def test_the_link_gate_is_silent_on_the_row_it_wrote(self):
        """Строка перечисления — ссылка, и гейт ссылок читает её у автора
        первым. Утверждается отчёт целиком до и после: находка, добавленная
        собственной правкой, — это дрейф, заведённый вместо снятого."""
        before = places(check_links.scan(self.root).findings)
        report, code = extend.add_area(self.root, "sales", "Продажи и сделки.")
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(places(check_links.scan(self.root).findings), before)

    def test_a_taken_name_is_refused(self):
        report, code = extend.add_area(self.root, "hiring", "Найм.")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("имя занято", report)

    def test_a_name_that_is_not_a_folder_name_is_refused(self):
        report, code = extend.add_area(self.root, "продажи/сделки", "Х.")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertFalse((self.root / "areas" / "продажи").exists())

    def test_a_readme_without_the_heading_is_refused_before_anything_is_written(self):
        """Заголовок — то место, куда кладётся строка. Нет его — команда
        отказывается, а не выдумывает второе место (§4 и незыблемое №4)."""
        readme = self.root / "areas" / "README.md"
        readme.write_text("# areas\n\nбез заголовка перечисления\n",
                          encoding="utf-8")
        report, code = extend.add_area(self.root, "sales", "Продажи.")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("заголовка перечисления", report)
        self.assertFalse((self.root / "areas" / "sales").exists())


class TestAddView(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def base_text(self, rel=PEOPLE):
        return (self.root / rel).read_text(encoding="utf-8")

    def test_a_view_over_an_empty_folder_is_refused(self):
        """Иначе `extend-structure` заводит ровно то, что слой спроса тут же
        покажет мёртвым."""
        before = self.base_text("areas/work/reviews/views.base")
        report, code = extend.add_view(self.root, "areas/work/reviews",
                                       name="Всё")
        self.assertEqual(code, EXIT_VIOLATION)
        # Причина названа целиком и той же фразой, что у слоя спроса: один
        # и тот же факт о дереве, сказанный двумя разными словами, читается
        # как два разных факта.
        self.assertEqual(report, "отказ: file.inFolder называет папку с нулём "
                                 "записей: areas/work/reviews/drafts\n")
        self.assertEqual(self.base_text("areas/work/reviews/views.base"), before)

    def test_a_collection_without_views_base_is_refused(self):
        report, code = extend.add_view(self.root, "core", name="Всё")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertFalse((self.root / "core" / "views.base").exists())

    def test_a_base_without_a_list_of_views_is_refused(self):
        """Отказ вместо дописывания `views:` за автора: файл, где списка
        видов нет, — не тот файл, о котором команда что-то знает."""
        (self.root / PEOPLE).write_text(
            'filters:\n  and:\n    - file.inFolder("core/people/items")\n',
            encoding="utf-8")
        report, code = extend.add_view(self.root, "core/people", name="Всё")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("списка видов", report)
        self.assertNotIn("Всё", self.base_text())

    def test_the_view_lands_in_the_file_and_the_parser_still_reads_it(self):
        """Вставка утверждается байтами, а не фактом «код вернул 0»:
        `views.base` читает и Obsidian, и оба гейта пакета."""
        report, code = extend.add_view(self.root, "core/people", name="Все люди")
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.base_text(),
                         'filters:\n'
                         '  and:\n'
                         '    - file.inFolder("core/people/items")\n'
                         'views:\n'
                         '  - type: table\n'
                         '    groupBy: status\n'
                         '    order:\n'
                         '      - description\n'
                         '  - type: table\n'
                         '    name: Все люди\n'
                         '    order:\n'
                         '      - created\n')
        base = parse_base(self.base_text())
        self.assertEqual(sorted(base.folders), ["core/people/items"])

    def test_the_added_view_asks_of_records_nothing_new(self):
        """`groupBy` в добавляемом виде нет намеренно: он делает поле
        обязательным для каждой записи коллекции (секция 14), и команда
        красила бы гейт frontmatter собственной правкой. Утверждается
        отчётом гейта до и после, а не рассуждением."""
        before = places(check_frontmatter.scan(self.root).findings)
        report, code = extend.add_view(self.root, "core/people", name="Все люди")
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(places(check_frontmatter.scan(self.root).findings),
                         before)

    def test_a_view_without_a_name_is_refused(self):
        """Тот же инвариант, что у коллекции и направления: содержимое вида
        при заведении — то, как автор его назвал."""
        before = self.base_text()
        report, code = extend.add_view(self.root, "core/people", name="  ")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("без имени", report)
        self.assertEqual(self.base_text(), before)

    def test_a_taken_view_name_is_refused(self):
        """Имя проверяется на дереве, где оно **действительно** занято: у
        видов фикстуры имён нет вовсе, и одиночный вызов отказался бы не по
        этой причине, а ни по какой — тест был бы зелёным на пустом месте."""
        report, code = extend.add_view(self.root, "core/people", name="По типу")
        self.assertEqual(code, EXIT_OK, report)
        report, code = extend.add_view(self.root, "core/people", name="По типу")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("имя вида занято", report)
        self.assertEqual(self.base_text().count("name: По типу"), 1)

    def test_a_longer_name_does_not_count_as_taken(self):
        """Совпадение — с именем целиком. Подстрокой `name: Всё` считалось бы
        занятым и `name: Всё вместе`, то есть команда отказывала бы, ссылаясь
        на вид, которого нет."""
        report, code = extend.add_view(self.root, "core/people",
                                       name="Всё вместе")
        self.assertEqual(code, EXIT_OK, report)
        report, code = extend.add_view(self.root, "core/people", name="Всё")
        self.assertEqual(code, EXIT_OK, report)

    def test_the_filter_is_never_evaluated(self):
        """Проверяется только статически разрешимый случай. Движка фильтров
        Obsidian Bases пакет не строит и не собирается."""
        self.assertFalse(hasattr(extend, "evaluate_filter"))


if __name__ == "__main__":
    unittest.main()
