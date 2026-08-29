import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIM = ROOT / "hooks" / "hook.sh"


def run_hook(event, payload, env=None, cwd=None):
    """Хук всегда прогоняется настоящим подпроцессом.

    Вызов логики напрямую не проверяет ни shim, ни код возврата, ни разбор
    stdin — то есть ровно то, что ломается на практике.
    """
    environ = dict(os.environ)
    environ.update(env or {})
    return subprocess.run(
        [str(SHIM), event],
        input=json.dumps(payload),
        capture_output=True, text=True,
        cwd=str(cwd or ROOT), env=environ,
    )


class TestEntryContract(unittest.TestCase):
    def test_shim_is_executable(self):
        self.assertTrue(os.access(SHIM, os.X_OK), "hook.sh не исполняем")

    def test_unknown_event_is_not_a_violation(self):
        """Незнакомое событие — не нарушение: код 0 и видимая причина."""
        result = run_hook("OnFullMoon", {"hook_event_name": "OnFullMoon"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("OnFullMoon", result.stdout + result.stderr)

    def test_broken_stdin_is_not_a_violation(self):
        """Битый JSON на входе — «не смог», а не «запретил»."""
        result = subprocess.run([str(SHIM), "PreToolUse"], input="{не json",
                                capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(result.returncode, 0)
        self.assertIn("не разобран", result.stderr)

    def test_missing_interpreter_is_visible_and_not_a_violation(self):
        """Нет python — код 0 и строка с причиной, никогда не тишина.

        Урок оплачен чужой болью: хук возвращал 1 из-за отсутствия flock
        на macOS, это читалось как «занято», и автокоммиты молча отключились
        у всех пользователей macOS.
        """
        env = {"TWINKLE_PYTHON": "/nonexistent/python3"}
        result = run_hook("SessionStart", {"hook_event_name": "SessionStart"}, env=env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("гейт не выполнился", result.stderr)


    def test_failing_import_is_visible_and_not_a_violation(self):
        """Сбой импорта — та же поломка, что и отсутствие flock, только внутри.

        Ветка «hook.py вернул не 0 и не 2» планом не покрыта, а это ровно тот
        отказ, ради которого шим и заведён: ядро прочитает любой ненулевой код
        как неблокирующую ошибку и промолчит. Здесь пакет хуков копируется
        без `scripts/` рядом, поэтому импорт гарантированно падает.
        """
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "hooks" / "hook.sh"
            shutil.copytree(ROOT / "hooks", shim.parent)
            result = subprocess.run([str(shim), "SessionStart"], input="{}",
                                    capture_output=True, text=True, cwd=tmp)
        self.assertEqual(result.returncode, 0)
        self.assertIn("гейт не выполнился", result.stderr)


class TestHandshake(unittest.TestCase):
    """Шим переводит не всякий код, а только два своих.

    Пока шим пропускал наружу 0 и 2 как есть, «hook.py не запускался» было
    неотличимо от «hook.py проверил»: любой посторонний, вернувший 2, приезжал
    в Claude Code блокировкой без причины, а вернувший 0 — молчаливым
    разрешением. Рукопожатие двумя частными кодами и есть доказательство, что
    проверка состоялась.
    """

    def _stand_in(self, tmp, body):
        """Исполняемая заглушка на месте интерпретатора."""
        path = Path(tmp) / "python3"
        path.write_text("#!/bin/sh\n%s\n" % body, encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_hook_py_returns_its_private_ok_code(self):
        """Код рукопожатия проверяется прогоном, а не чтением файла: два
        согласованных текстом числа могут не вернуться ни разу."""
        from hooks import hook
        result = subprocess.run(
            [sys.executable, str(ROOT / "hooks" / "hook.py"), "OnFullMoon"],
            input="{}", capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(result.returncode, hook.EXIT_CHECKED_OK)

    def test_shim_and_module_name_the_same_two_codes(self):
        """Числа живут в двух файлах на двух языках: разойдутся — гейт
        замолчит целиком, и никакой другой тест этого не заметит."""
        from hooks import hook
        text = SHIM.read_text(encoding="utf-8")
        self.assertIn(str(hook.EXIT_CHECKED_OK), text)
        self.assertIn(str(hook.EXIT_CHECKED_VIOLATION), text)
        self.assertNotEqual(hook.EXIT_CHECKED_OK, hook.EXIT_CHECKED_VIOLATION)
        for taken in (0, 1, 2, 120, 126, 127):
            self.assertNotIn(taken, (hook.EXIT_CHECKED_OK,
                                     hook.EXIT_CHECKED_VIOLATION))

    def test_a_foreign_exit_two_is_not_a_violation(self):
        """Чужая двойка — «не смог», а не «запретил».

        `python3` в дикой природе бывает обёрткой venv или pyenv, и двойка
        у неё своя. Пропущенная наружу, она читается ядром как блокировка
        записи — без единой строки причины. Ровно та поломка, ради которой
        шим и заведён, только на один код в сторону.
        """
        with tempfile.TemporaryDirectory() as tmp:
            stand_in = self._stand_in(tmp, "exit 2")
            result = run_hook("SessionStart", {},
                              env={"TWINKLE_PYTHON": str(stand_in)})
        self.assertEqual(result.returncode, 0)
        self.assertIn("гейт не выполнился", result.stderr)
        self.assertIn("2", result.stderr)

    def test_an_interpreter_that_never_ran_hook_py_is_not_an_approval(self):
        """Ноль от интерпретатора, не запускавшего hook.py, — не «чисто».

        Доказательства проверки в коде 0 нет никакого: его вернёт и `/bin/echo`
        на месте python. Молчаливое разрешение здесь опаснее ложного отказа —
        отказ видно, разрешение нет.
        """
        result = run_hook("PreToolUse", {}, env={"TWINKLE_PYTHON": "/bin/echo"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("гейт не выполнился", result.stderr)


class TestPayloadShape(unittest.TestCase):
    """Разобранный JSON ещё не значит понятный JSON.

    `read_event` ловил только `JSONDecodeError` — то есть обработан был тот
    случай, который придумали, а не тот, который приезжает. Массив, строка и
    поле с числом вместо пути дают трассировку в транскрипте, и причиной
    отказа в stderr значится код возврата, а не то, что случилось со входом.
    """

    def _run(self, event, raw):
        return subprocess.run([str(SHIM), event], input=raw,
                              capture_output=True, text=True, cwd=str(ROOT))

    def test_a_json_array_is_not_a_violation(self):
        result = self._run("PreToolUse", "[]")
        self.assertEqual(result.returncode, 0)
        self.assertIn("гейт не выполнился", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_json_string_is_not_a_violation(self):
        result = self._run("PreToolUse", '"привет"')
        self.assertEqual(result.returncode, 0)
        self.assertIn("гейт не выполнился", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_json_null_is_not_a_violation(self):
        result = self._run("PostToolUse", "null")
        self.assertEqual(result.returncode, 0)
        self.assertIn("гейт не выполнился", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_field_of_the_wrong_type_names_the_field(self):
        """Тип поля проверяется там же, где форма нагрузки: `cwd` числом
        доезжает до `Path()` и роняет хук `TypeError`'ом про аргумент, а не
        строкой про вход."""
        result = self._run("PreToolUse", json.dumps(
            {"cwd": 12345, "tool_input": {"file_path": "core/me.md"}}))
        self.assertEqual(result.returncode, 0)
        self.assertIn("cwd", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class TestNoSilencing(unittest.TestCase):
    """Три шаблона, которыми отказ превращают в тишину. Запрещены дословно."""

    def test_shim_never_silences(self):
        text = SHIM.read_text(encoding="utf-8")
        for banned in ("2>/dev/null", "|| true", ">/dev/null 2>&1"):
            self.assertNotIn(banned, text, banned)
