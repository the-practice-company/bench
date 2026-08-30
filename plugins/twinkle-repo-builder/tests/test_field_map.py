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


# Строки таблицы ссылок: та же дисциплина TSV, другие колонки. Порядок
# обратный сортировке намеренно — на отсортированном входе утверждение о
# сортировке проходит и без сортировки.
REF_ROWS = (
    ("README.md", 6, "[[notes/meeting]]", "[[areas/work/notes/meeting]]",
     "notes -> areas/work/notes"),
    ("README.md", 2, "[[notes/план]]", "[[areas/work/notes/план]]",
     "notes -> areas/work/notes"),
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


class TestTheReferenceTable(unittest.TestCase):
    """Переписанная ссылка — не значение поля, и колонки у неё свои.

    Происхождения (`computed` / `synthetic` / `deferred`) у неё нет вовсе:
    её не восстанавливало правило, её перенесла согласованная строка плана.
    Втащить ссылку в чужой словарь ради переиспользования функции значило бы
    получить таблицу, у которой врёт колонка, — это хуже честного счётчика.
    Разное здесь — данные (колонки, ключ, словари, токены), одинаковое —
    проверка: второй рендер с теми же четырьмя отказами разошёлся бы с этим
    на первом же новом правиле.
    """

    def test_the_columns_are_these_in_this_order(self):
        self.assertEqual(list(field_map.REF_COLUMNS),
                         ["path", "line", "before", "after", "plan"])

    def test_the_table_is_tsv_sorted_by_path_and_line_with_a_header(self):
        text = field_map.render(REF_ROWS, field_map.REFS)
        lines = text.rstrip("\n").split("\n")
        self.assertEqual(lines[0], "\t".join(field_map.REF_COLUMNS))
        self.assertEqual([l.split("\t")[1] for l in lines[1:]], ["2", "6"])
        self.assertEqual(
            lines[1],
            "README.md\t2\t[[notes/план]]\t[[areas/work/notes/план]]\t"
            "notes -> areas/work/notes")

    def test_the_name_carries_the_shape_and_never_a_date(self):
        name = field_map.name("rewrite-refs", ("notes", "areas/work/notes"),
                              field_map.REFS)
        self.assertEqual(
            name, "tmp/ref-map-rewrite-refs-notes-areas-work-notes.tsv")
        self.assertNotRegex(name, r"\d{4}-\d{2}-\d{2}")

    def test_no_absolute_path_can_enter_it_either(self):
        with self.assertRaises(ValueError):
            field_map.render([("/Users/кто-то/a.md", 1, "[[x]]", "[[y]]", "p")],
                             field_map.REFS)

    def test_the_same_reference_of_the_same_line_twice_is_refused(self):
        """Ключ строки — путь, номер строки и текст ссылки. Дважды описанная
        одна правка — две строки, из которых читающий машиной оставит одну,
        и какую именно, не сказано нигде."""
        with self.assertRaises(ValueError):
            field_map.render(
                [("README.md", 6, "[[notes/meeting]]", "[[a/meeting]]", "p"),
                 ("README.md", 6, "[[notes/meeting]]", "[[b/meeting]]", "p")],
                field_map.REFS)

    def test_two_different_links_on_one_line_are_two_rows(self):
        rows = [("README.md", 6, "[[notes/meeting]]", "[[a/meeting]]", "p"),
                ("README.md", 6, "![[notes/meeting]]", "![[a/meeting]]", "p")]
        self.assertEqual(len(field_map.render(rows, field_map.REFS)
                             .rstrip("\n").split("\n")), 3)

    def test_a_row_of_another_width_is_refused(self):
        with self.assertRaises(ValueError):
            field_map.render([("README.md", 6, "[[x]]", "[[y]]")],
                             field_map.REFS)

    def test_the_closed_list_of_tokens(self):
        self.assertEqual(list(field_map.REF_TOKENS),
                         ["bare-still-resolves", "md-link", "not-a-wikilink"])

    def test_the_origins_stay_the_vocabulary_of_the_field_table_alone(self):
        """`ORIGINS` — словарь колонки `origin`, а колонки такой у ссылок
        нет. Общий на две таблицы, он бы и заставил врать одну из них."""
        self.assertEqual(field_map.FIELDS.vocabularies, {4: field_map.ORIGINS})
        self.assertEqual(field_map.REFS.vocabularies, {})


class TestReferenceCounts(unittest.TestCase):
    """Дифф ссылок: находка встаёт на свою строку, а не на строку 1."""

    def test_matching_units_produce_nothing(self):
        expected = [("README.md", 6, "[[notes/meeting]]")]
        rows = [("README.md", 6, "[[notes/meeting]]",
                 "[[areas/work/notes/meeting]]", "notes -> areas/work/notes")]
        self.assertEqual(
            places(field_map.reconcile(expected, rows, {}, field_map.REFS)), [])

    def test_a_shortfall_without_a_token_is_unexplained_count(self):
        expected = [("README.md", 6, "[[notes/meeting]]")]
        self.assertEqual(
            places(field_map.reconcile(expected, [], {}, field_map.REFS)),
            [("README.md", 6, "unexplained-count",
              "ссылка ожидалась в таблице и её там нет, объяснения тоже")])

    def test_a_shortfall_with_a_token_is_explained(self):
        expected = [("README.md", 6, "[[meeting]]")]
        explained = {("README.md", 6, "[[meeting]]"): "bare-still-resolves"}
        self.assertEqual(
            places(field_map.reconcile(expected, [], explained, field_map.REFS)),
            [])

    def test_a_token_of_the_other_table_does_not_explain_a_reference(self):
        """Списки закрыты порознь: `undecodable` объясняет непрочитанную
        запись и не говорит про ссылку ничего."""
        expected = [("README.md", 6, "[[meeting]]")]
        explained = {("README.md", 6, "[[meeting]]"): "undecodable"}
        self.assertEqual(
            places(field_map.reconcile(expected, [], explained, field_map.REFS)),
            [("README.md", 6, "unexplained-count",
              "ссылка ожидалась в таблице и её там нет, объяснения тоже")])

    def test_a_row_for_a_reference_nobody_expected_is_a_finding_too(self):
        """Вторая половина: правка, которую резолвер ссылкой под источник не
        называл, — правка авторского текста мимо согласованной строки."""
        rows = [("README.md", 6, "[[notes/meeting]]",
                 "[[areas/work/notes/meeting]]", "notes -> areas/work/notes")]
        self.assertEqual(
            places(field_map.reconcile([], rows, {}, field_map.REFS)),
            [("README.md", 6, "unexplained-count",
              "строка в таблице есть, а такой ссылки не было")])


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
