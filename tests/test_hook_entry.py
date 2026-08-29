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


class TestNoSilencing(unittest.TestCase):
    """Три шаблона, которыми отказ превращают в тишину. Запрещены дословно."""

    def test_shim_never_silences(self):
        text = SHIM.read_text(encoding="utf-8")
        for banned in ("2>/dev/null", "|| true", ">/dev/null 2>&1"):
            self.assertNotIn(banned, text, banned)
