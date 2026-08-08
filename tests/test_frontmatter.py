import unittest

from scripts.frontmatter import FrontmatterError, parse


class TestParse(unittest.TestCase):
    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(parse("# Заголовок\n\nтекст\n"), {})

    def test_simple_scalars(self):
        text = "---\ntype: decision\nstatus: open\n---\n\nтело\n"
        self.assertEqual(parse(text), {"type": "decision", "status": "open"})

    def test_quoted_values_lose_their_quotes(self):
        text = '---\ncreated: "2026-07-14"\ndescription: \'а: б\'\n---\n'
        self.assertEqual(parse(text), {"created": "2026-07-14", "description": "а: б"})

    def test_flow_list_is_what_obsidian_properties_writes(self):
        text = "---\ntags: [найм, продукт]\n---\n"
        self.assertEqual(parse(text), {"tags": ["найм", "продукт"]})

    def test_block_list(self):
        text = "---\ntags:\n  - найм\n  - продукт\n---\n"
        self.assertEqual(parse(text), {"tags": ["найм", "продукт"]})

    def test_nested_map_is_how_values_are_declared(self):
        text = "---\narchetype: конвейер\nvalues:\n  status: [open, decided, revisited]\n---\n"
        self.assertEqual(
            parse(text),
            {"archetype": "конвейер", "values": {"status": ["open", "decided", "revisited"]}},
        )

    def test_empty_value_is_none_not_empty_string(self):
        self.assertEqual(parse("---\ncreated:\n---\n"), {"created": None})

    def test_comment_and_blank_lines_are_skipped(self):
        text = "---\n# комментарий\n\ntype: note\n---\n"
        self.assertEqual(parse(text), {"type": "note"})


class TestNeverGuesses(unittest.TestCase):
    def test_unclosed_frontmatter_raises_with_line(self):
        with self.assertRaises(FrontmatterError) as ctx:
            parse("---\ntype: note\n\nтело без закрытия\n")
        self.assertEqual(ctx.exception.line, 1)

    def test_block_scalar_raises_with_its_line(self):
        text = "---\ntype: note\nbody: |\n  многострочное\n---\n"
        with self.assertRaises(FrontmatterError) as ctx:
            parse(text)
        self.assertEqual(ctx.exception.line, 3)

    def test_tab_indent_raises_rather_than_being_normalised(self):
        text = "---\ntags:\n\t- a\n---\n"
        with self.assertRaises(FrontmatterError) as ctx:
            parse(text)
        self.assertEqual(ctx.exception.line, 3)

    def test_two_space_indent_is_not_required(self):
        """Существующий парсер в изученном аналоге требовал ровно двух пробелов
        и молча сбрасывал состояние на всём остальном. Здесь — любой отступ."""
        text = "---\ntags:\n    - a\n---\n"
        self.assertEqual(parse(text), {"tags": ["a"]})
