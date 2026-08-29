"""`merge`: каркасная часть дописывается в чужой файл по строке плана."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import init_tree, merge, revert, tree
from scripts.adopt import plan as adopt_plan
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from tests.foreign import committer, materialise
from tests.test_read_plan import TOTAL, write_plan

ROOT = Path(__file__).resolve().parent.parent

FOREIGN_CLAUDE = "# Чужой проект\n\nЗдесь были свои правила.\n"
FOREIGN_IGNORE = "node_modules/\n.DS_Store\n"

# Два файла, которые каркас делит с чужим деревом. Строки плана на них
# обязательны в обе стороны: без них слияние — `unagreed-change`, а сами
# файлы — `uncovered-path`.
MERGES = TOTAL + (
    "\n- [x] `CLAUDE.md` -> `merge`\n"
    "      Файл автора, каркасная часть дописывается под маркером.\n"
    "\n- [x] `.gitignore` -> `merge`\n"
    "      Строки каркаса, которых здесь нет.\n")

# Источник вне корня в плане законен: разбор `..` не запрещает, и граница
# спрашивается у мутации.
OUTSIDE = MERGES + ("\n- [x] `../соседний/CLAUDE.md` -> `merge`\n"
                    "      Файл, которого тут быть не должно.\n")


def _foreign(case, git=True):
    root = materialise(case.tmp.name, git_root=False, nested=False)
    (root / "CLAUDE.md").write_text(FOREIGN_CLAUDE, encoding="utf-8")
    (root / ".gitignore").write_text(FOREIGN_IGNORE, encoding="utf-8")
    plan = write_plan(root, MERGES)
    if git:
        report, code = init_tree.run(root)
        case.assertEqual(code, EXIT_OK, report)
    return root, plan


class TestMerge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root, self.plan = _foreign(self)

    def text(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def test_an_agreed_line_appends_the_recipe_and_keeps_the_text(self):
        report, code = merge.run(self.root, "CLAUDE.md", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        text = self.text("CLAUDE.md")
        self.assertTrue(text.startswith(FOREIGN_CLAUDE), text)
        self.assertIn("## Zone map", text)

    def test_the_line_becomes_done_and_the_second_run_changes_nothing(self):
        """Состояние строки читается из маркера, а не из файла состояния.
        Неидемпотентное слияние дописывало бы карту зон на каждом запуске, и
        дерево оставалось бы грязным после каждого хода."""
        line = [l for l in adopt_plan.load(self.root, self.plan)[0]
                if l.source == "CLAUDE.md"][0]
        self.assertEqual(adopt_plan.state(self.root, line), "pending")
        report, code = merge.run(self.root, "CLAUDE.md", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(adopt_plan.state(self.root, line), "done")
        before = tree.manifest(self.root)
        report, code = merge.run(self.root, "CLAUDE.md", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertIn("уже исполнено", report)
        self.assertEqual(tree.manifest(self.root), before)

    def test_the_gitignore_gains_the_recipe_lines_and_keeps_its_own(self):
        report, code = merge.run(self.root, ".gitignore", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        lines = [l for l in self.text(".gitignore").split("\n") if l.strip()]
        self.assertEqual(lines.count("node_modules/"), 1)
        self.assertEqual(lines.count(".DS_Store"), 1)
        self.assertIn(".trash/", lines)

    def test_the_merge_is_revertible_byte_for_byte(self):
        """Критерий 1 волны. Слияние правит файл, лежавший в коммите «как
        было», и без побайтового отката оно было бы правкой без пути назад."""
        before = (self.root / "CLAUDE.md").read_bytes()
        report, code = merge.run(self.root, "CLAUDE.md", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        # Иначе откат доказывает тождество: слияние, не сделавшее ничего,
        # возвращается к исходным байтам само собой.
        self.assertNotEqual((self.root / "CLAUDE.md").read_bytes(), before)
        report, code = revert.run(self.root, ["CLAUDE.md"])
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), before)

    def test_a_line_that_is_executed_otherwise_is_refused(self):
        report, code = merge.run(self.root, "notes", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("исполняется не как `merge`, а как `move`", report)
        self.assertTrue((self.root / "notes" / "meeting.md").exists())

    def test_a_path_outside_the_closed_set_is_refused(self):
        """Закрытое множество держится и здесь: строка плана согласовывает
        изменение, но какие файлы плагин вправе слить — не вопрос согласия,
        а линия ответственности (незыблемое №1)."""
        write_plan(self.root, MERGES.replace(
            "- [x] `notes` -> `areas/work/notes`", "- [x] `notes` -> `merge`"))
        before = tree.manifest(self.root)
        report, code = merge.run(self.root, "notes", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("слиянию подлежат только", report)
        self.assertEqual(tree.manifest(self.root), before)

    def test_an_unagreed_line_is_refused(self):
        write_plan(self.root, MERGES.replace("- [x] `CLAUDE.md`",
                                             "- [ ] `CLAUDE.md`"))
        report, code = merge.run(self.root, "CLAUDE.md", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("строка не согласована", report)
        self.assertEqual(self.text("CLAUDE.md"), FOREIGN_CLAUDE)

    def test_a_line_absent_from_the_plan_is_refused(self):
        report, code = merge.run(self.root, "СВОЁ.md", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertEqual(report, "такой строки в плане нет: `СВОЁ.md`\n")
        self.assertFalse((self.root / "СВОЁ.md").exists())

    def test_a_source_outside_the_root_is_refused(self):
        """Незыблемое №6, и спрошено оно раньше закрытого множества: сосед
        `../соседний/CLAUDE.md` в него не входит тоже, и отказ назвал бы
        автору не ту причину."""
        neighbour = self.root.parent / "соседний"
        neighbour.mkdir()
        (neighbour / "CLAUDE.md").write_text("чужое\n", encoding="utf-8")
        write_plan(self.root, OUTSIDE)
        report, code = merge.run(self.root, "../соседний/CLAUDE.md", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("вне корня", report)
        self.assertEqual((neighbour / "CLAUDE.md").read_text(encoding="utf-8"),
                         "чужое\n")

    def test_a_broken_plan_stops_the_merge(self):
        write_plan(self.root, MERGES + "мусор с нулевой позиции\n")
        report, code = merge.run(self.root, "CLAUDE.md", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("plan-unparseable", report)
        self.assertEqual(self.text("CLAUDE.md"), FOREIGN_CLAUDE)

    def test_the_command_line_carries_the_merge_through(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "adopt" / "merge.py"),
             str(self.root), "CLAUDE.md", "--plan", str(self.plan)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
        self.assertIn("слито: `CLAUDE.md`", proc.stdout)
        self.assertIn(adopt_plan.MERGE_MARKER, self.text("CLAUDE.md"))


class TestWithoutGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root, self.plan = _foreign(self, git=False)

    def test_without_a_commit_nothing_is_merged(self):
        """Ветка отказа от git: ADOPT вырождается в чтение. Дописать в чужой
        файл там, где отката нет, значило бы изменить его безвозвратно."""
        report, code = merge.run(self.root, "CLAUDE.md", self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("нет коммита", report)
        self.assertEqual((self.root / "CLAUDE.md").read_text(encoding="utf-8"),
                         FOREIGN_CLAUDE)


class TestPlanIsMandatory(unittest.TestCase):
    def test_the_command_line_has_no_way_to_omit_the_plan(self):
        """`--plan` обязателен: слияние без плана — дверь мимо инварианта,
        и закрыта она разбором аргументов, а не дисциплиной."""
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp, git_root=False, nested=False)
            (root / "CLAUDE.md").write_text(FOREIGN_CLAUDE, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "adopt" / "merge.py"),
                 str(root), "CLAUDE.md"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--plan", proc.stderr)
            self.assertEqual((root / "CLAUDE.md").read_text(encoding="utf-8"),
                             FOREIGN_CLAUDE)
