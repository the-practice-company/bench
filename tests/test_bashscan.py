import unittest

from hooks import bashscan


class TestQuoteScanner(unittest.TestCase):
    """Посимвольный разбор кавычек: `mv` внутри строки — не команда."""

    def test_bare_mv_is_found(self):
        self.assertEqual(bashscan.commands('mv a.md b.md'), ["mv"])

    def test_mv_inside_single_quotes_is_not_a_command(self):
        self.assertEqual(bashscan.commands("echo 'mv a b'"), ["echo"])

    def test_mv_inside_double_quotes_is_not_a_command(self):
        self.assertEqual(bashscan.commands('echo "mv a b"'), ["echo"])

    def test_escaped_quote_does_not_end_the_string(self):
        self.assertEqual(bashscan.commands('echo "a\\" mv b"'), ["echo"])

    def test_command_after_separator_is_found(self):
        self.assertEqual(bashscan.commands("cd x && mv a b"), ["cd", "mv"])
        self.assertEqual(bashscan.commands("cd x; mv a b"), ["cd", "mv"])
        self.assertEqual(bashscan.commands("cat f | mv a b"), ["cat", "mv"])


class TestSegmentPaths(unittest.TestCase):
    """Сегментное сопоставление: `journal/` совпадает, `journaling/` нет."""

    def test_zone_prefix_matches_by_segment(self):
        self.assertTrue(bashscan.touches_zone("mv sources/a.md tmp/b.md",
                                              ("sources",)))

    def test_longer_name_with_same_prefix_does_not_match(self):
        self.assertFalse(bashscan.touches_zone("mv sourcesx/a.md tmp/b.md",
                                               ("sources",)))

    def test_leading_dot_slash_is_the_same_path(self):
        """`./sources/a.md` и `sources/a.md` — один путь и один ответ."""
        self.assertTrue(bashscan.touches_zone("mv ./sources/a.md tmp/b.md",
                                              ("sources",)))

    def test_trailing_slash_is_the_same_path(self):
        self.assertTrue(bashscan.touches_zone("ls sources/", ("sources",)))


class TestVerdict(unittest.TestCase):
    def test_bare_mv_is_blocked_and_names_the_right_way(self):
        verdict = bashscan.judge("mv areas/a.md areas/b.md")
        self.assertTrue(verdict.blocked)
        self.assertIn("move", verdict.reason)
        self.assertNotIn("`", verdict.reason,
                         "путь в backtick'ах сам поднял бы unresolved")

    def test_git_mv_is_blocked(self):
        self.assertTrue(bashscan.judge("git mv areas/a.md areas/b.md").blocked)

    def test_ordinary_command_passes(self):
        self.assertFalse(bashscan.judge("python3 -m unittest").blocked)

    def test_uncatchable_list_is_stated_not_implied(self):
        """Записанный остаточный риск отличает бэкстоп от притворной песочницы."""
        self.assertTrue(bashscan.UNCATCHABLE)
        for item in bashscan.UNCATCHABLE:
            self.assertTrue(item.strip())


class TestVerdictSaysWhatItIs(unittest.TestCase):
    """Секция 4 спеки волны 2: «защита от случайности, не от намерения, и так
    и написано в тексте отказа». Без этой строки пользователь читает отказ как
    песочницу и считает, что защищён там, где не защищён."""

    def _reasons(self):
        return [bashscan.judge("mv areas/a.md areas/b.md").reason,
                bashscan.judge("git mv areas/a.md areas/b.md").reason,
                bashscan.judge("echo привет > areas/a.md").reason]

    def test_every_refusal_calls_itself_a_backstop(self):
        for reason in self._reasons():
            self.assertIn("случайности", reason)
            self.assertIn("намерения", reason)

    def test_no_refusal_carries_a_backtick_path(self):
        """У контекстного репозитория нет своего `scripts/`: backtick-путь
        в тексте отказа сам поднял бы unresolved в гейте ссылок."""
        for reason in self._reasons():
            self.assertNotIn("`", reason)


class TestMoveHidesBehindOtherForms(unittest.TestCase):
    """Формы, в которых `mv` не первое слово строки. Каждая — не гипотеза:
    ровно так пишет команды агент, когда сначала переходит в каталог."""

    def test_git_mv_after_a_separator_is_blocked(self):
        self.assertTrue(bashscan.judge("cd areas && git mv a.md b.md").blocked)

    def test_git_mv_with_a_global_option_is_blocked(self):
        self.assertTrue(bashscan.judge("git -C areas mv a.md b.md").blocked)

    def test_absolute_path_to_mv_is_blocked(self):
        self.assertTrue(bashscan.judge("/bin/mv areas/a.md areas/b.md").blocked)

    def test_mv_in_a_subshell_is_blocked(self):
        self.assertTrue(bashscan.judge("(cd areas && mv a.md b.md)").blocked)

    def test_mv_in_a_command_substitution_is_blocked(self):
        self.assertTrue(bashscan.judge("echo $(mv areas/a.md areas/b.md)").blocked)

    def test_mv_behind_a_pass_through_wrapper_is_blocked(self):
        for line in ("sudo mv areas/a.md areas/b.md",
                     "env GIT_PAGER=cat mv areas/a.md areas/b.md",
                     "ls areas | xargs mv -t tmp"):
            self.assertTrue(bashscan.judge(line).blocked, line)

    def test_mv_inside_a_loop_body_is_blocked(self):
        """Пакетное переименование циклом — самый частый способ сломать разом
        все входящие ссылки, а не одну."""
        self.assertTrue(
            bashscan.judge('for f in areas/*.md; do mv "$f" tmp/; done').blocked)

    def test_backslash_before_the_name_is_the_same_command(self):
        """`\\mv` — идиома обхода алиаса, а не другая команда."""
        self.assertTrue(bashscan.judge("\\mv areas/a.md areas/b.md").blocked)

    def test_mv_in_a_backtick_substitution_is_blocked(self):
        self.assertTrue(bashscan.judge("`mv areas/a.md areas/b.md`").blocked)

    def test_wrapper_with_its_own_arguments_does_not_hide_mv(self):
        """У обёртки свои опции и числа; команда — первое, что не они."""
        for line in ("timeout 5 mv areas/a.md areas/b.md",
                     "nice -n 5 mv areas/a.md areas/b.md",
                     "ls areas | xargs -I {} mv {} tmp/"):
            self.assertTrue(bashscan.judge(line).blocked, line)

    def test_word_mv_as_an_argument_is_not_a_move(self):
        """Смотрим на голову сегмента, а не на любое вхождение слова."""
        for line in ("grep -rn mv areas/", "git commit -m 'mv areas'",
                     "git status", "python3 -m unittest tests.test_bashscan"):
            self.assertFalse(bashscan.judge(line).blocked, line)

    def test_asking_for_help_is_not_a_move(self):
        """Справка ничего не двигает. Ложный блок на безобидной команде учит
        обходить гейт — ровно то, ради чего сегментное сравнение и заведено."""
        for line in ("git mv --help", "mv --help"):
            self.assertFalse(bashscan.judge(line).blocked, line)


class TestDirectWriteIntoContent(unittest.TestCase):
    """Секция 4 спеки: блокируется ещё и «прямая запись в дерево контента
    в обход инструментов». Такая запись минует `PostToolUse` — гейты по файлу
    не отработают, и в списке файлов хода его не будет, поэтому `Stop` сочтёт
    поломку чужой и не заблокирует ход."""

    def test_redirection_into_a_long_lived_zone_is_blocked(self):
        for line in ("echo привет > areas/a.md", "cat x >> core/me.md",
                     "python3 s.py >core/report.md"):
            self.assertTrue(bashscan.judge(line).blocked, line)

    def test_redirection_names_the_path_it_refuses(self):
        self.assertIn("areas/a.md", bashscan.judge("echo x > areas/a.md").reason)

    def test_redirection_outside_the_content_tree_passes(self):
        for line in ("python3 -m unittest > tmp/out.txt",
                     "echo x > /tmp/report.txt", "python3 s.py 2>&1",
                     "git diff > diff.txt"):
            self.assertFalse(bashscan.judge(line).blocked, line)

    def test_zone_lookalike_is_not_the_content_tree(self):
        """Сравнение по сегменту и здесь: `areasx/` — не зона."""
        self.assertFalse(bashscan.judge("echo x > areasx/a.md").blocked)

    def test_redirection_inside_quotes_is_not_a_write(self):
        self.assertFalse(bashscan.judge("echo 'x > areas/a.md'").blocked)


class TestUncatchableIsHonest(unittest.TestCase):
    """Список неперехватываемого — обещание, а не украшение: каждая названная
    в нём форма обязана и правда проходить. Запись «не ловим», которую на самом
    деле ловим, так же вводит в заблуждение, как молчаливая заглушка."""

    def test_named_forms_really_do_pass(self):
        for line in ('eval "$cmd"', 'bash -c "mv areas/a.md areas/b.md"',
                     "python3 scripts/rename.py areas/a.md",
                     "cp areas/a.md /tmp/a.md",
                     "tee areas/a.md < x", "rm areas/a.md",
                     "sed -i '' s/x/y/ areas/a.md",
                     "sudo -u root mv areas/a.md areas/b.md",
                     "'mv' areas/a.md areas/b.md",
                     "find areas -name '*.md' -exec mv {} tmp/ \\;"):
            self.assertFalse(bashscan.judge(line).blocked, line)

    def test_the_list_names_every_form_the_test_above_lets_through(self):
        """Список и тест выше — одно утверждение с двух сторон. Форма, которая
        проходит, обязана быть названа; проверка держит их вместе по ключевым
        словам, чтобы вычеркнутая строка списка не осталась незамеченной."""
        text = " ".join(bashscan.UNCATCHABLE)
        for word in ("python", "eval", "bash -c", "rm", "cp", "tee", "sed -i",
                     "find -exec", "имя команды в кавычках", "значение опции"):
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
