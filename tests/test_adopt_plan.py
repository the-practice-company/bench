"""Разбор плана усыновления: строгая шапка, свободное тело, ошибка вместо пропуска."""

import tempfile
import unittest
from pathlib import Path

from scripts.adopt import plan as adopt_plan

PLAN = "tmp/adopt-plan.md"


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


def parse(text):
    return adopt_plan.parse(text, PLAN)


GOOD = """\
# план усыновления, снят 2026-08-29
# 16 файлов, 10 каталогов. git заведён ADOPT, истории нет.

## Этап 1. Раскладка по зонам

- [ ] `journal` -> `areas/<?>/journal`
      147 файлов, записи по дням. В какую область — не знаю, спрашиваю.

- [x] `notes` -> `areas/work/notes`
      Рабочие заметки, лежат неправильно.

- [x] `archive` -> `git-history`
      Экспорт из Notion. Содержимое остаётся в истории.

- [x] `vendor-lib` -> `foreign-repo`
      Чужой репозиторий, не трогаем.

- [x] `state.md` -> `stay`
      Разбирается отдельными строками этапа 1б.
"""


class TestGoodPlan(unittest.TestCase):
    def setUp(self):
        self.lines, self.findings = parse(GOOD)

    def test_it_parses_without_findings(self):
        self.assertEqual(places(self.findings), [])

    def test_the_lines_are_these(self):
        """Точный список: разбор, потерявший строку, обязан уронить набор."""
        self.assertEqual(
            [(l.lineno, l.agreed, l.source, l.target) for l in self.lines],
            [(6, False, "journal", "areas/<?>/journal"),
             (9, True, "notes", "areas/work/notes"),
             (12, True, "archive", "git-history"),
             (15, True, "vendor-lib", "foreign-repo"),
             (18, True, "state.md", "stay")])

    def test_every_line_carries_its_stage_and_body(self):
        self.assertEqual({l.stage for l in self.lines},
                         {"Этап 1. Раскладка по зонам"})
        self.assertTrue(all(l.body.strip() for l in self.lines))

    def test_the_action_of_each_line(self):
        """Цель решает, чем строка исполняется, и `?` не исполняется ничем."""
        self.assertEqual([adopt_plan.action(l) for l in self.lines],
                         [None, "move", "drop", None, None])


class TestArrowForms(unittest.TestCase):
    def test_both_arrows_are_accepted(self):
        for arrow in ("->", "→"):
            lines, found = parse(
                "- [x] `a` %s `b`\n      причина\n" % arrow)
            self.assertEqual(places(found), [], arrow)
            self.assertEqual(lines[0].target, "b", arrow)

    def test_a_trailing_slash_is_the_same_path(self):
        """`journal/` и `journal` — один путь. Иначе полнота плана зависит
        от того, как автор набрал строку."""
        lines, found = parse("- [x] `journal/` -> `areas/work/journal/`\n      причина\n")
        self.assertEqual(places(found), [])
        self.assertEqual((lines[0].source, lines[0].target),
                         ("journal", "areas/work/journal"))


class TestRefusals(unittest.TestCase):
    def test_a_line_without_a_body_fails_the_parse(self):
        """То же правило, что у аллоулиста §13, и по той же причине."""
        lines, found = parse("- [x] `a` -> `b`\n\n- [x] `c` -> `d`\n      причина\n")
        self.assertEqual(places(found), [
            (PLAN, 1, "plan-unparseable", "строка без тела: `a` -> `b`")])
        self.assertEqual([l.source for l in lines], ["c"])

    def test_an_unrecognised_line_is_a_finding_not_a_skip(self):
        """Молчаливый пропуск означал бы, что правка рукой тихо выносит
        строку из исполнения."""
        lines, found = parse("## Этап 1\n\nпросто текст с нулевой позиции\n")
        self.assertEqual(places(found), [
            (PLAN, 3, "plan-unparseable", "строка не разобрана: просто текст с нулевой позиции")])
        self.assertEqual(lines, [])

    def test_a_head_without_backticks_is_unparseable(self):
        """Backtick'и обязательны: в чужих деревьях есть имена с пробелами."""
        lines, found = parse("- [x] a -> b\n      причина\n")
        self.assertEqual([f.cls for f in found], ["plan-unparseable"])
        self.assertEqual(lines, [])

    def test_the_body_of_a_rejected_head_is_not_reported_twice(self):
        """Одна сломанная строка — одна находка, сколько бы строк ни было
        в её теле. Иначе опечатка в шапке даёт отчёт длиной с абзац, и в
        нём тонет вторая сломанная строка."""
        lines, found = parse(
            "- [x] a -> b\n      причина\n      и вторая строка причины\n")
        self.assertEqual(places(found), [
            (PLAN, 1, "plan-unparseable", "строка не разобрана: - [x] a -> b")])
        self.assertEqual(lines, [])

    def test_a_body_before_any_head_is_unparseable(self):
        lines, found = parse("      причина без строки\n")
        self.assertEqual([f.cls for f in found], ["plan-unparseable"])

    def test_an_empty_path_is_unparseable(self):
        """`/` после снятия хвостовой косой — пустой путь. Пустой источник
        не совпадёт ни с чем в дереве и в полноте промолчит: строка,
        которая выглядит согласием, но не значит ничего."""
        lines, found = parse("- [x] `/` -> `stay`\n      причина\n")
        self.assertEqual(places(found), [
            (PLAN, 1, "plan-unparseable", "пустой путь в строке: - [x] `/` -> `stay`")])
        self.assertEqual(lines, [])

    def test_a_name_with_a_space_survives_the_backticks(self):
        lines, found = parse(
            "- [x] `2026-07-13 Эксперимент — последний год.md` -> `inbox`\n      измерено\n")
        self.assertEqual(places(found), [])
        self.assertEqual(lines[0].source,
                         "2026-07-13 Эксперимент — последний год.md")


class TestQuestions(unittest.TestCase):
    def test_a_question_mark_anywhere_in_the_target_disarms_the_line(self):
        """Критерий 5. Крестик его не снимает: согласие с вопросом — это
        согласие с тем, что ответа нет."""
        lines, found = parse("- [x] `a` -> `areas/<?>/a`\n      спрашиваю\n")
        self.assertEqual(places(found), [])
        self.assertTrue(lines[0].agreed)
        self.assertIsNone(adopt_plan.action(lines[0]))

    def test_a_bare_question_mark_is_a_target(self):
        lines, found = parse("- [ ] `identity` -> `?`\n      не знаю\n")
        self.assertEqual(places(found), [])
        self.assertIsNone(adopt_plan.action(lines[0]))


class TestReservedTargets(unittest.TestCase):
    def test_the_reserved_set_is_exactly_this(self):
        self.assertEqual(list(adopt_plan.RESERVED),
                         ["foreign-repo", "git-history", "merge", "stay"])

    def test_each_reserved_target_maps_to_one_action(self):
        actions = {}
        for target in adopt_plan.RESERVED:
            lines, _ = parse("- [x] `a` -> `%s`\n      причина\n" % target)
            actions[target] = adopt_plan.action(lines[0])
        self.assertEqual(actions, {"foreign-repo": None, "git-history": "drop",
                                   "merge": "merge", "stay": None})


class TestFile(unittest.TestCase):
    def test_reading_from_disk_uses_the_relative_path_in_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            (root / PLAN).write_text("мусор\n", encoding="utf-8")
            lines, found = adopt_plan.read(root, root / PLAN)
            self.assertEqual([f.path for f in found], [PLAN])
