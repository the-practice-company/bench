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
                bashscan.judge("echo привет > areas/a.md").reason,
                bashscan.judge("echo привет > knowledge/repo/a.md").reason,
                bashscan.judge("rm areas/a.md").reason,
                bashscan.judge("rm sources/интервью.md").reason]

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


class TestRedirectBeforeTheCommand(unittest.TestCase):
    """Перенаправление, стоящее перед командой, — не команда. Иначе головой
    сегмента оказывается оператор, и перемещение за ним проходит."""

    def test_leading_redirect_does_not_hide_the_command(self):
        for line in ("> tmp/log mv areas/a.md areas/b.md",
                     ">tmp/log mv areas/a.md areas/b.md",
                     "2>/dev/null mv areas/a.md areas/b.md",
                     "2>&1 mv areas/a.md areas/b.md"):
            self.assertTrue(bashscan.judge(line).blocked, line)

    def test_a_redirect_after_the_command_still_reads_the_command(self):
        self.assertTrue(bashscan.judge("mv areas/a.md areas/b.md > tmp/log").blocked)

    def test_an_ordinary_redirect_is_not_a_command(self):
        for line in ("echo привет > tmp/b", "python3 -m unittest 2>&1"):
            self.assertFalse(bashscan.judge(line).blocked, line)


class TestFindExec(unittest.TestCase):
    """`find … -exec mv` — настоящее пакетное перемещение: одной командой
    рушатся все входящие ссылки разом, а не одна. Зона берётся из аргументов
    самого find: цель у команды из `-exec` — то, что нашёл find, а не токен
    `{}`, который классифицировать нечем."""

    def test_move_through_exec_is_blocked(self):
        for line in ("find areas -name '*.md' -exec mv {} tmp/ \\;",
                     "find areas -name '*.md' -exec mv -t tmp/ {} +",
                     "find projects -type f -execdir mv {} tmp/ \\;"):
            self.assertTrue(bashscan.judge(line).blocked, line)

    def test_delete_through_exec_takes_the_zone_from_find_itself(self):
        self.assertTrue(bashscan.judge("find areas -type f -exec rm {} \\;").blocked)

    def test_exec_over_a_transient_zone_is_not_blocked(self):
        """`tmp` — стол: чистка там её назначение, а не поломка."""
        self.assertFalse(bashscan.judge("find tmp -type f -exec rm {} \\;").blocked)

    def test_an_innocent_exec_is_not_blocked(self):
        self.assertFalse(bashscan.judge("find areas -exec grep -l mv {} \\;").blocked)


class TestDeleteInsideTheContentTree(unittest.TestCase):
    """Удаление ломает входящие ссылки ровно так же, как перемещение: они
    остаются на пути, которого больше нет. Реакция по зонам разная, потому
    что удаление в них значит разное."""

    def test_delete_in_a_long_lived_zone_is_blocked(self):
        for line in ("rm areas/a.md", "rm -rf projects/старый",
                     "git rm core/me.md", "unlink knowledge/repo/a.md",
                     "cp areas/a.md /tmp/a.md && rm areas/a.md"):
            self.assertTrue(bashscan.judge(line).blocked, line)

    def test_delete_in_raw_sources_is_blocked_as_the_humans_operation(self):
        """Неизменяемость сырья держит доказуемость производного знания:
        удалённый задним числом источник делает недоказуемым каждый вывод,
        который на него ссылается. Хук блокирует агента, не человека."""
        verdict = bashscan.judge("rm sources/интервью.md")
        self.assertTrue(verdict.blocked)
        self.assertIn("человек", verdict.reason)

    def test_appending_to_raw_sources_is_blocked_too(self):
        """Правка сырья ломает доказуемость так же, как удаление, и ветка
        записи хука её уже блокирует. Разная реакция на одну поломку в двух
        ветках одного хука — расхождение, а не решение."""
        self.assertTrue(bashscan.judge("echo x >> sources/интервью.md").blocked)

    def test_delete_in_a_transient_zone_is_allowed(self):
        """Стол и приёмник чистят по назначению. Блок здесь был бы ложным."""
        for line in ("rm tmp/черновик.md", "rm -rf tmp/", "rm inbox/дамп.txt"):
            self.assertFalse(bashscan.judge(line).blocked, line)

    def test_delete_of_an_unclassifiable_path_is_allowed(self):
        """Путь, чью зону прочитать нечем, — не повод блокировать."""
        for line in ("rm build.log", "rm *.md", "rm -rf /tmp/сборка",
                     "rm", "rm -rf ../соседний-репозиторий"):
            self.assertFalse(bashscan.judge(line).blocked, line)

    def test_removing_an_empty_directory_is_not_a_broken_link(self):
        """`rmdir` сносит только пустой каталог, а на пустой каталог
        ссылаться нечему. Механизма без поломки не заводим."""
        self.assertFalse(bashscan.judge("rmdir areas/пустой").blocked)

    def test_the_long_lived_refusal_names_confirmation_not_a_script(self):
        """Спека даёт на удаление в долгоживущей зоне подтверждение автора,
        а не скрипт. Назвать несуществующий скрипт — тот же дефект, что
        назвать скрипт, делающий не то."""
        reason = bashscan.judge("rm areas/a.md").reason
        self.assertIn("find-refs", reason)
        self.assertIn("автор", reason)


class TestWritingIntoAReadOnlyZone(unittest.TestCase):
    """`knowledge` — чужие git-сабмодули: туда не пишут вообще. Совет
    «возьми Write» был бы советом сделать запрещённое."""

    def test_the_refusal_does_not_offer_the_editing_tool(self):
        reason = bashscan.judge("echo x > knowledge/repo/a.md").reason
        self.assertIn("сабмодул", reason)
        self.assertNotIn("Write", reason)

    def test_a_writable_zone_still_gets_the_editing_tool(self):
        self.assertIn("Write", bashscan.judge("echo x > areas/a.md").reason)


class TestHereDocBodyIsData(unittest.TestCase):
    """Тело here-doc — данные, а не команды. Строка `mv old.md new.md` внутри
    документа о том, как делать нельзя, — текст, и блокировать её значит
    запретить писать документацию про этот самый гейт."""

    def test_body_is_not_scanned_for_commands(self):
        for line in ("cat <<'EOF' > docs/note.md\nmv old.md new.md — нельзя\nEOF",
                     "python3 - <<'PY'\nmv = 1\nprint(mv)\nPY"):
            self.assertFalse(bashscan.judge(line).blocked, line)

    def test_writing_into_content_through_a_heredoc_is_still_blocked(self):
        """Гасится тело, а не команда: перенаправление на первой строке видно."""
        self.assertTrue(
            bashscan.judge("cat <<EOF > areas/a.md\nтекст\nEOF").blocked)

    def test_a_shift_inside_quotes_does_not_swallow_the_rest(self):
        """`<<` в кавычках — не ограничитель. Иначе погашенным оказался бы
        хвост команды, и перемещение за ним прошло бы незамеченным."""
        self.assertTrue(
            bashscan.judge('echo "x << y"\nmv areas/a.md areas/b.md').blocked)


class TestUncatchableIsHonest(unittest.TestCase):
    """Список неперехватываемого — обещание, а не украшение: каждая названная
    в нём форма обязана и правда проходить. Запись «не ловим», которую на самом
    деле ловим, так же вводит в заблуждение, как молчаливая заглушка."""

    def test_named_forms_really_do_pass(self):
        for line in ('eval "$cmd"', 'bash -c "mv areas/a.md areas/b.md"',
                     "python3 scripts/rename.py areas/a.md",
                     "cp areas/a.md areas/b.md",
                     "tee areas/a.md < x",
                     "sed -i '' s/x/y/ areas/a.md",
                     "sudo -u root mv areas/a.md areas/b.md",
                     "'mv' areas/a.md areas/b.md",
                     "M=mv; $M areas/a.md areas/b.md",
                     "busybox mv areas/a.md areas/b.md",
                     "rsync --remove-source-files areas/a.md tmp/",
                     "cd areas && rm a.md",
                     "echo x > /Users/кто-то/репозиторий/areas/a.md",
                     "sh <<EOF\nmv areas/a.md areas/b.md\nEOF"):
            self.assertFalse(bashscan.judge(line).blocked, line)

    def test_the_list_names_every_form_the_test_above_lets_through(self):
        """Список и тест выше — одно утверждение с двух сторон. Форма, которая
        проходит, обязана быть названа; проверка держит их вместе по ключевым
        словам, чтобы вычеркнутая строка списка не осталась незамеченной."""
        text = " ".join(bashscan.UNCATCHABLE)
        for word in ("python", "eval", "bash -c", "cp", "tee", "sed -i",
                     "имя команды в кавычках", "значение опции", "here-doc",
                     "переменной", "мультикоманд", "rsync", "текущий каталог",
                     "абсолютному пути", "функцию оболочки"):
            self.assertIn(word, text)

    def test_the_list_no_longer_names_what_the_scanner_now_catches(self):
        """Обратная сторона: строка «не ловим» про пойманное вводит
        в заблуждение ровно так же, как молчаливая заглушка."""
        text = " ".join(bashscan.UNCATCHABLE)
        for word in ("find -exec", "последующим rm"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
