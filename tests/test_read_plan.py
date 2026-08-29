"""`read-plan`: единственный источник списка «что исполнять»."""

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import read_plan
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from tests.foreign import materialise

ROOT = Path(__file__).resolve().parent.parent
PLAN = "tmp/adopt-plan.md"

TOTAL = """\
# план усыновления, снят 2026-08-29

## Этап 1. Раскладка по зонам

- [x] `README.md` -> `core/readme.md`
      Главный файл, переезжает в core.

- [ ] `state.md` -> `core/state.md`
      Не согласовано.

- [x] `journal` -> `areas/<?>/journal`
      Область неизвестна, спрашиваю.

- [x] `archive` -> `git-history`
      Экспорт из Notion.

- [x] `vendor-lib` -> `foreign-repo`
      Чужой репозиторий.

- [x] `identity` -> `stay`
      Лежит правильно.

- [x] `media` -> `sources/media`
      Выгрузки как получены.

- [x] `notes` -> `areas/work/notes`
      Рабочие заметки.

- [x] `pipeline` -> `sources/pipeline`
      Скрипт, вход и выход.

- [x] `projects` -> `projects/meeting`
      Встречи по проектам.
"""


def write_plan(root, text):
    (root / "tmp").mkdir(exist_ok=True)
    (root / PLAN).write_text(text, encoding="utf-8")
    return root / PLAN


def digest(root):
    """Хеш дерева: имена и байты. Доказательство read-only, как у гейтов."""
    out = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        out.update(path.relative_to(root).as_posix().encode("utf-8"))
        out.update(path.read_bytes())
    return out.hexdigest()


class TestWhatIsPrinted(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        write_plan(self.root, TOTAL)

    def rows(self):
        text, code = read_plan.render(self.root, self.root / PLAN)
        self.assertEqual(code, EXIT_OK, text)
        return [l.split("\t") for l in text.split("\n") if l]

    def test_only_agreed_executable_pending_lines_are_printed(self):
        """Точный список. Крестик, отсутствие `?`, состояние «не исполнено» —
        три условия, и снятие любого обязано изменить этот список."""
        self.assertEqual(self.rows(), [
            ["Этап 1. Раскладка по зонам", "move", "README.md", "core/readme.md"],
            ["Этап 1. Раскладка по зонам", "drop", "archive", "git-history"],
            ["Этап 1. Раскладка по зонам", "move", "media", "sources/media"],
            ["Этап 1. Раскладка по зонам", "move", "notes", "areas/work/notes"],
            ["Этап 1. Раскладка по зонам", "move", "pipeline", "sources/pipeline"],
            ["Этап 1. Раскладка по зонам", "move", "projects", "projects/meeting"],
        ])

    def test_a_question_with_a_cross_never_appears(self):
        """Критерий 5, фальсификатор: `journal` согласован крестиком и
        всё равно не исполняется, потому что цель несёт `?`."""
        self.assertEqual([r for r in self.rows() if r[2] == "journal"], [])

    def test_an_executed_line_disappears_from_the_output(self):
        """Повторный вход в цепочку: строка, чья цель уже на месте, больше
        не предлагается, а остальные предлагаются по-прежнему. Состояние
        берётся из дерева, не из файла."""
        (self.root / "areas" / "work").mkdir(parents=True)
        (self.root / "notes").rename(self.root / "areas" / "work" / "notes")
        self.assertEqual([r[2] for r in self.rows()],
                         ["README.md", "archive", "media", "pipeline", "projects"])


class TestRefusal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)

    def test_a_plan_with_findings_prints_them_and_no_lines(self):
        """Исполнять по разъехавшемуся плану — та самая дыра, ради которой
        `read-plan` объявлен единственным источником списка."""
        write_plan(self.root, TOTAL.replace(
            "- [x] `media` -> `sources/media`", "мусор с нулевой позиции"))
        text, code = read_plan.render(self.root, self.root / PLAN)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("plan-unparseable", text)
        self.assertNotIn("\tmove\t", text)

    def test_an_incomplete_plan_is_a_refusal_too(self):
        """Критерий 5: молчание наблюдаемо, потому что план обязан быть
        тотальным. Неполный план не исполняется вовсе."""
        write_plan(self.root, TOTAL.replace(
            "- [x] `media` -> `sources/media`\n      Выгрузки как получены.\n\n", ""))
        text, code = read_plan.render(self.root, self.root / PLAN)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("uncovered-path", text)
        self.assertNotIn("\tmove\t", text)


class TestReadOnly(unittest.TestCase):
    def test_the_command_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp, git_root=False, nested=False)
            write_plan(root, TOTAL)
            before = digest(root)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "adopt" / "read_plan.py"),
                 str(root), str(root / PLAN)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
            self.assertEqual(digest(root), before)
            self.assertIn("\tmove\tREADME.md\tcore/readme.md", proc.stdout)
