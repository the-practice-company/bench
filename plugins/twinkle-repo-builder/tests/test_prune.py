"""Критерий 2: показывает спрос и не действует по нему.

Единственное исключение — пустая коллекция за порогом: содержимого в ней нет
по определению, поэтому удаление не пересекает линию ответственности.
Соблазнительный случай не выдуман: обе коллекции пусты, кодовый путь удаления
существует и авторизован, удерживает только порог.
"""

import contextlib
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from scripts.adopt import drop, tree
from scripts.findings import EXIT_OK
from scripts.maintain import content_diff, demand, prune
from tests.maintain_fixture import materialise


def dirs(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                  if p.is_dir() and ".git" not in p.parts)


# Отчёт целиком, а не одна строка из него. Порог, промолчавший про
# `projects/fresh`, показал бы ровно то же самое «удалена projects/stale».
REPORT = """\
# порог 30 дней, today=2026-08-29
коллекция projects/fresh: пуста, дней 1
коллекция projects/stale: пуста, дней 59
удалена: projects/stale, дней 59
"""


class TestThreshold(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_only_the_collection_past_the_threshold_is_removed(self):
        removed, _ = prune.run(self.root, today="2026-08-29")
        self.assertEqual(removed, ["projects/stale"])
        self.assertFalse((self.root / "projects" / "stale").exists())
        self.assertTrue((self.root / "projects" / "fresh").exists())

    def test_the_removal_goes_through_git_and_the_content_stays_in_history(self):
        """Удаление — это `drop`, а `drop` ходит через индекс.

        Обе половины утверждаются, потому что порознь ни одна не разводит
        `git rm` и `shutil.rmtree`: в коммите содержимое остаётся при любом
        способе — историю никто не переписывает, — а мимо индекса удалённый
        путь остаётся отслеженным, то есть дерево грязно не тем, чем думает
        само-проверка волны, и `revert` подметает по `ls-files --others`
        совсем другое множество.
        """
        prune.run(self.root, today="2026-08-29")
        self.assertEqual(
            tree.git_zlines(self.root, "ls-files", "-z", "--", "projects/stale"),
            [])
        self.assertEqual(
            sorted(tree.git_zlines(self.root, "ls-tree", "-r", "--name-only",
                                   "-z", "HEAD", "--", "projects/stale")),
            ["projects/stale/README.md", "projects/stale/items/.gitkeep",
             "projects/stale/views.base"])

    def test_the_set_of_directories_changed_by_exactly_one(self):
        before = set(dirs(self.root))
        prune.run(self.root, today="2026-08-29")
        after = set(dirs(self.root))
        self.assertEqual(sorted(before - after),
                         ["projects/stale", "projects/stale/items"])
        self.assertEqual(after - before, set())

    def test_the_other_two_classes_are_not_accompanied_by_any_change(self):
        """`declared-unused` и `view-selects-nothing` показываются и не
        действуют: направление без материала и папка, которую вид выбирает
        вхолостую, остаются на месте."""
        prune.run(self.root, today="2026-08-29")
        self.assertTrue((self.root / "areas" / "hiring").is_dir())
        self.assertTrue((self.root / "areas" / "work" / "reviews"
                         / "drafts").is_dir())

    def test_content_diff_is_empty_for_the_removal(self):
        before = content_diff.snapshot(self.root)
        removed, _ = prune.run(self.root, today="2026-08-29")
        self.assertEqual(
            content_diff.compare(before, content_diff.snapshot(self.root),
                                 deleted=removed), [])

    def test_exactly_thirty_days_is_removed_and_twenty_nine_is_not(self):
        """Граница утверждается, а не «примерно так». Порог включающий:
        `projects/stale` тронута 2026-07-01, значит 2026-07-31 — ровно 30
        дней и удаление, 2026-07-30 — 29 дней и не удаление."""
        self.assertEqual(prune.run(self.root, today="2026-07-30")[0], [])
        self.assertTrue((self.root / "projects" / "stale").is_dir())
        self.assertEqual(prune.run(self.root, today="2026-07-31")[0],
                         ["projects/stale"])

    def test_a_collection_with_a_record_is_never_removed(self):
        removed, _ = prune.run(self.root, today="2030-01-01")
        self.assertNotIn("core/people", removed)
        self.assertNotIn("areas/work/journal", removed)
        self.assertTrue((self.root / "core" / "people" / "items"
                         / "anna.md").exists())

    def test_an_empty_zone_is_never_removed(self):
        """Зон всегда восемь. `inbox`, `tmp` и `decisions` пусты и объявлены
        неиспользуемыми — коллекциями они от этого не становятся."""
        removed, _ = prune.run(self.root, today="2030-01-01")
        self.assertEqual([r for r in removed if "/" not in r], [])
        for zone in ("inbox", "tmp", "decisions"):
            self.assertTrue((self.root / zone).is_dir(), zone)

    def test_the_report_is_exact(self):
        _, report = prune.run(self.root, today="2026-08-29")
        self.assertEqual(report, REPORT)


class TestTodayIsMandatory(unittest.TestCase):
    """У гейтов волны 1 `--today` необязателен; там его отсутствие меняет
    текст отчёта, здесь — удаляет папку."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_the_call_refuses_without_today(self):
        with self.assertRaises(TypeError):
            prune.run(self.root)

    def test_the_command_refuses_without_today(self):
        """Отказ argparse'а, а не подставленное умолчание. Ругань самого
        argparse'а уводится: набор судят по отказу, а не по его тексту."""
        with io.StringIO() as noise, contextlib.redirect_stderr(noise):
            with self.assertRaises(SystemExit):
                prune.main([str(self.root)])
        self.assertTrue((self.root / "projects" / "stale").is_dir())

    def test_the_command_line_carries_the_removal_through(self):
        with io.StringIO() as out, contextlib.redirect_stdout(out):
            code = prune.main([str(self.root), "--today", "2026-08-29"])
            printed = out.getvalue()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(printed, REPORT)
        self.assertFalse((self.root / "projects" / "stale").exists())


class TestFalsifiers(unittest.TestCase):
    """Четыре реализации, обязанные покраснеть. Каждая — подменённая функция,
    а не испорченное заранее дерево: фальсифицируется код, а не вход."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_prune_without_a_threshold_removes_both(self):
        """Первый: удаляющий обе. Кодовый путь удаления существует и
        авторизован; удерживает только порог."""
        with mock.patch.object(demand, "THRESHOLD_DAYS", 0):
            removed, _ = prune.run(self.root, today="2026-08-29")
        self.assertEqual(removed, ["projects/fresh", "projects/stale"])

    def test_reading_the_clock_instead_of_today_changes_the_answer(self):
        """Второй: часы вместо параметра. Подмена читает `date.today()` там,
        где продукт читает аргумент, — и ответ обязан разойтись.

        Предпосылка названа вслух: прогон случается позже 2026-07-31, то есть
        позже границы, которую спрашивает этот тест. Для `--today 2026-07-30`
        честный ответ пуст, а часы дают возраст за порогом.
        """
        self.assertGreaterEqual(date.today().isoformat(), "2026-07-31",
                                "часы машины отстают от истории фикстуры")
        honest = demand.age

        def clock_age(root, rel, today):
            del today                     # ровно это делает `date.today()`
            return honest(root, rel, date.today().isoformat())

        self.assertEqual(prune.run(self.root, today="2026-07-30")[0], [])
        with mock.patch.object(demand, "age", clock_age):
            self.assertEqual(prune.run(self.root, today="2026-07-30")[0],
                             ["projects/stale"])

    def test_st_mtime_instead_of_git_gives_a_different_age(self):
        """Третий, и он измерен: чекаут переставляет `st_mtime`, поэтому
        возраст, посчитанный по нему, у только что развёрнутой фикстуры
        нулевой — а git знает 2026-07-01."""
        def mtime_age(root, rel, today):
            del today
            touched = date.fromtimestamp((Path(root) / rel).stat().st_mtime)
            return (date.today() - touched).days

        self.assertLess(mtime_age(self.root, "projects/stale", "2026-08-29"),
                        demand.THRESHOLD_DAYS)
        self.assertEqual(demand.age(self.root, "projects/stale", "2026-08-29"),
                         59)
        with mock.patch.object(demand, "age", mtime_age):
            self.assertEqual(prune.run(self.root, today="2026-08-29")[0], [])

    def test_shifting_the_boundary_by_one_changes_the_verdict(self):
        """Четвёртый: порог, сдвинутый на день. Граница включающая, и сдвиг
        на единицу — это ровно разница между `>=` и `>`: на 2026-07-31
        коллекции ровно 30 дней."""
        self.assertEqual(prune.run(self.root, today="2026-07-31")[0],
                         ["projects/stale"])
        self.root = materialise(self.tmp.name, name="shifted")
        with mock.patch.object(demand, "THRESHOLD_DAYS", 31):
            self.assertEqual(prune.run(self.root, today="2026-07-31")[0], [])


class TestTheThresholdIsDefinedOnce(unittest.TestCase):
    """Порог живёт у слоя спроса, и удаляющий берёт его оттуда же.

    Второе определение разошлось бы с первым молча: показ говорил бы про
    тридцать дней, а удаление случалось бы на двадцатом.
    """

    def test_prune_carries_no_threshold_of_its_own(self):
        self.assertNotIn("THRESHOLD_DAYS", vars(prune))

    def test_the_reason_is_the_key_of_the_closed_set(self):
        """Литерал причины пишется один раз: строка, разошедшаяся с ключом
        закрытого множества, отказывала бы в удалении молча и навсегда."""
        self.assertIn(prune.REASON, drop.AUTHORISED)


if __name__ == "__main__":
    unittest.main()
