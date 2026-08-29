"""Разбор плана усыновления: строгая шапка, свободное тело, ошибка вместо пропуска."""

import tempfile
import unittest
from pathlib import Path

from scripts.adopt import plan as adopt_plan
from scripts.maintain import field_map
from tests.foreign import materialise

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


class TestOverlap(unittest.TestCase):
    def test_a_source_that_is_an_ancestor_of_another_is_a_finding(self):
        """Альтернатива — «побеждает ближайший предок» — отвергнута: смысл
        плана начал бы зависеть от порядка строк, а перекрытая строка стала
        бы невидимой ошибкой. Тот же класс тихой гнили, что `dead-allow`."""
        lines, _ = parse(
            "- [x] `a` -> `x`\n      причина\n"
            "- [x] `a/b` -> `y`\n      причина\n")
        self.assertEqual(places(adopt_plan.overlaps(lines, PLAN)), [
            (PLAN, 3, "overlapping-line",
             "источник `a/b` накрыт строкой 1: `a`")])

    def test_the_covering_line_may_come_second(self):
        """Тот же план строками наоборот. Проверка, глядящая только назад,
        здесь молчит, — и порядок строк снова начинает решать, есть ли
        ошибка. Ровно то, ради отказа от чего перекрытие и запрещено.
        Находка одна и всегда на накрытой строке, куда бы ни смотрела."""
        lines, _ = parse(
            "- [x] `a/b` -> `y`\n      причина\n"
            "- [x] `a` -> `x`\n      причина\n")
        self.assertEqual(places(adopt_plan.overlaps(lines, PLAN)), [
            (PLAN, 1, "overlapping-line",
             "источник `a/b` накрыт строкой 3: `a`")])

    def test_two_identical_sources_overlap_too(self):
        lines, _ = parse(
            "- [x] `a` -> `x`\n      причина\n"
            "- [ ] `a` -> `y`\n      причина\n")
        self.assertEqual(places(adopt_plan.overlaps(lines, PLAN)), [
            (PLAN, 3, "overlapping-line",
             "источник `a` накрыт строкой 1: `a`")])

    def test_siblings_do_not_overlap(self):
        lines, _ = parse(
            "- [x] `a/b` -> `x`\n      причина\n"
            "- [x] `a/c` -> `y`\n      причина\n")
        self.assertEqual(adopt_plan.overlaps(lines, PLAN), [])

    def test_a_prefix_that_is_not_a_path_boundary_does_not_overlap(self):
        """`a` не предок `ab`. Сравнение посегментное, а не по подстроке."""
        lines, _ = parse(
            "- [x] `a` -> `x`\n      причина\n"
            "- [x] `ab` -> `y`\n      причина\n")
        self.assertEqual(adopt_plan.overlaps(lines, PLAN), [])


TOP = ("README.md", "state.md", "archive", "identity", "journal",
       "media", "notes", "pipeline", "projects", "vendor-lib")


class TestCoverage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        (self.root / "tmp").mkdir()
        (self.root / PLAN).write_text("# план\n", encoding="utf-8")

    def _cover(self, sources):
        text = "".join("- [ ] `%s` -> `?`\n      причина\n" % s for s in sources)
        lines, _ = parse(text)
        return places(adopt_plan.coverage(self.root, lines, PLAN))

    def test_a_total_plan_leaves_nothing_uncovered(self):
        self.assertEqual(self._cover(TOP), [])

    def test_the_plan_file_itself_is_not_demanded_but_its_neighbour_is(self):
        """Из инвентаря вычитается ровно одно имя — сам файл плана, а не
        каталог вокруг него. Иначе под видом «вычесть план» из полноты
        выпадает целая папка, и первое же, что автор туда положит, пропадёт
        молча."""
        self.assertEqual(self._cover(TOP), [])
        (self.root / "tmp" / "scratch.md").write_text("x", encoding="utf-8")
        self.assertEqual(self._cover(TOP), [
            (PLAN, 1, "uncovered-path",
             "путь не покрыт ни одной строкой: tmp/scratch.md")])

    def test_the_recipes_own_mutation_table_is_not_demanded(self):
        """Таблица массовой мутации ложится рядом с планом **после** того,
        как план написан, и авторским путём не является.

        Требовать на неё строку — требовать от автора классифицировать вывод
        плагина, а от плагина — дописывать себе разрешение в файл согласия.
        Наблюдалось это не рассуждением: `rewrite-refs`, положив таблицу
        рядом с планом, отказывался на следующем же ходу цепочки — «план не
        разобран». Соседа-автора послабление не касается, он остаётся
        названным (тест выше).
        """
        self.assertEqual(self._cover(TOP), [])
        for rel in (field_map.name("rewrite-refs", ("notes", "areas/work/notes"),
                                   field_map.REFS),
                    field_map.name("backfill", ("areas/work/journal", "created"))):
            (self.root / rel).write_text("path\n", encoding="utf-8")
        self.assertEqual(self._cover(TOP), [])

    def test_an_unmentioned_directory_is_reported_once_at_its_top(self):
        """Отчёт называет самый мелкий непокрытый путь, а не все 733 под ним:
        иначе один забытый каталог заливает отчёт и его перестают читать."""
        found = self._cover([s for s in TOP if s != "journal"])
        self.assertEqual(found, [
            (PLAN, 1, "uncovered-path", "путь не покрыт ни одной строкой: journal")])

    def test_a_deeper_line_forces_the_walk_to_descend(self):
        """Строка про `archive/notion` обязывает назвать несестёр внутри
        `archive`, а не отчитаться про `archive` целиком."""
        found = self._cover(
            ["README.md", "state.md", "archive/notion", "identity", "journal",
             "media", "notes", "pipeline", "projects", "vendor-lib"])
        self.assertEqual(found, [])

    def test_an_empty_plan_names_the_top_of_the_tree(self):
        found = self._cover([])
        self.assertEqual(
            [f[3] for f in found],
            ["путь не покрыт ни одной строкой: %s" % name for name in
             sorted(TOP)])

    def test_the_target_of_an_executed_move_is_covered_by_that_move(self):
        """Повторный вход в цепочку. Перенесённое лежит там, куда его
        отправила согласованная строка, — требовать на него второй строки
        значило бы объявлять план неполным ровно за то, что он исполнен.
        Засчитывается только исполненная строка: непереехавшая цель ничего
        не покрывает, иначе одна строка тихо освобождала бы от разбора
        целый существующий каталог."""
        (self.root / "areas" / "work").mkdir(parents=True)
        (self.root / "notes").rename(self.root / "areas" / "work" / "notes")
        text = "".join(
            "- [x] `%s` -> `%s`\n      причина\n" % (s, t) for s, t in
            [(s, "?") for s in TOP if s != "notes"] +
            [("notes", "areas/work/notes")])
        lines, _ = parse(text)
        self.assertEqual(places(adopt_plan.coverage(self.root, lines, PLAN)), [])

    def test_an_unexecuted_target_covers_nothing(self):
        """Фальсификатор к строке выше: `journal` существует и без переезда,
        и строка, целящаяся в него, разбора с него не снимает."""
        text = "".join(
            "- [x] `%s` -> `%s`\n      причина\n" % (s, t) for s, t in
            [(s, "?") for s in TOP if s not in ("journal", "notes")] +
            [("notes", "journal")])
        lines, _ = parse(text)
        self.assertEqual(places(adopt_plan.coverage(self.root, lines, PLAN)), [
            (PLAN, 1, "uncovered-path", "путь не покрыт ни одной строкой: journal")])


class TestState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _state(self, source, target, make_source, make_target):
        if make_source:
            (self.root / source).write_text("s", encoding="utf-8")
        if make_target:
            (self.root / target).parent.mkdir(parents=True, exist_ok=True)
            (self.root / target).write_text("t", encoding="utf-8")
        lines, _ = parse("- [x] `%s` -> `%s`\n      причина\n" % (source, target))
        return adopt_plan.state(self.root, lines[0])

    def test_the_four_states(self):
        self.assertEqual(self._state("a.md", "z/a.md", True, False), "pending")
        self.assertEqual(self._state("b.md", "z/b.md", False, True), "done")
        self.assertEqual(self._state("c.md", "z/c.md", True, True), "collision")
        self.assertEqual(self._state("d.md", "z/d.md", False, False), "lost")

    def test_collision_and_loss_are_findings(self):
        (self.root / "c.md").write_text("s", encoding="utf-8")
        (self.root / "z").mkdir()
        (self.root / "z" / "c.md").write_text("t", encoding="utf-8")
        lines, _ = parse("- [x] `c.md` -> `z/c.md`\n      причина\n"
                         "- [x] `d.md` -> `z/d.md`\n      причина\n")
        self.assertEqual(places(adopt_plan.conflicts(self.root, lines, PLAN)), [
            (PLAN, 1, "line-state-conflict",
             "источник и цель существуют оба: `c.md` -> `z/c.md`"),
            (PLAN, 3, "line-state-conflict",
             "ни источника, ни цели: `d.md` -> `z/d.md`")])

    def test_a_question_has_no_state_and_never_conflicts(self):
        lines, _ = parse("- [x] `nothing.md` -> `?`\n      спрашиваю\n")
        self.assertIsNone(adopt_plan.state(self.root, lines[0]))
        self.assertEqual(adopt_plan.conflicts(self.root, lines, PLAN), [])

    def test_a_drop_line_is_done_when_the_source_is_gone(self):
        """У `git-history` цели в дереве нет по определению, и столкновения
        быть не может: судится только исчезновение источника."""
        lines, _ = parse("- [x] `archive` -> `git-history`\n      причина\n")
        self.assertEqual(adopt_plan.state(self.root, lines[0]), "done")
        (self.root / "archive").mkdir()
        self.assertEqual(adopt_plan.state(self.root, lines[0]), "pending")

    def test_a_merge_line_reads_the_marker_not_existence(self):
        """`CLAUDE.md` существует и до, и после слияния. Состояние берётся
        из содержимого — маркера, который оставляет установщик."""
        lines, _ = parse("- [x] `CLAUDE.md` -> `merge`\n      причина\n")
        (self.root / "CLAUDE.md").write_text("чужой текст\n", encoding="utf-8")
        self.assertEqual(adopt_plan.state(self.root, lines[0]), "pending")
        (self.root / "CLAUDE.md").write_text(
            "чужой текст\n<!-- %s -->\n" % adopt_plan.MERGE_MARKER,
            encoding="utf-8")
        self.assertEqual(adopt_plan.state(self.root, lines[0]), "done")

    def test_a_merge_line_without_its_file_is_lost(self):
        """Сливать нечего и слитого нет. Молчать об этом — значит держать
        в плане согласие, которому в дереве ничего не соответствует."""
        lines, _ = parse("- [x] `CLAUDE.md` -> `merge`\n      причина\n")
        self.assertEqual(adopt_plan.state(self.root, lines[0]), "lost")
        self.assertEqual([f.cls for f in
                          adopt_plan.conflicts(self.root, lines, PLAN)],
                         ["line-state-conflict"])


class TestFile(unittest.TestCase):
    def test_reading_from_disk_uses_the_relative_path_in_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            (root / PLAN).write_text("мусор\n", encoding="utf-8")
            lines, found = adopt_plan.read(root, root / PLAN)
            self.assertEqual([f.path for f in found], [PLAN])

    def test_load_gathers_the_parse_the_overlap_and_the_coverage(self):
        """Одна точка входа на все проверки плана: `read-plan`, `check-plan`
        и три мутирующие команды зовут её и не заводят своих наборов —
        иначе наборы разошлись бы, и половина команд поехала бы по плану,
        который вторая половина уже назвала сломанным."""
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp, git_root=False, nested=False)
            (root / "tmp").mkdir()
            (root / PLAN).write_text(
                "- [x] `journal` -> `x`\n      причина\n"
                "- [x] `journal/2026-01-04.md` -> `y`\n      причина\n"
                "мусор с нулевой позиции\n", encoding="utf-8")
            lines, found = adopt_plan.load(root, root / PLAN)
            self.assertEqual([l.source for l in lines],
                             ["journal", "journal/2026-01-04.md"])
            self.assertEqual(sorted({f.cls for f in found}),
                             ["overlapping-line", "plan-unparseable",
                              "uncovered-path"])
