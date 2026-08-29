import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_package, zones
from scripts.check_package import check, check_read_only, _check_tests_touched_product
from scripts.findings import Finding

ROOT = Path(__file__).resolve().parent.parent


def places(report):
    """Находки как (путь, строка, класс, деталь) — та же форма, что в test_fixtures.

    Утверждается точный список: `assertIn("absolute-path", counts())` держится
    зелёным, даже когда находка села не на ту строку и показывает не тот текст.
    """
    return [(f.path, f.line, f.cls, f.detail)
            for f in sorted(report.findings, key=Finding.key)]


# Хук, который в самом деле что-то запускает. Запись с пустым списком хуков
# объявлена и инертна — ровно то, о чём теперь говорит проверка, — поэтому
# минимальный пакет держит настоящую команду, а не пустой список.
_COMMAND_HOOK = {"type": "command",
                 "command": "${CLAUDE_PLUGIN_ROOT}/hooks/hook.sh SessionStart"}


def _minimal_package(root):
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "x", "version": "0.1.0"}), encoding="utf-8")
    (root / "hooks").mkdir()
    (root / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [
            {"matcher": "*", "hooks": [_COMMAND_HOOK]}]}}),
        encoding="utf-8")
    skill = root / "skills" / "drain-inbox"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: drain-inbox\ndescription: Разбирает inbox\n---\n", encoding="utf-8")
    (skill / "eval.txt").write_text("разбери инбокс\ndrain the inbox\n", encoding="utf-8")
    return root


def _adopt_skill(root, line, name="adopt-context-repo"):
    """Скилл усыновления, инструкция — ровно на пятой строке SKILL.md.

    `exist_ok`: тем же помощником сажается образец и в `skills/drain-inbox`,
    который у минимального пакета уже есть. Второй такой же помощник ради
    одного флага был бы второй формой скилла в наборе.
    """
    skill = root / "skills" / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        "---\nname: %s\ndescription: x\n---\n%s\n" % (name, line), encoding="utf-8")
    (skill / "eval.txt").write_text("прими репозиторий\nadopt this repo\n",
                                    encoding="utf-8")
    return "skills/%s/SKILL.md" % name


class TestPackageCheck(unittest.TestCase):
    def test_minimal_package_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            self.assertEqual(check(root).counts(), {})

    def test_unknown_hook_event_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"OnFullMoon": [{"matcher": "*", "hooks": []}]}}),
                encoding="utf-8")
            self.assertIn("unknown-hook-event", check(root).counts())

    def test_unknown_hook_type_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"SessionStart": [
                    {"matcher": "*", "hooks": [{"type": "script"}]}
                ]}}), encoding="utf-8")
            self.assertIn("unknown-hook-type", check(root).counts())

    def test_unknown_matcher_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"SessionStart": [
                    {"matcher": "Bash(rm)", "hooks": []}
                ]}}), encoding="utf-8")
            self.assertIn("unknown-matcher", check(root).counts())

    def test_matcher_typo_is_caught(self):
        """Критерий 3: матчер вне закрытого множества обязан валить проверку.

        `Bahs` — опечатка в `Bash`. Проверкой формы она проходила зелёной.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"PreToolUse": [
                    {"matcher": "Bahs", "hooks": []}
                ]}}), encoding="utf-8")
            self.assertIn("unknown-matcher", check(root).counts())

    def test_known_matcher_forms_pass(self):
        for matcher in ("*", "Bash", "Edit|Write"):
            with self.subTest(matcher=matcher), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "hooks" / "hooks.json").write_text(
                    json.dumps({"hooks": {"PreToolUse": [
                        {"matcher": matcher, "hooks": []}
                    ]}}), encoding="utf-8")
                self.assertNotIn("unknown-matcher", check(root).counts())

    def test_the_empty_matcher_is_the_documented_everything_form(self):
        """Пустой матчер — законная запись для событий без инструментов.

        Разбор ронял её на ровном месте: `"".split("|")` даёт `[""]`, пустой
        строки в `TOOL_NAMES` нет, и `{"matcher": ""}` объявлялся
        `unknown-matcher`. Это дефект разбора, а не вопрос о составе
        закрытого множества инструментов.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"SessionStart": [
                    {"matcher": "", "hooks": [_COMMAND_HOOK]}
                ]}}), encoding="utf-8")
            self.assertEqual(places(check(root)), [])

    def test_an_empty_member_of_an_alternation_is_still_unknown(self):
        """Пустая строка законна как весь матчер и незаконна внутри `|`.

        `Edit|` — опечатка, а не форма «совпадает со всем»: послабление для
        пустого матчера обязано остаться ровно на одном значении.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"PreToolUse": [
                    {"matcher": "Edit|", "hooks": [_COMMAND_HOOK]}
                ]}}), encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("hooks/hooks.json", 1, "unknown-matcher", "Edit|")])

    def test_alternation_with_one_bad_member_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"PreToolUse": [
                    {"matcher": "Edit|Wrote", "hooks": []}
                ]}}), encoding="utf-8")
            self.assertIn("unknown-matcher", check(root).counts())

    def test_absolute_path_anywhere_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: drain-inbox\ndescription: x\n---\nЗовёт /Users/artem/x.py\n",
                encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("skills/drain-inbox/SKILL.md", 5, "absolute-path",
                  "Зовёт /Users/artem/x.py")])

    def test_every_absolute_form_is_caught(self):
        """Критерий 3: пять префиксов оставляли зелёными шесть форм.

        Второй ряд — корни, которых список не знал вовсе: каждый абсолютен
        и верен ровно на одной машине, а `/bin/` из них ещё и делал
        невидимым shebang с захардкоженным интерпретатором.
        """
        forms = [
            "/Users/artem/x.py", "/home/artem/x.py", "/tmp/scratch/x.py",
            "/var/log/x.txt", "/usr/local/bin/tool", "/Volumes/disk/x.md",
            "/private/tmp/x.py", "~/notes/x.md", "C:\\Users\\artem\\x.py",
            "D:/data/x.py", "\\\\server\\share\\x.py",
            "/bin/sh", "/sbin/init", "/dev/null", "/sys/class/net",
            "/proc/1/cwd", "/run/user/501", "/lib/x.so", "/lib64/ld.so",
            "/boot/vmlinuz", "/snap/bin/tool", "/nix/store/hash-x",
            "/cores/core.1", "/Network/Servers/x", "~artem/notes/x.md",
        ]
        for form in forms:
            with self.subTest(form=form):
                self.assertIsNotNone(
                    check_package.ABSOLUTE.search("Зовёт %s отсюда" % form), form)

    def test_relative_and_route_like_tokens_are_not_absolute(self):
        """Ложные срабатывания, ради которых периметр уже откатывали.

        Последние три — цена новых корней: имя каталога, совпавшее с
        корнем, остаётся относительной ссылкой, пока перед ним нет косой,
        не приклеенной к слову или точке.
        """
        for token in ("scripts/x.py", "../core/me.md", "/backlinks/:path",
                      "/twinkle:auto 1", "http://example.com/x",
                      "dev/mutate.py", "tools/dev/mutate.py",
                      "http://example.com/lib/x"):
            with self.subTest(token=token):
                self.assertIsNone(check_package.ABSOLUTE.search(token), token)

    def test_a_shebang_is_not_an_absolute_path_finding(self):
        """Строка 1 вида `#!...` — директива ядра, а не путь в прозе.

        Ядро требует абсолютный путь интерпретатора, относительной формы
        не существует, а `env` из `/usr/bin/` верен на каждой POSIX-машине —
        то есть ровно обратное тому, ради чего класс заведён.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "tool.py").write_text(
                "#!/usr/bin/env python3\nprint(1)\n", encoding="utf-8")
            self.assertEqual(check(root).counts(), {})

    def test_an_absolute_path_below_the_shebang_is_still_caught(self):
        """Исключение — ровно первая строка, и ни одной больше."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "tool.py").write_text(
                "#!/usr/bin/env python3\nPATH = \"/usr/local/bin/tool\"\n",
                encoding="utf-8")
            self.assertIn("absolute-path", check(root).counts())

    def test_a_shebang_like_line_further_down_is_still_caught(self):
        """`#!` спасает только на первой строке, иначе это дыра."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "tool.py").write_text(
                "# заметка\n#!/usr/bin/env python3\n", encoding="utf-8")
            self.assertIn("absolute-path", check(root).counts())

    def test_a_hardcoded_interpreter_shebang_is_still_caught(self):
        """Исключение — ровно для `env`, а не для любой первой строки с `#!`.

        Захардкоженный интерпретатор в shebang — та самая машинная
        зависимость, ради которой класс заведён: на чужой машине, где
        интерпретатор лежит в другом месте, такой путь не существует.
        Исключать надо портируемую форму, а не форму вообще.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "tool.py").write_text(
                "#!/usr/bin/python3\nprint(1)\n", encoding="utf-8")
            self.assertIn("absolute-path", check(root).counts())

    def test_a_posix_shell_shebang_is_portable(self):
        """`#!` + POSIX-шелл — вторая портируемая форма, а не находка.

        Корня `/bin/` детектор не знал вовсе, и `#!/bin/sh` проходил зелёным
        не потому, что портируем, а потому что был невидим. Стоило корень
        добавить — и первая строка собственного `./check` этого репозитория
        стала бы находкой. Портируемых форм ровно две: шелл, гарантированный
        стандартом по этому пути, и `env` из стандартного каталога.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "run.sh").write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
            self.assertEqual(places(check(root)), [])

    def test_a_bash_shebang_is_still_caught(self):
        """`bash` по этому пути не гарантирован никем.

        На NixOS его там нет, на macOS это другая сборка. Портируемость
        `/bin/sh` даёт стандарт, а не каталог, — на соседа по каталогу она
        не распространяется.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "run.sh").write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("run.sh", 1, "absolute-path", "#!/bin/bash")])

    def test_an_absolute_path_in_shebang_arguments_is_caught(self):
        """Исключение снимает токен, а не всю строку.

        `env -S` — портируемая форма, и она же несёт произвольную команду с
        аргументами. Исключая строку целиком, гейт слеп ровно к тому месту,
        куда абсолютный путь и попадает.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            line = "#!/usr/bin/env -S python3 -c \"p='/Users/artem/lib'\""
            (root / "tool.py").write_text(line + "\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("tool.py", 1, "absolute-path", line)])

    def test_a_comment_after_a_portable_shebang_is_scanned(self):
        """Хвост первой строки — обычный текст, а не часть директивы ядра."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            line = "#!/usr/bin/env python3  # см. /Users/artem/notes.md"
            (root / "tool.py").write_text(line + "\nprint(1)\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("tool.py", 1, "absolute-path", line)])

    def test_an_undecodable_byte_does_not_remove_the_file_from_the_scan(self):
        """Один байт вне UTF-8 уводил весь файл из-под гейта.

        `UnicodeDecodeError` ловился и файл пропускался целиком: спрятать
        абсолютный путь от проверки стоило одной правки в один байт. Чтение
        с заменой делает невосстановимым ровно этот байт, а не файл, —
        незыблемое №4 запрещает молча терять остальное.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "n.sh").write_bytes(
                "# caf\xe9 ".encode("latin-1") + b"/Users/artem/secret\n")
            self.assertEqual(
                places(check(root)),
                [("hooks/n.sh", 1, "absolute-path", "# caf\ufffd /Users/artem/secret")])

    def test_compiled_bytecode_is_not_scanned(self):
        """`__pycache__` глубже первого сегмента — тоже не файлы пакета.

        Байт-код не входит в пакет и не пишется руками, зато после свёртки
        констант содержит ровно те абсолютные префиксы, которые в исходнике
        собраны из фрагментов. Пока такой файл не декодировался, он
        отсеивался сам собой; чтение с заменой сделало его видимым, и
        `scripts/__pycache__/check_package.*.pyc` покраснел первым же
        прогоном на собственном репозитории.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            cache = root / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "x.cpython-314.pyc").write_bytes(b"\xa7\x00/Users/artem/x.py\n")
            self.assertEqual(places(check(root)), [])

    def test_single_letter_uri_schemes_are_not_drive_letters(self):
        """Ложные срабатывания ветки буквы диска, ставшие достижимыми.

        Скан пошёл по всем текстовым файлам, а не по списку расширений, и
        ветка `[A-Za-z]:[\\\\/]` начала ловить схему URI из одной буквы и
        тернарник минифицированного JS.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "app.js").write_text(
                "url s://host\na?b:/re/.test(s)\n", encoding="utf-8")
            self.assertEqual(places(check(root)), [])

    def test_windows_drive_paths_are_still_caught(self):
        """Обе формы разделителя остаются находкой."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "notes.md").write_text("C:/x\nC:\\x\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("notes.md", 1, "absolute-path", "C:/x"),
                 ("notes.md", 2, "absolute-path", "C:\\x")])

    def test_an_octal_escape_run_is_not_a_unc_server(self):
        r"""Ветка UNC ищет имя сервера, а сплошные цифры — не имя.

        Проза про octal-escape'ы вывода git (`"areas/\\321\\204.md"`)
        совпадала с формой `\\сервер\` и красила собственный репозиторий:
        находка `absolute-path` утверждала, что в строке абсолютный путь,
        которого там нет.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "note.py").write_text(
                r'# git отдаёт путь как "areas/\\321\\204.md"' + "\n",
                encoding="utf-8")
            self.assertEqual(places(check(root)), [])

    def test_a_real_unc_path_is_still_absolute(self):
        r"""Цена сужения — ноль живых форм.

        Имя хоста, IP-адрес (точка нецифровая) и запись через удвоенную
        обратную косую внутри строкового литерала остаются находкой.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "notes.md").write_text(
                r"Смотри \\server\share\x.py" + "\n"
                + r"Смотри \\192.168.1.1\share\x.py" + "\n",
                encoding="utf-8")
            (root / "conf.py").write_text(
                r'P = "\\\\server\\share"' + "\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("conf.py", 1, "absolute-path", r'P = "\\\\server\\share"'),
                 ("notes.md", 1, "absolute-path", r"Смотри \\server\share\x.py"),
                 ("notes.md", 2, "absolute-path",
                  r"Смотри \\192.168.1.1\share\x.py")])

    def test_a_home_of_another_user_is_absolute_too(self):
        """`~user/` — та же машинная зависимость, что и `~/`, и она была зелёной."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "notes.md").write_text("Смотри ~artem/x.md\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("notes.md", 1, "absolute-path", "Смотри ~artem/x.md")])

    def test_skill_without_description_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: drain-inbox\n---\n", encoding="utf-8")
            self.assertIn("skill-without-description", check(root).counts())

    def test_skill_without_trigger_eval_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "eval.txt").unlink()
            self.assertIn("skill-without-eval", check(root).counts())

    def test_relative_script_call_in_a_skill_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: drain-inbox\ndescription: x\n---\n"
                "Запусти `python3 scripts/drain.py`\n", encoding="utf-8")
            self.assertIn("relative-path-in-skill", check(root).counts())

    def test_plugin_root_variable_is_the_allowed_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: drain-inbox\ndescription: x\n---\n"
                'Запусти `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/drain.py"`\n',
                encoding="utf-8")
            self.assertNotIn("relative-path-in-skill", check(root).counts())

    def test_destructive_example_in_adopt_instructions_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            adopt = root / "skills" / "adopt-context-repo"
            adopt.mkdir(parents=True)
            (adopt / "SKILL.md").write_text(
                "---\nname: adopt-context-repo\ndescription: x\n---\n"
                "Переложи так: mv journal areas/journal\n", encoding="utf-8")
            (adopt / "eval.txt").write_text("прими репозиторий\nadopt this repo\n",
                                            encoding="utf-8")
            self.assertIn("destructive-example", check(root).counts())

    def test_skill_name_must_match_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: другое-имя\ndescription: x\n---\n", encoding="utf-8")
            self.assertIn("skill-name-mismatch", check(root).counts())

    def test_malformed_hooks_json_does_not_swallow_other_findings(self):
        """Дефект 5: непойманный json.loads ронял всю проверку одной находкой.

        Битый hooks/hooks.json обязан стать находкой сам, а не оборвать
        разбор — остальные находки пакета (здесь: skill-name-mismatch)
        обязаны остаться в отчёте.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text("{не валидный json", encoding="utf-8")
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: другое-имя\ndescription: x\n---\n", encoding="utf-8")
            counts = check(root).counts()
            self.assertIn("unparseable", counts)
            self.assertIn("skill-name-mismatch", counts)

    def test_extensionless_and_yaml_files_are_scanned(self):
        """Критерий 3: фильтр по расширению уводил из-под скана целые форматы.

        Список находок точный, и в нём назван каждый файл. С `assertIn` тест
        держался зелёным, когда `Makefile` не сканировался вовсе: находку
        поднимал любой другой файл пакета, и утверждение «что-то нашлось»
        выполнялось при полностью выключенной проверяемой возможности.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "Makefile").write_text(
                "run:\n\tpython3 /Users/artem/x.py\n", encoding="utf-8")
            (root / "config.yaml").write_text(
                "path: /Users/artem/x.yaml\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("Makefile", 2, "absolute-path", "python3 /Users/artem/x.py"),
                 ("config.yaml", 1, "absolute-path", "path: /Users/artem/x.yaml")])

    def test_a_package_dir_named_like_a_zone_is_still_scanned(self):
        """Восемь имён зон в списке пропуска снимали со скана целые поддеревья.

        `core/` — не чужое содержимое, а содержимое пакета: каталог с таким
        именем в корне сканируется наравне с остальными.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            core = root / "core"
            core.mkdir()
            (core / "notes.md").write_text("Смотри /Users/artem/x.md\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("core/notes.md", 1, "absolute-path", "Смотри /Users/artem/x.md")])

    def test_binary_files_do_not_break_the_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
            self.assertEqual(places(check(root)), [])

    def test_the_claude_directory_is_package_content(self):
        """`.claude` в списке пропуска снимал со скана два живых периметра.

        Регрессия была тихой: имя добавили без теста и без названной поломки,
        а `.claude/rules/*.md` гейт ссылок читает по имени, и битая фикстура
        держит там свой образец. Обе строки уходили из проверки пакета
        целиком: тот же вход давал `absolute-path` до правки и тишину после.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / ".claude" / "rules").mkdir(parents=True)
            (root / ".claude" / "settings.json").write_text(
                json.dumps({"cmd": "/Users/artem/bin/tool"}), encoding="utf-8")
            (root / ".claude" / "rules" / "areas.md").write_text(
                "Смотри /Users/artem/x.md\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [(".claude/rules/areas.md", 1, "absolute-path",
                  "Смотри /Users/artem/x.md"),
                 (".claude/settings.json", 1, "absolute-path",
                  '{"cmd": "/Users/artem/bin/tool"}')])

    def test_a_read_only_zone_is_foreign_content_and_is_not_scanned(self):
        """`knowledge/` — чужие git-сабмодули (`zones.READ_ONLY`).

        Абсолютный путь в чужой цитате — не находка проверки *нашего*
        пакета: ровно та мотивировка, по которой из скана исключены `inbox/`
        и `sources/`. Убрав из списка все восемь имён зон разом, её потеряли
        вместе с ними: тот же файл был тишиной до правки и находкой после.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            vendor = root / "knowledge" / "vendor"
            vendor.mkdir(parents=True)
            (vendor / "README.md").write_text(
                "См. /Users/someone/else/x\n", encoding="utf-8")
            self.assertEqual(places(check(root)), [])

    def test_a_development_instrument_is_not_package_content(self):
        """`dev/` — оснастка разработки, и в пакет она не уезжает.

        Довод тот же, по которому со скана сняты `tests/` и `docs/`:
        абсолютный путь внутри инструмента, который не отгружается, машинной
        зависимостью пакета не становится. Каталог завели позже, чем список
        пропуска, и живая оснастка мутаций красила собственный `./check`
        тремя находками — двумя прозаическими и вызовом POSIX-шелла.

        Утверждаются оба направления разом: в `dev/` строка молчит, в
        `scripts/` та же самая краснеет. Без второй половины тест не
        отличает «`dev/` снят со скана» от «детектор сломан целиком».
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            line = 'subprocess.run(["/bin/sh", "-n", str(copy)])'
            (root / "dev").mkdir()
            (root / "dev" / "mutate.py").write_text(line + "\n", encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "scripts" / "mutate.py").write_text(line + "\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("scripts/mutate.py", 1, "absolute-path", line)])

    def test_the_only_skipped_zones_are_the_ones_the_table_names(self):
        """Имена зон в периметре берутся из `scripts/zones.py`, а не литералами.

        Тест видит расхождение с таблицей зон, которого не видит
        `tests/test_zones.py::TestSingleDefinition`: его эвристике нужно
        шесть имён и больше, и частичную копию из двух-трёх она пропускает
        по построению.
        """
        self.assertEqual(
            check_package.SKIP_AT_ROOT & set(zones.ZONES),
            set(zones.READ_ONLY) | set(zones.SELF_DEVELOPMENT))

    def test_gitignored_paths_are_outside_the_package(self):
        """Вердикт не зависит от неотслеживаемого локального состояния.

        `.gitignore` не читался вовсе; мусор держал за периметром фильтр по
        расширениям, и с его снятием `python3 -m venv .venv` стал красить
        `./check` на чистом коммите — `.venv/bin/activate` расширения не
        имеет, в пакет не входит и держит абсолютный путь по построению.
        Обе формы записи в `.gitignore` проверяются здесь: поддерево
        (`.venv/`) и отдельный файл (`.claude/settings.local.json`).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / ".gitignore").write_text(
                ".venv/\n.claude/settings.local.json\n", encoding="utf-8")
            venv = root / ".venv" / "bin"
            venv.mkdir(parents=True)
            (venv / "activate").write_text(
                'VIRTUAL_ENV="/Users/artem/.venv"\n', encoding="utf-8")
            (root / ".claude").mkdir()
            (root / ".claude" / "settings.local.json").write_text(
                json.dumps({"cmd": "/Users/artem/bin/tool"}), encoding="utf-8")
            (root / "notes.md").write_text(
                "Смотри /Users/artem/x.md\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("notes.md", 1, "absolute-path", "Смотри /Users/artem/x.md")])

    def test_an_unreadable_hooks_json_never_invents_a_matcher(self):
        """Замещающий знак в **значении** — обвинение в чужом тексте.

        Чтение с заменой байта верно ровно там, где извлекается предикат, а
        не значение: в скане абсолютных путей `�` не похож ни на один
        префикс. Здесь значение доезжает до автора находкой — `matcher:
        "Ed\\xffit"` давал `unknown-matcher Ed?it`, матчер, которого никто
        не писал.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_bytes(
                b'{"hooks": {"PreToolUse": [{"matcher": "Ed\xffit",'
                b' "hooks": [{"type": "command", "command": "x"}]}]}}')
            self.assertEqual(
                places(check(root)),
                [("hooks/hooks.json", 1, "undecodable",
                  "не читается как UTF-8: байт 0xff в позиции 41, "
                  "контракт хуков не проверен")])

    def test_an_unreadable_skill_manifest_never_invents_a_name(self):
        """`skill-name-mismatch 'nam?e' != 'name'` — расхождение из ниоткуда."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_bytes(
                b"---\nname: drain-inb\xffox\ndescription: x\n---\n")
            self.assertEqual(
                places(check(root)),
                [("skills/drain-inbox/SKILL.md", 1, "undecodable",
                  "не читается как UTF-8: байт 0xff в позиции 19, "
                  "манифест скилла не проверен")])

    def test_an_unreadable_eval_is_not_a_trigger_eval(self):
        """Здесь замена давала не обвинение, а ложное зелёное.

        Нечитаемый файл превращался в строку знаков, не начинающуюся с
        решётки, — то есть считался живой фразой срабатывания, и
        `skill-without-eval` молчал.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "eval.txt").write_bytes(b"\xff\xfe\n")
            self.assertEqual(
                places(check(root)),
                [("skills/drain-inbox/eval.txt", 1, "undecodable",
                  "не читается как UTF-8: байт 0xff в позиции 0, "
                  "срабатывание скилла не проверено")])

    def test_an_unreadable_gitignore_is_named_rather_than_narrowed_silently(self):
        """Периметр, собранный не из того текста, — чужой периметр молча.

        Проверка обещает вердикт, не зависящий от неотслеживаемого
        локального состояния. Нечитаемый `.gitignore` сужает периметр до
        умолчаний, и обещание держится на том, о чём не сказано вслух.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / ".gitignore").write_bytes("черновики/\n".encode("cp1251"))
            self.assertEqual(
                places(check(root)),
                [(".gitignore", 1, "undecodable",
                  "не читается как UTF-8: байт 0xf7 в позиции 0, "
                  "периметр прочитан без него")])

    def test_service_directories_are_skipped_at_any_depth(self):
        """`__pycache__` в списке первого сегмента был мёртвой строкой.

        В корне он не лежит никогда, а `scripts/__pycache__/note.txt`
        первым сегментом не отсеивался и уходил в скан. Вложенный `.git` —
        та же история: каталог сабмодуля руками не пишется и в пакет не
        входит. `_tree_hash` и `_product_hash` обе формы исключают давно.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            cache = root / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "note.txt").write_text("/Users/artem/x.py\n", encoding="utf-8")
            gitdir = root / "vendor" / ".git"
            gitdir.mkdir(parents=True)
            (gitdir / "config").write_text(
                "worktree = /Users/artem/vendor\n", encoding="utf-8")
            self.assertEqual(places(check(root)), [])

    def test_a_root_file_named_like_a_skipped_directory_is_scanned(self):
        """Пропуск первого сегмента — про каталог, а не про имя.

        Файл `docs` в корне репозитория — файл пакета: проверка первого
        сегмента не отличала его от каталога `docs/`, и он уходил из скана
        целиком.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "docs").write_text("Смотри /Users/artem/x.md\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("docs", 1, "absolute-path", "Смотри /Users/artem/x.md")])

    def test_absolute_path_inside_a_copy_of_check_package_is_reported(self):
        """Дефект 4: check_package.py не должен исключать себя из периметра.

        Раньше `_SELF = Path(__file__).resolve()` сравнивался с текущим
        файлом: вызванная из копии проверка совпадала с собственным путём
        и гасила находку в себе самой — ровно сценарий
        `python3 /copy/scripts/check_package.py /copy`. Копия здесь
        буквально запускается как отдельный процесс на дереве, где она сама
        и лежит, с добавленным настоящим абсолютным путём в своём тексте.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            shutil.copytree(ROOT / "scripts", root / "scripts",
                            ignore=shutil.ignore_patterns("__pycache__"))
            copy = root / "scripts" / "check_package.py"
            marker = "/Users/artem/x.py"
            copy.write_text(copy.read_text(encoding="utf-8") + "\n# %s\n" % marker,
                            encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(copy), str(root)],
                capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("absolute-path", result.stdout)
            self.assertIn("scripts/check_package.py", result.stdout)


    def test_hooks_json_without_the_top_level_key_is_a_finding(self):
        """Файл без ключа `hooks` Claude Code не читает вовсе.

        `(data.get("hooks") or {})` превращал такую форму в пустой контракт:
        `counts()` пустой, код возврата 0, а каждый объявленный пакетом хук
        молча не запускается — ровно та поломка, которую docstring модуля
        называет стоившей аналогу трёх с половиной месяцев.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"PreToolUse": [
                    {"matcher": "Bahs", "hooks": [{"type": "script"}]}
                ]}), encoding="utf-8")
            report = check(root)
            self.assertEqual(
                places(report),
                [("hooks/hooks.json", 1, "unparseable",
                  "нет ключа hooks: контракт хуков не объявлен")])
            self.assertEqual(report.exit_code(), 2)

    def test_a_structurally_wrong_hooks_json_does_not_lose_other_findings(self):
        """Валидный JSON неверной формы ронял `check()` исключением.

        `AttributeError: 'str' object has no attribute 'get'` уносил все
        остальные находки пакета и возвращал код 1, которого в контракте
        `scripts/findings.py` нет вовсе: там либо 2, либо 0.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"PreToolUse": {
                    "matcher": "Bahs", "hooks": [{"type": "script"}]}}}),
                encoding="utf-8")
            (root / "hooks" / "leak.py").write_text(
                'P = "/Users/artem/leak"\n', encoding="utf-8")
            report = check(root)
            self.assertEqual(
                places(report),
                [("hooks/hooks.json", 1, "unparseable",
                  "hooks.PreToolUse не список, а dict"),
                 ("hooks/leak.py", 1, "absolute-path", 'P = "/Users/artem/leak"')])
            self.assertEqual(report.exit_code(), 2)

    def test_every_wrong_shape_of_hooks_json_is_named(self):
        """Форма проверяется на каждом уровне, а не только на верхнем."""
        cases = [
            ("[]", "верхний уровень не объект, а list"),
            ('"hello"', "верхний уровень не объект, а str"),
            ('{"hooks": []}', "hooks не объект, а list"),
            ('{"hooks": {"PreToolUse": "нет"}}',
             "hooks.PreToolUse не список, а str"),
            ('{"hooks": {"PreToolUse": ["нет"]}}',
             "hooks.PreToolUse[0] не объект, а str"),
            ('{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": "нет"}]}}',
             "hooks.PreToolUse[0].hooks не список, а str"),
            ('{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": ["нет"]}]}}',
             "hooks.PreToolUse[0].hooks[0] не объект, а str"),
        ]
        for text, detail in cases:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "hooks" / "hooks.json").write_text(text, encoding="utf-8")
                self.assertEqual(
                    places(check(root)),
                    [("hooks/hooks.json", 1, "unparseable", detail)])

    def test_an_empty_hook_contract_is_a_legal_form(self):
        """`{"hooks": {}}` — пакет без хуков, а не находка."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {}}), encoding="utf-8")
            self.assertEqual(places(check(root)), [])

    def test_a_declared_hook_with_nothing_to_run_is_a_finding(self):
        """Хук объявлен, форма законна, запускать нечего — тот же промах формы.

        Ровно то же, что и файл без верхнего ключа `hooks`, только уровнем
        ниже: JSON разбирается, проверка молчит, а ни одна команда не
        выполняется. Три формы одной поломки — запись без ключа `hooks`,
        пустой список хуков и `type: command` без самой команды.
        """
        cases = [
            ('{"hooks": {"PreToolUse": [{}]}}',
             "hooks.PreToolUse[0]: нет ключа hooks: запускать нечего"),
            ('{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]}}',
             "hooks.PreToolUse[0].hooks: пустой список: запускать нечего"),
            ('{"hooks": {"PreToolUse": [{"hooks": [{"type": "command"}]}]}}',
             "hooks.PreToolUse[0].hooks[0]: тип command без непустой команды"),
            ('{"hooks": {"PreToolUse": [{"hooks": [{"type": "command",'
             ' "command": "   "}]}]}}',
             "hooks.PreToolUse[0].hooks[0]: тип command без непустой команды"),
        ]
        for text, detail in cases:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "hooks" / "hooks.json").write_text(text, encoding="utf-8")
                self.assertEqual(
                    places(check(root)),
                    [("hooks/hooks.json", 1, "unparseable", detail)])

    def test_a_skill_directory_named_adopt_is_still_adopt(self):
        """`startswith("skills/adopt-")` требовал дефиса.

        `skills/adopt/` — самое естественное имя для скилла усыновления, и
        оно выключало `destructive-example` целиком.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            line = "Переложи так: mv journal areas/journal"
            rel = _adopt_skill(root, line, name="adopt")
            self.assertEqual(
                places(check(root)),
                [(rel, 5, "destructive-example", line)])

    def test_every_destructive_form_is_caught(self):
        """Разрушающих форм не две: удаление, усечение и откат тоже.

        Все перечисленные проходили зелёными в инструкциях ADOPT, потому
        что класс знал ровно `mv` и `rm`.
        """
        forms = [
            "mv journal areas/journal",
            "rm -rf areas/old",
            "rmdir areas/old",
            "git clean -fdx",
            "find . -name '*.md' -delete",
            "shutil.rmtree(target)",
            "> notes.md",
            "git checkout -- .",
            "rsync -a --delete src/ dst/",
            "truncate -s 0 log.txt",
            "git reset --hard",
        ]
        for form in forms:
            with self.subTest(form=form), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                line = "Сделай: %s" % form
                rel = _adopt_skill(root, line)
                self.assertEqual(
                    places(check(root)),
                    [(rel, 5, "destructive-example", line)])

    def test_the_sibling_spelling_of_every_listed_form_is_caught_too(self):
        """Перечисление было короче того, что перечисляет.

        `git restore` — сегодняшнее написание `git checkout --`, и класс
        ловил устаревшую форму, пропуская ту, которую рекомендует
        документация. `rm` в конце звена конвейера не имел аргумента, а
        разбор требовал непробел следом. Удаление одного файла (`os.remove`,
        `unlink`) не было названо вовсе, как и целое семейство «переписать
        на месте»: `sed -i`, `tee`, `cp`, `dd`, `install`, `shred`, `chmod`,
        `git worktree remove`.

        `dd if=/dev/zero` даёт вдобавок `absolute-path`: `/dev/` — корень из
        списка, и это верно, а не побочный шум.
        """
        forms = [
            ("git restore .", ["destructive-example"]),
            ("find . -name '*.md' | xargs rm", ["destructive-example"]),
            ('os.remove("notes.md")', ["destructive-example"]),
            ('os.unlink("notes.md")', ["destructive-example"]),
            ("target.unlink()", ["destructive-example"]),
            (">| notes.md", ["destructive-example"]),
            ("sed -i '' 's/a/b/' notes.md", ["destructive-example"]),
            ("tee notes.md < in.md", ["destructive-example"]),
            ("cp new.md notes.md", ["destructive-example"]),
            ("dd if=/dev/zero of=notes.md",
             ["absolute-path", "destructive-example"]),
            ("install -d areas/new", ["destructive-example"]),
            ("git worktree remove ../wt", ["destructive-example"]),
            ("shred notes.md", ["destructive-example"]),
            ("chmod -R 000 areas", ["destructive-example"]),
        ]
        for form, classes in forms:
            with self.subTest(form=form), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                line = "Сделай: %s" % form
                rel = _adopt_skill(root, line)
                self.assertEqual(
                    places(check(root)),
                    [(rel, 5, cls, line) for cls in classes])

    def test_prose_in_adopt_instructions_is_not_destructive(self):
        """Цена расширения: цитата markdown и стрелка остаются прозой.

        `>` в начале строки — цитата, а не усекающее перенаправление;
        отличает их вид цели, а не сам знак.
        """
        for line in ("> Форму правит плагин, содержимое не трогает",
                     "> см. docs/roadmap.md, там таблица",
                     "Переход a -> b ничего не удаляет",
                     "Разметка <br>текста",
                     "Каталог areas/ остаётся на месте",
                     # Цена расширения на хвост конвейера, если считать
                     # признаком конец строки: прямая речь запрета краснеет
                     # раньше примера, и класс ловит предупреждение.
                     "Никогда не пиши в инструкции `rm`",
                     "Опасны и `mv`, и `rmdir`",
                     # Цена расширения на `install`, если считать признаком
                     # любой ключ: это установка зависимости, а не запись в
                     # чужое дерево.
                     "Поставь редактор: `brew install --cask obsidian`",
                     "Зависимости: `pip install -r requirements.txt`"):
            with self.subTest(line=line), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                _adopt_skill(root, line)
                self.assertEqual(places(check(root)), [])

    def test_an_empty_trigger_eval_is_not_a_trigger_eval(self):
        """`exists()` был всей проверкой: пустой файл считался эвалом.

        Критерий 4 уже установил, что пустая причина не проходит; к
        `eval.txt` тот же принцип не применяли.
        """
        for content in ("", "   \n\t\n"):
            with self.subTest(content=repr(content)), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "skills" / "drain-inbox" / "eval.txt").write_text(
                    content, encoding="utf-8")
                self.assertEqual(
                    places(check(root)),
                    [("skills/drain-inbox", 1, "skill-without-eval",
                      "пустой eval.txt: срабатывание не проверяется")])

    def test_an_eval_of_only_comments_is_not_a_trigger_eval(self):
        """«Непусто после strip» — не то же самое, что «есть фраза срабатывания».

        Файл из одних комментариев не содержит ни одной фразы, на которую
        скилл обязан сработать, а проверку проходил: `strip()` видит в нём
        текст. Одинокая BOM — тот же промах с другой стороны: `\\ufeff` не
        пробельный символ, и файл из одного невидимого знака считался эвалом.
        """
        cases = [
            ("# только комментарий\n# и ещё один\n",
             "в eval.txt только комментарии: срабатывание не проверяется"),
            ("\ufeff", "пустой eval.txt: срабатывание не проверяется"),
            ("\ufeff# только комментарий\n",
             "в eval.txt только комментарии: срабатывание не проверяется"),
        ]
        for content, detail in cases:
            with self.subTest(content=repr(content)), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "skills" / "drain-inbox" / "eval.txt").write_text(
                    content, encoding="utf-8")
                self.assertEqual(
                    places(check(root)),
                    [("skills/drain-inbox", 1, "skill-without-eval", detail)])

    def test_a_bom_before_the_first_trigger_phrase_is_still_a_trigger_eval(self):
        """Цена снятия BOM — ноль живых эвалов: редактор ставит её и молчит."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "eval.txt").write_text(
                "\ufeff# что должно сработать\nразбери инбокс\n", encoding="utf-8")
            self.assertEqual(places(check(root)), [])

    def test_a_quoted_whitespace_description_is_empty(self):
        """Кавычки сохраняют пробелы, и `not fields.get(...)` их пропускал.

        Незакавыченная форма ловилась случайно: там пробелы съедает сам
        разбор frontmatter и поле становится `None`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                '---\nname: drain-inbox\ndescription: "   "\n---\n', encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("skills/drain-inbox", 1, "skill-without-description",
                  "пустое описание")])

    def test_the_yaml_spellings_of_nothing_are_an_empty_description(self):
        """`null` и `~` — то, чем YAML записывает отсутствие значения.

        Парсер frontmatter скаляры не толкует, и до проверки доезжает
        строка из четырёх знаков: `_nonblank` объявлял её описанием. Форма
        не экзотическая — именно её пишет большинство инструментов,
        сериализующих пустое поле. Пустой flow-список — та же запись
        отсутствия, и он тоже проходил зелёным.

        Проверка не зависит от того, толкует ли парсер скаляры: начнёт
        возвращать `None` — ответ не изменится.
        """
        for text in ("null", "Null", "NULL", "~", "[]"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                    "---\nname: drain-inbox\ndescription: %s\n---\n" % text,
                    encoding="utf-8")
                self.assertEqual(
                    places(check(root)),
                    [("skills/drain-inbox", 1, "skill-without-description",
                      "пустое описание")])

    def test_a_useless_description_is_not_this_check_s_business(self):
        """`0` и `false` — описание есть, толку от него нет.

        Класс называется «скилл без описания», и судить качество написанного
        он не берётся: иначе граница между формой и содержимым, которую
        держит незыблемое №1, проходит там, где её проведёт регулярка.
        """
        for text in ("0", "false"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                    "---\nname: drain-inbox\ndescription: %s\n---\n" % text,
                    encoding="utf-8")
                self.assertEqual(places(check(root)), [])

    def test_every_relative_call_form_in_a_skill_is_caught(self):
        """Регулярка требовала запускающего слова и знала один каталог.

        Все четыре формы разрешаются от рабочего каталога — репозитория
        пользователя, а не плагина, — и все четыре были зелёными.
        """
        forms = [
            "Запусти scripts/check_links.py на корне.",
            "python3 -m scripts.check_links .",
            "python3 hooks/hook.py",
            "uv run scripts/check_links.py .",
            "python3 scripts/drain.py",
        ]
        for form in forms:
            with self.subTest(form=form), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                    "---\nname: drain-inbox\ndescription: x\n---\n%s\n" % form,
                    encoding="utf-8")
                self.assertEqual(
                    places(check(root)),
                    [("skills/drain-inbox/SKILL.md", 5, "relative-path-in-skill",
                      form)])

    def test_the_dot_slash_spellings_are_caught_and_plugin_root_still_is_not(self):
        """Обе стороны одного размена, в одном тесте.

        Расширяя класс на прозу без запускающего слова, в запрет слева
        внесли косую — чтобы законная форма `${CLAUDE_PLUGIN_ROOT}/scripts/…`
        не краснела. Косая слева стоит и в `./scripts/…`, и в
        `../scripts/…` — то есть в двух самых частых написаниях, с которых
        класс и начинался: исходная поломка перестала ловиться. Законную
        форму гасит отдельное условие по `${CLAUDE_PLUGIN_ROOT}` в строке,
        а не запрет слева, — поэтому обе стороны пиннятся вместе, и
        следующее сужение не сможет разменять одну на другую молча.
        """
        for form in ("Запусти `./scripts/check_links.py .`",
                     "Запусти `../scripts/check_links.py .`",
                     "Запусти `bash ./hooks/hook.sh`"):
            with self.subTest(form=form), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                    "---\nname: drain-inbox\ndescription: x\n---\n%s\n" % form,
                    encoding="utf-8")
                self.assertEqual(
                    places(check(root)),
                    [("skills/drain-inbox/SKILL.md", 5, "relative-path-in-skill",
                      form)])
        for form in ('Запусти `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/drain.py"`',
                     'Запусти `sh "${CLAUDE_PLUGIN_ROOT}/hooks/hook.sh"`',
                     # Дефис в запрете слева: чужой каталог, чьё имя кончается
                     # именем нашего, — не ссылка в пакет.
                     "Твой каталог `my-scripts/build.py` не наш"):
            with self.subTest(form=form), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                    "---\nname: drain-inbox\ndescription: x\n---\n%s\n" % form,
                    encoding="utf-8")
                self.assertEqual(places(check(root)), [])

    def test_a_relative_command_in_hooks_json_is_caught(self):
        """Та же дыра в hooks.json: команда хука тоже путь, и тоже чужой."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                '{\n'
                '  "hooks": {\n'
                '    "PreToolUse": [\n'
                '      {"matcher": "Bash", "hooks": [\n'
                '        {"type": "command", "command": "python3 hooks/hook.py"}\n'
                '      ]}\n'
                '    ]\n'
                '  }\n'
                '}\n', encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("hooks/hooks.json", 5, "relative-path-in-skill",
                  '{"type": "command", "command": "python3 hooks/hook.py"}')])

    def test_the_plugin_root_form_in_hooks_json_stays_silent(self):
        """Форма с `${CLAUDE_PLUGIN_ROOT}` — единственная законная."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                '{\n'
                '  "hooks": {\n'
                '    "PreToolUse": [\n'
                '      {"matcher": "Bash", "hooks": [\n'
                '        {"type": "command",\n'
                '         "command": "${CLAUDE_PLUGIN_ROOT}/hooks/hook.sh PreToolUse"}\n'
                '      ]}\n'
                '    ]\n'
                '  }\n'
                '}\n', encoding="utf-8")
            self.assertEqual(places(check(root)), [])

    def test_a_nested_skill_directory_is_checked_as_a_skill(self):
        """Плоский `iterdir()` видел только первый уровень.

        `skills/group/nested-skill/SKILL.md` давал находку «нет SKILL.md» на
        `skills/group` — неверную и по пути, и по существу, — а настоящий
        скилл не проверялся вовсе.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            nested = root / "skills" / "group" / "nested-skill"
            nested.mkdir(parents=True)
            (nested / "SKILL.md").write_text(
                "---\nname: nested-skill\ndescription: Вложенный\n---\n",
                encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("skills/group/nested-skill", 1, "skill-without-eval",
                  "нет eval.txt: срабатывание не проверяется")])

    def test_a_directory_without_any_manifest_is_still_a_finding(self):
        """Каталог, в котором SKILL.md нет нигде, остаётся находкой."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "пусто").mkdir()
            self.assertEqual(
                places(check(root)),
                [("skills/пусто", 1, "skill-without-description", "нет SKILL.md")])

    def test_container_roots_are_absolute_too(self):
        """`/workspace/`, `/workspaces/` и `/data/` списку известны не были.

        `/workspaces/` — умолчание GitHub Codespaces, `/workspace/` — почти
        любого образа: путь оттуда верен ровно в одном контейнере.
        """
        for form in ("/workspace/repo/x.py", "/workspaces/repo/x.py",
                     "/data/db/x.sqlite"):
            with self.subTest(form=form):
                self.assertIsNotNone(
                    check_package.ABSOLUTE.search("Зовёт %s отсюда" % form), form)

    def test_a_container_root_is_reported_like_any_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "notes.md").write_text(
                "Смотри /workspaces/repo/x.md\n", encoding="utf-8")
            self.assertEqual(
                places(check(root)),
                [("notes.md", 1, "absolute-path", "Смотри /workspaces/repo/x.md")])

    def test_an_undecodable_skill_manifest_does_not_crash_the_check(self):
        """`read_text` без замены ронял всю проверку на одном байте.

        Тот же дефект, что и в скане файлов пакета, только на SKILL.md:
        исключение уносило и остальные находки, и код возврата. Замена его
        закрыла и завела ложное зелёное: `description: caf\\xe9` доезжал как
        `caf?`, поля считались заполненными, имя — совпавшим, и проверка
        молчала о файле, который не прочитан. Теперь файл называется, а
        остальные находки на месте — крах не вернулся.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_bytes(
                "---\nname: drain-inbox\ndescription: caf".encode("utf-8")
                + b"\xe9\n---\n")
            report = check(root)
            self.assertEqual(
                places(report),
                [("skills/drain-inbox/SKILL.md", 1, "undecodable",
                  "не читается как UTF-8: байт 0xe9 в позиции 38, "
                  "манифест скилла не проверен")])
            self.assertEqual(report.exit_code(), 2)


class TestMutatingSkillPerimeter(unittest.TestCase):
    """Периметр `destructive-example` — все скиллы, мутирующие дерево.

    Волна 4 держала класс над одним усыновлением. Волна 5 отгружает ещё три
    скилла, и два из них удаляют: `maintain-context-repo` сносит пустую
    коллекцию, перешедшую порог, `drain-inbox` — разобранный элемент. Довод,
    ради которого класс заведён («разрушающий пример в инструкции рано или
    поздно исполнят буквально»), относится к ним ровно так же.
    """

    # Скиллы, которые дерево только читают. Список здесь, а не в продукте:
    # продукт называет периметр, а тест сверяет, что отгруженное дерево
    # скиллов этим периметром разобрано целиком.
    READ_ONLY = ("create-context-repo",)

    def test_the_perimeter_is_this_closed_set(self):
        """Закрытое множество, как `TOOL_NAMES`: новый мутирующий скилл
        дописывается сюда правкой, и правка видна."""
        self.assertEqual(sorted(check_package.MUTATING_SKILLS),
                         ["adopt", "drain-inbox", "extend-structure",
                          "maintain-context-repo"])

    def test_every_shipped_skill_is_on_one_of_the_two_sides(self):
        """Тест спрашивает дерево, а не константу.

        Периметр, сверенный только с литералом рядом, остаётся зелёным и
        тогда, когда в `skills/` приехал четвёртый мутирующий скилл, о
        котором константа не знает. Здесь красным становится **любой** новый
        каталог скилла: его придётся отнести к одной из двух сторон.
        """
        shipped = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
        inside = [name for name in shipped
                  if check_package._is_mutating_skill("skills/%s/SKILL.md" % name)]
        outside = [name for name in shipped if name not in inside]
        self.assertEqual(sorted(outside), sorted(self.READ_ONLY))
        self.assertEqual(inside, sorted(set(shipped) - set(self.READ_ONLY)))

    def test_every_name_of_the_perimeter_names_a_shipped_skill(self):
        """Опечатка в имени снимает скилл с класса молча: файла с таким
        именем в `skills/` нет, а `_is_mutating_skill` про это не знает."""
        shipped = [p.name for p in (ROOT / "skills").iterdir() if p.is_dir()]
        for name in check_package.MUTATING_SKILLS:
            self.assertTrue(
                [d for d in shipped if d == name or d.startswith(name + "-")],
                name)

    def test_each_of_them_is_inside_the_perimeter(self):
        for name in check_package.MUTATING_SKILLS:
            self.assertTrue(
                check_package._is_mutating_skill("skills/%s/SKILL.md" % name), name)

    def test_a_prefix_match_is_enough_for_adopt(self):
        """`skills/adopt/` и `skills/adopt-context-repo/` — оба усыновление.
        Требование дефиса однажды выключало класс целиком."""
        for rel in ("skills/adopt/SKILL.md", "skills/adopt-context-repo/SKILL.md"):
            self.assertTrue(check_package._is_mutating_skill(rel), rel)

    def test_a_nested_file_of_a_mutating_skill_is_inside_too(self):
        self.assertTrue(
            check_package._is_mutating_skill("skills/drain-inbox/refs/notes.md"))

    def test_a_read_only_skill_is_outside(self):
        self.assertFalse(
            check_package._is_mutating_skill("skills/create-context-repo/SKILL.md"))

    def test_a_directory_outside_skills_is_outside(self):
        self.assertFalse(check_package._is_mutating_skill("docs/drain-inbox/x.md"))

    def test_a_file_named_after_a_skill_does_not_join_the_perimeter(self):
        """Скилл с заметкой `maintain-context-repo.md` внутри мутирующим
        не становится: имя файла из проверки исключено."""
        self.assertFalse(
            check_package._is_mutating_skill("skills/other/maintain-context-repo.md"))

    def test_a_destructive_example_reddens_in_every_mutating_skill(self):
        """Периметр расширен — значит посаженный образец краснеет в каждом
        из четырёх, а не только в усыновлении."""
        for name in ("adopt-context-repo", "maintain-context-repo",
                     "extend-structure", "drain-inbox"):
            with self.subTest(skill=name), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                line = "Сделай: rm -rf projects/stale"
                rel = _adopt_skill(root, line, name=name)
                self.assertEqual(
                    places(check(root)),
                    [(rel, 5, "destructive-example", line)])

    def test_the_same_example_stays_silent_in_a_read_only_skill(self):
        """Обе стороны размена в одном тесте: расширение периметра не
        означает, что класс поехал на все скиллы подряд."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            _adopt_skill(root, "Сделай: rm -rf projects/stale",
                         name="create-context-repo")
            self.assertEqual(places(check(root)), [])


class TestGateNotReadOnlyMechanism(unittest.TestCase):
    """Доказательство для `gate-not-read-only` в docs/gate-coverage.md.

    Гейт, который пишет в фикстуру вместо того, чтобы только её читать,
    обязан быть пойман хешем дерева до и после (`check_read_only`).
    """

    def test_mutating_gate_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "mutating_gate.py").write_text(
                "import sys\n"
                "from pathlib import Path\n"
                "Path(sys.argv[1]).joinpath('mutated.txt').write_text('touched', encoding='utf-8')\n",
                encoding="utf-8",
            )
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / "keep.md").write_text("исходное содержимое\n", encoding="utf-8")

            findings = check_read_only(root, "mutating_gate.py", fixture)

            self.assertEqual([f.cls for f in findings], ["gate-not-read-only"])

    def test_read_only_gate_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "honest_gate.py").write_text(
                "import sys\n"
                "from pathlib import Path\n"
                "list(Path(sys.argv[1]).rglob('*'))\n",
                encoding="utf-8",
            )
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / "keep.md").write_text("исходное содержимое\n", encoding="utf-8")

            findings = check_read_only(root, "honest_gate.py", fixture)

            self.assertEqual(findings, [])

    def test_a_gate_that_writes_outside_the_fixture_is_caught(self):
        """Хеш одной фикстуры не доказывает ничего о остальном дереве.

        Посаженный гейт создавал файл двумя уровнями выше фикстуры:
        `counts()` оставался пустым, а файл действительно появлялся.
        Незыблемое №6 запрещает плагину писать что бы то ни было вне корня,
        и проверка обязана видеть это, а не только правку внутри фикстуры.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "leaky_gate.py").write_text(
                "import sys\n"
                "from pathlib import Path\n"
                "fixture = Path(sys.argv[1])\n"
                "fixture.parent.parent.joinpath('GATE_WROTE_HERE.txt')"
                ".write_text('touched', encoding='utf-8')\n",
                encoding="utf-8",
            )
            fixture = root / "fixtures" / "broken"
            fixture.mkdir(parents=True)
            (fixture / "keep.md").write_text("исходное содержимое\n", encoding="utf-8")

            findings = check_read_only(root, "leaky_gate.py", fixture)

            self.assertEqual(
                [(f.path, f.line, f.cls, f.detail) for f in findings],
                [("scripts/leaky_gate.py", 1, "gate-not-read-only",
                  "дерево репозитория изменилось после прогона")])
            self.assertTrue((root / "GATE_WROTE_HERE.txt").exists())


class TestTestsTouchedProductMechanism(unittest.TestCase):
    """Доказательство для `tests-touched-product` в docs/gate-coverage.md.

    Тот же приём вокруг прогона всего набора тестов: прогон, который
    изменяет файл в `scripts/`, обязан быть пойман (`_check_tests_touched_product`).
    """

    def test_test_run_that_writes_to_scripts_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "marker.py").write_text("VALUE = 1\n", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "__init__.py").write_text("", encoding="utf-8")
            (tests_dir / "test_mutator.py").write_text(
                "import unittest\n"
                "from pathlib import Path\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_touches_scripts(self):\n"
                "        marker = Path(__file__).resolve().parent.parent / 'scripts' / 'marker.py'\n"
                "        marker.write_text('VALUE = 2\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )

            findings = _check_tests_touched_product(root)

            self.assertEqual([f.cls for f in findings], ["tests-touched-product"])

    def test_test_run_that_leaves_scripts_alone_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "marker.py").write_text("VALUE = 1\n", encoding="utf-8")
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "__init__.py").write_text("", encoding="utf-8")
            (tests_dir / "test_honest.py").write_text(
                "import unittest\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_does_nothing_to_product(self):\n"
                "        self.assertEqual(1, 1)\n",
                encoding="utf-8",
            )

            findings = _check_tests_touched_product(root)

            self.assertEqual(findings, [])

    def test_every_shipped_directory_is_watched(self):
        """`hooks/` и `skills/` в снимке продукта не было вовсе.

        Docstring рядом называл `scripts/` и `.claude-plugin/` «единственным,
        чего тесты не вправе трогать», а `hooks/` — уже отгруженный продукт:
        тест, переписывающий `hooks/hook.py`, был для проверки невидим.
        """
        for rel in ("scripts/marker.py", ".claude-plugin/plugin.json",
                    "hooks/hook.py", "skills/drain-inbox/SKILL.md"):
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("исходное\n", encoding="utf-8")
                tests_dir = root / "tests"
                tests_dir.mkdir()
                (tests_dir / "__init__.py").write_text("", encoding="utf-8")
                (tests_dir / "test_mutator.py").write_text(
                    "import unittest\n"
                    "from pathlib import Path\n\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_touches_product(self):\n"
                    "        target = Path(__file__).resolve().parent.parent / %r\n"
                    "        target.write_text('изменено\\n', encoding='utf-8')\n" % rel,
                    encoding="utf-8",
                )

                findings = _check_tests_touched_product(root)

                self.assertEqual(
                    [(f.path, f.line, f.cls, f.detail) for f in findings],
                    [("tests", 1, "tests-touched-product",
                      "продукт изменился после прогона тестов")])


class TestThisPackage(unittest.TestCase):
    def test_our_own_package_is_green(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_package.py"), str(ROOT)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
