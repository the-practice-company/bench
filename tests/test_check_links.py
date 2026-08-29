import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_links
from scripts.check_links import extract_links, scan
from tests.test_fixtures import places

ROOT = Path(__file__).resolve().parent.parent
BROKEN = ROOT / "fixtures" / "broken"
GREEN = ROOT / "fixtures" / "green"


def _make(tmp, files):
    """Репозиторий из перечисленных файлов: {относительный путь: текст|байты}.

    Текст пишется в UTF-8, `bytes` — как есть: недекодируемый байт нужен
    ровно в том виде, в каком он приходит из чужого экспорта.
    """
    root = Path(tmp)
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
    return root


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


class TestTransientIsAboutTheTarget(unittest.TestCase):
    """Слепая зона 1: класс судился по тексту ссылки, а не по её цели.

    `[[scratch]]` — единственная форма, которую пишет Obsidian, — зоны
    в тексте не несёт вовсе (`zone_of("scratch")` это None), поэтому
    проверка молчала ровно там, где класс и нужен. Спека определяет
    `link-to-transient` через цель: ссылка из `core`/`areas`/`projects`/
    `knowledge` в `tmp/` или `inbox/` (секция 13).
    """

    def test_bare_wikilink_resolving_into_tmp_is_transient(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"tmp/scratch.md": "черновик\n",
                               "core/me.md": "см. [[scratch]]\n"})
            self.assertEqual(
                places(scan(root)),
                [("core/me.md", 1, "link-to-transient",
                  "[[scratch]] → tmp/scratch.md")])

    def test_the_path_form_still_fires(self):
        """Контроль: форма с зоной в тексте не потеряна."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"tmp/scratch.md": "черновик\n",
                               "core/me.md": "см. [[tmp/scratch]]\n"})
            self.assertEqual(
                places(scan(root)),
                [("core/me.md", 1, "link-to-transient",
                  "[[tmp/scratch]] → tmp/scratch.md")])

    def test_ambiguity_into_a_transient_zone_reports_both_facts(self):
        """Ссылка резолвится в два, и одно из двух — исчезающее.

        Два разных факта об одной ссылке, и починка у них разная:
        неоднозначность лечится полным путём, исчезающая цель — отказом
        ссылаться в `tmp/`. `ambiguous` — предупреждение, само по себе оно
        гейт не роняет; погасить им ошибку значило бы выпустить ссылку,
        которая по построению протухнет.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"projects/plan.md": "план\n",
                               "tmp/plan.md": "черновик плана\n",
                               "core/me.md": "см. [[plan]]\n"})
            self.assertEqual(
                places(scan(root)),
                [("core/me.md", 1, "ambiguous",
                  "[[plan]] → projects/plan.md, tmp/plan.md"),
                 ("core/me.md", 1, "link-to-transient",
                  "[[plan]] → tmp/plan.md")])

    def test_naming_a_transient_zone_that_does_not_resolve_stays_transient(self):
        """Текст называет `tmp/`, файла нет: класс прежний, не `unresolved`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/me.md": "см. [[tmp/ghost]]\n"})
            self.assertEqual(
                places(scan(root)),
                [("core/me.md", 1, "link-to-transient", "[[tmp/ghost]]")])

    def test_a_link_inside_the_transient_zone_is_not_a_finding(self):
        """Контроль: класс про источник в долгоживущей зоне, а не про `tmp/`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"tmp/a.md": "см. [[b]]\n", "tmp/b.md": "цель\n"})
            self.assertEqual(scan(root).counts(), {})


class TestUndecodableFileIsAFinding(unittest.TestCase):
    """Слепая зона 2, второй заход: замена байта сменила крах ложным обвинением.

    Первый фикс читал файл с `errors="replace"`, чтобы один байт не уносил
    весь отчёт. Крах он закрыл и открыл худшее. Замещающий знак стоит внутри
    текста ссылки и от имени цели ничем не отличается, поэтому гейт называл
    цель, которой никто не писал:

        `core/заметка.md` есть, `core/utf8.md` и `core/cp1251.md` несут
        дословно одну и ту же ссылку `[[заметка]]` в двух кодировках —
        и вторая давала `unresolved [[???????]]`.

    С другой стороны та же замена глотала файл целиком: `.md`, сохранённый
    в UTF-16, давал пустой отчёт — ни одной ссылки не видно, и это тоже
    молчание вместо ответа.

    Незыблемое №4 дословно: невосстановимое значение уходит в отчёт, а не
    подставляется тихо. Файл, который не декодируется, — находка про файл,
    и ссылки в нём не разбираются вовсе: чем они были, знать неоткуда.
    """

    CP1251 = "см. [[заметка]]\n".encode("cp1251")
    UTF16 = "см. [[заметка]]\n".encode("utf-16")

    def test_the_same_link_in_two_encodings_never_becomes_a_target_nobody_typed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/заметка.md": "цель\n",
                               "core/utf8.md": "см. [[заметка]]\n",
                               "core/cp1251.md": self.CP1251})
            self.assertEqual(
                places(scan(root)),
                [("core/cp1251.md", 1, "undecodable",
                  "не читается как UTF-8: байт 0xf1 в позиции 0, "
                  "ссылки в нём не проверены")])

    def test_a_utf16_file_is_named_instead_of_vanishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/me.md": self.UTF16})
            self.assertEqual(
                places(scan(root)),
                [("core/me.md", 1, "undecodable",
                  "не читается как UTF-8: байт 0xff в позиции 0, "
                  "ссылки в нём не проверены")])

    def test_the_backtick_perimeter_names_it_once_and_reads_no_tokens(self):
        """Оба прохода по `.md` встречают тот же файл — находка обязана быть одна."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"CLAUDE.md": "Скрипт `scripts/move.py`.\n".encode("cp1251")})
            self.assertEqual(
                places(scan(root)),
                [("CLAUDE.md", 1, "undecodable",
                  "не читается как UTF-8: байт 0xd1 в позиции 0, "
                  "ссылки в нём не проверены")])

    def test_a_neighbour_file_is_still_scanned(self):
        """Контроль: находка про один файл, а не про прогон."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/bad.md": self.CP1251,
                               "core/good.md": "[[nowhere]]\n"})
            self.assertEqual(
                places(scan(root)),
                [("core/bad.md", 1, "undecodable",
                  "не читается как UTF-8: байт 0xf1 в позиции 0, "
                  "ссылки в нём не проверены"),
                 ("core/good.md", 1, "unresolved", "[[nowhere]]")])

    def test_an_undecodable_settings_file_is_named_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".claude/settings.json":
                               '{"note": "заметка"}\n'.encode("cp1251")})
            self.assertEqual(
                places(scan(root)),
                [(".claude/settings.json", 1, "undecodable",
                  "не читается как UTF-8: байт 0xe7 в позиции 10, "
                  "пути в нём не проверены")])

    def test_an_undecodable_allowlist_is_named_too(self):
        """Аллоулист, который не прочитан, гасит не то, что думает автор."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "черновик # причина\n".encode("cp1251"),
                               "core/me.md": "[[черновик]]\n"})
            self.assertEqual(
                places(scan(root)),
                [(".link-allow", 1, "undecodable",
                  "не читается как UTF-8: байт 0xf7 в позиции 0, "
                  "записи аллоулиста не прочитаны"),
                 ("core/me.md", 1, "unresolved", "[[черновик]]")])

    def test_an_undecodable_gitignore_is_named_too(self):
        """Периметр, прочитанный с заменой, — это чужой периметр молча."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".gitignore": "черновики/\n".encode("cp1251"),
                               "core/me.md": "запись\n"})
            self.assertEqual(
                places(scan(root)),
                [(".gitignore", 1, "undecodable",
                  "не читается как UTF-8: байт 0xf7 в позиции 0, "
                  "периметр прочитан без него")])

    def test_exit_code_stays_inside_the_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/me.md": self.CP1251})
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check_links.py"), str(root)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("undecodable", result.stdout)


class TestGitignoreNegation(unittest.TestCase):
    """Слепая зона 3: `!`-строка выбрасывалась вместо применения.

    Игнорируемое множество оказывалось строго шире того, что репозиторий
    игнорирует на самом деле, — обратное тому, что обещает докстринг
    `_gitignore_prefixes`. Файл, который `.gitignore` возвращает в дерево,
    гейт не читал.
    """

    def test_a_negated_file_is_inside_the_perimeter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".gitignore": "build/\n!build/keep.md\n",
                               "build/keep.md": "[[nowhere]]\n",
                               "build/drop.md": "[[nowhere]]\n"})
            self.assertEqual(
                places(scan(root)),
                [("build/keep.md", 1, "unresolved", "[[nowhere]]")])

    def test_a_negated_glob_returns_a_whole_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".gitignore": "build/\n!build/*.md\n",
                               "build/keep.md": "[[nowhere]]\n"})
            self.assertEqual(
                places(scan(root)),
                [("build/keep.md", 1, "unresolved", "[[nowhere]]")])

    def test_without_the_negation_the_subtree_is_still_silent(self):
        """Контроль: отрицание не открыло игнорируемое поддерево целиком."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".gitignore": "build/\n",
                               "build/keep.md": "[[nowhere]]\n"})
            self.assertEqual(scan(root).counts(), {})


class TestReferenceStyleLinks(unittest.TestCase):
    """Слепая зона 4: определение ссылки-сноски обходило два класса.

    `_MDLINK` требует `](`, а `[out]: ../../../outside.md` — документированная
    форма markdown, дающая ту же самую цель. Мимо неё проходили и
    `escapes-root`, и `md-link-to-file`.
    """

    def test_a_definition_above_the_root_escapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/me.md":
                               "См. [файл][out].\n\n[out]: ../../../outside.md\n"})
            self.assertEqual(
                places(scan(root)),
                [("core/me.md", 3, "escapes-root", "[out]: ../../../outside.md")])

    def test_a_definition_pointing_at_a_local_file_is_the_same_class_as_inline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"areas/hiring/note.md":
                               "См. [профиль][me].\n\n[me]: ../../core/me.md\n",
                               "core/me.md": "я\n"})
            self.assertEqual(
                places(scan(root)),
                [("areas/hiring/note.md", 3, "md-link-to-file",
                  "[me]: ../../core/me.md")])

    def test_angle_brackets_do_not_hide_the_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/me.md": "[out]: <../../../outside.md>\n"})
            self.assertEqual(
                places(scan(root)),
                [("core/me.md", 1, "escapes-root", "[out]: <../../../outside.md>")])

    def test_a_definition_to_a_url_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/me.md":
                               "См. [сайт][s].\n\n[s]: https://example.com \"Пример\"\n"})
            self.assertEqual(scan(root).counts(), {})

    def test_prose_that_only_looks_like_a_definition_is_not_a_link(self):
        """Цель определения — один токен, а не фраза: `[1]: см. ниже` не ссылка."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/me.md": "[1]: см. ниже, в разделе про зоны\n"})
            self.assertEqual(scan(root).counts(), {})

    def test_a_footnote_is_not_a_link_definition(self):
        """`[^1]: Да` — примечание Obsidian: цели в нём нет, даже однословной."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"core/me.md": "Текст[^1].\n\n[^1]: Да\n"})
            self.assertEqual(scan(root).counts(), {})


class TestRegistryArchetype(unittest.TestCase):
    """Слепая зона 5: гейт ждал `archetype: реестр`, которого никто не пишет.

    Закрытый словарь спеки английский — `journal` / `pipeline` / `registry`
    (секции 9 и 28). Пока гейт сверялся с русским словом, периметр сирот
    у любой коллекции, созданной рецептом, был пуст, и класс `orphan`
    на живом выводе не мог сработать никогда.
    """

    README = "---\narchetype: registry\n---\n# Люди\n"

    def test_registry_items_without_incoming_links_are_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"people/README.md": self.README,
                               "people/items/ivan.md": "---\ntype: person\n---\nИван\n"})
            self.assertEqual(
                places(scan(root)),
                [("people/items/ivan.md", 1, "orphan", "на файл никто не сослался")])

    def test_a_referenced_registry_item_is_not_an_orphan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"people/README.md": self.README,
                               "people/items/ivan.md": "---\ntype: person\n---\nИван\n",
                               "core/hub.md": "[[people/items/ivan]]\n"})
            self.assertEqual(scan(root).counts(), {})


class TestAllowlistMatching(unittest.TestCase):
    """Слепая зона 6: запись аллоулиста была голой подстрокой.

    Одна буква гасила `unresolved` по всему репозиторию — и считалась
    использованной, поэтому `dead-allow` тоже молчал. Весь аргумент спеки
    за `dead-allow` в том, что уцелевшее исключение тихо ослабляет гейт;
    подстрока позволяла ослабить его везде, выглядя живой.
    """

    def test_a_one_character_entry_no_longer_swallows_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "a # причина\n",
                               "core/me.md": "[[nowhere-at-all]] и [[another-ghost]]\n"})
            self.assertEqual(
                places(scan(root)),
                [(".link-allow", 1, "dead-allow",
                  "правило ничего не исключает, удалите: a"),
                 ("core/me.md", 1, "unresolved", "[[another-ghost]]"),
                 ("core/me.md", 1, "unresolved", "[[nowhere-at-all]]")])

    def test_a_prefix_of_the_target_no_longer_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "nowhere # причина\n",
                               "core/me.md": "[[nowhere-at-all]]\n"})
            self.assertEqual(
                places(scan(root)),
                [(".link-allow", 1, "dead-allow",
                  "правило ничего не исключает, удалите: nowhere"),
                 ("core/me.md", 1, "unresolved", "[[nowhere-at-all]]")])

    def test_the_whole_target_still_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "nowhere-at-all # заметку вот-вот напишут\n",
                               "core/me.md": "[[nowhere-at-all]]\n"})
            self.assertEqual(scan(root).counts(), {})

    def test_a_glob_entry_covers_a_shape(self):
        """«Строка на паттерн» спеки: множество называется глобом, а не обрубком."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "черновики/* # раздел ещё не написан\n",
                               "core/me.md": "[[черновики/один]] и [[черновики/два]]\n"})
            self.assertEqual(scan(root).counts(), {})


class TestTokenExistenceIsCaseSensitive(unittest.TestCase):
    """Слепая зона 7: вердикт зависел от регистра файловой системы.

    `(root / token).exists()` на macOS отвечает «да» на `Scripts/Move.py`,
    на Linux — «нет». Резолв wikilink при этом всегда был регистрозависимым
    (поиск по словарю), то есть две половины одного гейта расходились между
    собой. Критерий 2 — про отчёт, не зависящий от места клона; здесь то же
    самое, только через платформу.
    """

    def test_a_token_differing_only_in_case_is_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"scripts/move.py": "# перенос\n",
                               "CLAUDE.md": "Скрипт `Scripts/Move.py`.\n"})
            self.assertEqual(
                places(scan(root)),
                [("CLAUDE.md", 1, "unresolved", "`Scripts/Move.py`")])

    def test_the_exact_case_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"scripts/move.py": "# перенос\n",
                               "CLAUDE.md": "Скрипт `scripts/move.py`.\n"})
            self.assertEqual(scan(root).counts(), {})

    def test_a_directory_token_resolves_by_its_exact_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"areas/hiring/note.md": "запись\n",
                               "CLAUDE.md": "Записи в `areas/hiring/`.\n"})
            self.assertEqual(scan(root).counts(), {})


class TestMultiBacktickSpan(unittest.TestCase):
    """Слепая зона 8: двойной backtick прятал токен от обоих проходов.

    ``` ``путь`` ``` — обычная форма markdown (ею оборачивают текст,
    в котором сам backtick и встречается). Регулярка «backtick, не-backtick,
    backtick» видела в ней две пустые вставки, поэтому backtick-проход терял
    токен целиком, а wikilink-проход, наоборот, переставал считать
    содержимое кодом и читал пример как живую ссылку.
    """

    def test_a_double_backtick_token_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"CLAUDE.md": "путь ``/Users/artem/secret.md`` тут\n"})
            self.assertEqual(
                places(scan(root)),
                [("CLAUDE.md", 1, "escapes-root", "`/Users/artem/secret.md`")])

    def test_a_double_backtick_span_still_hides_a_wikilink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"areas/hiring/note.md": "пример ``[[nowhere]]`` тут\n"})
            self.assertEqual(scan(root).counts(), {})

    def test_single_backticks_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {"CLAUDE.md":
                               "Агент ходит `grep`, скрипт — `scripts/move.py`.\n"})
            self.assertEqual(
                places(scan(root)),
                [("CLAUDE.md", 1, "unresolved", "`scripts/move.py`")])


class TestOverBroadAllowEntry(unittest.TestCase):
    """Слепая зона 6, второй заход: запрет подстроки обошли глоб-синтаксисом.

    Голую подстроку (`a`) запретили, и та же семантика вернулась в форме
    `*a*`, `*`, `?*`, `[a-z]*`: правило гасит `unresolved` по всему
    репозиторию и при этом считается использованным, поэтому `dead-allow`
    о нём молчит. Весь аргумент спеки за `dead-allow` в том, что уцелевшее
    исключение тихо ослабляет гейт; здесь ослабление везде и невидимо.

    Признак — наличие хотя бы одного целиком литерального сегмента пути.
    Правило без него не называет ни места, ни имени: подпасть под него
    может что угодно. Правило с ним место называет — и `черновики/*`
    остаётся законной «строкой на паттерн» (секция 13), как и было.
    """

    GHOSTS = "[[nowhere-at-all]] и [[another-ghost]]\n"

    def _findings(self, pattern):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "%s # причина\n" % pattern,
                               "core/me.md": self.GHOSTS})
            return places(scan(root))

    def test_a_substring_wearing_glob_syntax_is_over_broad(self):
        self.assertEqual(
            self._findings("*a*"),
            [(".link-allow", 1, "broad-allow",
              "правило не привязано ни к месту, ни к имени, сузьте: *a* "
              "(гасит: another-ghost, nowhere-at-all)")])

    def test_the_bare_star_is_over_broad(self):
        self.assertEqual(
            self._findings("*"),
            [(".link-allow", 1, "broad-allow",
              "правило не привязано ни к месту, ни к имени, сузьте: * "
              "(гасит: another-ghost, nowhere-at-all)")])

    def test_the_question_mark_spelling_is_over_broad(self):
        self.assertEqual(
            self._findings("?*"),
            [(".link-allow", 1, "broad-allow",
              "правило не привязано ни к месту, ни к имени, сузьте: ?* "
              "(гасит: another-ghost, nowhere-at-all)")])

    def test_a_character_class_spelling_is_over_broad(self):
        self.assertEqual(
            self._findings("[a-z]*"),
            [(".link-allow", 1, "broad-allow",
              "правило не привязано ни к месту, ни к имени, сузьте: [a-z]* "
              "(гасит: another-ghost, nowhere-at-all)")])

    def test_one_swallowed_target_is_enough(self):
        """Ждать второй цели незачем: правило уже гасит что угодно.

        Ровно это состояние опаснее двух: гейт зелен, автор считает его
        живым, а следующая мёртвая ссылка не покраснеет.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "* # причина\n",
                               "core/me.md": "[[nowhere-at-all]]\n"})
            self.assertEqual(
                places(scan(root)),
                [(".link-allow", 1, "broad-allow",
                  "правило не привязано ни к месту, ни к имени, сузьте: * "
                  "(гасит: nowhere-at-all)")])

    def test_an_anchored_glob_covering_a_shape_is_still_legal(self):
        """Контроль: «строка на паттерн» спеки не отменена.

        `черновики/*` называет место — раздел, которого ещё нет. Правило,
        сведённое к одной цели, не было бы паттерном вовсе, и секция 13
        перестала бы что-либо значить.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "черновики/* # раздел ещё не написан\n",
                               "core/me.md": "[[черновики/один]] и [[черновики/два]]\n"})
            self.assertEqual(scan(root).counts(), {})

    def test_a_glob_naming_a_file_rather_than_a_place_is_still_legal(self):
        """Литеральный сегмент не обязан быть первым: `*/README` называет имя."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "*/README # реестры ещё не заведены\n",
                               "core/me.md": "[[люди/README]] и [[места/README]]\n"})
            self.assertEqual(scan(root).counts(), {})

    def test_an_over_broad_entry_is_not_also_called_dead(self):
        """Два класса про одну строку противоречили бы друг другу.

        `dead-allow` утверждает «правило ничего не исключает». Про правило,
        погасившее две цели, это ложь — а ложное утверждение и есть то,
        что чинится в этом заходе.
        """
        self.assertEqual([f[2] for f in self._findings("*a*")], ["broad-allow"])

    def test_an_unanchored_entry_that_swallowed_nothing_is_dead_not_broad(self):
        """Контроль обратной стороны: не гасит ничего — прежний класс."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".link-allow": "*.md # причина\n",
                               "core/me.md": "запись без ссылок\n"})
            self.assertEqual(
                places(scan(root)),
                [(".link-allow", 1, "dead-allow",
                  "правило ничего не исключает, удалите: *.md")])


class TestGitignoredFileIsOutsideThePerimeter(unittest.TestCase):
    """Слепая зона 9: запись `.gitignore` про один файл становилась префиксом.

    `_ignored` дописывает косую каждой записи — верно для каталога и неверно
    для файла, а различить их по самому шаблону нечем. `.claude/
    settings.local.json` превращался в префикс `.claude/settings.local.json/`,
    не совпадающий ни с чем, и гейт читал файл, который репозиторий
    игнорирует. Последствие приезжает в каждый экземпляр, собранный
    рецептом: абсолютный путь в машинно-локальных настройках автора
    становится `escapes-root`.
    """

    LOCAL = '{"permissions": {"allow": ["Read(/Users/artem/notes.md)"]}}\n'

    def test_a_gitignored_settings_file_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".gitignore": ".claude/settings.local.json\n",
                               ".claude/settings.local.json": self.LOCAL})
            self.assertEqual(scan(root).counts(), {})

    def test_without_the_gitignore_entry_the_same_file_is_still_read(self):
        """Контроль: молчит запись, а не проверка."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".claude/settings.local.json": self.LOCAL})
            self.assertEqual(
                places(scan(root)),
                [(".claude/settings.local.json", 1, "escapes-root",
                  "Read(/Users/artem/notes.md)")])

    def test_a_gitignored_markdown_file_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".gitignore": "core/scratch.md\n",
                               "core/scratch.md": "[[nowhere]]\n"})
            self.assertEqual(scan(root).counts(), {})

    def test_the_subtree_form_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".gitignore": "build/\n",
                               "build/note.md": "[[nowhere]]\n"})
            self.assertEqual(scan(root).counts(), {})

    def test_a_gitignored_file_is_not_a_resolvable_target(self):
        """Периметр один: невидимый файл не должен гасить `unresolved`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make(tmp, {".gitignore": "core/scratch.md\n",
                               "core/scratch.md": "черновик\n",
                               "core/me.md": "[[scratch]]\n"})
            self.assertEqual(
                places(scan(root)),
                [("core/me.md", 1, "unresolved", "[[scratch]]")])


class TestPerimeterSplit(unittest.TestCase):
    """Разбор `.gitignore` и периметр гейта — две разные вещи.

    `archive/` вшит в периметр гейта секцией 13 и остаётся там. Инвентарь
    ADOPT обязан архив видеть, иначе он не может положить его в план — а
    положить обязан (§18: папки в дереве не остаётся). Сросшиеся, эти два
    множества дали бы инвентарь, слепой ровно к тому, ради чего заведён.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    def test_the_gate_perimeter_still_carries_archive(self):
        ignored = check_links._ignored(self.root)
        self.assertIn("archive/", tuple(ignored))
        self.assertIn("node_modules/", tuple(ignored))

    def test_the_gitignore_perimeter_does_not(self):
        ignored = check_links._gitignore_prefixes(self.root)
        self.assertNotIn("archive/", tuple(ignored))
        self.assertIn("node_modules/", tuple(ignored))
        self.assertIn(".git/", tuple(ignored))

    def test_the_undecodable_signal_survives_the_split(self):
        """Нечитаемый `.gitignore` не проглатывается ни одним из двух."""
        (self.root / ".gitignore").write_bytes(b"\xff\xfe node_modules/\n")
        self.assertIsNotNone(check_links._ignored(self.root).undecodable)
        self.assertIsNotNone(check_links._gitignore_prefixes(self.root).undecodable)

    def test_the_negations_ride_through_the_split(self):
        """Отрицание принадлежит `.gitignore`, а не гейту. Потеряв его на
        разделении, периметр гейта стал бы строго шире репозиторного — ровно
        та слепая зона 3, которую чинил `TestGitignoreNegation`."""
        (self.root / ".gitignore").write_text(
            "node_modules/\n!node_modules/keep.md\n", encoding="utf-8")
        self.assertEqual(check_links._gitignore_prefixes(self.root).negated,
                         ("node_modules/keep.md",))
        self.assertEqual(check_links._ignored(self.root).negated,
                         ("node_modules/keep.md",))
