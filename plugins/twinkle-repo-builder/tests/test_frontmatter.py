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
        text = "---\narchetype: pipeline\nvalues:\n  status: [open, decided, revisited]\n---\n"
        self.assertEqual(
            parse(text),
            {"archetype": "pipeline", "values": {"status": ["open", "decided", "revisited"]}},
        )

    def test_block_list_inside_the_nested_map(self):
        """Форма, которой Obsidian Properties пишет multi-value свойство.

        Докстрока модуля обещала и блочные списки, и вложенную мапу; их
        сочетание — ровно то, что писала панель Properties, — роняло разбор
        `элемент списка после скаляра`. Гейт эту ошибку глотал, и коллекция
        оставалась без словаря вовсе.
        """
        text = ("---\narchetype: pipeline\nvalues:\n  status:\n"
                "    - open\n    - decided\n    - revisited\n---\n")
        self.assertEqual(
            parse(text),
            {"archetype": "pipeline",
             "values": {"status": ["open", "decided", "revisited"]}},
        )

    def test_key_after_a_nested_block_list_returns_to_its_level(self):
        """Закрытие вложенного списка не теряет владельца.

        Разбор обязан вернуться и на уровень вложенной мапы, и на верхний:
        иначе форма выше разбирается, а следующее за ней поле уезжает не
        туда — тихо, потому что структура остаётся правдоподобной.
        """
        text = ("---\nvalues:\n  status:\n    - open\n  labels:\n    - срочно\n"
                "archetype: pipeline\n---\n")
        self.assertEqual(
            parse(text),
            {"values": {"status": ["open"], "labels": ["срочно"]},
             "archetype": "pipeline"},
        )

    def test_block_list_flush_with_its_key(self):
        """Отступ у блочного списка не обязателен, и ключ после него — ключ."""
        text = "---\ntags:\n- найм\n- продукт\nstatus: open\n---\n"
        self.assertEqual(parse(text), {"tags": ["найм", "продукт"], "status": "open"})

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

    def test_duplicate_key_raises_rather_than_last_wins(self):
        """Повторный ключ — тот самый молчаливый сброс состояния.

        Побеждала последняя строка, и первое значение исчезало без следа:
        `status: НЕТ-ТАКОГО` перед `status: open` уходил из-под словаря
        коллекции, потому что до гейта не доезжал вовсе.
        """
        text = "---\ntype: decision\nstatus: НЕТ-ТАКОГО\nstatus: open\n---\n"
        with self.assertRaises(FrontmatterError) as ctx:
            parse(text)
        self.assertEqual(ctx.exception.line, 4)
        self.assertIn("повторный ключ", str(ctx.exception))

    def test_duplicate_key_inside_the_nested_map_raises_too(self):
        text = "---\nvalues:\n  status: [open]\n  status: [decided]\n---\n"
        with self.assertRaises(FrontmatterError) as ctx:
            parse(text)
        self.assertEqual(ctx.exception.line, 4)

    def test_a_uniformly_indented_block_is_still_read(self):
        """Строгость к отступу не имеет права стать регрессией.

        Сдвинутый целиком блок — законный YAML, и разбирался он здесь
        всегда; ронять его вместе с потерянной вложенностью значит
        объявить нарушением то, что нарушением не было.
        """
        self.assertEqual(parse("---\n  type: note\n  status: open\n---\n"),
                         {"type": "note", "status": "open"})

    def test_key_indented_under_a_scalar_raises(self):
        """Отступ без владельца не приводится молча к верхнему уровню.

        `weird` уезжал в корневую мапу как обычное поле: структура на выходе
        оставалась правдоподобной, и об утраченной вложенности никто не знал.
        """
        text = "---\ntype: note\n  weird: x\n---\n"
        with self.assertRaises(FrontmatterError) as ctx:
            parse(text)
        self.assertEqual(ctx.exception.line, 3)
