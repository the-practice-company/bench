"""Точный список находок обоих гейтов на фикстурах и детерминизм отчёта.

Каждое число ниже заработано образцом из состава фикстуры (Task 7 плана), а не
прогоном гейта. Подгонять ожидание под вывод запрещено: тогда тест перестаёт
быть проверкой и становится снимком поведения, включая ошибочного.

Гейт ссылок — образец за образцом:

| класс | образцы |
|---|---|
| `unresolved` 5 | `[[несуществующая заметка]]` в `areas/hiring/note.md`; `scripts/move.py` в `CLAUDE.md` («его нет»); `areas/hiring/items/` и `scripts/rename.py` в `.claude/rules/areas.md`; `[[projects/dup]]` в `areas/hiring/pathlink.md` — путь не существует, откат на basename запрещён |
| `md-link-to-file` 1 | `[профиль](../../core/me.md)` |
| `link-to-transient` 1 | `[[tmp/plan]]` из `areas`, цель `tmp/plan.md` |
| `escapes-root` 3 | абсолютный путь в `CLAUDE.md`, `[[../../../soseddniy-repo/file]]` и глоб `~/vault/**/*.md` в `CLAUDE.md` |
| `ambiguous` 1 | `[[dup]]` при двух `dup.md` |
| `dead-allow` 2 | строка без причины и строка, ничего не исключающая |
| `broad-allow` 1 | запись `*тень*` — подстрока в глоб-написании, гасит обе ссылки `areas/hiring/broad.md` |
| `orphan` 1 | транскрипт, на который никто не сослался |
| `undecodable` 1 | `areas/hiring/cp1251.md` — выгрузка из старого редактора не в UTF-8 |

Про `unresolved` 4, а не 3, как стоит в таблице Task 13. Таблица перечислила три
образца и не досчитала четвёртый, который сама же и положила: `.claude/rules/
areas.md` — файл, заведённый в фикстуру с подписью «rule-файл, ссылающийся на
переименованную папку». Переименованная папка — это `areas/hiring/items/`:
записи лежат прямо в `areas/hiring/`, `items/` не существует. Образец в
фикстуре есть, класс он поднимает по делу, значит число — 4. Решение записано
в журнале как DEC-0003.

Про деталь `link-to-transient`: в ней стоит разрешённая цель, а не только текст
ссылки. Класс судится после резолва — `[[scratch]]`, единственная форма, которую
пишет Obsidian, зоны в тексте не несёт вовсе, — и без цели в отчёте автору
нечем понять, почему `[[scratch]]` вдруг ссылка в `tmp/`.

Про `escapes-root`: абсолютный путь — backtick-токен, а токены спека читает
только в `CLAUDE.md`, `README.md`, `SKILL.md` и `.claude/rules/*.md`. Поэтому
образец лежит в `CLAUDE.md` фикстуры, а не в `areas/hiring/escapes.md`, как
писал Task 7: периметр сканирования переезжать за образцом не может (DEC-0003).

Про `undecodable` и `broad-allow`: этих двух классов в таблице секции 13 нет.
Оба заведены под поломки, наблюдённые на живом выводе, и оба вынесены автору
правкой спеки (незыблемое №7). Первый — вместо чтения с заменой байта: гейт
называл цель `[[???????]]`, которой никто не писал. Второй — вместо запрета
одного лишь синтаксиса подстроки: `*тень*` гасит по всему репозиторию и
считается использованной, поэтому `dead-allow` о ней молчит.

Образец `undecodable` не даёт шестого `unresolved`, и это часть проверки:
внутри `cp1251.md` стоит ссылка в никуда, которая обязана остаться
непрочитанной. Вернётся чтение с заменой — `unresolved` станет 6, и список
покраснеет.

Третий образец `escapes-root` — глоб `~/vault/**/*.md`, и он тут не для счёта.
Строка спеки «глоб — шаблон, а не путь» приглашает отсеять глоб входным
фильтром и не проверять вовсе; тогда шаблон получает право выйти за корень,
которого нет у конкретного пути. Образец фальсифицирует ровно это прочтение:
у глоба не спрашивают, существует ли такой файл, но границу корня он
пересекает так же незаконно. Зеркальная половина правила — в зелёной фикстуре:
`.claude/settings.json` с `**/knowledge/**` и `Edit(./knowledge/*/**)`,
предписанными секцией 4, обязан давать ноль находок. До этого правила каркас,
который спека предписывает, не проходил гейт, который спека предписывает,
и волна 3 упиралась в это как в блокер.

Гейт frontmatter — образец за образцом:

| класс | образцы |
|---|---|
| `missing-required` 3 | `no-status.md`: нет `status`, обязательного архетипу `pipeline`, и нет `created` из стартового набора; `bad-status.md`: нет `created` |
| `value-outside-vocabulary` 1 | `status: активно` при словаре коллекции `[open, decided, revisited]` |
| `unparseable` 1 | блочный скаляр в `broken-yaml.md` |

`description` из `order` вида требованием не является — вид его показывает, но
не группирует по нему и не сортирует, поэтому в `missing-required` он не
попадает. Отсюда 3, а не 5.

Причина у `status` названа архетипом, хотя вид коллекции по нему ещё и
группирует: источники контракта перечислены секцией 14 по старшинству, и
стартовый набор стоит раньше вида. Требование архетипа переживёт правку
вида, требование вида — нет, и автору чинить надо то, что глубже. Одно поле
даёт одну находку, а не две: это один факт о записи.

Словарь в `decisions/README.md` объявлен **блочным списком** — формой, которой
Obsidian Properties пишет multi-value свойство. Раньше там стоял flow-список,
и вся дорога «блочный список внутри вложенной мапы» фикстурой не проверялась:
на ней разбор падал, гейт глотал отказ, и коллекция оставалась без словаря.
Flow-форма осталась в зелёной фикстуре — проверяются обе.
"""

import ast
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_frontmatter, check_links
from scripts.findings import Finding

ROOT = Path(__file__).resolve().parent.parent
BROKEN = ROOT / "fixtures" / "broken"
GREEN = ROOT / "fixtures" / "green"


def places(report):
    """Находки как (путь, строка, класс, деталь) в порядке отчёта.

    Деталь входит в ключ намеренно: без неё находки с одинаковыми путём,
    строкой и классом взаимозаменяемы, и подмена одного правила другим
    набор не роняет.
    """
    return [(f.path, f.line, f.cls, f.detail)
            for f in sorted(report.findings, key=Finding.key)]


class TestExactFindings(unittest.TestCase):
    def test_link_gate_finds_exactly_this(self):
        self.assertEqual(
            check_links.scan(BROKEN).counts(),
            {
                "unresolved": 5,
                "md-link-to-file": 1,
                "link-to-transient": 1,
                "escapes-root": 3,
                "ambiguous": 1,
                "dead-allow": 2,
                "broad-allow": 1,
                "orphan": 1,
                "undecodable": 1,
            },
        )

    def test_every_link_finding_sits_on_its_own_specimen(self):
        """Счётчик не различает «нашёл то» и «нашёл столько же не того»."""
        self.assertEqual(
            places(check_links.scan(BROKEN)),
            [
                (".claude/rules/areas.md", 5, "unresolved", "`areas/hiring/items/`"),
                (".claude/rules/areas.md", 5, "unresolved", "`scripts/rename.py`"),
                (".link-allow", 2, "dead-allow", "строка без причины: будущая-заметка"),
                (".link-allow", 3, "dead-allow",
                 "правило ничего не исключает, удалите: уже-не-нужное"),
                (".link-allow", 4, "broad-allow",
                 "правило не привязано ни к месту, ни к имени, сузьте: *тень* "
                 "(гасит: тень-вторая, тень-первая)"),
                ("CLAUDE.md", 3, "unresolved", "`scripts/move.py`"),
                ("CLAUDE.md", 4, "escapes-root", "`/Users/artem/notes.md`"),
                ("CLAUDE.md", 8, "escapes-root", "`~/vault/**/*.md`"),
                ("areas/hiring/bare.md", 4, "ambiguous",
                 "[[dup]] → areas/hiring/dup.md, core/dup.md"),
                ("areas/hiring/cp1251.md", 1, "undecodable",
                 "не читается как UTF-8: байт 0xc7 в позиции 19, "
                 "ссылки в нём не проверены"),
                ("areas/hiring/escapes.md", 4, "escapes-root",
                 "[[../../../soseddniy-repo/file]]"),
                ("areas/hiring/md-link.md", 4, "md-link-to-file",
                 "[профиль](../../core/me.md)"),
                ("areas/hiring/note.md", 4, "unresolved", "[[несуществующая заметка]]"),
                ("areas/hiring/pathlink.md", 6, "unresolved", "[[projects/dup]]"),
                ("areas/hiring/transient.md", 4, "link-to-transient",
                 "[[tmp/plan]] → tmp/plan.md"),
                ("sources/transcripts/items/2026-07-14-call.md", 1, "orphan",
                 "на файл никто не сослался"),
            ],
        )

    def test_frontmatter_gate_finds_exactly_this(self):
        self.assertEqual(
            check_frontmatter.scan(BROKEN).counts(),
            {"missing-required": 3, "value-outside-vocabulary": 1, "unparseable": 1},
        )

    def test_every_frontmatter_finding_sits_on_its_own_specimen(self):
        self.assertEqual(
            places(check_frontmatter.scan(BROKEN)),
            [
                ("decisions/items/bad-status.md", 1, "missing-required",
                 "стартовый набор: поле created"),
                ("decisions/items/bad-status.md", 1, "value-outside-vocabulary",
                 "status='активно' вне словаря ['open', 'decided', 'revisited']"),
                ("decisions/items/broken-yaml.md", 4, "unparseable",
                 "блочный скаляр не поддерживается (строка 4)"),
                ("decisions/items/no-status.md", 1, "missing-required",
                 "стартовый набор: поле created"),
                ("decisions/items/no-status.md", 1, "missing-required",
                 "стартовый набор: поле status у архетипа pipeline"),
            ],
        )

    def test_green_sample_is_silent_on_both_gates(self):
        self.assertEqual(check_links.scan(GREEN).counts(), {})
        self.assertEqual(check_frontmatter.scan(GREEN).counts(), {})


# Модули, чей импорт в гейте запрещён целиком. Запрещается импорт, а не
# отдельный вызов: у каждого из них столько написаний текущего момента, что
# перечислять их — заводить второй неполный список рядом с этим.
#
# Часы по назначению:
#   datetime  — `datetime.now()`, `date.today()`;
#   time      — `time.time()`, `time.monotonic()`, `time.localtime()`;
#   calendar  — часы в один шаг: модуль сам держит `import datetime`, поэтому
#               `calendar.datetime.date.today()` работает, не называя datetime
#               ни разу. Признак имени этого не видит вообще;
#   zoneinfo  — сам момента не читает, но существует только ради datetime.
#               Стоит здесь растяжкой: его появление в гейте означает, что
#               время приехало дорогой, которой в этом списке нет.
#
# Не часы, но ровно та же поломка — отчёт перестаёт быть побайтово тем же:
#   random    — сеется на процесс, второй прогон даёт другой отчёт;
#   uuid      — `uuid1()` кладёт в значение текущее время, `uuid4()` — random
#               под другим именем.
#
# Не часы и не про воспроизводимость:
#   importlib — динамический импорт обесценивает весь список выше, превращая
#               запрет в пожелание. Гейту незачем импортировать по строке.
_CLOCK_MODULES = frozenset({
    "datetime", "time", "calendar", "zoneinfo",
    "random", "uuid",
    "importlib",
})

# Написания текущего момента через модуль, который запретить нельзя: `os` и
# `pathlib` держат тут всё, от обхода дерева до чтения файла.
#
#   st_atime/st_ctime/st_mtime/st_birthtime и формы `_ns` — отметки времени
#     файла. Ровно это и посадил аудит: `Path(__file__).stat().st_mtime`
#     внутри `scan()` пережил подстрочный поиск, не уронив ни одного теста;
#   stat/lstat — вызов, в который заходят только ради полей выше. Запрет шире
#     нужного намеренно: половина полей `stat_result` — время, и гейт, которому
#     вдруг понадобился `st_size`, обязан это обосновать, а не пройти молча;
#   getmtime/getctime/getatime — те же отметки написанием `os.path`;
#   times/utime — текущий момент написанием `os`: `os.times()` читает время
#     процесса, `os.utime(path)` без второго аргумента ставит текущее.
#
# `time.monotonic` и родня сюда не входят: назвать их, не назвав `time`,
# нельзя, а `time` запрещён строкой выше. Дублировать запрет — делать вид, что
# список полнее, чем он есть.
_CLOCK_ATTRS = frozenset({
    "st_atime", "st_ctime", "st_mtime", "st_birthtime",
    "st_atime_ns", "st_ctime_ns", "st_mtime_ns", "st_birthtime_ns",
    "stat", "lstat",
    "getmtime", "getctime", "getatime",
    "times", "utime",
})

# Имя вызова, а не поле: снимается только оно.
_STAT_CALLS = frozenset({"stat", "lstat"})

# Обоснованные `stat` пакета, по одной строке с причиной. Запрет на
# `stat`/`lstat` шире нужного намеренно (см. `_CLOCK_ATTRS`), и модуль,
# которому понадобился `st_size`, «обязан это обосновать, а не пройти молча»
# — вот место, где он это делает. Снимается ровно имя вызова: `st_mtime`
# и родня остаются запрещены везде, включая перечисленные файлы, поэтому
# исключение открывает размер и не открывает часы.
#
# `scan-tree` считает вес поддерева. Прочесть размер иначе нечем:
# `len(read_bytes())` втягивает в память те самые гигабайты, ради которых
# инвентарь и считается каталогами, а не файлами.
_STAT_ALLOWED = {
    "scripts/adopt/inventory.py": "вес поддерева: st_size, без отметок времени",
}


def _clock_reads(tree, stat_allowed=False):
    """Обращения к часам в разобранном модуле: (строка, написание).

    Читается дерево разбора, а не текст. Подстрочный поиск не различает код и
    прозу — в `scripts/check_package.py` слова `os.remove` и `git restore`
    стоят в комментариях, — и не видит переименования: `import time as t`,
    `from datetime import datetime as dt`. Оба различия для этой проверки
    решающие.

    `stat_allowed` снимает `stat`/`lstat` и больше ничего: файл из
    `_STAT_ALLOWED` по-прежнему краснеет на `st_mtime`.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _CLOCK_MODULES:
                    yield node.lineno, "import %s" % alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or "."
            if module.split(".")[0] in _CLOCK_MODULES:
                yield node.lineno, "from %s import ..." % module
            for alias in node.names:
                if alias.name in _CLOCK_ATTRS:
                    yield node.lineno, "from %s import %s" % (module, alias.name)
        elif isinstance(node, ast.Attribute):
            if node.attr in _CLOCK_ATTRS:
                if stat_allowed and node.attr in _STAT_CALLS:
                    continue
                yield node.lineno, ".%s" % node.attr


class TestDeterminism(unittest.TestCase):
    def test_report_is_identical_from_another_checkout_location(self):
        first = check_links.scan(BROKEN).render()
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "другое-место"
            shutil.copytree(BROKEN, copy)
            second = check_links.scan(copy).render()
        self.assertEqual(first, second)

    def test_exit_code_is_two_on_the_broken_fixture(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_links.py"), str(BROKEN)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unresolved", result.stdout)

    def test_exit_code_is_zero_on_the_green_sample(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_links.py"), str(GREEN)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_no_module_in_scripts_reads_the_clock(self):
        """Настоящая гарантия детерминизма: часов в гейтах нет вовсе.

        `--today` существует ради правил, зависящих от даты (волна 5). Пока
        таких правил нет, единственное, что делает отчёт воспроизводимым, —
        отсутствие обращений к часам.

        Проверка читает код разбором, а не поиском подстрок. Прошлая её версия
        искала пять литералов, и аудит посадил два настоящих чтения часов —
        `Path(__file__).stat().st_mtime` внутри `scan()` и `import calendar`,
        — которые пережили её оба, не уронив ни одного теста. Список запретов
        и причина каждой строки — у `_CLOCK_MODULES` и `_CLOCK_ATTRS`.

        Дефект был не только в узости списка. Мутация, которая эту проверку
        убивала, сажала `import datetime` — первый же литерал, который
        проверка искала. Она доказывала, что список содержит собственную
        запись, а не что гейты обходятся без часов.

        **Чего разбор не видит.** Список остаточного риска — часть проверки,
        как `bashscan.UNCATCHABLE`: без него молчание проверки читается как
        доказательство, которым оно не является.

        - **часы через имя, собранное на исполнении**: `getattr(os, "st" +
          "at")`, `importlib.import_module(name)`, `__import__(name)`. Разбор
          читает имена как написано. `importlib` поэтому и стоит в запрете
          модулей — закрыть эту дорогу целиком нечем, но открывать её
          импортом незачем;
        - **часы в дочернем процессе**: `check_package.py` запускает и гейты,
          и `unittest` через `subprocess.run`. Видно вызов, а не то, что
          делает ребёнок;
        - **дата из среды**: `os.environ` в гейте есть по делу
          (`_NESTED_RUN_GUARD`), и разбор не судит, что лежит в переменной;
        - **часы в модуле вне `scripts/`**. Проверка обходит каталог целиком,
          вглубь, а не граф импортов. Сегодня `scripts/` импортирует только
          из `scripts/`, и замыкание совпадает с каталогом; в день, когда
          гейт потянет что-нибудь из `hooks/`, часы `hooks/summary.py`
          приедут внутрь незамеченными.

        **Про `hooks/` проверка намеренно не расширена.** Критерий 2 говорит
        про отчёт гейта, а сводка хука отчётом гейта не является: она про
        текущее состояние дерева, читает `git status` и `git log`, и требовать
        от неё побайтового совпадения между прогонами бессмысленно —
        совпадать ей не с чем. `hooks/summary.py` уже держит `import datetime`
        и делает им разбор, а не чтение часов
        (`datetime.date.fromisoformat`); распространить запрет на `hooks/`
        значит покраснеть на законном разборе даты и научить чинить это
        исключением. Дорога от хуков к часам всё равно короче любого запрета
        имён: они зовут `git`, а тот докладывает настоящие отметки времени, —
        и запрет на `import datetime` этого не трогает.
        """
        walked = [p.relative_to(ROOT).as_posix()
                  for p in sorted((ROOT / "scripts").rglob("*.py"))]
        offenders = []
        for rel in walked:
            path = ROOT / rel
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            offenders.extend(
                "%s:%d: %s" % (rel, line, spelling)
                for line, spelling in _clock_reads(tree, rel in _STAT_ALLOWED))
        self.assertEqual(offenders, [])
        # Обход рекурсивный, и это утверждается, а не подразумевается: пока
        # он был `glob("*.py")`, весь пакет `scripts/adopt/` лежал вне
        # критерия 2 — часы в нём не увидел бы никто. Имя в отчёте тоже
        # относительное: двух `inventory.py` на разных этажах `path.name`
        # не различает.
        self.assertIn("scripts/adopt/inventory.py", walked)

    def test_every_stat_allowance_is_live_and_opens_only_the_call(self):
        """Уцелевшее исключение тихо ослабляет проверку — довод `dead-allow`
        гейта ссылок, дословно. Плюс вторая половина: снятое имя вызова не
        снимает отметок времени, иначе исключение открывало бы часы."""
        for rel, reason in _STAT_ALLOWED.items():
            path = ROOT / rel
            self.assertTrue(path.exists(), rel)
            self.assertTrue(reason.strip(), rel)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            self.assertIn(".stat", [s for _, s in _clock_reads(tree)], rel)
        planted = ast.parse("import pathlib\n"
                            "x = pathlib.Path('.').stat().st_mtime\n")
        self.assertEqual([s for _, s in _clock_reads(planted, stat_allowed=True)],
                         [".st_mtime"])

    def test_today_is_carried_on_the_report(self):
        """Принятый параметр обязан быть наблюдаем, а не проглочен молча."""
        self.assertEqual(check_links.scan(BROKEN, today="2026-01-01").today,
                          "2026-01-01")
        self.assertIsNone(check_links.scan(BROKEN).today)
        self.assertEqual(check_frontmatter.scan(BROKEN, today="2026-01-01").today,
                          "2026-01-01")
