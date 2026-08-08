import unittest
from pathlib import Path

from scripts.findings import FRONTMATTER_CLASSES, LINK_CLASSES, PACKAGE_CLASSES

ROOT = Path(__file__).resolve().parent.parent
COVERAGE = ROOT / "docs" / "gate-coverage.md"


def _cells(line):
    return [c.strip() for c in line.strip("|").split("|")]


def _row_is_complete(line):
    """Строка таблицы обязана нести ровно два столбца — класс и причину.

    Не «все присутствующие клетки непустые» (`all(cells)` пропускает строку,
    у которой пропал целый столбец: `strip("|").split("|")` на такой строке
    даёт список из одной, непустой, клетки, и `all` её принимает), а именно
    два столбца, и оба непустые.
    """
    cells = _cells(line)
    return len(cells) == 2 and all(cells)


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
            self.assertTrue(_row_is_complete(line), "неполная или пустая клетка в строке: %s" % line)

    def test_omitted_trailing_cell_is_caught(self):
        r"""Регрессия на дефект 3.

        `| \`orphan\` |  |` (клетка пустая, но присутствует) и раньше падал
        на `all(cells)`. `| \`orphan\` |` (столбец-причина пропал целиком)
        схлопывался в одну непустую клетку и проходил зелёным — естественный
        способ забыть причину. Обе формы обязаны быть невалидны.
        """
        self.assertFalse(_row_is_complete("| `orphan` |"))
        self.assertFalse(_row_is_complete("| `orphan` |  |"))
        self.assertTrue(_row_is_complete("| `orphan` | битая фикстура, 1 находка |"))
