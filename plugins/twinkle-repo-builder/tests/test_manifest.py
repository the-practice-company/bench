"""Версия рецепта: манифест пакета против маркера инстанса.

Секция 21 («Версия одна», «Обновление ленивое») и таблица событий спеки
волны 5 требуют одного и того же: расхождение версий — **событие**, о котором
`SessionStart` печатает строку. До этого набора равенство версий держал один
тест в репозитории плагина (`tests/test_scaffold.py::TestRecipeMarker`), то
есть утверждение о дереве разработчика, а не поведение отгруженного пакета:
в инстансе на чужой машине сравнивать версии было нечем и некому.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scripts import manifest

ROOT = Path(__file__).resolve().parent.parent


def instance(base, text):
    """Инстанс с маркером ровно такого содержания."""
    root = Path(base) / "repo"
    root.mkdir()
    (root / manifest.MARKER).write_text(text, encoding="utf-8")
    return root


class TestPluginVersion(unittest.TestCase):
    def test_it_is_read_from_the_shipped_manifest(self):
        """Второго определения пути к манифесту в пакете нет.

        Литерал `.claude-plugin/plugin.json` жил в двух наборах тестов сразу
        и ни в одной строке продукта: манифест был артефактом, который никто
        не читает. Читающий его теперь один, и путь объявлен там же.
        """
        declared = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.plugin_version(), declared["version"])

    def test_the_manifest_path_points_at_the_shipped_file(self):
        self.assertEqual(manifest.MANIFEST,
                         ROOT / ".claude-plugin" / "plugin.json")


class TestInstanceVersion(unittest.TestCase):
    def test_it_is_read_from_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = instance(tmp, '{"version": "0.4.2"}')
            self.assertEqual(manifest.instance_version(root), "0.4.2")

    def test_a_missing_marker_is_named_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            with self.assertRaises(manifest.Unreadable) as caught:
                manifest.instance_version(root)
            self.assertIn("маркер рецепта", str(caught.exception))

    def test_broken_json_is_named_not_guessed(self):
        """Секция 22: битый JSON — не то же самое, что отсутствие. Подставить
        сюда версию манифеста значило бы объявить инстанс обновлённым
        (незыблемое №4)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = instance(tmp, "{не json")
            with self.assertRaises(manifest.Unreadable) as caught:
                manifest.instance_version(root)
            self.assertIn("маркер рецепта", str(caught.exception))

    def test_a_marker_without_the_field_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = instance(tmp, '{"схема": 1}')
            with self.assertRaises(manifest.Unreadable) as caught:
                manifest.instance_version(root)
            self.assertIn("version", str(caught.exception))

    def test_a_version_that_is_not_a_string_is_named(self):
        """`{"version": 1}` — не версия, а число: строковое сравнение с ним
        зелено по построению, а `str(1)` был бы догадкой о написании."""
        with tempfile.TemporaryDirectory() as tmp:
            root = instance(tmp, '{"version": 1}')
            with self.assertRaises(manifest.Unreadable) as caught:
                manifest.instance_version(root)
            self.assertIn("version", str(caught.exception))

    def test_an_undecodable_marker_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / manifest.MARKER).write_bytes(b'{"version": "\xff"}')
            with self.assertRaises(manifest.Unreadable) as caught:
                manifest.instance_version(root)
            self.assertIn("маркер рецепта", str(caught.exception))


class TestDivergence(unittest.TestCase):
    """Одна строка расхождения либо тишина. Блока нет ни в одном исходе:
    §21 говорит «сообщение, не блок», и `SessionStart` не блокирует вовсе."""

    def line(self, marker):
        with tempfile.TemporaryDirectory() as tmp:
            return manifest.divergence(instance(tmp, marker))

    def test_the_same_version_says_nothing(self):
        self.assertIsNone(
            self.line(json.dumps({"version": manifest.plugin_version()})))

    def test_an_older_instance_is_the_update_event(self):
        line = self.line('{"version": "0.0.1"}')
        self.assertIn("0.0.1", line)
        self.assertIn(manifest.plugin_version(), line)
        self.assertIn("старше", line)

    def test_a_newer_instance_says_there_is_nothing_to_fix(self):
        """§21 дословно: «Инстанс новее плагина — сообщение, не блок.
        Чинить нечего, работа идёт»."""
        line = self.line('{"version": "99.0.0"}')
        self.assertIn("99.0.0", line)
        self.assertIn("чинить нечего", line)

    def test_an_unorderable_version_does_not_invent_an_order(self):
        """`2026-08-30` старше `0.1.0` или младше — вопрос без ответа.
        Назвать порядок значило бы выдумать его (незыблемое №4)."""
        line = self.line('{"version": "2026-08-30"}')
        self.assertIn("2026-08-30", line)
        self.assertIn("порядок не установлен", line)

    def test_the_same_version_spelled_differently_is_still_named(self):
        """Маркер обязан нести версию манифеста, а не эквивалентную ей:
        сравнение формы идёт побайтово, и «1» вместо «1.0.0» — расхождение
        формы, даже когда номер тот же.

        Написание выводится из манифеста, а не стоит литералом: `"0.1"`
        здесь был равен версии только до первого бампа, и релиз `0.1.1`
        покрасил тест, не тронув ни строки продукта."""
        respelled = manifest.plugin_version() + ".0"
        with tempfile.TemporaryDirectory() as tmp:
            root = instance(tmp, json.dumps({"version": respelled}))
            line = manifest.divergence(root)
        self.assertIsNotNone(line)
        self.assertIn("написаны по-разному", line)

    def test_a_broken_marker_stops_the_comparison_and_says_so(self):
        line = self.line("{не json")
        self.assertIn("маркер рецепта", line)
        self.assertIn("сравнивать не с чем", line)

    def test_the_line_is_one_line(self):
        """Строка, а не абзац: она уезжает в контекст сессии на каждом старте."""
        for marker in ('{"version": "0.0.1"}', '{"version": "99.0.0"}',
                       '{"version": "2026-08-30"}', "{не json"):
            self.assertNotIn("\n", self.line(marker), marker)


if __name__ == "__main__":
    unittest.main()
