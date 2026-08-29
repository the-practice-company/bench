"""Критерий 5: машинная таблица массовой мутации и дифф счётчиков."""

import unittest

from scripts.maintain import field_map


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


# Порядок обратный сортировке намеренно: на уже отсортированном входе
# утверждение о сортировке проходит и без сортировки.
ROWS = (
    ("areas/work/journal/items/b.md", "created", "", "unknown",
     "synthetic", "no-rule"),
    ("areas/work/journal/items/a.md", "created", "", "2026-08-25",
     "computed", "git-first-commit"),
)


class TestFormat(unittest.TestCase):
    def test_the_columns_are_these_in_this_order(self):
        self.assertEqual(list(field_map.COLUMNS),
                         ["path", "field", "before", "after", "origin", "rule"])

    def test_the_table_is_tsv_sorted_by_path_with_a_header(self):
        text = field_map.render(ROWS)
        lines = text.rstrip("\n").split("\n")
        self.assertEqual(lines[0], "\t".join(field_map.COLUMNS))
        self.assertEqual([l.split("\t")[0] for l in lines[1:]],
                         sorted(r[0] for r in ROWS))
        self.assertEqual(
            lines[1],
            "areas/work/journal/items/a.md\tcreated\t\t2026-08-25\t"
            "computed\tgit-first-commit")

    def test_the_file_name_never_carries_a_date(self):
        """Метка времени в имени вернула бы часы и сломала побайтовую
        воспроизводимость теста. Перезапись прежнего файла законна: зона
        транзитная, прошлый прогон лежит в git."""
        name = field_map.name("backfill", ("areas/work/journal", "created"))
        self.assertEqual(name, "tmp/field-map-backfill-areas-work-journal-created.tsv")
        self.assertNotRegex(name, r"\d{4}-\d{2}-\d{2}")

    def test_a_single_argument_may_come_as_a_bare_string(self):
        """Строка — последовательность символов, и разобранная как список
        аргументов дала бы имя по буквам, ничего про это не сказав."""
        self.assertEqual(field_map.name("backfill", "created"),
                         "tmp/field-map-backfill-created.tsv")

    def test_the_three_origins_are_a_closed_set(self):
        self.assertEqual(list(field_map.ORIGINS),
                         ["computed", "synthetic", "deferred"])

    def test_no_absolute_path_can_enter_the_table(self):
        with self.assertRaises(ValueError):
            field_map.render([("/Users/кто-то/a.md", "created", "", "x",
                               "computed", "git-first-commit")])

    def test_a_path_above_the_root_cannot_enter_either(self):
        """Правило то же и проверяется тем же предикатом, что у гейтов:
        таблица не называет ничего вне корня репозитория."""
        with self.assertRaises(ValueError):
            field_map.render([("../соседний/a.md", "created", "", "x",
                               "computed", "git-first-commit")])

    def test_an_origin_outside_the_closed_set_is_refused(self):
        with self.assertRaises(ValueError):
            field_map.render([("a.md", "created", "", "x", "угадано", "r")])

    def test_a_row_of_another_width_is_refused(self):
        with self.assertRaises(ValueError):
            field_map.render([("a.md", "created", "", "x", "computed")])

    def test_a_cell_carrying_a_tab_is_refused(self):
        """Разделитель внутри значения сдвинул бы колонки и был бы прочитан
        машиной как другая строка — молча."""
        with self.assertRaises(ValueError):
            field_map.render([("a.md", "created", "", "до\tпосле",
                               "computed", "r")])

    def test_the_same_field_of_the_same_path_twice_is_refused(self):
        """`content_diff` кладёт строки в словарь по `(путь, поле)`: из двух
        строк уцелеет одна, и какая именно — не сказано нигде."""
        with self.assertRaises(ValueError):
            field_map.render([("a.md", "created", "", "x", "computed", "r"),
                              ("a.md", "created", "", "y", "computed", "r")])


class TestCounts(unittest.TestCase):
    def test_matching_counts_produce_nothing(self):
        expected = ["a.md", "b.md"]
        rows = [(name, "created", "", "x", "computed", "r") for name in expected]
        self.assertEqual(places(field_map.reconcile(expected, rows, {})), [])

    def test_a_shortfall_with_a_token_is_explained(self):
        expected = ["a.md", "b.md"]
        rows = [("a.md", "created", "", "x", "computed", "r")]
        self.assertEqual(
            places(field_map.reconcile(expected, rows, {"b.md": "undecodable"})),
            [])

    def test_a_shortfall_without_a_token_is_unexplained_count(self):
        expected = ["a.md", "b.md"]
        rows = [("a.md", "created", "", "x", "computed", "r")]
        self.assertEqual(places(field_map.reconcile(expected, rows, {})), [
            ("b.md", 1, "unexplained-count",
             "запись ожидалась в таблице и её там нет, объяснения тоже")])

    def test_a_row_for_a_record_nobody_expected_is_a_finding_too(self):
        """Вторая половина диффа. Без неё строка мимо множества записей
        коллекции проходит бесплатно — и она же оправдывает появление поля
        в `content_diff`, то есть открывает гейт содержимого."""
        expected = ["items/a.md"]
        rows = [("items/a.md", "created", "", "x", "computed", "r"),
                ("README.md", "created", "", "x", "computed", "r")]
        self.assertEqual(places(field_map.reconcile(expected, rows, {})), [
            ("README.md", 1, "unexplained-count",
             "строка в таблице есть, а запись не ожидалась")])

    def test_a_token_outside_the_closed_list_is_itself_unexplained(self):
        """Свободный токен позволил бы объяснить что угодно словом."""
        expected = ["a.md"]
        self.assertEqual(
            places(field_map.reconcile(expected, [], {"a.md": "устал"})),
            [("a.md", 1, "unexplained-count",
              "запись ожидалась в таблице и её там нет, объяснения тоже")])

    def test_the_closed_list_of_tokens(self):
        self.assertEqual(list(field_map.TOKENS),
                         ["undecodable", "unparseable-frontmatter",
                          "not-a-record", "dirty-path"])


class TestSilentSubstitution(unittest.TestCase):
    def test_a_deferred_row_absent_from_the_report_is_a_finding(self):
        """`deferred` больше нуля при пустом разделе отчёта — то самое
        молчание, ради запрета которого заведён незыблемый №4."""
        rows = [("a.md", "status", "", "", "deferred", "vocabulary-declared")]
        self.assertEqual(places(field_map.audit(rows, report_section="")), [
            ("a.md", 1, "silent-substitution",
             "отложено и не названо в отчёте: status")])

    def test_a_deferred_row_named_in_the_report_is_fine(self):
        rows = [("a.md", "status", "", "", "deferred", "vocabulary-declared")]
        self.assertEqual(field_map.audit(rows, report_section="a.md status"), [])

    def test_the_path_and_the_field_meet_on_one_line_or_not_at_all(self):
        """Путь в одной строке отчёта, поле в другой — это два разных
        сообщения, и вместе они не говорят про эту запись ничего."""
        rows = [("a.md", "status", "", "", "deferred", "vocabulary-declared")]
        section = "a.md created вычислено\nb.md status отложено"
        self.assertEqual(places(field_map.audit(rows, report_section=section)), [
            ("a.md", 1, "silent-substitution",
             "отложено и не названо в отчёте: status")])

    def test_a_synthetic_row_does_not_owe_the_report_a_line(self):
        """Незыблемое №4 — либо помечено синтетическим, либо в отчёт.
        `unknown` лежит на диске и виден там, где значение читают."""
        rows = [("a.md", "created", "", "unknown", "synthetic", "no-rule")]
        self.assertEqual(field_map.audit(rows, report_section=""), [])

    def test_a_written_value_absent_from_the_table_is_a_finding(self):
        """Второй производитель класса: значение на диске есть, строки нет."""
        self.assertEqual(
            places(field_map.audit([], report_section="",
                                   written=[("a.md", "created")])),
            [("a.md", 1, "silent-substitution",
              "значение записано мимо таблицы: created")])

    def test_a_written_value_named_in_the_table_is_fine(self):
        rows = [("a.md", "created", "", "2026-08-25", "computed", "r")]
        self.assertEqual(
            field_map.audit(rows, report_section="",
                            written=[("a.md", "created")]), [])
