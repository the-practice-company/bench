import unittest

from scripts.paths import escapes_root, is_path_token, normalise


class TestPathToken(unittest.TestCase):
    def test_slash_makes_it_a_path(self):
        self.assertTrue(is_path_token("scripts/move.py"))
        self.assertTrue(is_path_token("areas/hiring/"))

    def test_known_extension_makes_it_a_path(self):
        self.assertTrue(is_path_token("hooks.json"))
        self.assertTrue(is_path_token("views.base"))
        self.assertTrue(is_path_token("SKILL.md"))

    def test_leading_slash_or_tilde_is_a_path_and_will_be_reported(self):
        self.assertTrue(is_path_token("/etc/hosts"))
        self.assertTrue(is_path_token("~/notes.md"))

    def test_bare_words_are_not_paths(self):
        for token in ("grep", "archetype", "status", "git", "mv"):
            self.assertFalse(is_path_token(token), token)

    def test_versions_and_durations_are_not_paths(self):
        """Закрытый список расширений, а не «есть точка»."""
        for token in ("0.05", "v1.2", "3.14", "0.05 с"):
            self.assertFalse(is_path_token(token), token)

    def test_bare_slash_tilde_and_dotdot_are_paths_by_the_table(self):
        """Таблица спеки не знает исключения для голого маркера.

        `/` и `~` — «начинается с `/` или `~` → путь, и сразу ошибка»,
        `../` — «содержит `/` → путь». Ужатие DEC-0003 откатано: в спеке
        для этих трёх токенов опоры нет.
        """
        for token in ("/", "~", "../"):
            self.assertTrue(is_path_token(token), token)

    def test_slash_command_with_arguments_is_not_a_path(self):
        """Отвергается пробелом, а не двоеточием: это командная строка."""
        self.assertFalse(is_path_token("/baton:auto 1"))

    def test_slash_command_without_arguments_is_a_path_by_the_table(self):
        """Оно же без аргумента — путь, начинающийся с `/`, и потому ошибка.

        Спеке этого мало не кажется: вопрос предъявлен автору (DEC-0003,
        «Invalidated if»). До ответа гейт ведёт себя так, как написано.
        """
        self.assertTrue(is_path_token("/baton:auto"))

    def test_api_route_with_param_is_a_path_by_the_table(self):
        """Содержит `/` — значит путь. Отдельной строки про `:` в таблице нет."""
        self.assertTrue(is_path_token("/backlinks/:path"))

    def test_delimited_regex_is_a_path_by_the_table(self):
        """Начинается с `/` — значит путь. Формы регулярки таблица не знает."""
        self.assertTrue(is_path_token("/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/"))

    def test_shell_command_with_a_slash_is_not_a_path(self):
        """Единственное ужатие, которое спека обосновывает сама.

        «Без признака гейт либо ругается на `grep`» — а `grep -rn "x" areas/`
        отличается от пути ровно пробелами.
        """
        for token in ('grep -rn "x" areas/', "sed 's/a/b/'"):
            self.assertFalse(is_path_token(token), token)


class TestRootBoundary(unittest.TestCase):
    def test_absolute_path_escapes(self):
        self.assertTrue(escapes_root("/etc/hosts", base="areas/hiring"))
        self.assertTrue(escapes_root("~/notes.md", base="areas"))

    def test_dotdot_above_root_escapes(self):
        self.assertTrue(escapes_root("../../outside.md", base="areas/hiring"))

    def test_dotdot_inside_root_is_fine(self):
        self.assertFalse(escapes_root("../core/me.md", base="areas/hiring"))

    def test_normalisation_happens_before_comparison(self):
        """Сравнение по префиксу строки ловится собственным `..`."""
        self.assertFalse(escapes_root("areas/../core/me.md", base=""))
        self.assertTrue(escapes_root("areas/../../x.md", base=""))

    def test_urls_are_not_paths_and_never_escape(self):
        for url in ("https://example.com", "mailto:a@b.c", "tel:+70000000000"):
            self.assertFalse(escapes_root(url, base="areas"))
