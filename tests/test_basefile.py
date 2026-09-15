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

    def test_hasproperty_argument_is_a_property_not_the_function_name(self):
        """Review defect 1, bullet 1: file.hasProperty("X") -> X is a
        property, and "hasProperty" itself must never leak in as one."""
        text = (
            "filters:\n"
            "  and:\n"
            '    - file.inFolder("decisions/items")\n'
            '    - file.hasProperty("reviewed")\n'
            '    - status != "closed"\n'
        )
        base = parse_base(text)
        self.assertEqual(base.required, {"reviewed", "status"})
        self.assertNotIn("hasProperty", base.required)
        self.assertNotIn("closed", base.required)

    def test_bracket_access_names_a_property(self):
        """Review defect 1, bullet 2: note["X"] / file["X"] -> X is a
        property; "note" and "file" themselves are not."""
        text = (
            "filters:\n"
            "  and:\n"
            '    - note["priority"] == "high"\n'
            '    - file["status"] != "done"\n'
        )
        base = parse_base(text)
        self.assertEqual(base.required, {"priority", "status"})
        self.assertNotIn("note", base.required)
        self.assertNotIn("high", base.required)
        self.assertNotIn("done", base.required)

    def test_infolder_argument_never_becomes_a_property(self):
        """Review defect 1, bullet 3 (already true, kept honest by a test):
        the folder path is a folder, never a property."""
        text = (
            "filters:\n"
            "  and:\n"
            '    - file.inFolder("decisions/items")\n'
        )
        base = parse_base(text)
        self.assertEqual(base.folders, ["decisions/items"])
        self.assertEqual(base.required, set())

    def test_single_quoted_comparison_value_is_a_literal_not_a_property(self):
        """Review defect 1, bullet 4: quoted comparison operands are
        literal values, whichever quote character delimits them."""
        text = (
            "filters:\n"
            "  and:\n"
            "    - stage != 'done'\n"
        )
        base = parse_base(text)
        self.assertEqual(base.required, {"stage"})
        self.assertNotIn("done", base.required)

    def test_groupby_as_an_object_names_one_field_not_three(self):
        """Форма, которую Obsidian принимает: `property` и `direction` —
        ключи YAML, а не имена полей. Разобранные как поля, они требуют
        `property`, `direction` и `ASC` от каждой записи коллекции."""
        text = (
            "views:\n"
            "  - type: table\n"
            "    groupBy:\n"
            "      property: status\n"
            "      direction: ASC\n"
        )
        base = parse_base(text)
        self.assertEqual(base.required, {"status"})

    def test_groupby_as_a_flow_mapping_names_the_same_field(self):
        """Потоковая форма — тот же YAML в одну строку. Тихо потерять
        требование хуже, чем потребовать лишнее: гейт ослаб бы, выглядя
        рабочим."""
        text = (
            "views:\n"
            "  - type: table\n"
            "    groupBy: {property: status, direction: ASC}\n"
        )
        base = parse_base(text)
        self.assertEqual(base.required, {"status"})

    def test_sort_as_a_list_of_objects_names_the_sorted_field(self):
        """`sort` — тот же структурированный YAML, что и `groupBy`, только
        списком: поле берётся из `property`, а не из каждого идентификатора."""
        text = (
            "views:\n"
            "  - type: table\n"
            "    sort:\n"
            "      - property: created\n"
            "        direction: DESC\n"
        )
        base = parse_base(text)
        self.assertEqual(base.required, {"created"})
