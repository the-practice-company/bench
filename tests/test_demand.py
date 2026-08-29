"""Слой спроса: показывает и не действует.

Числа и даты, ни одного вердикта. Часы не читаются: «сегодня» приходит
параметром и обязателен, «последнее касание» — из git.
"""

import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.maintain import demand
from tests.maintain_fixture import materialise


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


def only(findings, cls):
    return [f for f in places(findings) if f[2] == cls]


def git(root, *args, date=None):
    """Тот же пиннинг дат, что у `tests/maintain_fixture.py`."""
    env = dict(os.environ)
    if date is not None:
        stamp = "%sT12:00:00+00:00" % date
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
    return subprocess.run(["git", *args], cwd=str(root), env=env,
                          capture_output=True, text=True, check=True)


def one_commit_repo(base, name, day):
    """Репозиторий, вся история которого — один коммит: форма после ADOPT."""
    root = Path(base) / name
    (root / "projects" / "x" / "items").mkdir(parents=True)
    (root / "projects" / "x" / "README.md").write_text("x\n", encoding="utf-8")
    (root / "projects" / "x" / "views.base").write_text(
        'filters:\n  and:\n    - file.inFolder("projects/x/items")\n',
        encoding="utf-8")
    git(root, "init", "-q")
    git(root, "config", "user.email", "demand@example.invalid")
    git(root, "config", "user.name", "demand")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "как было", date=day)
    return root


# Отчёт целиком, а не одна строка из него. Признак, потерявший направления
# или перепутавший записи с материалом, оставляет посаженное на месте и
# проходит проверку на одно наблюдение.
REPORT = """\
# спрос today=2026-08-29
зона core: материала 2, последнее касание 2026-08-20, дней 9
зона areas: материала 3, последнее касание 2026-08-25, дней 4
зона projects: материала 2, последнее касание 2026-08-28, дней 1
зона knowledge: папки нет
зона inbox: материала 0, последнее касание 2026-05-01, дней 120
зона sources: материала 1, последнее касание 2026-08-15, дней 14
зона tmp: материала 0, последнее касание 2026-05-01, дней 120
зона decisions: материала 0, последнее касание 2026-05-01, дней 120
направление areas/hiring: материала 0, последнее касание 2026-06-20, дней 70
направление areas/work: материала 3, последнее касание 2026-08-25, дней 4
коллекция areas/work/journal: записей 2, последнее касание 2026-08-25, дней 4
коллекция areas/work/reviews: записей 1, последнее касание 2026-06-10, дней 80
коллекция core/people: записей 2, последнее касание 2026-08-20, дней 9
коллекция projects/deals: записей 2, последнее касание 2026-08-27, дней 2
коллекция projects/fresh: записей 0, последнее касание 2026-08-28, дней 1
коллекция projects/stale: записей 0, последнее касание 2026-07-01, дней 59
"""


class TestObservations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)
        self.report, self.findings = demand.run(self.root, today="2026-08-29")

    def test_both_empty_collections_are_named(self):
        self.assertEqual(
            only(self.findings, "empty-collection"),
            [("projects/fresh", 1, "empty-collection", "виды есть, записей ноль"),
             ("projects/stale", 1, "empty-collection", "виды есть, записей ноль")])

    def test_a_view_selecting_an_empty_folder_is_named(self):
        """`areas/work/reviews` называет две папки, пуста из них `drafts/`, а
        сама коллекция при этом не пуста — в этом смысл образца: класс обязан
        отличаться от «пустой коллекции», а на пустой их нечем развести."""
        self.assertEqual(
            only(self.findings, "view-selects-nothing"),
            [("areas/work/reviews", 1, "view-selects-nothing",
              "file.inFolder называет папку с нулём записей: "
              "areas/work/reviews/drafts"),
             ("projects/fresh", 1, "view-selects-nothing",
              "file.inFolder называет папку с нулём записей: "
              "projects/fresh/items"),
             ("projects/stale", 1, "view-selects-nothing",
              "file.inFolder называет папку с нулём записей: "
              "projects/stale/items")])

    def test_a_declared_direction_without_material_is_named(self):
        """Список целиком: признак, красящий все направления и зоны подряд,
        посаженное наблюдение тоже показывает."""
        self.assertEqual(
            only(self.findings, "declared-unused"),
            [("areas/hiring", 1, "declared-unused",
              "направление объявлено, материала нет"),
             ("decisions", 1, "declared-unused", "зона объявлена, материала нет"),
             ("inbox", 1, "declared-unused", "зона объявлена, материала нет"),
             ("tmp", 1, "declared-unused", "зона объявлена, материала нет")])

    def test_no_other_classes_are_produced(self):
        self.assertEqual(sorted({f.cls for f in self.findings}),
                         ["declared-unused", "empty-collection",
                          "view-selects-nothing"])

    def test_the_report_carries_dates_and_no_verdicts(self):
        """§27 отверг меру потому, что порога назвать нельзя. Показ — не мера:
        разница в том, кто делает вывод."""
        for word in ("протухл", "устарел", "пора", "мало", "слишком"):
            self.assertNotIn(word, self.report.lower(), word)
        self.assertIn("2026-07-01", self.report)

    def test_the_report_is_exact(self):
        self.assertEqual(self.report, REPORT)


class TestNothingOnDiskChanged(unittest.TestCase):
    """Read-only доказывается хешем дерева, как у гейтов волны 1.

    Дерево своё, а не общее с `TestObservations`: там прогон случается в
    `setUp`, и снимок «до», взятый после него, уже содержит всё, что прогон
    записал. Слой, пишущий на диск одно и то же, прошёл бы такую проверку
    зелёным — измерено посаженной записью в `OPEN-THREADS.md`.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def digest(self):
        h = hashlib.sha256()
        for path in sorted(p for p in self.root.rglob("*") if p.is_file()):
            if ".git/" in path.as_posix():
                continue
            h.update(path.relative_to(self.root).as_posix().encode("utf-8"))
            h.update(path.read_bytes())
        return h.hexdigest()

    def test_nothing_on_disk_changed(self):
        before = self.digest()
        demand.run(self.root, today="2026-08-29")
        self.assertEqual(self.digest(), before)

    def test_a_second_run_says_the_same(self):
        """Инвариант 2 волны: второй прогон не меняет ни байта — и отчёт
        показа тоже, иначе дерево становилось бы грязным на каждом ходе."""
        first = demand.run(self.root, today="2026-08-29")
        before = self.digest()
        self.assertEqual(demand.run(self.root, today="2026-08-29")[0], first[0])
        self.assertEqual(self.digest(), before)


class TestAges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_the_age_is_counted_from_git_and_not_from_the_file_system(self):
        """`st_mtime` переставляется чекаутом, и возраст начал бы зависеть от
        того, когда гоняли набор. Это буквально мутация, пережившая проверку
        волны 1."""
        self.assertEqual(demand.age(self.root, "projects/stale", "2026-08-29"), 59)
        self.assertEqual(demand.age(self.root, "projects/fresh", "2026-08-29"), 1)

    def test_today_is_mandatory(self):
        """У гейтов волны 1 `--today` необязателен; там его отсутствие меняет
        текст отчёта, здесь — удаляет папку."""
        with self.assertRaises(TypeError):
            demand.run(self.root)

    def test_the_command_refuses_to_run_without_today(self):
        """Отказ argparse'а, а не подставленное умолчание. Ругань самого
        argparse'а уводится: набор судят по отказу, а не по его тексту."""
        with io.StringIO() as noise, contextlib.redirect_stderr(noise):
            with self.assertRaises(SystemExit):
                demand.main([str(self.root)])

    def test_the_boundary_of_the_blindness_is_named(self):
        """Видимая история короче порога — числа нет ни у чего: любое число
        дней меньше порога по построению и решить ничего не может. Граница
        утверждается поимённо, история в 30 дней даёт число, в 29 — токен.
        `vault` тронут 2026-05-20, история начинается 2026-05-01."""
        self.assertEqual(demand.age(self.root, "vault", "2026-05-31"), 11)
        self.assertEqual(demand.age(self.root, "vault", "2026-05-30"),
                         "history-starts-2026-05-01")

    def test_a_touch_later_than_today_gets_no_number(self):
        """Коммит позже названного дня в видимой истории не лежит, и число
        дней вышло бы отрицательным — правдоподобной неправдой со знаком."""
        self.assertEqual(demand.age(self.root, "projects/fresh", "2026-07-30"),
                         "history-starts-2026-05-01")
        self.assertEqual(demand.age(self.root, "projects/stale", "2026-05-15"),
                         "history-starts-2026-05-01")

    def test_a_path_git_never_committed_says_so(self):
        """Папку зоны заводит слой «форма содержательно», и до первого коммита
        касания у неё нет вовсе. Пустота на этом месте прочиталась бы как
        «тронуто сегодня»."""
        (self.root / "knowledge").mkdir()
        self.assertEqual(demand.age(self.root, "knowledge", "2026-08-29"),
                         "no-commit")

    def test_git_failure_is_not_silence(self):
        """Незыблемое №4: не сумев спросить git, слой отказывает, а не молчит."""
        shutil.rmtree(self.root / ".git")
        with self.assertRaises(RuntimeError):
            demand.run(self.root, today="2026-08-29")


class TestTheCalendar(unittest.TestCase):
    """Календарь посчитан в пакете руками, и это сверяется с образцом.

    `scripts/` не импортирует `datetime` вовсе: критерий 2 требует, чтобы
    часов там не было, и запрет выражен именами модулей. Набору импорт
    разрешён — здесь он и стоит, в роли образца, а не в роли часов.
    """

    def test_the_ordinal_matches_the_standard_library_over_two_centuries(self):
        """Шаг в 97 дней — простое число, поэтому обход перебирает все дни
        недели и все месяцы, а не топчется по одним и тем же числам. Две
        границы века внутри: правило «каждый четвёртый», написанное без
        исключения на 1900 и 2100, врёт не на границе месяца, а там."""
        day = date(1897, 1, 1)
        while day < date(2112, 1, 1):
            self.assertEqual(demand._ordinal(day.isoformat()), day.toordinal(),
                             day.isoformat())
            day += timedelta(days=97)

    def test_the_named_boundaries_are_counted_by_hand(self):
        """Числа фикстуры литералами: тест не должен уметь считать так же,
        как считает продукт."""
        self.assertEqual(demand._ordinal("2026-08-29") - demand._ordinal("2026-07-01"),
                         59)
        self.assertEqual(demand._ordinal("2026-07-31") - demand._ordinal("2026-07-01"),
                         30)
        self.assertEqual(demand._ordinal("2024-03-01") - demand._ordinal("2024-02-28"),
                         2)
        self.assertEqual(demand._ordinal("2026-03-01") - demand._ordinal("2026-02-28"),
                         1)
        self.assertEqual(demand._ordinal("2100-03-01") - demand._ordinal("2100-02-28"),
                         1)


class TestAfterAnAdoption(unittest.TestCase):
    """Названное ограничение спеки: слой спроса слеп после ADOPT.

    История начинается коммитом «как было», поэтому у каждого пути последний
    коммит — сегодняшний. Ноль дней здесь был бы правдоподобной неправдой.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = one_commit_repo(self.tmp.name, "adopted", "2026-08-29")

    def test_every_unit_says_where_history_starts_instead_of_zero(self):
        self.assertEqual(demand.age(self.root, "projects/x", "2026-08-29"),
                         "history-starts-2026-08-29")

    def test_the_report_carries_no_day_counts_at_all(self):
        report, _ = demand.run(self.root, today="2026-08-29")
        self.assertNotIn("дней", report)
        self.assertIn("history-starts-2026-08-29", report)


class TestASubmodulePin(unittest.TestCase):
    """Дата закоммиченного пина: локальный git, без сети, без порога, без
    вердикта. Собирается настоящий сабмодуль: в фикстуре `knowledge/` нет
    вовсе, и утверждение о пине на ней нечем покраснеть."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        source = Path(self.tmp.name) / "atlas-source"
        (source / "people" / "items").mkdir(parents=True)
        (source / "people" / "README.md").write_text("чужое\n", encoding="utf-8")
        (source / "people" / "views.base").write_text(
            'filters:\n  and:\n    - file.inFolder("people/items")\n',
            encoding="utf-8")
        (source / "people" / "items" / "кто-то.md").write_text("x\n",
                                                               encoding="utf-8")
        git(source, "init", "-q")
        git(source, "config", "user.email", "atlas@example.invalid")
        git(source, "config", "user.name", "atlas")
        git(source, "add", "-A")
        git(source, "commit", "-q", "-m", "атлас", date="2026-01-05")

        self.root = materialise(self.tmp.name)
        git(self.root, "-c", "protocol.file.allow=always", "submodule", "add",
            "-q", str(source), "knowledge/atlas")
        git(self.root, "commit", "-q", "-m", "знание: атлас", date="2026-06-15")
        self.report, self.findings = demand.run(self.root, today="2026-08-29")

    def test_the_pin_date_is_shown_without_a_verdict(self):
        self.assertIn("пин сабмодуля knowledge/atlas: 2026-06-15", self.report)

    def test_a_collection_inside_the_submodule_is_not_counted(self):
        """Вид внутри чужого репозитория принадлежит его хозяину. Посчитанный
        здесь, он ушёл бы дальше в удаление по порогу — то есть плагин
        дотянулся бы до чужого дерева."""
        self.assertEqual([c for c in demand.collections(self.root)
                          if c.startswith("knowledge/")], [])
        self.assertEqual([f for f in places(self.findings)
                          if f[0].startswith("knowledge/")], [])


if __name__ == "__main__":
    unittest.main()
