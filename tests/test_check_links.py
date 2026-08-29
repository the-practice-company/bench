import unittest
from pathlib import Path

from scripts.check_links import extract_links, scan

ROOT = Path(__file__).resolve().parent.parent
BROKEN = ROOT / "fixtures" / "broken"
GREEN = ROOT / "fixtures" / "green"


class TestExtraction(unittest.TestCase):
    def test_wikilink_shapes(self):
        text = "[[a]] [[b#заголовок]] [[c^блок]] [[d|алиас]] ![[e]]"
        self.assertEqual(
            [l.target for l in extract_links(text)], ["a", "b", "c", "d", "e"]
        )

    def test_code_blocks_are_cut_before_parsing(self):
        text = "```\n[[внутри кода]]\n```\n[[снаружи]]\n"
        self.assertEqual([l.target for l in extract_links(text)], ["снаружи"])

    def test_inline_code_is_cut_too(self):
        self.assertEqual([l.target for l in extract_links("`[[нет]]` [[да]]")],
                         ["да"])

    def test_line_numbers_are_one_based(self):
        links = extract_links("первая\n[[цель]]\n")
        self.assertEqual(links[0].line, 2)


class TestUnresolved(unittest.TestCase):
    def test_green_sample_is_silent(self):
        report = scan(GREEN)
        self.assertEqual(report.counts(), {})

    def test_broken_fixture_reports_unresolved(self):
        report = scan(BROKEN)
        self.assertGreaterEqual(report.counts().get("unresolved", 0), 1)


class TestForbiddenShapes(unittest.TestCase):
    def test_markdown_link_to_local_file_is_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("md-link-to-file"), 1)

    def test_external_url_is_allowed(self):
        from scripts.check_links import classify_mdlink
        self.assertIsNone(classify_mdlink("https://example.com"))
        self.assertIsNone(classify_mdlink("mailto:a@b.c"))
        self.assertIsNone(classify_mdlink("#якорь"))
        self.assertEqual(classify_mdlink("../core/me.md"), "md-link-to-file")

    def test_link_from_long_lived_zone_into_transient_is_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("link-to-transient"), 1)

    def test_escaping_root_is_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("escapes-root"), 3)


class TestPerimeter(unittest.TestCase):
    def test_settings_json_paths_are_checked(self):
        import json, tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "settings.local.json").write_text(
                json.dumps({"hooks": {"cmd": ".claude/scripts/missing.sh"}}), encoding="utf-8")
            self.assertEqual(scan(root).counts().get("unresolved"), 1)

    def test_archive_is_outside_the_perimeter(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / "archive").mkdir()
            (root / "archive" / "old.md").write_text("[[в никуда]]\n", encoding="utf-8")
            self.assertEqual(scan(root).counts(), {})


class TestAmbiguous(unittest.TestCase):
    def test_two_candidates_make_a_warning_not_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("ambiguous"), 1)
        self.assertEqual(report.exit_code(), 2)  # из-за ошибок, не из-за ambiguous

    def test_matching_names_alone_are_not_a_finding(self):
        """Класс — про ссылку, которая резолвится в двух, а не про совпадение имён."""
        from scripts.check_links import scan
        report = scan(GREEN)
        self.assertNotIn("ambiguous", report.counts())


class TestAllowlist(unittest.TestCase):
    def test_line_without_reason_fails_the_gate(self):
        report = scan(BROKEN)
        self.assertGreaterEqual(report.counts().get("dead-allow", 0), 1)

    def test_dead_entry_fails_the_gate(self):
        from scripts.check_links import parse_allowlist
        entries = parse_allowlist("будущая\nстарая # причина\n")
        self.assertEqual([e.pattern for e in entries], ["будущая", "старая"])
        self.assertIsNone(entries[0].reason)
        self.assertEqual(entries[1].reason, "причина")


class TestIndexDedup(unittest.TestCase):
    def test_root_level_wikilink_target_is_not_falsely_ambiguous(self):
        """README.md — и basename, и относительный путь без расширения совпадают,
        а корень регистрирует один и тот же файл под этим ключом дважды."""
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / "README.md").write_text("корень\n", encoding="utf-8")
            (root / "core").mkdir()
            (root / "core" / "note.md").write_text("[[README]]\n", encoding="utf-8")
            report = scan(root)
            self.assertNotIn("ambiguous", report.counts())


class TestBacktickPerimeter(unittest.TestCase):
    """Периметр backtick-сканирования — таблица «Что проверяется» спеки.

    Backtick-токены читаются только в `CLAUDE.md`, `README.md`, `SKILL.md`
    и `.claude/rules/*.md`. Wikilink и markdown-ссылка — в любом `.md`:
    это первые две строки той же таблицы. Расширять сканирование
    backtick'ов за периметр запрещено (DEC-0003), чего бы это ни стоило
    счёту находок.
    """

    NOISE = "Домашний путь: `~/notes.md`, скрипта `scripts/net.py` нет.\n"

    def _root(self, tmp, rel, text):
        from pathlib import Path as P
        root = P(tmp)
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return root

    def test_backtick_tokens_outside_the_perimeter_are_not_read(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, "areas/hiring/note.md", self.NOISE)
            self.assertEqual(scan(root).counts(), {})

    def test_backtick_tokens_in_claude_md_are_read(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, "CLAUDE.md", self.NOISE)
            self.assertEqual(scan(root).counts(),
                             {"escapes-root": 1, "unresolved": 1})

    def test_backtick_tokens_in_rule_files_are_read(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, ".claude/rules/areas.md", self.NOISE)
            self.assertEqual(scan(root).counts(),
                             {"escapes-root": 1, "unresolved": 1})

    def test_wikilink_above_the_root_is_caught_in_any_md(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, "areas/hiring/note.md",
                              "Выше корня: [[../../../soseddniy-repo/file]]\n")
            self.assertEqual(scan(root).counts(), {"escapes-root": 1})

    def test_markdown_link_to_a_file_is_caught_in_any_md(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, "areas/hiring/note.md",
                              "Так нельзя: [профиль](../core/me.md)\n")
            self.assertEqual(scan(root).counts(), {"md-link-to-file": 1})


class TestBacktickTokenNoise(unittest.TestCase):
    def test_shell_commands_with_slashes_are_not_unresolved_in_canonical_files(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / "CLAUDE.md").write_text(
                "# Карта\n\n"
                "Агент ходит `grep -rn \"x\" areas/` и правит через `sed 's/a/b/'`.\n",
                encoding="utf-8",
            )
            self.assertEqual(scan(root).counts(), {})


class TestBacktickTokensInsideFences(unittest.TestCase):
    """Дефект 1: backtick-цикл не резал ```-блоки, хотя extract_links режет.

    Один и тот же пример внутри fenced-блока: wikilink в нём и так молчит
    (extract_links вырезает код первым), а соседний backtick-путь в том же
    блоке до фикса становился живым токеном — гейт противоречил сам себе
    насчёт того, где код является кодом.
    """

    def test_dangling_path_inside_a_fence_is_not_scanned(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / "CLAUDE.md").write_text(
                "# Пример\n\n"
                "Внутри примера и wikilink, и backtick-путь на несуществующее:\n\n"
                "```\n"
                "[[nonexistent/target]] и `docs/example-nonexistent.md`\n"
                "```\n",
                encoding="utf-8",
            )
            self.assertEqual(scan(root).counts(), {})

    def test_same_dangling_path_outside_the_fence_still_fires(self):
        """Контроль: фикс не глушит backtick-сканирование целиком, только fenced-блок."""
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / "CLAUDE.md").write_text(
                "# Пример\n\n"
                "Снаружи примера: `docs/example-nonexistent.md`\n",
                encoding="utf-8",
            )
            self.assertEqual(scan(root).counts(), {"unresolved": 1})


class TestGlobIsNotAPath(unittest.TestCase):
    """Блокер волны 3: каркас, предписанный спекой, не проходил гейт.

    `**/knowledge/**` в `claudeMdExcludes`, `Edit(./knowledge/*/**)` в
    `permissions.deny` (секция 4), `paths: **/items/**` и `**/*.base`
    в правилах зон (секция 9) — всё это гейт считал несуществующими
    путями и поднимал `unresolved` на каркасе, который сам же и предписан.
    Глоб называет множество: вопрос «есть ли такой файл» к нему неприменим.

    Снимается ровно этот вопрос. Граница корня остаётся: шаблон наружу —
    та же ошибка, что конкретный путь наружу.
    """

    def _root(self, tmp, rel, text):
        from pathlib import Path as P
        root = P(tmp)
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return root

    def test_glob_in_a_rule_file_is_not_unresolved(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, ".claude/rules/collection.md",
                              "---\n"
                              "description: Правило коллекций\n"
                              "paths: [\"**/items/**\"]\n"
                              "---\n"
                              "Записи коллекции лежат в `**/items/**`, "
                              "виды описаны в `**/*.base`.\n")
            self.assertEqual(scan(root).counts(), {})

    def test_settings_globs_and_permission_rules_are_not_unresolved(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(
                tmp, ".claude/settings.json",
                '{\n'
                '  "claudeMdExcludes": ["**/knowledge/**"],\n'
                '  "permissions": {\n'
                '    "deny": ["Edit(./knowledge/*/**)", "Write(./knowledge/*/**)"]\n'
                '  }\n'
                '}\n')
            self.assertEqual(scan(root).counts(), {})

    def test_a_glob_pointing_outside_the_root_is_still_an_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, "CLAUDE.md",
                              "Наружу шаблоном: `~/vault/**/*.md`.\n")
            self.assertEqual(scan(root).counts(), {"escapes-root": 1})

    def test_the_root_check_survives_the_tool_wrapper_too(self):
        """Разворачивание не должно превращаться в лазейку наружу."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(
                tmp, ".claude/settings.json",
                '{\n'
                '  "permissions": {\n'
                '    "deny": ["Edit(~/vault/**/*.md)"]\n'
                '  }\n'
                '}\n')
            report = scan(root)
            self.assertEqual(report.counts(), {"escapes-root": 1})
            self.assertEqual(report.render(),
                             ".claude/settings.json:3 escapes-root Edit(~/vault/**/*.md)")

    def test_a_concrete_missing_path_is_still_unresolved(self):
        """Контроль: ослабления нет, метасимволов в токене нет — проверка прежняя."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, ".claude/rules/areas.md",
                              "Записи кладутся в `areas/hiring/items/`.\n")
            self.assertEqual(scan(root).counts(), {"unresolved": 1})


class TestAllowlistCoversEveryUnresolvedSite(unittest.TestCase):
    """Дефект 2: аллоулист проверялся только там, где резолвится wikilink.

    Backtick-цикл и проверка settings.json поднимали unresolved, минуя
    allow-check, — запись аллоулиста, покрывающая такой путь, никогда не
    отмечалась использованной. Автор получал два противоречащих друг другу
    сообщения: неподавленный unresolved и dead-allow, требующий удалить то
    самое правило, которое должно было его погасить.
    """

    def test_allow_entry_suppresses_an_unresolved_backtick_token(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / ".claude" / "rules").mkdir(parents=True)
            (root / ".claude" / "rules" / "areas.md").write_text(
                "---\n"
                "description: Правило зоны areas\n"
                "paths: [\"areas/**\"]\n"
                "---\n"
                "Записи кладутся в `areas/hiring/items/`.\n",
                encoding="utf-8",
            )
            (root / ".link-allow").write_text(
                "areas/hiring/items/ # папка создаётся по ходу работы, ссылка опережает\n",
                encoding="utf-8",
            )
            self.assertEqual(scan(root).counts(), {})

    def test_allow_entry_suppresses_an_unresolved_settings_json_path(self):
        import json
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "settings.local.json").write_text(
                json.dumps({"hooks": {"cmd": ".claude/scripts/missing.sh"}}), encoding="utf-8")
            (root / ".link-allow").write_text(
                ".claude/scripts/missing.sh # хук ещё не написан\n", encoding="utf-8")
            self.assertEqual(scan(root).counts(), {})


class TestOrphan(unittest.TestCase):
    def test_unreferenced_source_is_a_report_not_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("orphan"), 1)

    def test_orphan_does_not_change_the_exit_code_on_its_own(self):
        from scripts.findings import Finding, Report
        self.assertEqual(Report([Finding("orphan", "sources/a.md", 1, "x")]).exit_code(), 0)

    def test_records_outside_sources_and_registries_are_not_counted(self):
        report = scan(GREEN)
        self.assertNotIn("orphan", report.counts())

    def test_bare_stem_match_elsewhere_does_not_silence_a_real_orphan(self):
        """Дефект 3: orphan гасился по голому stem файла где угодно в дереве.

        Ссылка на `core/notes/call.md` (полный путь, резолвится однозначно)
        не имеет отношения к `sources/calls/items/call.md`, но до фикса
        совпадение одного лишь basename «call» гасило сироту.
        """
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / "sources" / "calls" / "items").mkdir(parents=True)
            (root / "sources" / "calls" / "items" / "call.md").write_text(
                "нет входящих\n", encoding="utf-8")
            (root / "core" / "notes").mkdir(parents=True)
            (root / "core" / "notes" / "call.md").write_text(
                "другой файл с тем же именем\n", encoding="utf-8")
            (root / "core" / "hub.md").write_text(
                "[[core/notes/call]]\n", encoding="utf-8")
            report = scan(root)
            self.assertEqual(report.counts().get("orphan"), 1)

    def test_gitignored_subtree_is_outside_the_orphan_perimeter(self):
        """Дефект 4: периметр сирот не применял тот же .gitignore-фильтр,
        что оба главных цикла, поэтому файл из игнорируемого поддерева
        проверялся на сирот, хотя ссылки, которые могли бы его прикрыть,
        гейт там же никогда не читает."""
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / "sources" / "vendor" / "items").mkdir(parents=True)
            (root / ".gitignore").write_text("sources/vendor/\n", encoding="utf-8")
            (root / "sources" / "vendor" / "items" / "x.md").write_text(
                "контент из игнорируемого поддерева\n", encoding="utf-8")
            self.assertEqual(scan(root).counts(), {})
