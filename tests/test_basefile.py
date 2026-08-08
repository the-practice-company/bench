import unittest

from scripts.basefile import parse_base

SAMPLE = """filters:
  and:
    - file.inFolder("decisions/items")
    - 'type == "decision"'
formulas:
  age: 'now() - created'
views:
  - type: table
    name: Все решения
    order:
      - status
      - description
    groupBy: status
    sort:
      - created
"""


class TestBaseFile(unittest.TestCase):
    def test_folders_come_from_infolder_calls(self):
        base = parse_base(SAMPLE)
        self.assertEqual(base.folders, ["decisions/items"])

    def test_required_properties_are_the_ones_that_decide_visibility(self):
        base = parse_base(SAMPLE)
        self.assertEqual(base.required, {"type", "status", "created"})

    def test_known_properties_are_display_only(self):
        base = parse_base(SAMPLE)
        self.assertEqual(base.known, {"description"})

    def test_formula_names_are_not_record_fields(self):
        """Потребовать `age` от каждой записи — ложная ошибка на всей коллекции."""
        base = parse_base(SAMPLE)
        self.assertNotIn("age", base.required)
        self.assertNotIn("age", base.known)
        self.assertEqual(base.formulas, {"age"})

    def test_fields_used_inside_a_formula_inherit_its_consumer(self):
        text = (
            "formulas:\n"
            "  stale: 'reviewed'\n"
            "views:\n"
            "  - type: table\n"
            "    groupBy: stale\n"
        )
        base = parse_base(text)
        self.assertIn("reviewed", base.required)
        self.assertNotIn("stale", base.required)

    def test_empty_base_is_not_an_error(self):
        base = parse_base("")
        self.assertEqual(base.folders, [])
        self.assertEqual(base.required, set())
