import unittest
from pathlib import Path

from scripts import zones

ROOT = Path(__file__).resolve().parent.parent


class TestZones(unittest.TestCase):
    def test_eight_zones_on_two_axes(self):
        self.assertEqual(len(zones.ZONES), 8)
        self.assertEqual(set(zones.SEMANTIC), {"core", "areas", "projects", "knowledge"})
        self.assertEqual(set(zones.PIPELINE), {"inbox", "sources", "tmp", "decisions"})
        self.assertEqual(set(zones.SEMANTIC) & set(zones.PIPELINE), set())

    def test_transient_zones_are_the_ones_that_empty_by_construction(self):
        self.assertEqual(zones.TRANSIENT, frozenset({"tmp", "inbox"}))

    def test_zone_of_reads_first_segment_only(self):
        self.assertEqual(zones.zone_of("areas/hiring/notes.md"), "areas")
        self.assertEqual(zones.zone_of("sources/transcripts/items/a.md"), "sources")
        self.assertIsNone(zones.zone_of("README.md"))
        self.assertIsNone(zones.zone_of("docs/areas/thing.md"))

    def test_deny_patterns_close_foreign_git(self):
        self.assertIn("knowledge/*/**", zones.DENY_PATTERNS)


class TestSingleDefinition(unittest.TestCase):
    """Критерий выхода волны: второе определение восьми зон валит тест.

    Эвристика намеренно грубая — файл, перечисляющий шесть и более имён зон
    строковыми литералами, почти наверняка держит свою копию таблицы.
    Спека измерила цену обратного: три разошедшиеся таблицы зон в одном
    репозитории.
    """

    def test_no_second_zone_table_in_package(self):
        names = set(zones.ZONES)
        offenders = []
        for path in sorted(ROOT.glob("scripts/*.py")):
            if path.name == "zones.py":
                continue
            text = path.read_text(encoding="utf-8")
            hits = {n for n in names if f'"{n}"' in text or f"'{n}'" in text}
            if len(hits) >= 6:
                offenders.append(f"{path.name}: {sorted(hits)}")
        self.assertEqual(offenders, [], "второе определение зон — импортируй scripts.zones")
