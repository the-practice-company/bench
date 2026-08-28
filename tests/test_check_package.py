import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_package import check, check_read_only, _check_tests_touched_product

ROOT = Path(__file__).resolve().parent.parent


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
