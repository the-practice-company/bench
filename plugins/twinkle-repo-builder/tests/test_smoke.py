"""Манифест плагина: то, что читает Claude Code при установке пакета.

Проверяется отгружаемый файл, а не выдуманный: путь берётся у `scripts.
manifest`, единственного места в пакете, где он написан.
"""

import json
import unittest
from pathlib import Path

from scripts import manifest

ROOT = Path(__file__).resolve().parent.parent

# Поля, которые формат плагина знает. Закрытое множество, как `TOOL_NAMES`
# в проверке пакета: поле, которого в этом списке нет, ядро молча не читает,
# а автор считает объявленным — ровно тот класс тихой поломки, ради которого
# в этом репозитории заводят закрытые множества. Список — из документации
# формата, сверен `claude plugin validate` на этом же пакете.
KNOWN_FIELDS = frozenset({
    "name", "description", "version", "author", "homepage", "repository",
    "license", "keywords", "metadata", "skills", "commands", "agents",
    "hooks", "mcpServers", "lspServers", "defaultEnabled",
})

# Поля, каждое из которых — путь или перечисление путей внутрь пакета.
# Объявленные, они становятся вторым списком того, что в пакете лежит, и
# расходятся с деревом молча: каталог переименован, поле осталось, и скиллы
# перестают подниматься без единой красной строки. Умолчания формата
# (`skills/`, `hooks/hooks.json`) читают дерево, а не список.
PATH_FIELDS = ("skills", "commands", "agents", "hooks", "mcpServers",
               "lspServers")


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(manifest.MANIFEST.read_text(encoding="utf-8"))

    def test_plugin_manifest_has_name_and_version(self):
        self.assertEqual(self.manifest["name"], "twinkle-repo-builder")
        self.assertRegex(self.manifest["version"], r"^\d+\.\d+\.\d+$")

    def test_it_carries_a_description_and_an_author(self):
        """Оба поля — то, что видно человеку в менеджере плагинов. Без автора
        `claude plugin validate --strict` красный, и это единственное, что он
        находил в этом пакете."""
        self.assertTrue(self.manifest["description"].strip())
        self.assertTrue(self.manifest["author"]["name"].strip())

    def test_no_field_is_outside_what_the_format_reads(self):
        """Выдуманное поле выглядит объявленным и не читается никем."""
        self.assertEqual(sorted(set(self.manifest) - KNOWN_FIELDS), [])

    def test_it_enumerates_no_path_into_the_package(self):
        """Второго перечисления состава пакета нет и не заводится.

        Раскладка §21 — пять вещей, и все пять лежат там, где формат ищет их
        сам. Поле с путём было бы третьим списком того же самого (после
        `check_package._PRODUCT_DIRS` и дерева) и разошлось бы с деревом
        молча — тот же дрейф, которым этот репозиторий уже терял критерий
        выхода.
        """
        declared = [field for field in PATH_FIELDS if field in self.manifest]
        self.assertEqual(declared, [])

    def test_the_places_the_format_looks_at_are_the_shipped_ones(self):
        """Раз пути не объявлены, работает умолчание — и умолчание обязано
        находить отгруженное. Проверяется дерево, а не строка манифеста."""
        self.assertTrue((ROOT / "hooks" / "hooks.json").is_file())
        self.assertTrue(
            sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir()))
        for skill in sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir()):
            self.assertTrue((skill / "SKILL.md").is_file(), skill.name)
