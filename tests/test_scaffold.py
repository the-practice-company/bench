"""Каркас рецепта: инвентарь, содержание артефактов, оба гейта.

Чистая фикстура секции 16 — это сам `scaffold/`, а не копия в `fixtures/`:
проверять надо тот объект, который уезжает пользователю. Красное здесь
означает дефект пакета, а не дефект инстанса.
"""

import re
import unittest
from pathlib import Path

from scripts import paths, zones
from scripts.frontmatter import parse as parse_frontmatter

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "scaffold"

# Разделы, которые несёт README любой зоны. Порядок обязателен: README читают
# сверху вниз, и «что сюда кладётся» обязано стоять раньше порогов.
README_SECTIONS = ("**Membership test.**", "**Shape.**", "**Writing.**",
                   "**By threshold.**")

# Пять зон, которым секция 4 предписывает exemplar; в каркасе его нет ни у
# одной, и README обязан сказать это прямо, а не молчать пустой папкой.
NEEDS_SPECIMEN = ("core", "areas", "projects", "sources", "decisions")
NO_SPECIMEN_LINE = "**Nothing here yet.**"
# Зоны, где пустота — не режим отказа, а норма; там строка обратная.
EMPTY_IS_FINE = ("knowledge", "inbox", "tmp")
EMPTY_IS_FINE_LINE = "**Empty is normal here.**"

_CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def zone_readme(zone):
    return (SCAFFOLD / zone / "README.md").read_text(encoding="utf-8")


class TestZoneReadmes(unittest.TestCase):
    def test_every_zone_has_a_directory_and_a_readme(self):
        self.assertEqual(
            sorted(z for z in zones.ZONES if (SCAFFOLD / z / "README.md").is_file()),
            sorted(zones.ZONES))

    def test_the_scaffold_has_no_zone_beyond_the_eight(self):
        actual = sorted(p.name for p in SCAFFOLD.iterdir()
                        if p.is_dir() and not p.name.startswith("."))
        self.assertEqual(actual, sorted(zones.ZONES))

    def test_every_zone_readme_carries_the_mandatory_sections(self):
        missing = []
        for zone in zones.ZONES:
            text = zone_readme(zone)
            for section in README_SECTIONS:
                if section not in text:
                    missing.append((zone, section))
        self.assertEqual(missing, [])

    def test_a_zone_without_material_says_so(self):
        """Секция 4: «образца здесь нет, спроси прежде чем писать».

        Честнее пустой папки со схемой: агент не гадает, он знает, что зона
        не запущена.
        """
        offenders = []
        for zone in NEEDS_SPECIMEN:
            if NO_SPECIMEN_LINE not in zone_readme(zone):
                offenders.append(zone)
        for zone in EMPTY_IS_FINE:
            if EMPTY_IS_FINE_LINE not in zone_readme(zone):
                offenders.append(zone)
        self.assertEqual(offenders, [])

    def test_no_zone_readme_lists_files(self):
        """Секция 3: перечисление подпапок — можно, перечисление файлов — нельзя.

        Исключения нет и быть не должно: у каркаса нет ни одного файла,
        на который README зоны имел бы право сослаться по имени. Токен
        `README.md` в backtick'ах гейт судит от корня каркаса, где такого
        файла нет, — то есть исключение здесь означало бы находку там.
        """
        offenders = []
        for zone in zones.ZONES:
            for token in re.findall(r"[\w./-]+", zone_readme(zone)):
                if token.endswith(paths.PATH_EXTENSIONS):
                    offenders.append((zone, token))
        self.assertEqual(offenders, [])

    def test_every_zone_readme_is_english(self):
        """Секция 25: форму везёт плагин, значит форма английская.

        Проверка, а не намерение: этот репозиторий пишет по-русски всё, кроме
        каркаса, и соседний файл на расстоянии одной вкладки — русский. Без
        исполняемого признака правило держится только вниманием того, кто
        пишет следующий README (незыблемое №2).
        """
        offenders = []
        for zone in zones.ZONES:
            for lineno, line in enumerate(zone_readme(zone).split("\n"), start=1):
                if _CYRILLIC.search(line):
                    offenders.append((zone, lineno))
        self.assertEqual(offenders, [])


class TestProjectsVocabulary(unittest.TestCase):
    """Словарь `status` объявлен один раз и объяснён без второй копии."""

    def test_the_frontmatter_declares_the_collection(self):
        fields = parse_frontmatter(zone_readme("projects"))
        self.assertEqual(fields["archetype"], "pipeline")
        self.assertEqual(fields["values"]["status"], ["active", "paused", "done"])

    def test_the_prose_explains_exactly_the_declared_values(self):
        """Проза и frontmatter расходятся молча — значит равенство держит тест.

        Сравнение в обе стороны: значение без объяснения и объяснение без
        значения роняют тест одинаково.
        """
        fields = parse_frontmatter(zone_readme("projects"))
        explained = re.findall(r"^- ([a-z]+) — ", zone_readme("projects"), re.M)
        self.assertEqual(explained, fields["values"]["status"])


class TestDecisionsVocabulary(unittest.TestCase):
    def test_the_frontmatter_declares_the_collection(self):
        fields = parse_frontmatter(zone_readme("decisions"))
        self.assertEqual(fields["archetype"], "pipeline")
        self.assertEqual(fields["values"]["status"],
                         ["open", "decided", "revisited"])

    def test_the_prose_explains_exactly_the_declared_values(self):
        fields = parse_frontmatter(zone_readme("decisions"))
        explained = re.findall(r"^- ([a-z]+) — ", zone_readme("decisions"), re.M)
        self.assertEqual(explained, fields["values"]["status"])

    def test_the_three_filter_conditions_are_all_there(self):
        text = zone_readme("decisions")
        for condition in ("rejected alternative", "costs more", "later"):
            self.assertIn(condition, text)
