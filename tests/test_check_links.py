import unittest
from pathlib import Path

from scripts.check_links import extract_links, scan

ROOT = Path(__file__).resolve().parent.parent
BROKEN = ROOT / "fixtures" / "broken"
GREEN = ROOT / "fixtures" / "green"


class TestExtraction(unittest.TestCase):
    def test_wikilink_shapes(self):
        text = "[[a]] [[b#заголовок]] [[c^блок]] [[d|алиас]] ![[e]]"
        self.assertEqual(
            [l.target for l in extract_links(text)], ["a", "b", "c", "d", "e"]
        )

    def test_code_blocks_are_cut_before_parsing(self):
        text = "```\n[[внутри кода]]\n```\n[[снаружи]]\n"
        self.assertEqual([l.target for l in extract_links(text)], ["снаружи"])

    def test_inline_code_is_cut_too(self):
        self.assertEqual([l.target for l in extract_links("`[[нет]]` [[да]]")],
                         ["да"])

    def test_line_numbers_are_one_based(self):
        links = extract_links("первая\n[[цель]]\n")
        self.assertEqual(links[0].line, 2)


class TestUnresolved(unittest.TestCase):
    def test_green_sample_is_silent(self):
        report = scan(GREEN)
        self.assertEqual(report.counts(), {})

    def test_broken_fixture_reports_unresolved(self):
        report = scan(BROKEN)
        self.assertGreaterEqual(report.counts().get("unresolved", 0), 1)
