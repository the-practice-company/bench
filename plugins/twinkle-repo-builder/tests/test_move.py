"""Критерий 3: ничего не двигается до согласия автора."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import init_tree, move, tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from tests.foreign import committer, materialise
from tests.test_read_plan import TOTAL, write_plan

ROOT = Path(__file__).resolve().parent.parent


class TestMove(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        self.plan = write_plan(self.root, TOTAL)
        report, code = init_tree.run(self.root)
        self.assertEqual(code, EXIT_OK, report)

    def test_an_agreed_line_moves_and_git_knows_it_as_a_rename(self):
        """Перенос идёт через git, а не мимо него: в индексе он лежит
        переименованием, и следующий коммит покажет автору именно переезд."""
        report, code = move.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertFalse((self.root / "notes").exists())
        self.assertTrue((self.root / "areas" / "work" / "notes" / "meeting.md").exists())
        staged = tree.git(self.root, "diff", "--cached", "--name-status", "-M").stdout
        self.assertEqual(
            staged, "R100\tnotes/meeting.md\tareas/work/notes/meeting.md\n")

    def test_an_unagreed_line_is_refused_with_a_named_reason(self):
        """Критерий 3. Строка `state.md` в плане есть, крестика на ней нет."""
        report, code = move.run(self.root, "state.md", "core/state.md", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("строка не согласована", report)
        self.assertTrue((self.root / "state.md").exists())

    def test_a_line_absent_from_the_plan_is_refused(self):
        report, code = move.run(self.root, "README.md", "core/иное.md", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("такой строки в плане нет", report)
        self.assertFalse((self.root / "core").exists())

    def test_a_question_is_refused_even_with_a_cross(self):
        """Критерий 5, второй фальсификатор: согласие с вопросом — это
        согласие с тем, что ответа нет."""
        report, code = move.run(self.root, "journal", "areas/<?>/journal", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("цель несёт знак вопроса", report)
        self.assertTrue((self.root / "journal").is_dir())

    def test_a_reserved_target_is_executed_by_another_command(self):
        report, code = move.run(self.root, "archive", "git-history", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("исполняется не как `move`, а как `drop`", report)
        self.assertTrue((self.root / "archive").is_dir())

    def test_a_line_that_nothing_executes_is_refused_too(self):
        """`stay` и `foreign-repo` не исполняются никакой командой вовсе.
        Сказать про них «не как `move`, а как ...» было бы нечем закончить."""
        report, code = move.run(self.root, "identity", "stay", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("строка не исполняется ничем", report)

    def test_the_refusal_names_the_action_the_caller_expected(self):
        """Ту же функцию зовёт `drop`. Слово «перенос», зашитое в отказ,
        обвиняло бы автора в несогласованном переезде там, где речь про
        удаление, — и отчёт говорил бы неправду о происходящем."""
        line, reason = move.agreed_line(
            self.root, "notes", "areas/work/notes", self.plan, "drop")
        self.assertIsNone(line)
        self.assertIn("исполняется не как `drop`, а как `move`", reason)

    def test_a_collision_is_refused_by_the_plan_itself(self):
        """Источник и цель существуют оба — состояние, о котором `plan.load`
        уже говорит находкой. Мутация до неё не доходит, и цель не
        перезаписывается."""
        (self.root / "areas" / "work" / "notes").mkdir(parents=True)
        report, code = move.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("line-state-conflict", report)
        self.assertIn("источник и цель существуют оба", report)
        self.assertTrue((self.root / "notes" / "meeting.md").exists())

    def test_a_broken_plan_stops_the_move(self):
        write_plan(self.root, TOTAL + "мусор с нулевой позиции\n")
        report, code = move.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("plan-unparseable", report)
        self.assertTrue((self.root / "notes").exists())

    def test_a_target_outside_the_root_is_refused(self):
        """Незыблемое №6. Разбор плана `..` в цели не запрещает — граница
        спрашивается здесь, у мутации, и другого места у неё нет."""
        write_plan(self.root, TOTAL.replace(
            "- [x] `notes` -> `areas/work/notes`",
            "- [x] `notes` -> `../соседний/notes`"))
        report, code = move.run(self.root, "notes", "../соседний/notes", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("вне корня", report)
        self.assertTrue((self.root / "notes").exists())
        self.assertFalse((self.root.parent / "соседний").exists())

    def test_an_executed_line_is_not_executed_twice(self):
        """Повторная входимость цепочки: оборвавшись между `rewrite-refs` и
        `move`, она доводится следующим запуском, а уже доведённая — молчит
        и ничего не трогает."""
        report, code = move.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        before = tree.manifest(self.root)
        report, code = move.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertIn("уже исполнено", report)
        self.assertEqual(tree.manifest(self.root), before)

    def test_the_command_line_carries_the_move_through(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "adopt" / "move.py"),
             str(self.root), "notes", "areas/work/notes", "--plan", str(self.plan)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
        self.assertIn("перенесено: `notes` -> `areas/work/notes`", proc.stdout)
        self.assertTrue((self.root / "areas" / "work" / "notes" / "meeting.md").exists())


class TestWithoutGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        self.plan = write_plan(self.root, TOTAL)

    def test_a_move_by_hand_instead_of_git_is_not_an_option(self):
        """Дерева без точки отката эта команда не двигает. Перенос средствами
        файловой системы прошёл бы здесь молча и дал бы мутацию, которую
        `revert` вернуть не может: в индексе её нет, в `HEAD` её нет."""
        report, code = move.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("перенос не прошёл", report)
        self.assertTrue((self.root / "notes" / "meeting.md").exists())

    def test_a_refused_move_leaves_no_directory_behind(self):
        """Каталог под целью создаётся до `git mv`, иначе перенос не идёт.
        Оставшись после отказа, он становится `uncovered-path` в следующем же
        `read-plan`: план объявляется неполным за то, чего автор не делал."""
        move.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertFalse((self.root / "areas").exists())


class TestPlanIsMandatory(unittest.TestCase):
    def test_the_command_line_has_no_way_to_omit_the_plan(self):
        """`--plan` обязателен: мутация без плана — это дверь мимо инварианта,
        и закрыта она разбором аргументов, а не дисциплиной."""
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp, git_root=False, nested=False)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "adopt" / "move.py"),
                 str(root), "notes", "areas/work/notes"],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--plan", proc.stderr)
            self.assertTrue((root / "notes" / "meeting.md").exists())
