"""`drop`: папка уезжает в историю, а не удаляется безвозвратно."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import drop, init_tree, tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from tests.foreign import committer, materialise
from tests.test_read_plan import TOTAL, write_plan

ROOT = Path(__file__).resolve().parent.parent

# Источник вне корня в плане законен: разбор `..` не запрещает, и граница
# спрашивается у мутации. Строка добавляется, а не заменяет существующую:
# заменённая оставила бы свой путь непокрытым, и план не разобрался бы вовсе.
OUTSIDE = TOTAL + ("\n- [x] `../соседний` -> `git-history`\n"
                   "      Соседний каталог, которого тут быть не должно.\n")


class TestDrop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        self.plan = write_plan(self.root, TOTAL)
        report, code = init_tree.run(self.root)
        self.assertEqual(code, EXIT_OK, report)

    def test_an_agreed_line_removes_the_folder_and_keeps_the_history(self):
        """§13 не читает `archive/`, §18 не оставляет его в дереве. Мирит их
        не снятое исключение, а согласованная строка: после неё папки нет, а
        содержимое лежит в коммите «как было»."""
        report, code = drop.run(self.root, "archive", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertFalse((self.root / "archive").exists())
        base = tree.read_base(self.root)
        in_base = tree.git_zlines(self.root, "ls-tree", "-r", "--name-only",
                                  "-z", base, "--", "archive")
        self.assertEqual(sorted(in_base),
                         ["archive/notion/Page%20one.md",
                          "archive/notion/index.md"])

    def test_a_path_absent_from_head_is_refused(self):
        """Удалить нескоммиченное значило бы удалить безвозвратно — то самое,
        против чего заведён коммит «как было»."""
        (self.root / "новая").mkdir()
        (self.root / "новая" / "a.md").write_text("х\n", encoding="utf-8")
        write_plan(self.root, TOTAL + ("\n- [x] `новая` -> `git-history`\n"
                                       "      Появилась после коммита.\n"))
        report, code = drop.run(self.root, "новая", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("пути нет в коммите", report)
        self.assertTrue((self.root / "новая" / "a.md").exists())

    def test_a_line_whose_target_is_not_git_history_is_refused(self):
        """Цель `drop` не вводит автор, она подразумевается. Поэтому строка
        ищется по источнику: сверка по паре ответила бы «такой строки в плане
        нет» на строку, которая в плане есть и исполняется переносом."""
        report, code = drop.run(self.root, "notes", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("исполняется не как `drop`, а как `move`", report)
        self.assertTrue((self.root / "notes" / "meeting.md").exists())

    def test_an_unagreed_line_is_refused(self):
        write_plan(self.root, TOTAL.replace("- [x] `archive`", "- [ ] `archive`"))
        report, code = drop.run(self.root, "archive", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("строка не согласована", report)
        self.assertTrue((self.root / "archive" / "notion" / "index.md").exists())

    def test_a_line_absent_from_the_plan_is_refused(self):
        """Отказ сверяется дословно, а не вхождением: цели у `drop` нет, и
        текст, дописывающий к источнику ` -> \\`None\\``, вхождением проходит
        зелёным, показывая автору цель, которой он не писал."""
        report, code = drop.run(self.root, "identity/how-we-work.md", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertEqual(report,
                         "такой строки в плане нет: `identity/how-we-work.md`\n")
        self.assertTrue((self.root / "identity" / "how-we-work.md").exists())

    def test_a_question_is_refused_even_with_a_cross(self):
        """Согласие с вопросом — это согласие с тем, что ответа нет."""
        report, code = drop.run(self.root, "journal", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("цель несёт знак вопроса", report)
        self.assertTrue((self.root / "journal").is_dir())

    def test_a_source_outside_the_root_is_refused(self):
        """Незыблемое №6. Граница спрашивается **до** состояния строки:
        несуществующего соседа состояние назвало бы исполненным, и отказ
        уехал бы в бодрое «уже исполнено»."""
        neighbour = self.root.parent / "соседний"
        neighbour.mkdir()
        (neighbour / "чужое.md").write_text("не наше\n", encoding="utf-8")
        write_plan(self.root, OUTSIDE)
        report, code = drop.run(self.root, "../соседний", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("вне корня", report)
        self.assertTrue((neighbour / "чужое.md").exists())

    def test_an_executed_line_is_not_executed_twice(self):
        """Повторная входимость цепочки: `git rm` по уже убранному пути падает
        на pathspec, и отказ обвинял бы автора в поломке там, где ход просто
        доведён."""
        report, code = drop.run(self.root, "archive", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        before = tree.manifest(self.root)
        report, code = drop.run(self.root, "archive", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertIn("уже исполнено", report)
        self.assertEqual(tree.manifest(self.root), before)

    def test_a_broken_plan_stops_the_drop(self):
        write_plan(self.root, TOTAL + "мусор с нулевой позиции\n")
        report, code = drop.run(self.root, "archive", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("plan-unparseable", report)
        self.assertTrue((self.root / "archive" / "notion" / "index.md").exists())

    def test_the_command_line_carries_the_drop_through(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "adopt" / "drop.py"),
             str(self.root), "archive", "--plan", str(self.plan)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
        self.assertIn("убрано из дерева, осталось в истории: archive",
                      proc.stdout)
        self.assertFalse((self.root / "archive").exists())


class TestWithoutGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        self.plan = write_plan(self.root, TOTAL)

    def test_without_a_commit_nothing_is_dropped(self):
        """Без коммита «как было» удаление невозвратно, и отказ называется
        вслух: молчаливое «удалено» здесь означало бы потерю чужого дерева."""
        report, code = drop.run(self.root, "archive", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("нет коммита", report)
        self.assertTrue((self.root / "archive" / "notion" / "index.md").exists())


class TestPlanIsMandatory(unittest.TestCase):
    def test_the_command_line_has_no_way_to_omit_the_plan(self):
        """`--plan` обязателен: удаление без плана — дверь мимо инварианта,
        и закрыта она разбором аргументов, а не дисциплиной."""
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp, git_root=False, nested=False)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "adopt" / "drop.py"),
                 str(root), "archive"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--plan", proc.stderr)
            self.assertTrue((root / "archive" / "notion" / "index.md").exists())
