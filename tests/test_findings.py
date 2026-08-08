import unittest

from scripts.findings import EXIT_OK, EXIT_VIOLATION, Finding, Report


class TestFinding(unittest.TestCase):
    def test_link_gate_classes_are_closed(self):
        from scripts.findings import LINK_CLASSES
        self.assertEqual(
            set(LINK_CLASSES),
            {"unresolved", "md-link-to-file", "link-to-transient",
             "escapes-root", "dead-allow", "ambiguous", "orphan"},
        )

    def test_severity_is_a_property_of_the_class_not_the_caller(self):
        from scripts.findings import severity
        self.assertEqual(severity("unresolved"), "error")
        self.assertEqual(severity("escapes-root"), "error")
        self.assertEqual(severity("dead-allow"), "error")
        self.assertEqual(severity("ambiguous"), "warning")
        self.assertEqual(severity("orphan"), "report")


class TestReportDeterminism(unittest.TestCase):
    def test_same_findings_in_any_order_render_identically(self):
        a = Finding("unresolved", "areas/b.md", 12, "[[nope]]")
        b = Finding("md-link-to-file", "areas/a.md", 3, "[x](y.md)")
        self.assertEqual(Report([a, b]).render(), Report([b, a]).render())

    def test_render_has_no_absolute_paths(self):
        r = Report([Finding("unresolved", "areas/b.md", 12, "[[nope]]")]).render()
        self.assertNotIn("/Users/", r)
        self.assertTrue(r.startswith("areas/b.md:12"), r)

    def test_exit_code_is_violation_only_for_errors(self):
        self.assertEqual(Report([]).exit_code(), EXIT_OK)
        self.assertEqual(Report([Finding("ambiguous", "a.md", 1, "x")]).exit_code(), EXIT_OK)
        self.assertEqual(Report([Finding("orphan", "a.md", 1, "x")]).exit_code(), EXIT_OK)
        self.assertEqual(
            Report([Finding("unresolved", "a.md", 1, "x")]).exit_code(), EXIT_VIOLATION
        )

    def test_counts_by_class_are_what_tests_assert_against(self):
        r = Report([
            Finding("unresolved", "a.md", 1, "x"),
            Finding("unresolved", "b.md", 2, "y"),
            Finding("ambiguous", "c.md", 3, "z"),
        ])
        self.assertEqual(r.counts(), {"unresolved": 2, "ambiguous": 1})
