import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_package
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


def _minimal_package(root):
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "x", "version": "0.1.0"}), encoding="utf-8")
    (root / "hooks").mkdir()
    (root / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [{"matcher": "*", "hooks": []}]}}),
        encoding="utf-8")
    skill = root / "skills" / "drain-inbox"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: drain-inbox\ndescription: Разбирает inbox\n---\n", encoding="utf-8")
    (skill / "eval.txt").write_text("разбери инбокс\ndrain the inbox\n", encoding="utf-8")
    return root


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
            self.assertIn("absolute-path", check(root).counts())

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
        """Критерий 3: фильтр по расширению уводил из-под скана целые форматы."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "Makefile").write_text(
                "run:\n\tpython3 /Users/artem/x.py\n", encoding="utf-8")
            self.assertIn("absolute-path", check(root).counts())

    def test_a_package_dir_named_like_a_zone_is_still_scanned(self):
        """Восемь имён зон в SKIP_DIRS снимали со скана целые поддеревья."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            core = root / "core"
            core.mkdir()
            (core / "notes.md").write_text("Смотри /Users/artem/x.md\n", encoding="utf-8")
            self.assertIn("absolute-path", check(root).counts())

    def test_binary_files_do_not_break_the_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
            self.assertEqual(check(root).counts(), {})

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


class TestThisPackage(unittest.TestCase):
    def test_our_own_package_is_green(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_package.py"), str(ROOT)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
