import unittest
from pathlib import Path

from scripts.check_frontmatter import scan

ROOT = Path(__file__).resolve().parent.parent
BROKEN = ROOT / "fixtures" / "broken"
GREEN = ROOT / "fixtures" / "green"


class TestContract(unittest.TestCase):
    def test_green_sample_is_silent(self):
        self.assertEqual(scan(GREEN).counts(), {})

    def test_missing_required_field(self):
        """Три: status у no-status.md плюс created у обеих разобравшихся записей.

        `created` требует стартовый набор секции 2, а не вид, — поэтому
        находка появляется и там, где вид поле не упоминает.
        """
        self.assertEqual(scan(BROKEN).counts().get("missing-required"), 3)

    def test_value_outside_vocabulary(self):
        self.assertEqual(scan(BROKEN).counts().get("value-outside-vocabulary"), 1)

    def test_unparseable_with_consumer_reports_the_line(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("unparseable"), 1)
        line = [f for f in report.findings if f.cls == "unparseable"][0]
        self.assertEqual(line.line, 4)

    def test_perimeter_is_records_of_collections_only(self):
        """core, папки документов и вложения не проверяются вовсе."""
        report = scan(BROKEN)
        touched = {f.path for f in report.findings}
        self.assertTrue(all(p.startswith("decisions/items/") for p in touched), touched)

    def test_field_with_no_consumer_is_silence(self):
        from scripts.check_frontmatter import check_record
        from scripts.basefile import parse_base
        base = parse_base('filters:\n  - file.inFolder("x")\n')
        fields = {"type": "note", "created": "2026-07-01", "случайное": 1}
        self.assertEqual(check_record("x/a.md", fields, base, {}), [])


if __name__ == "__main__":
    unittest.main()
