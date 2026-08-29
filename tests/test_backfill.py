"""Критерий 4: ничего не подставлено молча, и каждое значение проверяемо.

Три исхода на запись и ни одного четвёртого. `computed` пересчитывается
здесь независимо от модуля — другой формой команды git и другим разбором
имени, — потому что тест, зовущий ту же функцию, доказывает только её
самосогласованность.
"""

import os
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import tree
from scripts.frontmatter import parse as parse_frontmatter
from scripts.maintain import backfill, content_diff, field_map
from tests.maintain_fixture import materialise

JOURNAL = "areas/work/journal"
DEALS = "projects/deals"
PEOPLE = "core/people"

DATED = "areas/work/journal/items/2026-08-25.md"
LATE = "areas/work/journal/items/late-entry.md"
TWO = "projects/deals/items/two.md"


def places(findings):
    return [(f.path, f.line, f.cls, f.detail) for f in findings]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def items(self, collection):
        return self.root / collection / "items"

    def snapshot(self, collection):
        return {path: path.read_bytes()
                for path in sorted(self.items(collection).glob("*.md"))}

    def assert_untouched(self, before):
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw, path.name)

    def field(self, rel, name):
        text = (self.root / rel).read_text(encoding="utf-8")
        return parse_frontmatter(text).get(name)

    def commit(self, rel, text, date):
        """Запись, попавшая в git позже события, которое она описывает."""
        (self.root / rel).write_text(text, encoding="utf-8")
        tree.git(self.root, "add", "--", rel)
        stamp = "%sT12:00:00+00:00" % date
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
        tree.git(self.root, "commit", "-q", "-m", "журнал: перенос", env=env)


class TestTheClosedSets(Fixture):
    def test_the_outcomes_are_the_origins_of_field_map_and_not_a_second_list(self):
        """Второе перечисление исходов разошлось бы с тем, по которому
        `field_map.render` роняет строку, — и расхождение вылезло бы
        исключением на живой таблице, а не тестом."""
        self.assertIs(backfill.OUTCOMES, field_map.ORIGINS)
        self.assertEqual(list(backfill.OUTCOMES),
                         ["computed", "synthetic", "deferred"])

    def test_every_outcome_is_produced_by_the_fixture_and_no_fourth_is(self):
        """Исходы спрашиваются у дерева, а не у константы: исход, которого
        не производит ничто, — украшение, а четвёртый — нарушение спеки."""
        seen = set()
        for collection, name in ((JOURNAL, "created"),
                                 (JOURNAL, "description"),
                                 (DEALS, "status")):
            rows, _ = backfill.run(self.root, collection, name)
            seen.update(row[4] for row in rows)
        self.assertEqual(seen, set(backfill.OUTCOMES))

    def test_the_named_rules_are_these(self):
        self.assertEqual(sorted(backfill.RULES),
                         ["body-words", "filename-date", "filename-source",
                          "git-first-commit"])

    def test_no_field_names_a_rule_that_does_not_exist(self):
        named = {name for names in backfill.FOR_FIELD.values() for name in names}
        self.assertEqual(sorted(named - set(backfill.RULES)), [])

    def test_no_rule_sits_unreachable_from_every_field(self):
        """Незыблемое №3: правило, которого не зовёт ни одно поле, —
        механизм без предъявленного потребителя."""
        named = {name for names in backfill.FOR_FIELD.values() for name in names}
        self.assertEqual(sorted(set(backfill.RULES) - named), [])


class TestComputed(Fixture):
    def test_the_exact_list_of_rows_for_created(self):
        rows, report = backfill.run(self.root, JOURNAL, "created")
        self.assertEqual(rows, [
            (DATED, "created", "", "2026-08-25", "computed", "filename-date"),
            (LATE, "created", "", "2026-08-25", "computed", "git-first-commit"),
        ])
        self.assertEqual(report, "")
        self.assertEqual(self.field(DATED, "created"), "2026-08-25")
        self.assertEqual(self.field(LATE, "created"), "2026-08-25")

    def test_each_computed_value_is_recomputed_independently(self):
        """Другая форма команды git (`--reverse`, первая строка) и свой
        разбор имени. Фальсификатор — `created`, получающий дату прогона."""
        rows, _ = backfill.run(self.root, JOURNAL, "created")
        for rel, _field, _before, value, origin, rule in rows:
            if origin != "computed":
                continue
            if rule == "git-first-commit":
                proc = tree.git(self.root, "log", "--date=short", "--format=%ad",
                                "--reverse", "--", ":(literal)%s" % rel)
                self.assertEqual(value, proc.stdout.split("\n")[0], rel)
            elif rule == "filename-date":
                self.assertEqual(value, Path(rel).name[:10], rel)
            else:
                self.fail("правило без независимого пересчёта: %s" % rule)

    def test_the_date_in_the_name_beats_the_date_of_the_commit_that_carried_it(self):
        """Имя файла — утверждение автора о дате, дата коммита —
        обстоятельство переноса. Обратный порядок отдал бы записи,
        внесённой задним числом, дату внесения."""
        rel = "areas/work/journal/items/2026-03-01.md"
        self.commit(rel, "---\ntype: планёрка\n---\nИз старого блокнота.\n",
                    "2026-08-29")
        rows, _ = backfill.run(self.root, JOURNAL, "created")
        self.assertEqual([(r[0], r[3], r[5]) for r in rows if r[0] == rel],
                         [(rel, "2026-03-01", "filename-date")])
        self.assertNotIn("2026-08-29", [row[3] for row in rows])


class TestSynthetic(Fixture):
    def test_a_field_with_no_rule_and_no_vocabulary_is_stamped_in_the_record(self):
        """Незыблемое №4, первая ветка: помечено синтетическим. Токен лежит
        в самой записи — читающий файл отличает восстановленное от
        выдуманного, ничего не запуская."""
        rows, report = backfill.run(self.root, JOURNAL, "description")
        self.assertEqual(rows, [
            (DATED, "description", "", "unknown", "synthetic", "no-rule"),
            (LATE, "description", "", "unknown", "synthetic", "no-rule"),
        ])
        self.assertEqual(self.field(DATED, "description"), "unknown")
        self.assertEqual(self.field(LATE, "description"), "unknown")
        self.assertEqual(report, "")

    def test_the_synthetic_token_is_the_one_wave_four_already_introduced(self):
        """Второго синтетического токена рецепт не заводит."""
        from scripts.adopt.dates import UNKNOWN
        rows, _ = backfill.run(self.root, JOURNAL, "description")
        self.assertEqual({row[3] for row in rows}, {UNKNOWN})


class TestDeferred(Fixture):
    def test_a_field_with_a_declared_vocabulary_is_deferred_not_stamped(self):
        """`unknown` в поле со словарём — это `value-outside-vocabulary`, то
        есть починка, производящая ошибку гейта. §2 называет `status`
        невосстановимым по определению."""
        before = self.snapshot(DEALS)
        rows, report = backfill.run(self.root, DEALS, "status")
        self.assertEqual(rows, [
            (TWO, "status", "", "", "deferred", "vocabulary-declared"),
        ])
        self.assert_untouched(before)
        self.assertIsNone(self.field(TWO, "status"))
        self.assertEqual(report,
                         "отложено, значение принадлежит автору:\n"
                         "projects/deals/items/two.md status "
                         "(vocabulary-declared)\n")

    def test_the_deferred_row_is_named_in_the_report_or_it_is_a_silent_substitution(self):
        rows, report = backfill.run(self.root, DEALS, "status")
        self.assertEqual(field_map.audit(rows, report), [])
        self.assertEqual(places(field_map.audit(rows, "")), [
            (TWO, 1, "silent-substitution",
             "отложено и не названо в отчёте: status")])

    def test_a_declaration_that_cannot_be_read_defers_instead_of_stamping(self):
        """Фальсификатор второй ветки: то же поле, тот же файл, разница
        только в читаемости объявления. Проглоченный отказ разбора превратил
        бы коллекцию со словарём в коллекцию без него и проштамповал бы
        `unknown` там, где он запрещён."""
        readme = self.root / JOURNAL / "README.md"
        readme.write_text("---\narchetype: journal\narchetype: journal\n---\n",
                          encoding="utf-8")
        before = self.snapshot(JOURNAL)
        rows, report = backfill.run(self.root, JOURNAL, "description")
        self.assertEqual([(row[0], row[4], row[5]) for row in rows], [
            (DATED, "deferred", "vocabulary-unreadable"),
            (LATE, "deferred", "vocabulary-unreadable"),
        ])
        self.assert_untouched(before)
        self.assertEqual(field_map.audit(rows, report), [])


class TestNothingIsOverwritten(Fixture):
    def test_a_collection_where_everyone_has_the_field_produces_nothing(self):
        """Фальсификатор — backfill, переписывающий существующее."""
        before = self.snapshot(PEOPLE)
        rows, report = backfill.run(self.root, PEOPLE, "type")
        self.assertEqual(rows, [])
        self.assertEqual(report, "")
        self.assert_untouched(before)

    def test_a_present_field_wins_over_the_vocabulary_of_its_collection(self):
        """`status` у людей объявлен словарём и стоит у обеих записей:
        отложить тут нечего, потому что писать не собирались."""
        before = self.snapshot(PEOPLE)
        rows, _ = backfill.run(self.root, PEOPLE, "status")
        self.assertEqual(rows, [])
        self.assert_untouched(before)

    def test_an_empty_value_is_the_authors_and_is_not_filled_in(self):
        """Поверхность формы разрешает **отсутствующий** ключ. Ключ, стоящий
        пустым, — уже написанное автором; дописать второй такой же значило бы
        сделать frontmatter неразбираемым, переписать — выйти за поверхность."""
        path = self.items(JOURNAL) / "late-entry.md"
        path.write_text(path.read_text(encoding="utf-8")
                        .replace("type: планёрка", 'type: планёрка\ncreated: ""'),
                        encoding="utf-8")
        before = self.snapshot(JOURNAL)
        rows, _ = backfill.run(self.root, JOURNAL, "created")
        self.assertEqual([row[0] for row in rows], [DATED])
        self.assertEqual(path.read_bytes(), before[path])


class TestRecordsThatCannotBeRead(Fixture):
    def plant(self):
        (self.items(JOURNAL) / "сырое.md").write_text(
            "Просто текст, frontmatter'а нет.\n", encoding="utf-8")
        (self.items(JOURNAL) / "кривое.md").write_text(
            "---\ntype: a\ntype: b\n---\nтело\n", encoding="utf-8")
        (self.items(JOURNAL) / "битое.md").write_bytes(
            b"---\ntype: \xff\xfe\n---\n")

    def test_they_are_named_by_token_and_not_dropped_in_silence(self):
        """Незыблемое №4: `continue` без следа — это и есть молчание.
        Токены — из закрытого списка `field_map.TOKENS`."""
        self.plant()
        before = self.snapshot(JOURNAL)
        rows, report = backfill.run(self.root, JOURNAL, "created")
        self.assertEqual([row[0] for row in rows], [DATED, LATE])
        self.assertEqual(
            report,
            "не прочитано как запись:\n"
            "areas/work/journal/items/битое.md (undecodable)\n"
            "areas/work/journal/items/кривое.md (unparseable-frontmatter)\n"
            "areas/work/journal/items/сырое.md (not-a-record)\n")
        for name in ("сырое.md", "кривое.md", "битое.md"):
            path = self.items(JOURNAL) / name
            self.assertEqual(path.read_bytes(), before[path], name)

    def test_every_token_belongs_to_the_closed_list(self):
        self.plant()
        _, skipped = backfill.plan(self.root, JOURNAL, "created")
        self.assertEqual(sorted(set(skipped.values()) - set(field_map.TOKENS)), [])


class TestMaintainCallsItNarrowly(Fixture):
    def new_record(self):
        """Запись, которую автор только что написал и ещё не закоммитил:
        истории у пути нет, даты в имени нет."""
        (self.items(JOURNAL) / "новая.md").write_text(
            "---\ntype: планёрка\n---\nЕщё не в git.\n", encoding="utf-8")

    def test_one_unrecoverable_record_stops_the_whole_collection(self):
        """Фальсификатор спеки: две записи из трёх восстановимы, одна нет.
        Не записано **ни одной**, и запись названа в отчёте."""
        self.new_record()
        before = self.snapshot(JOURNAL)
        written, report = backfill.run_silently(self.root, JOURNAL, "created")
        self.assertEqual(written, [])
        self.assert_untouched(before)
        self.assertEqual(
            report,
            "backfill created не выполнен молча: невычислимо у 1 записей\n"
            "areas/work/journal/items/новая.md created (synthetic)\n")

    def test_a_record_that_cannot_be_read_also_stops_it(self):
        (self.items(JOURNAL) / "сырое.md").write_text(
            "Просто текст.\n", encoding="utf-8")
        before = self.snapshot(JOURNAL)
        written, report = backfill.run_silently(self.root, JOURNAL, "created")
        self.assertEqual(written, [])
        self.assert_untouched(before)
        self.assertEqual(
            report,
            "backfill created не выполнен молча: невычислимо у 1 записей\n"
            "areas/work/journal/items/сырое.md created (not-a-record)\n")

    def test_a_fully_computable_collection_is_filled_silently(self):
        written, report = backfill.run_silently(self.root, JOURNAL, "created")
        self.assertEqual(written, [DATED, LATE])
        self.assertEqual(report, "")
        self.assertEqual(self.field(LATE, "created"), "2026-08-25")


class TestTheSelfCheckAcceptsIt(Fixture):
    def test_what_backfill_wrote_is_justified_by_its_own_table(self):
        """Проверка того, что `maintain run` сказал бы про эти правки."""
        before = content_diff.snapshot(self.root)
        rows, _ = backfill.run(self.root, JOURNAL, "created")
        after = content_diff.snapshot(self.root)
        self.assertEqual(content_diff.compare(before, after, field_map=rows), [])

    def test_the_same_writes_without_the_table_are_content_modified(self):
        """Строка таблицы — единственное оправдание появившегося поля."""
        before = content_diff.snapshot(self.root)
        backfill.run(self.root, JOURNAL, "created")
        after = content_diff.snapshot(self.root)
        self.assertEqual(places(content_diff.compare(before, after)), [
            (DATED, 1, "content-modified", "поле появилось мимо field-map: created"),
            (LATE, 1, "content-modified", "поле появилось мимо field-map: created"),
        ])

    def test_the_rows_render_as_a_field_map_table(self):
        rows, _ = backfill.run(self.root, JOURNAL, "created")
        self.assertEqual(field_map.render(rows), "\n".join([
            "\t".join(field_map.COLUMNS),
            "%s\tcreated\t\t2026-08-25\tcomputed\tfilename-date" % DATED,
            "%s\tcreated\t\t2026-08-25\tcomputed\tgit-first-commit" % LATE,
        ]) + "\n")

    def test_the_table_names_every_value_that_landed_on_disk(self):
        """Сверка не с намерением, а с диском: поле, появившееся мимо
        таблицы, — `silent-substitution` по определению класса."""
        was = {path: parse_frontmatter(path.read_text(encoding="utf-8"))
               for path in sorted(self.items(JOURNAL).glob("*.md"))}
        rows, _ = backfill.run(self.root, JOURNAL, "created")
        appeared = set()
        for path, fields in was.items():
            now = parse_frontmatter(path.read_text(encoding="utf-8"))
            rel = path.relative_to(self.root).as_posix()
            appeared.update((rel, key) for key in now if key not in fields)
        self.assertEqual(appeared,
                         {(row[0], row[1]) for row in rows if row[4] != "deferred"})


if __name__ == "__main__":
    unittest.main()
