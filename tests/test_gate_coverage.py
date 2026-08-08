import unittest
from pathlib import Path

from scripts.findings import FRONTMATTER_CLASSES, LINK_CLASSES, PACKAGE_CLASSES

ROOT = Path(__file__).resolve().parent.parent
COVERAGE = ROOT / "docs" / "gate-coverage.md"


class TestEveryClassIsProven(unittest.TestCase):
    """У каждого класса либо фикстура, либо записанная причина её отсутствия.

    Пустым оставить нельзя — это и есть механизм под «эффективность,
    а не маскарад»: нельзя молча сделать вид, что покрыто.
    """

    def test_coverage_table_lists_every_class(self):
        table = COVERAGE.read_text(encoding="utf-8")
        for cls in LINK_CLASSES + FRONTMATTER_CLASSES + PACKAGE_CLASSES:
            self.assertIn("`%s`" % cls, table, "класс %s не объяснён" % cls)

    def test_no_empty_justifications(self):
        for line in COVERAGE.read_text(encoding="utf-8").split("\n"):
            if not line.startswith("| `"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            self.assertTrue(all(cells), "пустая клетка в строке: %s" % line)
