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


class TestAmbiguous(unittest.TestCase):
    def test_two_candidates_make_a_warning_not_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("ambiguous"), 1)
        self.assertEqual(report.exit_code(), 2)  # из-за ошибок, не из-за ambiguous

    def test_matching_names_alone_are_not_a_finding(self):
        """Класс — про ссылку, которая резолвится в двух, а не про совпадение имён."""
        from scripts.check_links import scan
        report = scan(GREEN)
        self.assertNotIn("ambiguous", report.counts())


class TestAllowlist(unittest.TestCase):
    def test_line_without_reason_fails_the_gate(self):
        report = scan(BROKEN)
        self.assertGreaterEqual(report.counts().get("dead-allow", 0), 1)

    def test_dead_entry_fails_the_gate(self):
        from scripts.check_links import parse_allowlist
        entries = parse_allowlist("будущая\nстарая # причина\n")
        self.assertEqual([e.pattern for e in entries], ["будущая", "старая"])
        self.assertIsNone(entries[0].reason)
        self.assertEqual(entries[1].reason, "причина")


class TestOrphan(unittest.TestCase):
    def test_unreferenced_source_is_a_report_not_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("orphan"), 1)

    def test_orphan_does_not_change_the_exit_code_on_its_own(self):
        from scripts.findings import Finding, Report
        self.assertEqual(Report([Finding("orphan", "sources/a.md", 1, "x")]).exit_code(), 0)

    def test_records_outside_sources_and_registries_are_not_counted(self):
        report = scan(GREEN)
        self.assertNotIn("orphan", report.counts())
