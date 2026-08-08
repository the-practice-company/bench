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


class TestForbiddenShapes(unittest.TestCase):
    def test_markdown_link_to_local_file_is_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("md-link-to-file"), 1)

    def test_external_url_is_allowed(self):
        from scripts.check_links import classify_mdlink
        self.assertIsNone(classify_mdlink("https://example.com"))
        self.assertIsNone(classify_mdlink("mailto:a@b.c"))
        self.assertIsNone(classify_mdlink("#якорь"))
        self.assertEqual(classify_mdlink("../core/me.md"), "md-link-to-file")

    def test_link_from_long_lived_zone_into_transient_is_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("link-to-transient"), 1)

    def test_escaping_root_is_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("escapes-root"), 2)


class TestPerimeter(unittest.TestCase):
    def test_settings_json_paths_are_checked(self):
        import json, tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "settings.local.json").write_text(
                json.dumps({"hooks": {"cmd": ".claude/scripts/missing.sh"}}), encoding="utf-8")
            self.assertEqual(scan(root).counts().get("unresolved"), 1)

    def test_archive_is_outside_the_perimeter(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / "archive").mkdir()
            (root / "archive" / "old.md").write_text("[[в никуда]]\n", encoding="utf-8")
            self.assertEqual(scan(root).counts(), {})
