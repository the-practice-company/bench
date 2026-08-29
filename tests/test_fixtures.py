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
| `orphan` 1 | транскрипт, на который никто не сослался |

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
| `missing-required` 3 | `no-status.md`: нет `status`, который читает вид, и нет `created` из стартового набора; `bad-status.md`: нет `created` |
| `value-outside-vocabulary` 1 | `status: активно` при словаре коллекции `[open, decided, revisited]` |
| `unparseable` 1 | блочный скаляр в `broken-yaml.md` |

`description` из `order` вида требованием не является — вид его показывает, но
не группирует по нему и не сортирует, поэтому в `missing-required` он не
попадает. Отсюда 3, а не 5.
"""

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
                "orphan": 1,
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
                ("CLAUDE.md", 3, "unresolved", "`scripts/move.py`"),
                ("CLAUDE.md", 4, "escapes-root", "`/Users/artem/notes.md`"),
                ("CLAUDE.md", 8, "escapes-root", "`~/vault/**/*.md`"),
                ("areas/hiring/bare.md", 4, "ambiguous",
                 "[[dup]] → areas/hiring/dup.md, core/dup.md"),
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
                 "поле status читает вид"),
                ("decisions/items/no-status.md", 1, "missing-required",
                 "стартовый набор: поле created"),
            ],
        )

    def test_green_sample_is_silent_on_both_gates(self):
        self.assertEqual(check_links.scan(GREEN).counts(), {})
        self.assertEqual(check_frontmatter.scan(GREEN).counts(), {})


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
        """
        offenders = []
        for path in sorted((ROOT / "scripts").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for marker in ("import datetime", "import time", "datetime.now",
                           "date.today", "time.time"):
                if marker in text:
                    offenders.append("%s: %s" % (path.name, marker))
        self.assertEqual(offenders, [])

    def test_today_is_carried_on_the_report(self):
        """Принятый параметр обязан быть наблюдаем, а не проглочен молча."""
        self.assertEqual(check_links.scan(BROKEN, today="2026-01-01").today,
                          "2026-01-01")
        self.assertIsNone(check_links.scan(BROKEN).today)
        self.assertEqual(check_frontmatter.scan(BROKEN, today="2026-01-01").today,
                          "2026-01-01")
