"""`check-plan`: уход с плана, кем бы он ни был сделан."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import check_plan, init_tree, move, rewrite_refs, tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from tests.foreign import committer, materialise
from tests.test_read_plan import TOTAL, write_plan

ROOT = Path(__file__).resolve().parent.parent

OFF_PLAN = ("identity/how-we-work.md", 1, "unagreed-change",
            "путь изменился вне согласованной строки плана")


def places(text):
    """Находки из отчёта в `(путь, строка, класс, деталь)`. `run` возвращает
    текст и код — та же форма, что у `move`, `revert` и `drop`."""
    out = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        head, _, rest = line.partition(" ")
        path, _, lineno = head.rpartition(":")
        cls, _, detail = rest.partition(" ")
        out.append((path, int(lineno), cls, detail))
    return sorted(out)


class Prepared(unittest.TestCase):
    """Чужое дерево, план в коммите «как было» и точка отката."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        self.plan = write_plan(self.root, TOTAL)
        report, code = init_tree.run(self.root)
        self.assertEqual(code, EXIT_OK, report)


class TestCheck(Prepared):
    def test_an_untouched_tree_is_clean(self):
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(places(text), [])
        self.assertEqual(code, EXIT_OK)

    def test_a_change_outside_any_agreed_line_is_a_finding(self):
        """Ловит уход с плана независимо от того, кто его сделал: скрипт,
        скилл или рука автора. Строка `identity` согласована крестиком, но
        целью `stay`: её не исполняет ничто, и правка под ней не согласована
        ничем."""
        (self.root / "identity" / "how-we-work.md").write_text(
            "переписано мимо плана\n", encoding="utf-8")
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(places(text), [OFF_PLAN])
        self.assertEqual(code, EXIT_VIOLATION)

    def test_a_tracked_new_file_is_not_judged(self):
        """Создание под инвариант не подпадает: оно обратимо удалением того,
        чего до ADOPT не было. Иначе коммит каркаса — сплошная находка.

        Файл кладётся в индекс намеренно: неотслеженного `git diff` не
        показывает вовсе, и на нём этот тест был бы зелен независимо от того,
        судит проверка создание или нет.

        Кладётся он под `identity` — строку с целью `stay`. Согласие её не
        исполняет ничто, значит новый файл под ней ничем и не накрыт, и
        зелёным тест остаётся ровно из-за правила «судятся только пути
        коммита „как было“»."""
        (self.root / "identity" / "новая.md").write_text(
            "# новая\n", encoding="utf-8")
        tree.git(self.root, "add", "--", "identity/новая.md")
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(places(text), [])
        self.assertEqual(code, EXIT_OK)

    def test_an_executed_agreed_line_is_clean(self):
        report, code = move.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(places(text), [])
        self.assertEqual(code, EXIT_OK)

    def test_a_rename_by_hand_is_judged_by_the_path_it_left(self):
        """`--no-renames` держит эту находку. С определением переименования
        git показывает только новый путь, а его в коммите «как было» не
        было, — и правка ушла бы незамеченной."""
        tree.git(self.root, "mv", "identity/how-we-work.md", "identity/устав.md")
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(places(text), [OFF_PLAN])
        self.assertEqual(code, EXIT_VIOLATION)

    def test_a_file_edited_by_rewrite_refs_is_justified_by_the_journal(self):
        """Без журнала такой файл выглядит уходом с плана: он существовал в
        коммите «как было», изменился и источником строки не является.

        Переписывается `identity/how-we-work.md`, а не `README.md`: README —
        источник согласованной строки, и его накрыло бы согласие раньше, чем
        журнал, то есть тест был бы зелен и без журнала."""
        (self.root / "identity" / "how-we-work.md").write_text(
            "# Как мы работаем\n\nВстреча — в [[notes/meeting]].\n",
            encoding="utf-8")
        tree.git(self.root, "commit", "-q", "-am", "правка автора до этапа")
        report, code = rewrite_refs.run(self.root, "notes", "areas/work/notes",
                                        self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertIn("ссылок переписано: 1", report)
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(places(text), [])
        self.assertEqual(code, EXIT_OK)

    def test_a_journal_entry_for_an_unagreed_line_does_not_justify_anything(self):
        """Журнал оправдывает правку только под согласованной строкой.
        Иначе он становится дырой шире той, что закрывает."""
        (self.root / "identity" / "how-we-work.md").write_text(
            "х\n", encoding="utf-8")
        tree.record_touched(self.root, "state.md", ["identity/how-we-work.md"])
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(places(text), [OFF_PLAN])
        self.assertEqual(code, EXIT_VIOLATION)

    def test_the_plan_itself_is_not_judged(self):
        """План лежит в коммите «как было» и правится всю процедуру: ответы
        на вопросы дописываются в него. Судить инструмент согласия им же
        значит остановить усыновление на первом же ответе."""
        write_plan(self.root, TOTAL + "\n# ответ: journal — область work\n")
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(places(text), [])
        self.assertEqual(code, EXIT_OK)

    def test_without_a_base_the_check_refuses_instead_of_passing(self):
        """Молчаливое зелёное здесь означало бы, что инвариант не проверялся."""
        (self.root / ".git" / tree.BASE_FILE).unlink()
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("точки отката нет", text)

    def test_a_broken_plan_stops_the_check(self):
        """Сверять с планом, который не разобрался, значило бы объявить
        дерево чистым по документу, которого никто не прочитал."""
        write_plan(self.root, TOTAL + "мусор с нулевой позиции\n")
        text, code = check_plan.run(self.root, self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("plan-unparseable", text)
        self.assertIn("план не разобран", text)


class TestCommandLine(Prepared):
    def test_the_check_names_the_finding_and_changes_nothing(self):
        """Проверка read-only: она судит дерево и не правит его, иначе
        сверять было бы не с чем уже на втором запуске."""
        (self.root / "identity" / "how-we-work.md").write_text(
            "х\n", encoding="utf-8")
        before = tree.manifest(self.root)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "adopt" / "check_plan.py"),
             str(self.root), str(self.plan)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, EXIT_VIOLATION, proc.stderr)
        self.assertIn("identity/how-we-work.md:1 unagreed-change", proc.stdout)
        self.assertEqual(tree.manifest(self.root), before)
