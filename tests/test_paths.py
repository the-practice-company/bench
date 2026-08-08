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
