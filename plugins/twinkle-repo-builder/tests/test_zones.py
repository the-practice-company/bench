import re
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

    def test_self_development_zones_are_named_in_the_table(self):
        """Зоны собственной разработки — часть таблицы, а не литералы у потребителя.

        Их читает периметр проверки пакета: этот репозиторий удваивается под
        контекст-репозиторий своей же разработки, и абсолютный путь в чужой
        цитате внутри них не находка о пакете. Пока имена стояли строками в
        `check_package.py`, это была частичная копия таблицы зон — из двух
        имён, то есть невидимая для `TestSingleDefinition` по построению.
        """
        self.assertEqual(zones.SELF_DEVELOPMENT, frozenset({"inbox", "sources"}))
        self.assertLessEqual(zones.SELF_DEVELOPMENT, frozenset(zones.ZONES))


_NOT_PACKAGE = {".git", "__pycache__", "tests", "fixtures", "docs"}

# Имя зоны, как оно встречается в тексте: в кавычках или без. Счёт только по
# кавычкам не видел копию таблицы, написанную одним литералом —
# `tuple("core areas projects ... decisions".split())` набирал ноль вхождений
# и проходил. Это тот же вид дыры, что и пропуск офендера по имени файла:
# копия таблицы, невидимая для проверки на копии.
#
# Границы шире `\b` на дефис: `drain-inbox` — имя скилла, а не зона, и
# считать его за вхождение значило бы подтягивать счёт файлам, которые
# таблицы не держат. Косая и точка границей остаются: `knowledge/*/**` в
# комментарии — вхождение, и это верно, поэтому порог в шесть имён.
_BARE = {name: re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(name))
         for name in zones.ZONES}


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
        hits = {n for n in names if _BARE[n].search(text)}
        if len(hits) >= 6:
            out.append(f"{rel.as_posix()}: {sorted(hits)}")
    return out


class TestSingleDefinition(unittest.TestCase):
    """Критерий выхода 5: второе определение восьми зон валит тест.

    Эвристика намеренно грубая — файл, называющий шесть и более имён зон,
    почти наверняка держит свою копию таблицы. Как именно они записаны,
    значения не имеет: счёт по кавычкам пропускал копию, собранную из одной
    строки. Спека измерила цену обратного: три разошедшиеся таблицы зон в
    одном репозитории.
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

    def test_a_split_string_copy_of_the_table_is_an_offender(self):
        """Копия таблицы одной строкой: счёт по кавычкам её не видел вовсе.

        Восемь имён внутри одного литерала не дают ни одного вхождения вида
        `"core"` — детектор копий насчитывал ноль и пропускал файл. Это тот
        же вид дыры, который тут уже чинили: копия таблицы, невидимая для
        проверки на копии.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            (fake / "hooks").mkdir()
            (fake / "hooks" / "zones.py").write_text(
                'ZONES = tuple("core areas projects knowledge inbox sources tmp'
                ' decisions".split())\n',
                encoding="utf-8")
            offenders = _offenders(fake)
        self.assertEqual(len(offenders), 1, offenders)
        self.assertIn("hooks/zones.py", offenders[0])
