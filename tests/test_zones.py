import tempfile
import unittest
from pathlib import Path

from scripts import zones

ROOT = Path(__file__).resolve().parent.parent


class TestZones(unittest.TestCase):
    def test_eight_zones_on_two_axes(self):
        self.assertEqual(len(zones.ZONES), 8)
        self.assertEqual(set(zones.SEMANTIC), {"core", "areas", "projects", "knowledge"})
        self.assertEqual(set(zones.PIPELINE), {"inbox", "sources", "tmp", "decisions"})
        self.assertEqual(set(zones.SEMANTIC) & set(zones.PIPELINE), set())

    def test_transient_zones_are_the_ones_that_empty_by_construction(self):
        self.assertEqual(zones.TRANSIENT, frozenset({"tmp", "inbox"}))

    def test_zone_of_reads_first_segment_only(self):
        self.assertEqual(zones.zone_of("areas/hiring/notes.md"), "areas")
        self.assertEqual(zones.zone_of("sources/transcripts/items/a.md"), "sources")
        self.assertIsNone(zones.zone_of("README.md"))
        self.assertIsNone(zones.zone_of("docs/areas/thing.md"))

    def test_deny_patterns_close_foreign_git(self):
        self.assertIn("knowledge/*/**", zones.DENY_PATTERNS)


_NOT_PACKAGE = {".git", "__pycache__", "tests", "fixtures", "docs"}


def _offenders(root):
    """Файлы пакета, держащие свою копию таблицы зон.

    Пропускается ровно канонический `scripts/zones.py`, по относительному
    пути. Пропуск по имени файла делал невидимой любую копию модуля —
    единственный способ завести второе определение, который проверка
    исключала по построению.

    Скан идёт по всему дереву, не только по `scripts/`: критерий 5 —
    «второе определение появилось в пакете», а `hooks/` (волна 2) и
    `scaffold/`+`skills/` (волна 3) — такие же потребители модуля зон, как
    и `scripts/`. Из скана исключены каталоги, не входящие в пакет
    (dev-инструменты и фикстуры из секции 21 спеки: `tests/`, `fixtures/`,
    `docs/`) — иначе этот же файл ловил бы сам себя как офендера.
    """
    root = Path(root)
    names = set(zones.ZONES)
    out = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if rel.as_posix() == "scripts/zones.py":
            continue
        if any(part in _NOT_PACKAGE for part in rel.parts):
            continue
        text = path.read_text(encoding="utf-8")
        hits = {n for n in names if f'"{n}"' in text or f"'{n}'" in text}
        if len(hits) >= 6:
            out.append(f"{rel.as_posix()}: {sorted(hits)}")
    return out


class TestSingleDefinition(unittest.TestCase):
    """Критерий выхода 5: второе определение восьми зон валит тест.

    Эвристика намеренно грубая — файл, перечисляющий шесть и более имён зон
    строковыми литералами, почти наверняка держит свою копию таблицы.
    Спека измерила цену обратного: три разошедшиеся таблицы зон в одном
    репозитории.
    """

    def test_no_second_zone_table_in_package(self):
        self.assertEqual(_offenders(ROOT), [],
                         "второе определение зон — импортируй scripts.zones")

    def test_a_copy_of_zones_py_elsewhere_is_an_offender(self):
        """Регрессия на критерий 5: копия модуля обязана быть офендером."""
        source = (ROOT / "scripts" / "zones.py").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            (fake / "scripts").mkdir()
            (fake / "hooks").mkdir()
            (fake / "scripts" / "zones.py").write_bytes(source)
            (fake / "hooks" / "zones.py").write_bytes(source)
            offenders = _offenders(fake)
        self.assertEqual(len(offenders), 1, offenders)
        self.assertIn("hooks/zones.py", offenders[0])
