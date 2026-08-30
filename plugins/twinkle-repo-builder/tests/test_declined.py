"""Критерий 4: нет git и автор отказался — план написан, ничего не изменено."""

import tempfile
import unittest

from scripts.adopt import init_tree, plan, tree
from scripts.findings import EXIT_OK
from tests.foreign import committer, materialise

# Шапка собирается из константы пакета, а не набирается в тесте руками:
# набранная руками, она проверяла бы, что тест умеет писать ту строку,
# которую сам же ищет.
HEADER = ("# план усыновления, снят 2026-08-29\n"
          "# %s. Усыновление останавливается после плана.\n" % plan.DECLINED)

PLAN = "tmp/adopt-plan.md"


class TestDeclined(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)

    def _write_plan(self):
        (self.root / "tmp").mkdir()
        (self.root / PLAN).write_text(HEADER, encoding="utf-8")

    def test_nothing_but_the_plan_appears_and_nothing_changes(self):
        before_files, before_dirs = tree.manifest(self.root)
        report, code = init_tree.run(self.root, no_git=True)
        self.assertEqual(code, EXIT_OK, report)
        self._write_plan()

        after_files, after_dirs = tree.manifest(self.root)
        self.assertEqual(sorted(set(after_files) - set(before_files)), [PLAN])
        self.assertEqual({k: v for k, v in after_files.items()
                          if k in before_files}, before_files)
        self.assertEqual(sorted(set(after_dirs) - set(before_dirs)), ["tmp"])
        self.assertFalse((self.root / ".git").exists())

    def test_the_refusal_is_recorded_in_the_plan_header_not_in_open_threads(self):
        """§18 велит фиксировать отказ в открытых нитях. `OPEN-THREADS.md` в
        чужом дереве может уже существовать, и дописать в него — изменение
        файла, запрещённое критерием 4."""
        (self.root / "OPEN-THREADS.md").write_text("чужие нити\n",
                                                   encoding="utf-8")
        before, _ = tree.manifest(self.root)
        init_tree.run(self.root, no_git=True)
        self._write_plan()
        after, _ = tree.manifest(self.root)
        self.assertEqual(after["OPEN-THREADS.md"], before["OPEN-THREADS.md"])
        self.assertTrue(plan.declined(
            (self.root / PLAN).read_text(encoding="utf-8")))

    def test_the_stopped_run_names_the_line_the_header_must_carry(self):
        """Отказ читается повторным запуском, чтобы не переспрашивать (§18).
        Читатель и печатающий обязаны держать одну строку: разойдясь, они
        дадут вечный переспрос при на вид записанном отказе."""
        report, _ = init_tree.run(self.root, no_git=True)
        self.assertIn(plan.DECLINED, report)


class TestTheHeaderIsTheHeader(unittest.TestCase):
    """Читатель отказа. Шапка — комментарии до первой строки плана."""

    def test_a_header_with_the_refusal_reads_as_declined(self):
        self.assertTrue(plan.declined(HEADER))

    def test_a_header_without_it_claims_no_refusal(self):
        self.assertFalse(plan.declined("# план усыновления, снят 2026-08-29\n"))

    def test_a_refusal_below_the_first_line_is_not_the_header(self):
        """Иначе «шапка» значит «где угодно», и фраза, дописанная в тело
        задним числом, читается как решение, принятое до усыновления."""
        text = ("# план усыновления, снят 2026-08-29\n"
                "- [ ] `state.md` -> `core/state.md`\n"
                "    состояние проекта\n"
                "# %s\n" % plan.DECLINED)
        self.assertFalse(plan.declined(text))

    def test_a_refusal_below_a_stage_heading_is_not_the_header(self):
        text = ("# план усыновления, снят 2026-08-29\n"
                "## этап 1\n"
                "# %s\n" % plan.DECLINED)
        self.assertFalse(plan.declined(text))

    def test_the_header_is_still_a_comment_for_the_parser(self):
        """Шапка отказа обязана разбираться как план, иначе остановленный
        прогон оставляет за собой файл, который сам пакет считает сломанным."""
        lines, found = plan.parse(HEADER, PLAN)
        self.assertEqual((lines, found), ([], []))
