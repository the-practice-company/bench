import re
import unittest
from pathlib import Path

from scripts import check_frontmatter, check_links
from scripts.findings import FRONTMATTER_CLASSES, LINK_CLASSES, PACKAGE_CLASSES

ROOT = Path(__file__).resolve().parent.parent
COVERAGE = ROOT / "docs" / "gate-coverage.md"

CITATION = re.compile(r"`(tests/[A-Za-z0-9_./]+\.py)((?:::[A-Za-z0-9_]+)+)`")
NO_TEST = "нет проверки:"
# Число находок класса на битой фикстуре, заявленное строкой таблицы.
CLAIMED_COUNT = re.compile(r"битая фикстура, (\d+) находк")


def _rows(text):
    for line in text.split("\n"):
        if line.startswith("| `"):
            yield line, [c.strip() for c in line.strip("|").split("|")]


def _problems(text, root):
    """Строки таблицы, которые ничего не доказывают.

    Три формы негодности: не три столбца, пустая клетка, ссылка на тест,
    которого нет. Последняя — та, из-за которой критерий 4 держался
    наполовину: выдуманное имя теста и удаление настоящего проходили зелёными.
    """
    out = []
    for line, cells in _rows(text):
        if len(cells) != 3 or not all(cells):
            out.append("не три непустых столбца: %s" % line)
            continue
        citation = cells[2]
        if citation.startswith(NO_TEST):
            if not citation[len(NO_TEST):].strip():
                out.append("пустая причина отсутствия проверки: %s" % line)
            continue
        match = CITATION.fullmatch(citation)
        if match is None:
            out.append("ссылка не в форме `tests/файл.py::Класс::тест`: %s" % line)
            continue
        path = Path(root) / match.group(1)
        if not path.exists():
            out.append("нет файла %s: %s" % (match.group(1), line))
            continue
        source = path.read_text(encoding="utf-8")
        for symbol in [s for s in match.group(2).split("::") if s]:
            if symbol not in source:
                out.append("в %s нет %s: %s" % (match.group(1), symbol, line))
    return out


def _fixture_counts(root):
    """Сколько находок каждого класса гейты дают на битой фикстуре сейчас.

    Оба гейта в одном словаре: класс `unparseable` производят и гейт
    frontmatter, и проверка пакета, и строка таблицы называет класс, а не
    гейт. Проверка пакета на фикстуру не гоняется — фикстура не пакет, — и
    её вклад в эти числа нулевой.
    """
    broken = Path(root) / "fixtures" / "broken"
    counts = {}
    for report in (check_links.scan(broken), check_frontmatter.scan(broken)):
        for cls, number in report.counts().items():
            counts[cls] = counts.get(cls, 0) + number
    return counts


def _miscounts(text, counts):
    """Строки, чьё число находок разошлось с тем, что гейт даёт сейчас.

    Столбец «чем доказан» не проверялся ничем. На заведении этой проверки
    из чисел разошлось одно — `unresolved` держал 4 при пяти образцах в
    фикстуре, — но разошлось молча и неизвестно как давно. Строка таблицы
    покрытия существует ровно затем, чтобы утверждать, что класс доказан;
    утверждение, которое никто не сверяет, доказывает ровно столько же,
    сколько пустая клетка.

    **Чего эта проверка не видит: прозу.** Строка может верно назвать число
    и при этом описывать не тот механизм — «хеш фикстуры» там, где код
    хеширует весь корень. Такое ловит только читатель. Назвать остаток
    здесь дешевле, чем сделать вид, что таблица проверена целиком.
    """
    out = []
    for line, cells in _rows(text):
        if len(cells) < 2:
            continue
        match = CLAIMED_COUNT.search(cells[1])
        if match is None:
            continue
        cls = cells[0].strip("`")
        claimed, actual = int(match.group(1)), counts.get(cls, 0)
        if claimed != actual:
            out.append("%s: в таблице %d, гейт даёт %d" % (cls, claimed, actual))
    return out


class TestTableCountsMatchTheGates(unittest.TestCase):
    """Число в строке таблицы обязано совпадать с выводом гейта."""

    def test_the_real_table_counts_are_current(self):
        counts = _fixture_counts(ROOT)
        self.assertEqual(_miscounts(COVERAGE.read_text(encoding="utf-8"), counts), [])

    def test_a_stale_count_is_caught(self):
        counts = _fixture_counts(ROOT)
        row = ("| `unresolved` | битая фикстура, %d находки | "
               "`tests/test_fixtures.py::TestExactFindings::"
               "test_every_link_finding_sits_on_its_own_specimen` |"
               % (counts["unresolved"] + 1))
        self.assertEqual(len(_miscounts(row, counts)), 1)

    def test_a_current_count_passes(self):
        counts = _fixture_counts(ROOT)
        row = ("| `unresolved` | битая фикстура, %d находки | "
               "`tests/test_fixtures.py::TestExactFindings::"
               "test_every_link_finding_sits_on_its_own_specimen` |"
               % counts["unresolved"])
        self.assertEqual(_miscounts(row, counts), [])

    def test_a_count_for_a_class_the_fixture_never_produces_is_caught(self):
        """Класс, которого на фикстуре нет вовсе, — не «ноль находок», а ложь.

        Строка `absolute-path` доказана временным пакетом, а не фикстурой, и
        числа про фикстуру не заявляет. Заявила бы — обязана покраснеть.
        """
        row = ("| `absolute-path` | битая фикстура, 2 находки | "
               "`tests/test_check_package.py::TestPackageCheck::"
               "test_every_absolute_form_is_caught` |")
        self.assertEqual(len(_miscounts(row, _fixture_counts(ROOT))), 1)


class TestEveryClassIsProven(unittest.TestCase):
    """У каждого класса либо исполняемая проверка, либо записанная причина.

    Пустым оставить нельзя — это и есть механизм под «эффективность,
    а не маскарад»: нельзя молча сделать вид, что покрыто.
    """

    def test_coverage_table_lists_every_class(self):
        table = COVERAGE.read_text(encoding="utf-8")
        for cls in LINK_CLASSES + FRONTMATTER_CLASSES + PACKAGE_CLASSES:
            self.assertIn("`%s`" % cls, table, "класс %s не объяснён" % cls)

    def test_the_real_table_is_sound(self):
        self.assertEqual(_problems(COVERAGE.read_text(encoding="utf-8"), ROOT), [])


class TestTheTableCannotLie(unittest.TestCase):
    """Регрессия на критерий 4: таблица обязана отличать тест от имени."""

    _GOOD = ("| `orphan` | битая фикстура, 1 находка | "
             "`tests/test_fixtures.py::TestExactFindings::"
             "test_every_link_finding_sits_on_its_own_specimen` |")

    def test_a_sound_row_has_no_problems(self):
        self.assertEqual(_problems(self._GOOD, ROOT), [])

    def test_a_fabricated_test_name_is_caught(self):
        row = self._GOOD.replace("test_every_link_finding_sits_on_its_own_specimen",
                                 "test_this_never_existed")
        self.assertEqual(len(_problems(row, ROOT)), 1)

    def test_a_missing_test_file_is_caught(self):
        row = self._GOOD.replace("test_fixtures.py", "test_deleted.py")
        self.assertEqual(len(_problems(row, ROOT)), 1)

    def test_prose_instead_of_a_citation_is_caught(self):
        row = "| `orphan` | битая фикстура, 1 находка | покрыто тестами |"
        self.assertEqual(len(_problems(row, ROOT)), 1)

    def test_omitted_and_empty_cells_are_caught(self):
        self.assertEqual(len(_problems("| `orphan` |", ROOT)), 1)
        self.assertEqual(len(_problems("| `orphan` |  |  |", ROOT)), 1)

    def test_an_empty_reason_for_having_no_test_is_caught(self):
        row = "| `orphan` | нечем | нет проверки:  |"
        self.assertEqual(len(_problems(row, ROOT)), 1)

    def test_a_named_reason_for_having_no_test_passes(self):
        row = "| `orphan` | нечем | нет проверки: класс появится в волне 4 |"
        self.assertEqual(_problems(row, ROOT), [])
