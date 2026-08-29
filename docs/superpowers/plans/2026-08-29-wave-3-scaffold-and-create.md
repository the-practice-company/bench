# Волна 3. Каркас и CREATE — план реализации

> **Исполнителю:** обязательный под-скилл — `superpowers:subagent-driven-development`
> либо `superpowers:executing-plans`. Шаги отмечаются чекбоксами.

**Цель:** в пакете лежит `scaffold/` — физическая папка, которая копируется
побайтово и проходит оба гейта с нулём находок, в том числе с удалённым
`.claude/`; скилл `create-context-repo` разворачивает её первым коммитом,
байт в байт равным пакетному каркасу, и не сочиняет ни одной записи за автора.

**Архитектура:** каркас — данные, не код. Копирование и слияние настроек —
один детерминированный скрипт (`scripts/install_scaffold.py`), суждение
(три вопроса, что считать настоящей записью) — скилл. Гейты волны 1
импортируются модулями и на каркасе обязаны молчать.

**Стек:** Python 3 stdlib, git, POSIX sh. Ноль зависимостей.

**Спека волны:** `docs/superpowers/specs/2026-08-29-wave-3-scaffold-and-create-design.md`
**Общая спека:** секции 1–5, 8–10, 17, 21, 22, 25
**Критерии выхода:** `docs/roadmap.md`, «Волна 3»

## Состояние плана

**Задачи 1–8 исполнены** — код в дереве, `./check` зелёный, галочки проставлены.
Перечитывать и переисполнять их не нужно: гейт frontmatter больше не считает
README коллекции записью; восемь зон, восемь README, `CLAUDE.md`, одиннадцать
`.claude/rules/*.md` и четыре мелких артефакта (`.gitignore`,
`.twinkle-repo-builder`, `OPEN-THREADS.md`, `settings-fragment.json`) лежат
в `scaffold/`; инвентарь утверждён поимённо — двадцать четыре файла и десять
каталогов, — оба гейта на каркасе молчат, и с удалённым `.claude/` тоже.
`scripts/install_scaffold.py` разворачивает каркас в репозиторий, а критерий 2
волны утверждён по хешам объектов git: коммит из отчёта установщика равен
каркасу побайтово, с единственным исключением `.claude/settings.json`.

**Начинать с задачи 9.**

---

## Что уже проверено и не переоткрывается

Сверено по коду волны 1, а не по памяти. Опираться на это можно.

| факт | следствие для каркаса |
|---|---|
| периметр backtick-сканирования — `CLAUDE.md`, `README.md`, `SKILL.md`, `.claude/rules/*.md` (`check_links._scanned_for_tokens`) | каждый backtick-токен в этих файлах каркаса судится как путь |
| признак пути (`paths.is_path_token`) — есть `/`, либо закрытое расширение `.md .py .sh .json .base`, либо ведущий `/`/`~`; токен с пробелом — не путь | `views.base`, `README.md`, `items/` в backtick'ах — **находки**: у каркаса нет таких путей от корня |
| глоб дальше существования не проверяется, но границу корня не отменяет (`_classify_token`) | `**/items/**`, `**/*.base`, `**/README.md` в backtick'ах законны |
| `_settings_paths` читает `.claude/settings*.json` и разворачивает `Инструмент(аргумент)` | `settings-fragment.json` **попадает** под этот проход: `**/knowledge/**` и `Edit(./knowledge/*/**)` дают ноль находок, это уже доказано зелёной фикстурой |
| `check_frontmatter.scan` заходит только туда, где есть `views.base` | каркас без коллекций гейт frontmatter проходит тривиально; правка гейта нужна ради инстанса, а не ради каркаса |
| `_ignored` собирает из `.gitignore` три вещи: обычную строку — в префикс `строка + "/"`, строку с `!` — в `Ignored.negated`, отказ чтения самого файла — в `Ignored.undecodable`. `_in_perimeter` применяет отрицания **раньше** префикса и, не найдя префикса, сверяет запись `fnmatchcase`'ом как имя файла | все пять строк `.gitignore` каркаса работают: каталоги (`.trash/`, `node_modules/`, `__pycache__/`) снимаются префиксом, а `.DS_Store` и `.obsidian/workspace*.json` — файловой формой, которой префикс не ловил никогда. Отрицаний каркас не везёт: `!` в его `.gitignore` нет ни одного, и заводить их волна 3 не будет |
| `check_package._iter_package_files` не пропускает `scaffold/` (в `SKIP_AT_ROOT` его нет) | каркас сканируется на `absolute-path` наравне со `scripts/` |
| `check_links` не запускается на корне пакета ни одним тестом | backtick-токены каркаса судятся только когда корнем гейта назначен сам `scaffold/` |
| `dev/mutate.py` уже несёт мутацию, подписанную «в3 К1» | таблицу мутаций волна 3 дополняет, а не заводит |

---

## Расхождения, найденные при планировании

Незыблемое №7: спека — источник истины, разошлись — правится спека. Ниже то,
что план исполняет иначе, чем написано, и почему. Каждое обратимо; каждое
обязано доехать до автора отдельной строкой в трекере.

**1. «Двадцать два артефакта» не сходится ни с одним прочтением состава.**
Спека волны перечисляет: восемь папок зон, восемь `README.md`, одиннадцать
правил, `CLAUDE.md`, `.gitignore`, `.twinkle-repo-builder`, фрагмент настроек,
`OPEN-THREADS.md`. Это 24 файла (или 32 объекта вместе с каталогами), и
«остальные двадцать копируются как есть» не получается ни при каком счёте.
План перечисляет инвентарь поимённо и утверждает его тестом: **24 файла,
8 каталогов зон**. Число из спеки не воспроизводится и подлежит правке.

**2. Из двух «не-копий» некопией остаётся одна.** `.claude/settings.json`
в каркасе физически отсутствует — вместо него едет `settings-fragment.json`,
и это решение той же спеки. `.twinkle-repo-builder` копией быть **может**:
внутри одного релиза он побайтово одинаков во всех инстансах, а равенство его
`version` манифесту плагина держится тестом (`§21`: «версия одна»). Итог:
23 файла копируются, 1 сливается, фрагмент в инстанс не едет вовсе.

**3. Хеш дерева коммита против хеша `scaffold/` не может совпасть никогда.**
Проверочная таблица спеки предписывает буквально это, но коммит 1 несёт
`.claude/settings.json` (слит) и не несёт `settings-fragment.json`.
План сверяет **по-путное соответствие blob-хешей** с одним поимённо названным
исключением — это сравнение хешей, а не глазами, и оно выполнимо.

**4. §5 против §17 в headless без брифа.** §5: «единственная коллекция,
которая заводится всегда, — `decisions`». §17 и спека волны: без брифа
не заводится ни одной коллекции. Обе не могут быть верны. План берёт §17:
коллекция без настоящей записи не заводится, а «всегда» из §5 верно для
диалогового пути, где запись гарантирована самим разговором.

**5. `.gitignore` каркаса шире, чем три строки спеки волны.** §8 называет
исключёнными `.trash`, `.obsidian`, `.git`, `node_modules`, и у этого списка
нет **ни одного** механизма доставки: `_ignored` знает только `.git/` и
`archive/`, остальное приходит из `.gitignore`. Без строки `.trash/` гейт
читает удалённые в Obsidian заметки и находит в них дохлые ссылки в первом же
живом инстансе. План кладёт пять строк, а не три; расхождение названо здесь.

**6. Смежная дыра волны 1 — закрыта до начала волны 3, расхождением больше
не является.** План писался, когда `_in_perimeter` сравнивал только префиксы,
и запись `.gitignore` об **одном файле** (`.claude/settings.local.json`)
превращалась в префикс `…json/`, не совпадающий ни с чем: абсолютный путь
в машинно-локальных настройках автора становился `escapes-root` в каждом
инстансе. Сейчас `_in_perimeter` проверяет обе формы — поддерево префиксом,
файл `fnmatchcase`'ом, — а докстринг `check_package._is_ignored`, который
раньше утверждал обратное («гейт ссылок читает только `*.md`»), переписан
и называет цену той неправды. Проверено прогоном: дерево с
`.gitignore`-строкой `.claude/settings.local.json` и абсолютным путём внутри
самого файла даёт ноль находок, без строки — `escapes-root`. Автору эта
строка не едет; она стоит здесь, чтобы её не «нашли» третий раз.

**7. Мелочь в §9.** «Меняют его только описание домена, неформализуемые
запреты и **указатели**» соседствует с решением ниже удалить раздел
«Указатели» из скелета. Скелет-фенса авторитетен, план идёт по нему.

---

## Структура файлов

| файл | ответственность |
|---|---|
| `scaffold/CLAUDE.md` | скелет секции 9: карта зон, правило размещения, домен не заполнен |
| `scaffold/<зона>/README.md` × 8 | политика зоны дословно по таблицам секции 4 |
| `scaffold/.claude/rules/*.md` × 11 | правила с областью действия по пути (секция 9) |
| `scaffold/.claude/settings-fragment.json` | `claudeMdExcludes` и `permissions.deny` — сливается, не копируется |
| `scaffold/.gitignore` | периметр гейтов |
| `scaffold/.twinkle-repo-builder` | версия рецепта, однополевая |
| `scaffold/OPEN-THREADS.md` | адрес всего, на что не нашлось ответа |
| `scripts/boundary.py` | переезжает из `hooks/` целиком: граница рабочего каталога — общий модуль, у неё два потребителя, а определение обязано быть одно |
| `scripts/install_scaffold.py` | копия каркаса + слияние настроек, одна детерминированная операция |
| `skills/create-context-repo/SKILL.md` | порядок, три вопроса, два коммита |
| `skills/create-context-repo/eval.txt` | фразы срабатывания на обоих языках и соседние, по которым не должен |
| `tests/test_scaffold.py` | инвентарь, содержание каждого артефакта, оба гейта, прогон без `.claude/` |
| `tests/test_install_scaffold.py` | копия побайтово, слияние настроек, первый коммит |
| `tests/test_create_skill.py` | форма скилла и его эвал |

Разделение по ответственности: каркас (данные) проверяется отдельно от
установщика (код) и отдельно от скилла (процедура). Фикстуры каркас себе
не заводит: чистая фикстура секции 16 — это сам `scaffold/`, и именно
поэтому проверять его надо там, где он лежит.

---

## Task 1: Гейт frontmatter — README коллекции не запись

Первой идёт правка гейта: инстанс, у которого появился `projects/views.base`,
иначе получает находку на файле, который рецепт сам и положил.

`projects/README.md` — политика зоны и объявление коллекции (`archetype`,
`values`), а `projects/<имя>/README.md` — запись. Перечисление записей идёт
`rglob("*.md")` по папке из `file.inFolder(...)`, и при фильтре по `projects`
оно сметает README самой коллекции.

**Files:**
- Modify: `scripts/check_frontmatter.py`
- Test: `tests/test_check_frontmatter.py`

- [x] **Step 1: Написать падающий тест**

Дописать в `tests/test_check_frontmatter.py`:

```python
import tempfile
from pathlib import Path

from scripts import check_frontmatter
from scripts.findings import Finding


def _places(report):
    return [(f.path, f.line, f.cls, f.detail)
            for f in sorted(report.findings, key=Finding.key)]


COLLECTION_VIEW = """\
filters:
  and:
    - file.inFolder("projects")
    - 'type == "project"'
views:
  - type: table
    groupBy: status
    order:
      - description
"""

ZONE_README = """\
---
archetype: pipeline
values:
  status: [active, paused, done]
---
# projects

Policy of the zone, not a record.
"""

PROJECT_README = """\
---
type: project
created: 2026-08-29
status: active
description: One line
---
# alpha
"""


class TestCollectionOwnReadme(unittest.TestCase):
    """Исключение: проект — папка, и её README одновременно политика и запись.

    Собственный README коллекции записью не становится (секция 2: «он лежит
    уровнем выше и в виды не попадает»), но при фильтре по папке зоны он
    оказывается внутри перечисления и требует `type` и `created` — от файла,
    который положил сам рецепт.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "projects" / "alpha").mkdir(parents=True)
        (self.root / "projects" / "views.base").write_text(
            COLLECTION_VIEW, encoding="utf-8")
        (self.root / "projects" / "README.md").write_text(
            ZONE_README, encoding="utf-8")
        (self.root / "projects" / "alpha" / "README.md").write_text(
            PROJECT_README, encoding="utf-8")

    def test_the_collections_own_readme_is_not_a_record(self):
        self.assertEqual(_places(check_frontmatter.scan(self.root)), [])

    def test_a_project_readme_is_still_a_record(self):
        """Послабление ровно на один файл: README проекта проверяется как был."""
        (self.root / "projects" / "alpha" / "README.md").write_text(
            PROJECT_README.replace("created: 2026-08-29\n", ""), encoding="utf-8")
        self.assertEqual(
            _places(check_frontmatter.scan(self.root)),
            [("projects/alpha/README.md", 1, "missing-required",
              "стартовый набор: поле created")],
        )

    def test_the_declaration_still_feeds_the_vocabulary(self):
        """Исключение снимает файл с перечисления, но не с чтения словаря."""
        (self.root / "projects" / "alpha" / "README.md").write_text(
            PROJECT_README.replace("status: active", "status: живой"),
            encoding="utf-8")
        self.assertEqual(
            _places(check_frontmatter.scan(self.root)),
            [("projects/alpha/README.md", 1, "value-outside-vocabulary",
              "status='живой' вне словаря ['active', 'paused', 'done']")],
        )
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_frontmatter -v`
Expected: `test_the_collections_own_readme_is_not_a_record` FAIL — вместо
пустого списка приходят три находки на `projects/README.md`:
`стартовый набор: поле type`, `стартовый набор: поле created`,
`поле status читает вид`. Два остальных теста проходят и остаются
сторожами послабления.

- [x] **Step 3: Реализация**

В `scripts/check_frontmatter.py`, внутри `scan`, после вычисления `readme`:

```python
        # README самой коллекции — её объявление (`archetype` и `values`),
        # а не запись. В перечисление он попадает только когда вид фильтрует
        # по папке коллекции целиком: так устроен `projects` — политика зоны
        # лежит рядом с `views.base`, а записи уровнем ниже. Требовать от
        # него `type` и `created` значит сажать находку на файл, который
        # положил сам рецепт, в каждом инстансе. Исключение ровно на один
        # путь: `projects/<имя>/README.md` — запись и проверяется как запись
        # (секция 4, единственное место, где README является записью).
        declaration = readme.resolve()

        for folder in base.folders:
            records_dir = root / folder
            if not records_dir.exists():
                continue
            for record in sorted(records_dir.rglob("*.md")):
                if record.resolve() == declaration:
                    continue
                rel = record.relative_to(root).as_posix()
```

`resolve()` с обеих сторон, а не сравнение `Path`-объектов: `readme`
собирается от `base_path.parent`, а `record` — от `root / folder`, и на
симлинке или ином написании корня один и тот же файл дал бы два разных пути.

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_frontmatter tests.test_fixtures -v`
Expected: зелено; счёт находок на битой фикстуре не изменился
(`missing-required` 3, `value-outside-vocabulary` 1, `unparseable` 1) —
там фильтр идёт по `decisions/items`, и README коллекции в перечисление
не попадал никогда.

- [x] **Step 5: Коммит**

```bash
git add scripts/check_frontmatter.py tests/test_check_frontmatter.py
git commit -m "wave3: README коллекции — объявление, а не запись"
```

---

## Task 2: Восемь зон и восемь README

Каркас заводится с того, без чего он не каркас. Тексты ниже — перенос таблиц
секции 4, строка в строку: **назначение, тест принадлежности, вид, запись,
README, коллекции, exemplar, порог**. Сочинять здесь нечего.

Английский — секция 25: всё в каркасе форма, форму везёт плагин.

**Files:**
- Create: `scaffold/{core,areas,projects,knowledge,inbox,sources,tmp,decisions}/README.md`
- Test: `tests/test_scaffold.py`

- [x] **Step 1: Написать падающий тест**

```python
"""Каркас рецепта: инвентарь, содержание артефактов, оба гейта.

Чистая фикстура секции 16 — это сам `scaffold/`, а не копия в `fixtures/`:
проверять надо тот объект, который уезжает пользователю. Красное здесь
означает дефект пакета, а не дефект инстанса.
"""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import check_frontmatter, check_links, paths, zones
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
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_scaffold -v`
Expected: все FAIL — каталога `scaffold/` не существует, первым падает
`test_every_zone_has_a_directory_and_a_readme`.

- [x] **Step 3: Реализация — `scaffold/core/README.md`**

```markdown
# core

The slow layer: who we are and what we are guided by.

**Membership test.** The answer this file gives stays true when the quarter
changes and when the project changes.

**Shape.** A folder of documents, subfolders by topic. No collection by
default.

**Writing.** Creating is free. Rewriting an existing document asks the author
first: the agent reads this zone before everything else and interprets the
rest through it, so an error here poisons every later judgement.

**Boundary.** The current state of a direction lives in `areas/`. Something
with a completion criterion lives in `projects/`. A choice with a named
rejected alternative lives in `decisions/`.

**Nothing here yet.** There is no document in this zone — ask before writing.

**By threshold.** Subfolders by topic once there are more than seven
documents. A collection of principles once the question "which principles
apply to X" appears.
```

- [x] **Step 4: Реализация — `scaffold/areas/README.md`**

```markdown
# areas

Working directories of directions that do not end.

**Membership test.** There is a level of quality that is kept up, and there is
no completion criterion.

**Shape.** One folder per direction; inside it anything the direction needs —
dated data, nested collections, arbitrary formats.

**Writing.** Creating is free. Rewriting an existing file asks the author
first: this zone is read as the current state of affairs.

**Boundary.** Something that can be finished is a project and lives in
`projects/`. Expertise that would be true without us lives in `knowledge/`.
Material as received lives in `sources/`.

**Dated data is welcome here.** A file that is an entry on a date rather than
a statement about now says so in its own fields; the zone does not split.

**Nothing here yet.** There is no direction in this zone — ask before writing.

**By threshold.** A new direction once a stream of work appears. A collection
inside a direction once its records are of one kind and a question "which of
them X" appears.
```

- [x] **Step 5: Реализация — `scaffold/projects/README.md`**

```markdown
---
archetype: pipeline
values:
  status: [active, paused, done]
---
# projects

Finite undertakings.

**Membership test.** A completion criterion can be named. Not a deadline —
a deadline is not an invariant, completability is.

**Shape.** A collection of folders, one per project. A project's own README is
at once the folder's policy and the collection's record: it carries the record
fields and the view shows it. This is the only README that is a record, and
the reason is that a project is one thing — splitting its card from its
material breaks it in half.

**Writing.** Free.

**Status vocabulary.**

- active — being worked on
- paused — deliberately set aside and meant to be picked up
- done — the completion criterion is met

The machine-readable copy of these three words is this file's frontmatter;
there is no third place where they are written down.

**A finished project stays where it is** with its status changed. There is no
archive: history is kept by git, and an archive inside the working tree is
read by the agent as current.

**Nothing here yet.** There is no project in this zone — ask before writing.

**By threshold.** A "done" view once the first project reaches that status.
```

- [x] **Step 6: Реализация — `scaffold/knowledge/README.md`**

```markdown
# knowledge

The connection point for external expertise.

**Membership test.** This statement would still be true if we did not exist.
Not "how our hiring is going" but "how hiring works".

**Shape.** Mount points of external repositories, connected as git submodules,
one folder per base.

**Writing.** Nobody. Knowledge bases live in their own repositories; here they
are only read. A static deny rule in this repository's Claude settings holds
it, so it does not depend on anyone's judgement. This README is the exception —
the zone itself is ours.

**Trust.** For each connected base: where it came from and what in it can be
relied on. Written when the base is connected.

**Empty is normal here.** There may be no bases at all. This is not a zone
that failed to start.

**By threshold.** A new base is added by connecting a submodule.
```

- [x] **Step 7: Реализация — `scaffold/inbox/README.md`**

```markdown
# inbox

A single entry point for anything whose nature is not yet decided.

**Membership test.** It has not been decided what this is.

**Shape.** Arbitrary files, one per captured item.

**Writing.** Append only. Sorting an item out means moving it, not editing it
in place.

**Where things go from here.** Material as received — `sources/`. Something
with a completion criterion — `projects/`. The current state of a direction —
`areas/`. A choice with a named rejected alternative — `decisions/`. A session
leftover — `tmp/`.

**Nothing stays here for ever.** An item that has been sitting here for a long
time is a signal about the pipeline, not about the item.

**Empty is normal here.** This is the one zone where emptiness at creation is
not a failure mode: the value of the zone is that capture costs no decision.

**By threshold.** A skill for sorting out once doing it by hand becomes
tiresome.
```

- [x] **Step 8: Реализация — `scaffold/sources/README.md`**

```markdown
# sources

Raw material as it was received.

**Membership test.** Received, not written. True as a record of a fact, not as
a statement about the present.

**Shape.** Arbitrary files — transcripts, exports, résumés, articles — with
optional companion records.

**Writing.** Append only, and immutable afterwards. A source is never edited
and never corrected: a mistake inside it is part of the record. This is the
only layer where what was actually said is written down; everything else is
interpretation, and a disagreement is settled by coming back here.

**Naming convention.** Date first, then what it is: 2026-07-14-call-with-x.

**Link direction is fixed: derived → source, never the other way.** One source
feeds several consumers; a copy in each gives N diverging copies and no
canonical one. A source that nobody has linked to is unprocessed material.

**Nothing here yet.** There is no source in this zone — ask before writing.

**By threshold.** Subfolders by type once there is more than one type. A
collection of companion records once sources need filtering.
```

- [x] **Step 9: Реализация — `scaffold/tmp/README.md`**

```markdown
# tmp

The workbench: artefacts of sessions and tasks with a limited life.

**Membership test.** This stops being needed when the task ends.

**Shape.** Anything.

**Writing.** Free, deletion included.

**Nothing here is a source of truth.** What has ripened moves out by the
placement rule; what has not is deleted.

**Nothing long-lived links here.** `core/`, `areas/` and `knowledge/` outlive
this zone, so a link from them into it is a breakage on a delay.

**Empty is normal here.** The zone exists in advance so that what the agent
produces along the way has somewhere to land instead of being held in context
and lost.

**By threshold.** None.
```

- [x] **Step 10: Реализация — `scaffold/decisions/README.md`**

```markdown
---
archetype: pipeline
values:
  status: [open, decided, revisited]
---
# decisions

Closed questions, kept so that the agent does not reopen them.

**Membership test.** Three conditions, all of them required:

1. There was a named rejected alternative. No alternative means an action, not
   a decision.
2. Reversing it costs more than taking it. Free to undo — not written down.
3. It will bear on decisions taken later by someone who does not remember it.

In practice: if in three months someone proposes the opposite, do I want the
agent to object by pointing at this record? No — it does not belong here.

**Shape.** A collection: one file per decision, plus views.

**Writing.** Append only. A decision is not edited; it is superseded by a new
record that links back to the one it replaces.

**Status vocabulary.**

- open — the question is stated and not closed
- decided — the choice is made
- revisited — reopened and replaced by a later record

The machine-readable copy of these three words is this file's frontmatter;
there is no third place where they are written down.

**Nothing here yet.** There is no decision in this zone — ask before writing.

**By threshold.** A "due for review" view with the first record that carries a
review trigger. A field for grouping once there are enough records to group.
```

- [x] **Step 11: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_scaffold -v`
Expected: зелено.

Две ловушки, каждая стоила бы находки в гейте на Task 6, и обе уже обойдены
в текстах выше — не расшивать их обратно:

- `2026-07-14-call-with-x` в `sources/README.md` идёт **без расширения**.
  `2026-07-14-call.md` в backtick'ах стал бы `unresolved`: закрытое
  расширение делает токен путём, а такого пути от корня каркаса нет.
- слово README в `projects/README.md` идёт **без backtick'ов**. Проверено:
  `is_path_token("README.md")` истинно, а `README.md` от корня каркаса
  не существует — токен в backtick'ах дал бы `unresolved`. Правится каркас,
  не гейт: периметр за образцом не переезжает.

- [x] **Step 12: Коммит**

```bash
git add scaffold/core/README.md scaffold/areas/README.md \
        scaffold/projects/README.md scaffold/knowledge/README.md \
        scaffold/inbox/README.md scaffold/sources/README.md \
        scaffold/tmp/README.md scaffold/decisions/README.md \
        tests/test_scaffold.py
git commit -m "wave3: восемь зон и восемь README по таблицам секции 4"
```

---

## Task 3: `CLAUDE.md` каркаса

Скелет секции 9 дословно, по-английски. Раздел «Указатели» удалён намеренно —
его работу взял на себя слой правил, и возвращать его нельзя.

**Files:**
- Create: `scaffold/CLAUDE.md`
- Modify: `tests/test_scaffold.py`

- [x] **Step 1: Написать падающий тест**

```python
# Права записи в карте — единственное исключение из теста «какая проверка
# упадёт». Их держит PreToolUse, но агент обязан знать до попытки, иначе
# тратит ход на exit 2. Одно слово в колонке, не правило.
WRITE_RULE = {
    "core": "confirm before rewriting",
    "areas": "confirm before rewriting",
    "projects": "free",
    "knowledge": "do not write",
    "inbox": "append only",
    "sources": "append only",
    "tmp": "free",
    "decisions": "append only",
}

DOMAIN_PLACEHOLDER = "Domain not described yet"
ZONE_ROW = re.compile(r"^\| (\w+)/ +\| ([^|]+?) +\| ([^|]+?) +\|$", re.M)


class TestGeneratedClaudeMd(unittest.TestCase):
    def setUp(self):
        self.text = (SCAFFOLD / "CLAUDE.md").read_text(encoding="utf-8")

    def test_the_zone_map_names_the_eight_zones_in_order(self):
        self.assertEqual([row[0] for row in ZONE_ROW.findall(self.text)],
                         list(zones.ZONES))

    def test_every_zone_row_carries_its_write_rule(self):
        self.assertEqual({row[0]: row[2] for row in ZONE_ROW.findall(self.text)},
                         WRITE_RULE)

    def test_the_placement_rule_asks_the_pipeline_question_first(self):
        first = self.text.index("1.")
        second = self.text.index("2.")
        self.assertLess(first, second)
        self.assertIn("pipeline zone", self.text[first:second])
        self.assertIn("semantic zone", self.text[second:])

    def test_it_lists_no_files(self):
        """Критерий 4 волны: карта зон и правило размещения — да, файлы — нет.

        Признак механический: токен с закрытым расширением. Перечисление
        файлов начинается именно с него, в backtick'ах или без.
        """
        offenders = [token for token in re.findall(r"[\w./-]+", self.text)
                     if token.endswith(paths.PATH_EXTENSIONS)]
        self.assertEqual(offenders, [])

    def test_the_domain_line_is_an_explicit_placeholder(self):
        """Незыблемое №4: невосстановимое помечается, а не подставляется молча.

        Домен в коммите 1 неизвестен, и строка об этом говорит вслух. CREATE
        заменяет её ответом автора в коммите 2; в headless без брифа она
        остаётся, а вопрос уезжает в открытые нити.
        """
        self.assertEqual(self.text.count(DOMAIN_PLACEHOLDER), 1)

    def test_it_says_which_language_it_is_in(self):
        """Секция 25: без этой строки агент в русском репозитории
        подстраивается под инструкции и начинает отвечать по-английски."""
        self.assertIn("English by convention", self.text)

    def test_there_is_no_pointers_section(self):
        """Раздел удалён вместе с появлением path-scoped rules и не возвращается."""
        self.assertNotIn("## Pointers", self.text)

    def test_it_asks_whether_a_gate_could_hold_the_rule(self):
        self.assertIn("could hold it", self.text)
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_scaffold.TestGeneratedClaudeMd -v`
Expected: все FAIL с `FileNotFoundError` — `scaffold/CLAUDE.md` нет.

- [x] **Step 3: Реализация — `scaffold/CLAUDE.md`**

```markdown
# Context repository

Domain not described yet — this line is a placeholder, replaced with one or
two sentences about what is kept here.

## Zone map

| zone | purpose | writing |
|---|---|---|
| core/ | what everything else is read through | confirm before rewriting |
| areas/ | directions that do not end | confirm before rewriting |
| projects/ | finite undertakings | free |
| knowledge/ | external expertise | do not write |
| inbox/ | entry point | append only |
| sources/ | raw material as received | append only |
| tmp/ | workbench | free |
| decisions/ | closed questions | append only |

## Placement rule

1. Raw, draft, undecided or temporary? → a pipeline zone
2. No? Then what is it about? → a semantic zone

The order matters: processing state beats topic. A transcript about hiring is
a source, not a hiring note, and the conclusion drawn from it is the note.

## What cannot be derived and cannot be linted

Nothing recorded here yet. Three to six items belong in this section, each
specific to this domain, and they come from practice rather than from the
first day.

Before writing a rule here, ask which check would fail if someone broke it.
If a gate or an artefact could hold it, it goes there instead.

---

This file is English by convention. The conversation and the content of the
repository are in the author's language.
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_scaffold -v`
Expected: зелено.

- [x] **Step 5: Коммит**

```bash
git add scaffold/CLAUDE.md tests/test_scaffold.py
git commit -m "wave3: CLAUDE.md каркаса — карта зон, правило размещения, домен не заполнен"
```

---

## Task 4: Одиннадцать правил с областью действия по пути

Восемь по зонам плюс три сквозных. Форма каждого: `description` и `paths`
во фронтматтере, тело — тест принадлежности и правила, обязательная финальная
строка одного из **двух** видов. Правило без такой строки — кандидат
на удаление при аудите, поэтому форму держит тест, а не дисциплина.

Rule-файл **никогда не воспроизводит** `archetype` и `values` коллекции:
разъехавшаяся копия словаря молчалива.

**Files:**
- Create: `scaffold/.claude/rules/*.md` (11 файлов)
- Modify: `tests/test_scaffold.py`

- [x] **Step 1: Написать падающий тест**

```python
RULES = SCAFFOLD / ".claude" / "rules"

# Три сквозных правила и их глобы — дословно из секции 9. Восемь зонных
# выводятся из zones.ZONES: второй таблицы зон в пакете быть не должно.
CROSS_CUTTING = {
    "collection.md": "**/items/**",
    "views.md": "**/*.base",
    "readme.md": "**/README.md",
}

HELD = "Held by gates: "
NOT_GATED = "Not gated — this is a convention."

# Механизмы, которые правило вправе назвать. Закрытый список: правило,
# ссылающееся на несуществующий гейт, — это та самая гниль, которую ловит
# гейт №1, только этажом выше.
KNOWN_MECHANISMS = ("link gate", "frontmatter gate", "write hook",
                    "end-of-turn hook", "deny rule")

# Закрытые словари рецепта. Rule-файл вправе сослаться на README коллекции,
# но не переписать словарь к себе.
VOCABULARIES = (("open", "decided", "revisited"), ("active", "paused", "done"))


def rule_files():
    return sorted(RULES.glob("*.md"))


class TestPathScopedRules(unittest.TestCase):
    def test_there_are_exactly_eleven_and_these_are_they(self):
        expected = sorted(["%s.md" % zone for zone in zones.ZONES]
                          + list(CROSS_CUTTING))
        self.assertEqual([p.name for p in rule_files()], expected)

    def test_every_rule_declares_a_description_and_paths(self):
        empty = []
        for path in rule_files():
            fields = parse_frontmatter(path.read_text(encoding="utf-8"))
            if not str(fields.get("description") or "").strip():
                empty.append(path.name)
            if not fields.get("paths"):
                empty.append(path.name + ":paths")
        self.assertEqual(empty, [])

    def test_zone_rules_scope_themselves_to_their_zone(self):
        actual = {}
        for zone in zones.ZONES:
            fields = parse_frontmatter(
                (RULES / ("%s.md" % zone)).read_text(encoding="utf-8"))
            actual[zone] = fields["paths"]
        self.assertEqual(actual, {z: ["%s/**" % z] for z in zones.ZONES})

    def test_cross_cutting_rules_scope_themselves_by_shape(self):
        actual = {}
        for name, glob in CROSS_CUTTING.items():
            fields = parse_frontmatter((RULES / name).read_text(encoding="utf-8"))
            actual[name] = fields["paths"]
        self.assertEqual(actual, {name: [glob] for name, glob in CROSS_CUTTING.items()})

    def test_every_rule_ends_with_one_of_the_two_closing_forms(self):
        """Закрытие — **абзац**, а не строка: текст после последней пустой,
        склеенный в одну.

        Прочтение «последняя непустая строка» роняло восемь правил из
        одиннадцати: у areas, collection, core, decisions, knowledge,
        projects, sources и views закрытие переносится на две строки, и
        последней оказывалась вторая половина фразы. Чинить это переливкой
        одиннадцати файлов в одну длинную строку значило бы портить прозу
        ради теста. Соседний `test_a_named_gate_is_a_gate_that_exists`
        ищет то же место через `rfind` по всему тексту, то есть уже читает
        закрытие абзацем: два прочтения одного места — это расхождение,
        а не строгость.

        `tmp.md` старую форму проходил **случайно** — его фраза уместилась
        в одну строку. Восстанавливать построчное чтение по этому образцу
        нельзя: оно зелёное на совпадении длины, а не на форме.
        """
        wrong = []
        for path in rule_files():
            paragraphs = [block for block
                          in path.read_text(encoding="utf-8").split("\n\n")
                          if block.strip()]
            closing = " ".join(paragraphs[-1].split()) if paragraphs else ""
            if closing == NOT_GATED:
                continue
            if closing.startswith(HELD) and closing[len(HELD):].strip():
                continue
            wrong.append((path.name, closing))
        self.assertEqual(wrong, [])

    def test_a_named_gate_is_a_gate_that_exists(self):
        unknown = []
        for path in rule_files():
            text = path.read_text(encoding="utf-8")
            index = text.rfind(HELD)
            if index < 0:
                continue
            closing = text[index + len(HELD):]
            if not any(name in closing for name in KNOWN_MECHANISMS):
                unknown.append((path.name, closing.strip()[:60]))
        self.assertEqual(unknown, [])

    def test_both_closing_forms_are_actually_used(self):
        """Форма «не гейтится» существует не на бумаге: конвенций две —
        разбор inbox и жанр README, и обе названы конвенциями в спеке."""
        ungated = [p.name for p in rule_files()
                   if NOT_GATED in p.read_text(encoding="utf-8")]
        self.assertEqual(ungated, ["inbox.md", "readme.md"])

    def test_no_rule_reproduces_a_collection_vocabulary(self):
        offenders = []
        for path in rule_files():
            words = set(re.findall(r"[a-z]+", path.read_text(encoding="utf-8").lower()))
            for vocabulary in VOCABULARIES:
                present = [value for value in vocabulary if value in words]
                if len(present) > 1:
                    offenders.append((path.name, present))
        self.assertEqual(offenders, [])

    def test_no_rule_outgrows_its_budget(self):
        """Около тридцати строк на файл. Правило, доросшее до README,
        перестаёт быть правилом и начинает расходиться с ним."""
        oversized = [(p.name, len(p.read_text(encoding="utf-8").split("\n")))
                     for p in rule_files()
                     if len(p.read_text(encoding="utf-8").split("\n")) > 40]
        self.assertEqual(oversized, [])
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_scaffold.TestPathScopedRules -v`
Expected: все FAIL — `test_there_are_exactly_eleven_and_these_are_they`
сравнивает пустой список с одиннадцатью именами.

- [x] **Step 3: Реализация — восемь правил зон**

`scaffold/.claude/rules/core.md`:

```markdown
---
description: Zone rules for core
paths: ["core/**"]
---
# core

**Belongs here** if the answer this file gives stays true when the quarter
changes and when the project changes.

**Not here.** The current state of a direction is areas. Something with a
completion criterion is projects. A choice with a named rejected alternative
is decisions.

**Rules.**

- Creating a document is free; rewriting an existing one asks the author
  first. This zone is read before everything else, so an error here is
  inherited by every later judgement.
- No hand-written table of contents. What is in a folder is answered by a
  listing; a paragraph that lists files goes stale silently.
- Subfolders by topic once there are more than seven documents.
- Do not link from here into tmp: that zone is emptied and the link stays.

Held by gates: link gate — a link into a transient zone and a link out of the
repository; write hook — a warning before rewriting in a long-lived zone.
```

`scaffold/.claude/rules/areas.md`:

```markdown
---
description: Zone rules for areas
paths: ["areas/**"]
---
# areas

**Belongs here** if there is a level of quality that is kept up and no
completion criterion to reach.

**Not here.** Something that can be finished is projects. Expertise that would
be true without us is knowledge. Material as received is sources.

**Rules.**

- One folder per direction. Inside it anything the work needs: dated data,
  nested collections, arbitrary formats.
- A file that is an entry on a date rather than a statement about now says so
  in its own fields. The zone does not split into raw and derived — that split
  is what the pipeline zones are for.
- Creating is free; rewriting an existing file asks the author first.
- A collection appears inside a direction only when there is a real record to
  put in it.

Held by gates: link gate — a link into a transient zone and a link out of the
repository; write hook — a warning before rewriting in a long-lived zone.
```

`scaffold/.claude/rules/projects.md`:

```markdown
---
description: Zone rules for projects
paths: ["projects/**"]
---
# projects

**Belongs here** if a completion criterion can be named. Not a deadline: a
project can run for a year and a direction can have a date.

**Rules.**

- A project is a folder, and its own README is the collection's record: it
  carries the record fields and the view shows it. This is the only README
  that is a record.
- The status vocabulary is declared in the zone README. Read it there; do not
  restate it anywhere else.
- A finished project keeps its place with its status changed. Nothing is moved
  out and nothing is archived — the view hides what is finished, and history
  is kept by git.
- Where the leftovers of a finished project settle is decided when they are
  needed, by the placement rule, and only for what turned out to be needed.

Held by gates: frontmatter gate — the starter fields on every record and the
status value from the vocabulary the zone README declares.
```

`scaffold/.claude/rules/knowledge.md`:

```markdown
---
description: Zone rules for knowledge
paths: ["knowledge/**"]
---
# knowledge

**Belongs here** if the statement would still be true had we never existed.

**Rules.**

- Bases are connected as git submodules, one folder per base. Creating,
  validating and maintaining them happens in their own repositories, not here.
- Nobody writes inside a connected base. Not the agent, not a skill, not by
  hand through a tool call.
- The zone README is ours: it says where each base came from and what in it
  can be relied on.
- A connected base may carry its own instructions. They are not instructions
  for this repository, and the settings exclude them from its context.

Held by gates: deny rule in this repository's Claude settings — editing and
writing inside a connected base; link gate — links here still have to resolve.
```

`scaffold/.claude/rules/inbox.md`:

```markdown
---
description: Zone rules for inbox
paths: ["inbox/**"]
---
# inbox

**Belongs here** while it has not been decided what the thing is.

**Rules.**

- Capture asks no questions. Choosing a place at the moment of capture is the
  friction that kills capture itself.
- One file per captured item, always. A list of items in one file cannot be
  moved out item by item.
- Sorting out is a move, not an edit in place. What leaves gets its zone from
  the placement rule.
- Nothing stays here for ever. Age here is a fact about the pipeline, not
  about the item.

Not gated — this is a convention.
```

`scaffold/.claude/rules/sources.md`:

```markdown
---
description: Zone rules for sources
paths: ["sources/**"]
---
# sources

**Belongs here** if it was received rather than written: true as a record of a
fact, not as a statement about the present.

**Rules.**

- Never edited, never corrected, never tidied. A mistake inside a source is
  part of the record.
- Naming is the date first, then what the thing is.
- The link direction is fixed: derived → source, never the reverse. A source
  is immutable and therefore cannot accumulate links to what came later.
- A source is not copied to its consumers. One source feeds several; a copy in
  each gives diverging copies and no canonical one.

Held by gates: write hook — an agent editing an existing file here is blocked;
link gate — a source nobody has linked to is reported.
```

`scaffold/.claude/rules/tmp.md`:

```markdown
---
description: Zone rules for tmp
paths: ["tmp/**"]
---
# tmp

**Belongs here** if it stops being needed when the task ends.

**Rules.**

- Nothing here is a source of truth. Anything relied on later moves out first,
  by the placement rule.
- Writing and deleting are both free.
- No long-lived zone links here. Those zones outlive this one, so such a link
  is a breakage on a delay rather than a risk.
- Session artefacts belong here rather than in context: what is held only in
  context is lost when the context is compacted.

Held by gates: link gate — a link from a long-lived zone into a transient one.
```

`scaffold/.claude/rules/decisions.md`:

```markdown
---
description: Zone rules for decisions
paths: ["decisions/**"]
---
# decisions

**Belongs here** only if all three hold: there was a named rejected
alternative; reversing costs more than taking it; it will bear on choices made
later by someone who does not remember it.

The practical form of the test: if in three months someone proposes the
opposite, do I want the agent to object by pointing at this record?

**Rules.**

- A record is added, never edited. A choice that changed is superseded by a
  new record linking back to the one it replaces.
- How something was done is work, not a decision. The zone fills with process
  notes the moment that line is crossed.
- The status vocabulary is declared in the zone README. Read it there; do not
  restate it anywhere else.
- A record that names a review trigger carries its date as a field, so that a
  view can compare it. What can be computed is not stored.

Held by gates: frontmatter gate — the starter fields on every record and the
status value from the vocabulary the zone README declares.
```

- [x] **Step 4: Реализация — три сквозных правила**

`scaffold/.claude/rules/collection.md`:

```markdown
---
description: What a collection record must carry
paths: ["**/items/**"]
---
# collection records

**This folder holds the records of one collection and nothing else.** Anything
that does not read as markdown goes elsewhere: it clutters the view and the
frontmatter gate stumbles on it.

**A thing earns a file** when it has its own life cycle — it is created,
changes status, and is found separately from its neighbours. A checklist item,
a metric row or a paragraph inside a write-up is not a record; the sign is
that the only way to find it is to open its parent.

**Rules.**

- Every record carries the starter fields, plus whatever the collection's
  views read.
- The archetype and the status vocabulary are declared in the collection
  README. Refer to them there; a copy of a vocabulary diverges silently.
- A value that cannot be reconstructed six months later is written at creation
  even if no view reads it yet. A value that a script could backfill waits for
  a consumer.
- Attachments live in a sibling folder, not among the records. Records link to
  attachments, never the other way round.

Held by gates: frontmatter gate — a missing required field, a status value
outside the declared vocabulary, unparseable frontmatter.
```

`scaffold/.claude/rules/views.md`:

```markdown
---
description: What a collection view must hold to
paths: ["**/*.base"]
---
# views

**This file is the views of one collection.** It is the navigation layer, and
it lives one level above the records.

**Rules.**

- The filter names the folder the records are in, and that folder has to
  exist. A filter pointing at a renamed folder draws an empty table and says
  nothing about why.
- A view may only read fields the records carry. A field mentioned in a
  filter, a sort or a grouping becomes required for every record of the
  collection — that is where the contract comes from, not from a schema.
- What can be computed is not stored: keep the date, and let the view compute
  whether it has gone stale.
- A second view appears when a question arrives that the first cannot answer.
- Editing this file through the Obsidian UI drops its comments. Edit it as
  text.

Held by gates: frontmatter gate — a field a view reads and a record lacks;
link gate — the folder the filter names.
```

`scaffold/.claude/rules/readme.md`:

```markdown
---
description: What a README carries and what it must not
paths: ["**/README.md"]
---
# README

**This file is the policy of its folder**, and everything in it is about the
folder as a whole or about relations between its contents.

**Carries.** What is put here. What is deliberately not here and where that
lives instead. Naming conventions. Relations between records — "these two
compete" is about a relation and belongs here.

**Does not carry.** A listing of files, in any form. A retelling of a single
record: that belongs in the record's own description field, where a view shows
it, and a copy here goes stale while the original does not. Narrative about
why the folder matters.

**One exception.** A project's own README is also the record of its
collection, so it carries frontmatter and appears in a view.

**Why the ban is worth it.** A listing of fifteen files with a sentence each
is where dead links accumulate: the policy stays true, the retelling does not,
and nothing announces the difference.

Not gated — this is a convention.
```

- [x] **Step 5: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_scaffold -v`
Expected: зелено.

- [x] **Step 6: Коммит**

```bash
git add scaffold/.claude/rules tests/test_scaffold.py
git commit -m "wave3: одиннадцать правил по пути — восемь зон и три сквозных"
```

---

## Task 5: Четыре маленьких артефакта

`.gitignore`, `.twinkle-repo-builder`, `OPEN-THREADS.md` и фрагмент настроек.
Фрагмент — единственный артефакт каркаса, который в инстанс не копируется,
а сливается: файл с именем `settings.json` затёр бы `enabledPlugins`, которым
включён сам плагин, и плагин выключил бы себя первым же действием.

Значения `permissions.deny` **собираются** из `zones.DENY_PATTERNS`, а не
переписываются литералами: глубина глоба уже отсуждена (`knowledge/**` был
шире своей причины и блокировал запись собственного `knowledge/README.md`),
и второй копии этого решения в пакете быть не должно.

**Files:**
- Create: `scaffold/.gitignore`, `scaffold/.twinkle-repo-builder`,
  `scaffold/OPEN-THREADS.md`, `scaffold/.claude/settings-fragment.json`
- Modify: `tests/test_scaffold.py`

- [x] **Step 1: Написать падающий тест**

```python
FRAGMENT = SCAFFOLD / ".claude" / "settings-fragment.json"

GITIGNORE_LINES = (
    ".obsidian/workspace*.json",
    ".trash/",
    ".DS_Store",
    "node_modules/",
    "__pycache__/",
)


class TestSettingsFragment(unittest.TestCase):
    def test_the_fragment_is_composed_from_the_single_definition(self):
        """Обёртки собираются из zones.DENY_PATTERNS, а не пишутся заново.

        Глубина глоба — отсуженное решение: `knowledge/**` был шире своей
        причины и блокировал CREATE, которому надо положить в зону README.
        Разошедшиеся копии такого решения молчаливы.
        """
        fragment = json.loads(FRAGMENT.read_text(encoding="utf-8"))
        self.assertEqual(
            fragment,
            {
                "claudeMdExcludes": ["**/%s/**" % z for z in sorted(zones.READ_ONLY)],
                "permissions": {
                    "deny": ["%s(./%s)" % (tool, pattern)
                             for tool in ("Edit", "Write")
                             for pattern in zones.DENY_PATTERNS],
                },
            },
        )

    def test_the_fragment_is_not_named_settings_json(self):
        self.assertFalse((SCAFFOLD / ".claude" / "settings.json").exists())


class TestRecipeMarker(unittest.TestCase):
    def test_the_marker_carries_the_version_and_nothing_else(self):
        """Секция 22: в конфиге только то, чего не вывести из дерева.
        Осталось одно поле, и это признак работающего правила."""
        manifest = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marker = json.loads(
            (SCAFFOLD / ".twinkle-repo-builder").read_text(encoding="utf-8"))
        self.assertEqual(marker, {"version": manifest["version"]})


class TestGitignore(unittest.TestCase):
    def test_it_carries_exactly_these_lines(self):
        lines = [line.strip() for line
                 in (SCAFFOLD / ".gitignore").read_text(encoding="utf-8").split("\n")
                 if line.strip() and not line.strip().startswith("#")]
        self.assertEqual(lines, list(GITIGNORE_LINES))

    def test_it_states_no_size_threshold(self):
        """Порог в байтах здесь выразить нечем; механизм переезжает в MAINTAIN
        и до тех пор не притворяется существующим."""
        text = (SCAFFOLD / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("MB", text)
        self.assertNotIn("size", text)


class TestOpenThreads(unittest.TestCase):
    def test_it_ships_as_a_form_without_invented_content(self):
        """Пустой список — не выдуманное содержимое, а форма, как README зоны."""
        text = (SCAFFOLD / "OPEN-THREADS.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Open threads"))
        bullets = [line for line in text.split("\n") if line.startswith("- ")]
        self.assertEqual(bullets, [])

    def test_it_lives_in_the_root_and_not_in_a_zone(self):
        """Это состояние работы над доменом, а не содержимое домена; `tmp`
        вдобавок исчезающая зона, и ссылка на неё — класс находки."""
        strays = [p.relative_to(SCAFFOLD).as_posix()
                  for p in SCAFFOLD.rglob("OPEN-THREADS.md")]
        self.assertEqual(strays, ["OPEN-THREADS.md"])
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_scaffold -v`
Expected: четыре класса FAIL с `FileNotFoundError`.

- [x] **Step 3: Реализация — `scaffold/.claude/settings-fragment.json`**

```json
{
  "claudeMdExcludes": ["**/knowledge/**"],
  "permissions": {
    "deny": ["Edit(./knowledge/*/**)", "Write(./knowledge/*/**)"]
  }
}
```

- [x] **Step 4: Реализация — `scaffold/.twinkle-repo-builder`**

```json
{
  "version": "0.1.0"
}
```

- [x] **Step 5: Реализация — `scaffold/.gitignore`**

```
# Rewritten on every click in Obsidian.
.obsidian/workspace*.json

# Deleted notes: Obsidian keeps them, the repository does not.
.trash/

.DS_Store
node_modules/
__pycache__/
```

Пять строк, а не три: `.trash/` и `node_modules/` названы исключёнными в
секции 8, и другого механизма доставки у этого списка нет — `_ignored` знает
только `.git/` и `archive/`. Без `.trash/` гейт читает удалённые в Obsidian
заметки и находит в них дохлые ссылки в первом же живом инстансе. Расхождение
со спекой волны названо в разделе «Расхождения».

- [x] **Step 6: Реализация — `scaffold/OPEN-THREADS.md`**

```markdown
# Open threads

Questions that had no answer when this repository was created or extended.
They live here, in git, rather than in a report that dies with the session.

A thread is removed when it is answered, not when it gets old.
```

- [x] **Step 7: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_scaffold -v`
Expected: зелено.

- [x] **Step 8: Коммит**

```bash
git add scaffold/.gitignore scaffold/.twinkle-repo-builder \
        scaffold/OPEN-THREADS.md scaffold/.claude/settings-fragment.json \
        tests/test_scaffold.py
git commit -m "wave3: gitignore, маркер версии, открытые нити, фрагмент настроек"
```

---

## Task 6: Инвентарь целиком и оба гейта на каркасе

Здесь закрывается критерий 1: каркас — чистая фикстура, ноль находок,
и то же самое с удалённым `.claude/`.

Проверка «без `.claude/`» отвечает на один вопрос: не стал ли репозиторий
читаемым только вместе с плагином. Правила и настройки — слой, который плагин
везёт и может унести; записи, коллекции и виды остаются у автора.

**Files:**
- Modify: `tests/test_scaffold.py`

- [x] **Step 1: Написать падающий тест**

```python
from tests.test_fixtures import places

# Инвентарь каркаса поимённо. Спека волны называет двадцать два артефакта;
# из её же состава получается двадцать четыре файла и восемь каталогов зон,
# и расхождение вынесено автору. Здесь стоит то, что можно проверить.
SCAFFOLD_FILES = (
    ".claude/rules/areas.md",
    ".claude/rules/collection.md",
    ".claude/rules/core.md",
    ".claude/rules/decisions.md",
    ".claude/rules/inbox.md",
    ".claude/rules/knowledge.md",
    ".claude/rules/projects.md",
    ".claude/rules/readme.md",
    ".claude/rules/sources.md",
    ".claude/rules/tmp.md",
    ".claude/rules/views.md",
    ".claude/settings-fragment.json",
    ".gitignore",
    ".twinkle-repo-builder",
    "CLAUDE.md",
    "OPEN-THREADS.md",
    "areas/README.md",
    "core/README.md",
    "decisions/README.md",
    "inbox/README.md",
    "knowledge/README.md",
    "projects/README.md",
    "sources/README.md",
    "tmp/README.md",
)


class TestScaffoldInventory(unittest.TestCase):
    def test_the_scaffold_is_exactly_these_files(self):
        actual = sorted(p.relative_to(SCAFFOLD).as_posix()
                        for p in SCAFFOLD.rglob("*") if p.is_file())
        self.assertEqual(actual, sorted(SCAFFOLD_FILES))

    def test_the_scaffold_carries_no_collection(self):
        """Зона заводится всегда, коллекция без настоящей записи — никогда.

        Вид, отбирающий из несуществующей папки, — буквально класс находки
        битой фикстуры, и пустая коллекция не сигналит ничем: она выглядит
        рабочей.
        """
        self.assertEqual(list(SCAFFOLD.rglob("views.base")), [])
        self.assertEqual([p for p in SCAFFOLD.rglob("items") if p.is_dir()], [])

    def test_the_scaffold_carries_no_exemplar(self):
        """CREATE не генерирует правдоподобное: синтетическая запись хуже
        пустой папки, потому что автор не отличит её от своего."""
        stray = [p.relative_to(SCAFFOLD).as_posix()
                 for p in SCAFFOLD.rglob("*.md")
                 if p.name != "README.md" and p.parent != SCAFFOLD
                 and ".claude" not in p.parts]
        self.assertEqual(stray, [])

    def test_the_scaffold_ships_neither_allowlist_nor_hooks(self):
        """`.link-allow` принадлежит репозиторию, хуки регистрирует плагин."""
        self.assertFalse((SCAFFOLD / ".link-allow").exists())
        self.assertFalse((SCAFFOLD / "hooks.json").exists())
        self.assertFalse((SCAFFOLD / ".claude" / "hooks.json").exists())


class TestScaffoldPassesBothGates(unittest.TestCase):
    def test_the_link_gate_finds_nothing(self):
        self.assertEqual(places(check_links.scan(SCAFFOLD)), [])

    def test_the_frontmatter_gate_finds_nothing(self):
        self.assertEqual(places(check_frontmatter.scan(SCAFFOLD)), [])

    def test_both_gates_are_still_silent_without_the_claude_directory(self):
        """Проверка пакета требует того же: ни одна проверка не опирается
        на файлы, которых у человека может не быть."""
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "instance"
            shutil.copytree(SCAFFOLD, copy)
            shutil.rmtree(copy / ".claude")
            self.assertEqual(places(check_links.scan(copy)), [])
            self.assertEqual(places(check_frontmatter.scan(copy)), [])

    def test_no_surviving_file_points_into_the_claude_directory(self):
        """Причина, по которой предыдущий тест зелёный, названа отдельно.

        Backtick-токен, ведущий в `.claude/`, резолвится на полном каркасе и
        становится `unresolved` ровно тогда, когда каталог унесли, — то есть
        в чужом репозитории без плагина.
        """
        offenders = []
        for path in sorted(SCAFFOLD.rglob("*.md")):
            rel = path.relative_to(SCAFFOLD).as_posix()
            if rel.startswith(".claude/"):
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.split("\n"), start=1):
                for match in check_links._INLINE.finditer(line):
                    token = match.group(2).strip()
                    if paths.is_path_token(token) and token.startswith(".claude"):
                        offenders.append((rel, lineno, token))
        self.assertEqual(offenders, [])
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_scaffold -v`
Expected: `test_the_scaffold_is_exactly_these_files` FAIL, если инвентарь
разошёлся (например, в каталоге завёлся `.DS_Store` — он не имеет права
уехать в пакет). Гейтовые тесты обязаны пройти сразу: если нет, читать отчёт
и чинить **каркас**, а не гейт.

Самые вероятные находки на этом шаге и что они значат:

| находка | причина | починка |
|---|---|---|
| `unresolved` на `` `README.md` `` | у каркаса нет README в корне | снять backtick, оставить слово |
| `unresolved` на `` `views.base` `` | коллекций в каркасе нет | писать `**/*.base` либо без backtick'ов |
| `unresolved` на `` `items/` `` | папки записей в каркасе нет | писать `**/items/**` |
| `unresolved` на `` `.claude/rules/…` `` | ссылка переживает свой каталог | убрать вовсе |
| `undecodable` на файле каркаса | файл сохранён не в UTF-8; ссылки в нём не проверил никто, и класс поэтому ошибка, а не отчёт | пересохранить в UTF-8 одним движением |
| `dead-allow` или `broad-allow` | оба приходят только из `.link-allow`, а каркас его не везёт | это не находка о тексте: краснеет заодно `test_the_scaffold_ships_neither_allowlist_nor_hooks`, и чинить надо инвентарь |

Последние две строки — про классы, которых на момент написания плана не
существовало вовсе. Обе видны сегодня на битой фикстуре, так что это не
догадка; в каркасе, каким его пишут задачи 2–5, ни одна из них возникнуть не
может, и стоят они здесь ровно затем, чтобы отчёт с незнакомым классом не
читали как поломку гейта. Полный список — `scripts/findings.py`,
`LINK_CLASSES`; таблица выше не перечисление классов, а перечисление
вероятных причин.

- [x] **Step 3: Реализация**

Кода в этой задаче нет: она проверяет уже написанное. Всё, что краснеет, —
правка текста каркаса по таблице выше.

- [x] **Step 4: Прогнать — должно пройти**

Run: `./check`
Expected: код 0. Проверка пакета сканирует `scaffold/` наравне со `scripts/`
и обязана не найти в нём абсолютных путей.

- [x] **Step 5: Коммит**

```bash
git add tests/test_scaffold.py scaffold
git commit -m "wave3: каркас как чистая фикстура — ноль находок, в том числе без .claude"
```

---

## Task 7: `install_scaffold.py` — копия побайтово и слияние настроек

Разворачивание детерминировано, значит это скрипт, а не суждение скилла.
Копия байт в байт нужна не из эстетики: одинаковость инстансов проверяется
сравнением байтов, а не доверием к генератору.

Установщик пишет в дерево, значит обязан спросить границу рабочего каталога
(незыблемое №6). Спросить, а не переписать: предикат уже отгружен волной 2 в
`hooks/boundary.py::outside` — с той же нормализацией, тем же посегментным
сравнением и тем же примером про соседний каталог, начинающийся на имя
корня. Второй такой же предикат внутри `scripts/install_scaffold.py` был бы
копией отсуженного решения, а расходятся копии молча: этот проект держит
`tests/test_zones.py::TestSingleDefinition` ровно против такой поломки,
потому что в сопоставимом продукте однажды намерили три разошедшиеся
таблицы одних и тех же восьми зон. Копия предиката тем же тестом **не**
ловится — он сторожит таблицу зон, и только её. И дальше становится хуже,
а не стоит на месте: закрытие волны обещает `scripts/install_scaffold.py`
волне 4, ADOPT унаследовал бы копию, и копий стало бы три.

Поэтому первым делом предикат переезжает в `scripts/` — туда, где живут
общие модули и откуда его читают оба потребителя, `hooks/` и `scripts/`,
— а Step 3 закрывает это тестом на **одно** определение.

**Files:**
- Move: `hooks/boundary.py` → `scripts/boundary.py`
- Create: `scripts/install_scaffold.py`
- Modify: `scripts/check_package.py` (`_PRODUCT_DIRS`), `hooks/hook.py`
  (строка импорта), `dev/mutate.py` (путь в мутации «в2 К4»)
- Test: `tests/test_install_scaffold.py`, `tests/test_scaffold.py`,
  `tests/test_boundary.py` (строка импорта плюс класс на одно определение;
  двенадцать утверждений волны 2 не меняются)

- [x] **Step 1: Написать падающий тест**

```python
"""Установщик каркаса: копия побайтово, слияние настроек, граница корня."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import install_scaffold
from scripts.findings import EXIT_OK, EXIT_VIOLATION

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "scaffold"
FRAGMENT = ".claude/settings-fragment.json"
SETTINGS = ".claude/settings.json"


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root),
                          capture_output=True, text=True, check=True)


def _new_repo(base, name="instance"):
    root = Path(base) / name
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "create@example.invalid")
    _git(root, "config", "user.name", "create")
    return root


def _tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


class TestCopy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _new_repo(self.tmp.name)

    def test_every_scaffold_file_lands_byte_for_byte(self):
        install_scaffold.install(SCAFFOLD, self.root)
        differing = []
        for source in sorted(p for p in SCAFFOLD.rglob("*") if p.is_file()):
            rel = source.relative_to(SCAFFOLD).as_posix()
            if rel == FRAGMENT:
                continue
            target = self.root / rel
            if not target.exists() or target.read_bytes() != source.read_bytes():
                differing.append(rel)
        self.assertEqual(differing, [])

    def test_the_fragment_itself_does_not_travel(self):
        """Файл существует ради слияния; в инстансе ему делать нечего."""
        install_scaffold.install(SCAFFOLD, self.root)
        self.assertFalse((self.root / FRAGMENT).exists())

    def test_it_reports_every_path_it_wrote(self):
        written = install_scaffold.install(SCAFFOLD, self.root)
        self.assertIn(SETTINGS, written)
        self.assertIn("CLAUDE.md", written)
        self.assertNotIn(FRAGMENT, written)
        self.assertEqual(written, sorted(written))

    def test_it_refuses_without_git(self):
        """`git init` — первое действие, до первой записи: иначе ничего
        из последующего не откатывается, а Stop-хук встречает каталог без git."""
        with tempfile.TemporaryDirectory() as bare:
            with self.assertRaises(install_scaffold.Refused) as caught:
                install_scaffold.install(SCAFFOLD, Path(bare))
            self.assertIn("git", str(caught.exception))
            self.assertEqual(list(Path(bare).iterdir()), [])

    def test_it_never_overwrites_what_is_already_there(self):
        (self.root / "CLAUDE.md").write_text("автор писал сюда сам\n",
                                             encoding="utf-8")
        with self.assertRaises(install_scaffold.Refused) as caught:
            install_scaffold.install(SCAFFOLD, self.root)
        self.assertIn("CLAUDE.md", str(caught.exception))
        self.assertEqual((self.root / "CLAUDE.md").read_text(encoding="utf-8"),
                         "автор писал сюда сам\n")

    def test_it_writes_nothing_outside_the_root(self):
        """Незыблемое №6: плагин не пишет ничего вне корня репозитория."""
        neighbour = Path(self.tmp.name) / "чужое-дерево"
        neighbour.mkdir()
        (neighbour / "заметка.md").write_text("чужое\n", encoding="utf-8")
        before = _tree_hash(neighbour)
        install_scaffold.install(SCAFFOLD, self.root)
        self.assertEqual(_tree_hash(neighbour), before)


class TestSettingsMerge(unittest.TestCase):
    """Слияние, а не копирование: `settings.json` уже существует, им включён
    плагин, и копия поверх выключила бы плагин первым же действием."""

    FRAGMENT_DATA = json.loads((SCAFFOLD / FRAGMENT).read_text(encoding="utf-8"))

    def test_an_absent_file_is_created_from_the_fragment(self):
        self.assertEqual(install_scaffold.merge_settings({}, self.FRAGMENT_DATA),
                         self.FRAGMENT_DATA)

    def test_existing_keys_survive(self):
        existing = {"enabledPlugins": {"twinkle-repo-builder": True}}
        merged = install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertEqual(merged["enabledPlugins"],
                         {"twinkle-repo-builder": True})

    def test_deny_is_extended_without_duplicates(self):
        existing = {"permissions": {"deny": ["Edit(./knowledge/*/**)",
                                             "Bash(rm:*)"]}}
        merged = install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertEqual(merged["permissions"]["deny"],
                         ["Edit(./knowledge/*/**)", "Bash(rm:*)",
                          "Write(./knowledge/*/**)"])

    def test_a_neighbouring_permission_key_is_untouched(self):
        existing = {"permissions": {"allow": ["Read(./core/**)"]}}
        merged = install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertEqual(merged["permissions"]["allow"], ["Read(./core/**)"])

    def test_excludes_are_extended_without_duplicates(self):
        existing = {"claudeMdExcludes": ["**/knowledge/**", "**/vendor/**"]}
        merged = install_scaffold.merge_settings(existing, self.FRAGMENT_DATA)
        self.assertEqual(merged["claudeMdExcludes"],
                         ["**/knowledge/**", "**/vendor/**"])

    def test_merging_twice_changes_nothing(self):
        once = install_scaffold.merge_settings({}, self.FRAGMENT_DATA)
        self.assertEqual(install_scaffold.merge_settings(once, self.FRAGMENT_DATA),
                         once)

    def test_broken_json_is_not_the_same_as_absent(self):
        """Файл есть — значит его писали. Затирать нельзя, молчать нельзя."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_repo(tmp)
            (root / ".claude").mkdir()
            (root / SETTINGS).write_text("{не json", encoding="utf-8")
            with self.assertRaises(install_scaffold.Refused) as caught:
                install_scaffold.install(SCAFFOLD, root)
            self.assertIn(SETTINGS, str(caught.exception))
            self.assertEqual((root / SETTINGS).read_text(encoding="utf-8"),
                             "{не json")


class TestCommandLine(unittest.TestCase):
    def test_exit_codes_follow_the_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _new_repo(tmp)
            ok = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "install_scaffold.py"),
                 str(root)], capture_output=True, text=True)
            self.assertEqual(ok.returncode, EXIT_OK)
            self.assertIn("CLAUDE.md", ok.stdout)

            again = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "install_scaffold.py"),
                 str(root)], capture_output=True, text=True)
            self.assertEqual(again.returncode, EXIT_VIOLATION)
            self.assertIn("CLAUDE.md", again.stderr)
```

И один тест в `tests/test_scaffold.py` — каркас теперь продукт:

```python
class TestScaffoldIsProduct(unittest.TestCase):
    def test_the_product_hash_covers_the_scaffold(self):
        """`tests-touched-product` обязан видеть запись в каркас: он уезжает
        пользователю ровно так же, как `scripts/` и `hooks/`."""
        from scripts import check_package
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scaffold").mkdir()
            (root / "scaffold" / "CLAUDE.md").write_text("a", encoding="utf-8")
            before = check_package._product_hash(root)
            (root / "scaffold" / "CLAUDE.md").write_text("b", encoding="utf-8")
            self.assertNotEqual(check_package._product_hash(root), before)
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_install_scaffold tests.test_scaffold -v`
Expected: `ModuleNotFoundError: scripts.install_scaffold`, и отдельно
`test_the_product_hash_covers_the_scaffold` FAIL — хеши равны, потому что
`scaffold` в `_PRODUCT_DIRS` пока нет.

- [x] **Step 3: Одно определение границы — предикат переезжает в `scripts/`**

Сначала тест, потом переезд. Тест дописывается в `tests/test_boundary.py`,
а не в `tests/test_install_scaffold.py`: последний на этом шаге не
импортируется вовсе — `scripts.install_scaffold` ещё не написан, — и красный
шаг вышел бы ошибкой импорта вместо утверждения. К импортам файла
добавляются `re` и `ROOT = Path(__file__).resolve().parent.parent`.

```python
# Признак собственной копии предиката границы: нормализация `realpath`
# **и** посегментное сравнение с корнем — в одном файле. Два сигнала, а не
# один: `os.path.realpath` сам по себе стоит в `hooks/hook.py` шесть раз и
# там законен, а срез `parts[:len(` без нормализации — уже другая проверка.
# Копию выдаёт именно пара.
#
# Срез ищется без ведущей точки: копия, которую этот план и вёз, сначала
# складывала сегменты в локальные `root_parts`/`target_parts` и резала уже
# их, — `\.parts\[` не нашёл бы её ни разу.
NORMALISATION = "os.path.realpath"
SEGMENTS = re.compile(r"parts\[:\s*len\(")

# Каталоги вне пакета: тот же периметр, что у
# `tests/test_zones.py::TestSingleDefinition`, плюс `dev/` — таблица мутаций
# цитирует продукт по построению и офендером быть не может.
_NOT_PACKAGE = {".git", "__pycache__", "tests", "fixtures", "docs", "dev"}


def _boundary_carriers(root):
    """Файлы пакета, несущие собственную реализацию сравнения с корнем."""
    out = []
    for path in sorted(Path(root).rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in _NOT_PACKAGE for part in rel.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if NORMALISATION in text and SEGMENTS.search(text):
            out.append(rel.as_posix())
    return out


class TestOneBoundaryDefinition(unittest.TestCase):
    """Предикат границы определён ровно один раз, и это `scripts/boundary.py`.

    Утверждение прямое, а не эвристика про «похоже на копию»: список
    несущих файлов сверяется целиком, и второй файл в нём — это провал.
    Эвристика внутри признака грубая, как и у таблицы зон: копия,
    написанная через `startswith` по строке, сюда не попадёт. Она и не
    должна — такая копия не эквивалентна, она просто неверна, и её ловит
    `TestOutside::test_prefix_match_alone_is_not_enough` этажом выше,
    в тот же день, когда её позовут.
    """

    def test_only_one_file_carries_the_comparison(self):
        self.assertEqual(_boundary_carriers(ROOT), ["scripts/boundary.py"])

    def test_a_second_copy_is_visible_to_this_check(self):
        """Регрессия на сам детектор: не находящий ничего зелен и бесполезен.

        Посажена не выдумка, а буквально тот `_inside`, который вёз этот
        план до правки, — с локальными `root_parts`/`target_parts`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            (fake / "scripts").mkdir()
            (fake / "scripts" / "boundary.py").write_bytes(
                (ROOT / "scripts" / "boundary.py").read_bytes())
            (fake / "scripts" / "install_scaffold.py").write_text(
                "import os\n"
                "from pathlib import Path\n"
                "\n"
                "def _inside(root, target):\n"
                "    root_parts = Path(os.path.realpath(str(root))).parts\n"
                "    target_parts = Path(os.path.realpath(str(target))).parts\n"
                "    return target_parts[:len(root_parts)] == root_parts\n",
                encoding="utf-8")
            self.assertEqual(_boundary_carriers(fake),
                             ["scripts/boundary.py",
                              "scripts/install_scaffold.py"])
```

Run: `python3 -m unittest tests.test_boundary.TestOneBoundaryDefinition -v`
Expected: `test_only_one_file_carries_the_comparison` FAIL —
`AssertionError: ['hooks/boundary.py'] != ['scripts/boundary.py']`. Несущий
файл уже один, и это важно: краснеет не «копий много», а «единственное
определение лежит не там, откуда его смогут спросить оба потребителя».
`test_a_second_copy_is_visible_to_this_check` на этом шаге тоже красный —
он копирует `scripts/boundary.py`, которого ещё нет.

Переезд — целым модулем, а не одной функцией. `find_root` и `outside` —
две половины одного вопроса: докстринг `find_root` прямо говорит, что
возвращает нормализованный путь «он же база для `outside`», и развести их
по разным каталогам значило бы завести два места, где решают, что такое
корень. Волне 4 `find_root` нужен из `scripts/` наравне с `outside`:
ADOPT ищет маркер до того, как что-то писать.

1. `git mv hooks/boundary.py scripts/boundary.py`. Содержимое не меняется
   ни на байт — переезжает место, а не решение.
2. `hooks/hook.py`: `from hooks import bashscan, boundary, summary, turnfiles`
   → `from hooks import bashscan, summary, turnfiles`, а `boundary` уезжает
   в соседнюю строку `from scripts import ...`. Ни `boundary.find_root`, ни
   `boundary.outside` в теле не трогаются.
3. `tests/test_boundary.py`: `from hooks import boundary` →
   `from scripts import boundary`. Единственная **существующая** строка
   файла, которая меняется: все двенадцать утверждений волны 2 остаются
   дословно теми же, и это условие правки, а не пожелание. Дописанное —
   только класс выше.
4. `dev/mutate.py`, мутация «граница сравнивается без нормализации» (в2 К4):
   путь `"hooks/boundary.py"` → `"scripts/boundary.py"`. Без этого шага
   оснастка отчитается «не легла» — то есть волна 3 сломала бы
   доказательство критерия волны 2, и отчёт назвал бы это устаревшей
   таблицей, а не переездом.

Реэкспорта в `hooks/boundary.py` не остаётся. Модуль-перенаправление дал бы
два импортируемых имени для одного предиката, а вся цена этого шага — в том,
что имя одно; «переходный» шим переживает переход всегда.

Run: `python3 -m unittest tests.test_boundary tests.test_hook_events tests.test_hook_entry -v`
Expected: зелено; `_boundary_carriers` возвращает ровно
`["scripts/boundary.py"]`. Этот шаг закрывается целиком и коммитится
отдельно (Step 7): переезд с его тестом — законченная зелёная правка, ей
не нужен ни установщик, ни каркас.

- [x] **Step 4: Реализация — `scripts/install_scaffold.py`**

```python
#!/usr/bin/env python3
"""Разворачивание каркаса рецепта в репозиторий.

Одна детерминированная операция, поэтому скрипт, а не шаг скилла: у каркаса
три потребителя (CREATE, гейт пакета, обновление версии), и все три обязаны
получить один и тот же объект байт в байт. Генератор такого не доказывает —
доказывает копия.

Ровно один файл каркаса не копируется: `settings-fragment.json` сливается
в `.claude/settings.json`. Копия поверх затёрла бы `enabledPlugins`, которым
включён сам плагин, и плагин выключил бы себя первым же действием.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import boundary
from scripts.findings import EXIT_OK, EXIT_VIOLATION

FRAGMENT = ".claude/settings-fragment.json"
SETTINGS = ".claude/settings.json"


class Refused(Exception):
    """Установка не состоялась, и причина названа.

    Отдельный класс, а не находка гейта: у находок закрытый список классов
    и таблица покрытия, а это не гейт, а отказ операции.
    """


def _union(current, addition):
    out = list(current)
    for item in addition:
        if item not in out:
            out.append(item)
    return out


def merge_settings(existing, fragment):
    """Слияние без потерь: чужие ключи остаются, списки дополняются без дублей.

    Идемпотентно: повторное слияние того же фрагмента не меняет ничего —
    иначе обновление версии дописывало бы одно и то же правило каждый раз.
    """
    merged = dict(existing)
    for key, value in fragment.items():
        if key == "permissions" and isinstance(value, dict):
            permissions = dict(merged.get("permissions") or {})
            for rule_key, rules in value.items():
                permissions[rule_key] = _union(permissions.get(rule_key) or [],
                                               rules)
            merged["permissions"] = permissions
        elif isinstance(value, list):
            merged[key] = _union(merged.get(key) or [], value)
        else:
            merged[key] = value
    return merged


def install(scaffold, root):
    """Копирует каркас в `root`, сливает настройки. Возвращает список путей.

    Ничего не перезаписывает: существующий файл — это работа автора либо
    повторный запуск, и оба случая решаются человеком, а не молча.
    """
    scaffold = Path(scaffold)
    root = Path(root)

    if not (root / ".git").exists():
        raise Refused("нет git: `git init` делается до первой записи, "
                      "иначе ничего из написанного не откатывается")

    sources = sorted(p for p in scaffold.rglob("*") if p.is_file())
    plan = []
    for source in sources:
        rel = source.relative_to(scaffold).as_posix()
        if rel == FRAGMENT:
            continue
        target = root / rel
        # Незыблемое №6, и спрошено оно у единственного места, которое на
        # этот вопрос отвечает. Своя проверка здесь была бы вторым
        # определением границы — см. Step 3.
        if boundary.outside(target, root):
            raise Refused("путь уходит за корень репозитория: %s" % rel)
        if target.exists():
            raise Refused("файл уже существует, каркас не пишется поверх: %s" % rel)
        plan.append((source, target, rel))

    fragment_path = scaffold / FRAGMENT
    fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
    settings_path = root / SETTINGS
    existing = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise Refused("%s не разобран (%s): файл есть, значит его писали, "
                          "и затирать его нельзя" % (SETTINGS, error))

    written = []
    for source, target, rel in plan:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        written.append(rel)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(merge_settings(existing, fragment), indent=2,
                   ensure_ascii=False) + "\n",
        encoding="utf-8")
    written.append(SETTINGS)
    return sorted(written)


def main(argv=None):
    parser = argparse.ArgumentParser(description="install the recipe scaffold")
    parser.add_argument("root")
    parser.add_argument("--scaffold",
                        default=str(Path(__file__).resolve().parent.parent
                                    / "scaffold"))
    args = parser.parse_args(argv)
    try:
        for rel in install(args.scaffold, args.root):
            print(rel)
    except Refused as error:
        print("каркас не развёрнут: %s" % error, file=sys.stderr)
        return EXIT_VIOLATION
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 5: Реализация — каркас попадает в снимок продукта**

В `scripts/check_package.py`:

```python
# Продукт: всё, что уезжает в пакет. `hooks/` и `skills/` в снимке не было,
# хотя docstring рядом называл его «единственным, чего тесты не вправе
# трогать»: тест, переписывающий `hooks/hook.py`, был невидим, а `hooks/` —
# уже отгруженный продукт. `scaffold/` добавлен волной 3 по той же причине:
# он уезжает пользователю целиком, а тесты волны копируют его во временные
# каталоги — значит запись в оригинал была бы ошибкой, которую никто не видит.
_PRODUCT_DIRS = ("scripts", ".claude-plugin", "hooks", "skills", "scaffold")
```

- [x] **Step 6: Прогнать — должно пройти**

Run: `./check`
Expected: код 0. Отдельно `python3 dev/mutate.py` обязан пройти без единого
«не легла»: переезд модуля тронул путь в мутации в2 К4, и это единственное
место, где волна 3 достаёт до доказательств волны 2.

- [x] **Step 7: Коммит**

Два коммита, а не один: переезд предиката — правка волны 2, и в истории
она обязана читаться отдельно от установщика, который её потребовал.
Первый коммит самодостаточен и зелен сам по себе — модуль, его потребители,
его тесты и путь в оснастке мутаций.

```bash
git add hooks/boundary.py scripts/boundary.py hooks/hook.py \
        tests/test_boundary.py dev/mutate.py
git commit -m "граница рабочего каталога переезжает в scripts: одно определение на пакет"

git add scripts/install_scaffold.py scripts/check_package.py \
        tests/test_install_scaffold.py tests/test_scaffold.py
git commit -m "wave3: установщик каркаса — копия побайтово и слияние настроек"
```

---

## Task 8: Первый коммит равен каркасу побайтово

Критерий 2 волны. Сравнение — по хешам объектов git, а не глазами: визуальный
диф не отличает «одинаково» от «похоже», а именно на одинаковости стоит вся
процедура обновления версии.

Одно исключение названо поимённо: `.claude/settings.json` — слит, а не
скопирован, и сверяется по значению JSON.

**Files:**
- Modify: `tests/test_install_scaffold.py`

- [x] **Step 1: Написать падающий тест**

```python
def _blob_id(path):
    """Идентификатор объекта git для файла, посчитанный локально.

    Формула самого git (`blob <длина>\\0<содержимое>`), поэтому подпроцесс на
    каждый файл не нужен, а сравнение остаётся сравнением хешей.
    """
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


class TestFirstCommit(unittest.TestCase):
    """Коммит 1 — база рецепта. При обновлении версии `git diff` против него
    показывает, что автор изменил сам, а что приехало из пакета; без
    побайтового равенства это неразличимо."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _new_repo(self.tmp.name)
        self.written = install_scaffold.install(SCAFFOLD, self.root)
        _git(self.root, "add", *self.written)
        _git(self.root, "commit", "-q", "-m", "scaffold")

    def _tree(self):
        listing = _git(self.root, "ls-tree", "-r", "HEAD").stdout
        out = {}
        for line in listing.strip().split("\n"):
            meta, path = line.split("\t", 1)
            out[path] = meta.split()[2]
        return out

    def test_the_commit_carries_the_scaffold_blob_for_blob(self):
        expected = {}
        for source in sorted(p for p in SCAFFOLD.rglob("*") if p.is_file()):
            rel = source.relative_to(SCAFFOLD).as_posix()
            if rel == FRAGMENT:
                continue
            expected[rel] = _blob_id(source)
        actual = {path: blob for path, blob in self._tree().items()
                  if path != SETTINGS}
        self.assertEqual(actual, expected)

    def test_the_only_path_that_is_not_a_copy_is_the_merged_settings(self):
        extra = set(self._tree()) - {
            p.relative_to(SCAFFOLD).as_posix()
            for p in SCAFFOLD.rglob("*") if p.is_file()}
        self.assertEqual(extra, {SETTINGS})

    def test_the_merged_settings_carry_the_fragment(self):
        self.assertEqual(
            json.loads((self.root / SETTINGS).read_text(encoding="utf-8")),
            json.loads((SCAFFOLD / FRAGMENT).read_text(encoding="utf-8")))

    def test_the_working_tree_is_clean_after_the_commit(self):
        """Ничего не осталось вне коммита: иначе «коммит 1 — каркас»
        неправда, и следующий Stop-хук найдёт незакоммиченное."""
        self.assertEqual(_git(self.root, "status", "--porcelain").stdout, "")

    def test_both_gates_are_green_on_the_first_commit(self):
        """Красное здесь — дефект пакета, а не репозитория: каркас во всех
        инстансах один и тот же."""
        from scripts import check_frontmatter, check_links
        self.assertEqual(check_links.scan(self.root).counts(), {})
        self.assertEqual(check_frontmatter.scan(self.root).counts(), {})

    def test_the_commit_creates_all_eight_zones(self):
        """Зона заводится всегда, даже пустой: пустая зона наблюдаема, а
        git пустых каталогов не хранит — их держат README зон."""
        from scripts import zones
        committed = {path.split("/")[0] for path in self._tree()}
        self.assertEqual(sorted(z for z in zones.ZONES if z in committed),
                         sorted(zones.ZONES))

    def test_the_commit_creates_no_collection(self):
        self.assertEqual([p for p in self._tree() if p.endswith("views.base")], [])
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_install_scaffold -v`
Expected: FAIL до появления кода Task 7 нет — код уже есть, поэтому здесь
тесты обязаны пройти сразу. Если `test_the_commit_carries_the_scaffold_blob_for_blob`
краснеет, читать разницу словарей: расхождение по ключу значит, что файл
не доехал; расхождение по значению — что доехал изменённым.

> **Оговорка про TDD.** Эта задача — не новая функция, а критерий выхода
> над уже написанным кодом. Падающий тест здесь пишется первым по форме:
> он падает, если Task 7 сделан неверно, и это единственное состояние,
> в котором он вправе краснеть.

- [x] **Step 3: Прогнать — должно пройти**

Run: `./check`
Expected: код 0.

- [x] **Step 4: Коммит**

```bash
git add tests/test_install_scaffold.py
git commit -m "wave3: первый коммит равен каркасу — сверка по хешам объектов git"
```

---

## Task 9: Скилл `create-context-repo`

Скилл, а не скрипт: диалог с порядком, из ответов собирается `core`,
выбираются стартовые коллекции, добываются настоящие exemplar'ы. Ошибка
порядка дорога — `git init` после первой записи делает написанное
неоткатываемым.

**Files:**
- Create: `skills/create-context-repo/SKILL.md`, `skills/create-context-repo/eval.txt`
- Test: `tests/test_create_skill.py`

- [ ] **Step 1: Написать падающий тест**

```python
"""Форма скилла CREATE и его эвал на срабатывание.

Проверка пакета уже требует непустого описания, совпадения имени с папкой и
непустого `eval.txt`. Здесь — то, чего она не проверяет: двуязычность фраз
(секция 25, поломка наблюдённая), порядок процедуры и запрет сочинять.
"""

import re
import unittest
from pathlib import Path

from scripts.frontmatter import parse as parse_frontmatter

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "create-context-repo"
CYRILLIC = re.compile(r"[а-яё]", re.I)


def _eval_sections():
    """Фразы, по которым скилл обязан подняться, и соседние, по которым нет."""
    sections = {"triggers": [], "non-triggers": []}
    current = None
    for line in (SKILL / "eval.txt").read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            current = line.lstrip("# ").strip()
            continue
        if current in sections:
            sections[current].append(line)
    return sections


class TestSkillForm(unittest.TestCase):
    def setUp(self):
        self.text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.fields = parse_frontmatter(self.text)

    def test_the_name_matches_the_directory(self):
        self.assertEqual(self.fields["name"], SKILL.name)

    def test_the_description_is_english(self):
        """Описание грузится всегда и решает, поднимется ли скилл вообще;
        форма английская — секция 25."""
        self.assertIsNone(CYRILLIC.search(self.fields["description"]))

    def test_it_stays_within_the_form_budget(self):
        """70–180 строк: карта процедуры, не глубина. Схождение измерено
        на трёх репозиториях владельца."""
        self.assertLessEqual(len(self.text.split("\n")), 180)
        self.assertGreaterEqual(len(self.text.split("\n")), 70)

    def test_it_calls_the_installer_through_the_plugin_root(self):
        """Относительный путь разрешится от репозитория пользователя.
        У изученного аналога так молча не работали восемь скиллов."""
        calls = [line for line in self.text.split("\n")
                 if "install_scaffold.py" in line]
        self.assertTrue(calls)
        for line in calls:
            self.assertIn("${CLAUDE_PLUGIN_ROOT}", line)

    def test_it_never_stages_everything(self):
        """`git add -A` заберёт сдвиги сабмодулей knowledge и параллельные
        правки человека в Obsidian. Коммит идёт по названным путям."""
        for banned in ("git add -A", "git add --all", "git add ."):
            self.assertNotIn(banned, self.text)

    def test_it_puts_git_init_before_the_first_write(self):
        self.assertLess(self.text.index("git init"),
                        self.text.index("install_scaffold.py"))

    def test_it_names_the_three_questions_and_no_more(self):
        """Анкета по восьми зонам отвергнута: она даёт заполненный
        репозиторий, в котором автор не отличает своё от продиктованного."""
        questions = re.findall(r"^\| \d\. (.+?) \|", self.text, re.M)
        self.assertEqual(len(questions), 3)

    def test_it_forbids_generating_the_plausible(self):
        for marker in ("Never generate", "Example Person"):
            self.assertIn(marker, self.text)

    def test_it_sends_what_was_not_obtained_to_open_threads(self):
        """Не в отчёт, исчезающий вместе с сессией."""
        self.assertIn("OPEN-THREADS.md", self.text)

    def test_it_says_what_it_does_not_do(self):
        self.assertIn("## Out of scope", self.text)

    def test_it_states_the_headless_result_as_a_result(self):
        """Форма без брифа — правильный исход, а не отказ."""
        self.assertIn("not a refusal", self.text)


class TestTriggerEval(unittest.TestCase):
    def test_triggers_are_written_in_both_languages(self):
        """Английское описание не ловит русскую просьбу — поломка
        наблюдённая, не гипотеза (секция 25)."""
        triggers = _eval_sections()["triggers"]
        russian = [p for p in triggers if CYRILLIC.search(p)]
        english = [p for p in triggers if not CYRILLIC.search(p)]
        self.assertGreaterEqual(len(russian), 5)
        self.assertGreaterEqual(len(english), 5)

    def test_neighbouring_phrases_that_must_not_raise_it_are_listed(self):
        """Половина эвала без соседних фраз доказывает только, что скилл
        поднимается на всё подряд."""
        self.assertGreaterEqual(len(_eval_sections()["non-triggers"]), 3)

    def test_the_non_triggers_name_the_two_neighbouring_modes(self):
        joined = " ".join(_eval_sections()["non-triggers"]).lower()
        self.assertIn("adopt", joined)
        self.assertIn("maintain", joined)
```

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_create_skill -v`
Expected: все FAIL — каталога `skills/create-context-repo` нет.

- [ ] **Step 3: Реализация — `skills/create-context-repo/SKILL.md`**

```markdown
---
name: create-context-repo
description: Create a context repository from scratch — eight zones, the recipe scaffold, and the author's own first records. Use when a directory carries no recipe marker and no material of its own.
---
# Create a context repository

A context repository is markdown kept for a domain — a company, a project,
hiring, a life — with Obsidian as the human front end and Claude Code as the
agent. This skill turns an empty directory into one.

## Which mode is this

Two observable facts, no judgement:

| marker file | material in the tree | mode |
|---|---|---|
| present | — | already on the recipe: maintain, extend |
| absent | none | **create** — this skill |
| absent | some | **adopt** — stop and use the adopt skill |

Material means content, not files: a settings directory, a git directory and
OS droppings do not count. One README and nothing else is the disputed case —
ask. If there is nobody to answer, take adopt: its first step is additive,
while a mistaken create writes over somebody's work.

## Order

The order is the reason this is a skill. Getting it wrong is expensive.

1. `git init` — the first action, before anything is written. Everything after
   it becomes revertible, and the end-of-turn hook does not meet a directory
   without git.
2. Install the scaffold:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/install_scaffold.py" .`
   It prints every path it wrote and refuses to overwrite anything.
3. Run both gates on the repository. Red here is a defect of the package, not
   of this repository — the scaffold is identical in every instance. Stop and
   report it rather than editing the scaffold in place.
4. **Commit 1 — the scaffold.** Stage the paths the installer printed, by
   name. Never stage everything: that would pick up submodule pointers and
   whatever the human is editing in Obsidian at that moment.
5. Ask the three questions below, or read their answers from the brief.
6. Write what the answers give, and only that.
7. Run both gates again.
8. **Commit 2 — everything that came from the author.**

The two commits are split by origin, not by time. When the recipe version is
updated later, a diff against commit 1 shows what the author changed and what
arrived from the package; without the split, the two are indistinguishable.

## The three questions

| question | what it becomes |
|---|---|
| 1. What is kept here? | the domain line in CLAUDE.md, the draft of core |
| 2. What already exists — work, material, people? | the starting collections and their archetypes |
| 3. What cannot be derived from files and cannot be checked by a machine? | the last section of CLAUDE.md |

Three, not a questionnaire over eight zones. A questionnaire gives a filled-in
repository in which the author cannot tell their own material from what was
dictated to them.

The third question usually yields nothing or one item, and that is the right
answer. Three to six items come from practice; invented on day one they are
rules nobody has broken.

## What is written from the answers

- **A zone is created always, even empty.** The scaffold already did this.
- **A collection is never created without a real record.** An empty collection
  looks like a working one and signals nothing, so it waits for content.
- `core` gets the answer to the first question: who this is, what this is —
  one page, in the author's words.
- `decisions` gets the conversation that just happened: which collections were
  chosen, which archetypes, what was rejected. This record exists whenever
  there was a conversation, because the choice was just made.
- `areas`, `projects` and `sources` get what the second answer named, and
  nothing else.

## Never generate the plausible

No invented project, no `Example Person`, no sample decision along the lines
of "chose X over Y". This is the failure mode of template generators: the tree
looks complete, the author cannot tell their own material from the decoration,
and they do not delete it in case it is needed. A synthetic record is worse
than an empty folder, because the empty folder is honest.

Whatever could not be obtained goes into `OPEN-THREADS.md` — a file in git,
not a report that dies with the session.

## Without a human

In a headless session the three questions are read from the brief. With no
brief, deploy the form: eight zones, no collection at all, and every question
recorded in the open threads. That is the correct result and **not a refusal**.

## Output

```
created: 8 zones, N collections, M records
empty: areas, sources — there was nothing to put there
gates: links ok  frontmatter ok
open threads: 5
```

## Out of scope

- A tree that already has material — that is the adopt skill, and it never
  moves anything before the author agrees to the plan line covering it.
- Keeping an existing repository in shape, including revising CLAUDE.md —
  the maintain skill.
- Adding a collection, an area or a view later — the extend skill, which will
  not finish a structural unit without real content either.
- Writing anything inside a connected knowledge base. Nobody does that.
```

- [ ] **Step 4: Реализация — `skills/create-context-repo/eval.txt`**

```
# triggers
создай контекстный репозиторий
заведи репозиторий для контекста
разверни контекстный репозиторий с нуля
сделай из этой папки контекстный репозиторий
нужен репозиторий под домен, начни с нуля
собери восемь зон и каркас
create a context repository
set up a context repo from scratch
turn this empty directory into a context repository
scaffold a new context repository
start a context repository for this domain
bootstrap the eight zones here

# non-triggers
adopt this existing vault
усынови этот репозиторий, тут уже всё лежит
maintain the repository and fix the form
почини форму в уже готовом репозитории
add a collection to an existing repository
create a python package here
```

- [ ] **Step 5: Прогнать — должно пройти**

Run: `./check`
Expected: код 0. Проверка пакета видит скилл: имя совпадает с папкой,
описание непустое, `eval.txt` непустой, относительных путей к скриптам нет,
абсолютных путей нет.

- [ ] **Step 6: Коммит**

```bash
git add skills/create-context-repo tests/test_create_skill.py
git commit -m "wave3: скилл create-context-repo — порядок, три вопроса, эвал"
```

---

## Task 10: Мутации волны и документы

Волна закрывается не зелёным `./check`, а зелёным `./check` плюс
доказательством, что посаженное нарушение его роняет.

**Files:**
- Modify: `dev/mutate.py`, `docs/criteria-coverage.md`, `docs/roadmap.md`,
  `docs/tracker.md`

- [ ] **Step 1: Дописать мутации**

Пять строк в `MUTATIONS`, по одной на каждый критерий выхода плюс одна на
правку гейта:

```python
    Mutation(
        criterion="в3 К1",
        name="каркас ссылается в свой .claude",
        module="tests.test_scaffold",
        expect="tests.test_scaffold.TestScaffoldPassesBothGates"
               ".test_both_gates_are_still_silent_without_the_claude_directory",
        steps=(
            substitution(
                "scaffold/core/README.md",
                "**Nothing here yet.**",
                "The zone rule lives in `.claude/rules/core.md`.\n\n"
                "**Nothing here yet.**",
            ),
        ),
    ),
    Mutation(
        criterion="в3 К2",
        name="установщик правит байты по дороге",
        module="tests.test_install_scaffold",
        expect="tests.test_install_scaffold.TestFirstCommit"
               ".test_the_commit_carries_the_scaffold_blob_for_blob",
        steps=(
            substitution(
                "scripts/install_scaffold.py",
                "        target.write_bytes(source.read_bytes())\n",
                "        target.write_bytes(source.read_bytes() + b\"\\n\")\n",
            ),
        ),
    ),
    Mutation(
        criterion="в3 К3",
        name="каркас везёт коллекцию без записей",
        module="tests.test_scaffold",
        expect="tests.test_scaffold.TestScaffoldInventory"
               ".test_the_scaffold_carries_no_collection",
        steps=(
            copied_file("fixtures/green/decisions/views.base",
                        "scaffold/decisions/views.base"),
        ),
    ),
    Mutation(
        criterion="в3 К4",
        name="перечисление файлов в порождённом CLAUDE.md",
        module="tests.test_scaffold",
        expect="tests.test_scaffold.TestGeneratedClaudeMd.test_it_lists_no_files",
        steps=(
            substitution(
                "scaffold/CLAUDE.md",
                "## Placement rule\n",
                "## Files\n\n- core/me.md — who we are\n\n## Placement rule\n",
            ),
        ),
    ),
    Mutation(
        # Анкер — на поведении, а не на строках Task 1. Мутация снимает
        # **ветку, исключающую README коллекции из перечисления**, и
        # опознаёт её по двум коротким приметам: сама сверка (`== declaration`,
        # без отступа и без имени слева) и её `continue`. Как записана
        # сверка — `rel == declaration_rel`, `record.resolve() == declaration`
        # или что-то третье — мутации всё равно, отступ в маркер не входит,
        # комментарий внутри ветки её не сдвигает.
        #
        # Почему не дословный кусок: первая редакция этой строки цитировала
        # две строки Task 1 вместе с шестнадцатью пробелами отступа — и
        # устарела до первого прогона, потому что Task 1 переписали. Таблица
        # мутаций, цитирующая реализацию, гниёт при каждом касании
        # реализации; `substitution` отчиталась бы «не легла», то есть о
        # чужой правке, а не о гейте (тот же довод, что у `line_removal`
        # и `block_replacement` в их докстрингах).
        #
        # `line_removal` здесь не годится: снятая одна строка `if` оставляет
        # голый `continue`, гейт перестаёт проверять записи вовсе и
        # `test_the_collections_own_readme_is_not_a_record` — он ждёт пустого
        # списка — становится **зелёным**. Мутация выжила бы, ничего не сказав.
        criterion="в3 К1",
        name="README коллекции снова перечисляется как запись",
        module="tests.test_check_frontmatter",
        expect="tests.test_check_frontmatter.TestCollectionOwnReadme"
               ".test_the_collections_own_readme_is_not_a_record",
        steps=(
            block_replacement(
                "scripts/check_frontmatter.py",
                "== declaration",
                "continue",
                "",
            ),
        ),
    ),
```

Про первую: она посажена так, что **полный** каркас остаётся зелёным — файл
существует, — и краснеет ровно прогон без `.claude/`. Это единственная
мутация, которую убивает только тест второй половины критерия 1; посади она
несуществующий путь, её убил бы любой гейтовый тест, и вторая половина
осталась бы недоказанной.

Про пятую: попутно краснеет весь `TestCollectionOwnReadme` — сверено
прогоном на дереве с реализацией Task 1: убит объявленный тест, попутно ещё
три, и все три про то же самое послабление. Это не «КРАСНОЕ НЕ ТО»:
объявленный тест в разнице есть, а соседи по классу проверяют границы того
же исключения и обязаны краснеть вместе с ним.

- [ ] **Step 2: Прогнать оснастку**

Run: `python3 dev/mutate.py`
Expected: все мутации убиты; ноль ВЫЖИЛА, ноль КРАСНОЕ НЕ ТО, ноль «не легла».
Выжившая — находка о проверке, а не повод ослабить мутацию.

- [ ] **Step 3: Дописать `docs/criteria-coverage.md`**

Новый раздел «Волна 3» с той же таблицей «критерий → чем атакован → чем
доказан», дословными критериями из `docs/roadmap.md`. Имена мутаций обязаны
совпадать с таблицей `MUTATIONS` буква в букву.

- [ ] **Step 4: Обновить `docs/roadmap.md` и `docs/tracker.md`**

В roadmap — состояние волны 3 и что она отдаёт волне 4:
`scaffold/` как объект сравнения при обновлении версии,
`scripts/install_scaffold.py` (ADOPT разворачивает недостающую форму тем же
кодом), `merge_settings`.

В tracker — строка волны и **шесть расхождений** из раздела «Расхождения»
этого плана, каждое отдельной строкой в «Правки спеки», с пометкой, какие
из них правит агент, а какие ждут автора. Строк в разделе семь: шестая
закрыта до начала волны (периметр уже различает файл и поддерево), и в
трекер она не едет — там она была бы правкой спеки, которой нет.

- [ ] **Step 5: Коммит**

```bash
git add dev/mutate.py docs/criteria-coverage.md docs/roadmap.md docs/tracker.md
git commit -m "wave3: пять мутаций на критерии выхода, покрытие и трекер"
```

---

## Закрытие волны

| критерий выхода | чем проверен |
|---|---|
| 1. The scaffold shall pass both gates with zero findings as the clean fixture, and shall still pass with the `.claude` directory removed. | `tests/test_scaffold.py::TestScaffoldPassesBothGates` — четыре теста: оба гейта на каркасе, оба на копии без `.claude/`, и отдельный тест, называющий причину (ни один переживающий файл не ссылается в `.claude/`) |
| 2. CREATE shall produce a first commit whose tree contains the scaffold byte-for-byte identical to the scaffold shipped in the package. | `tests/test_install_scaffold.py::TestFirstCommit::test_the_commit_carries_the_scaffold_blob_for_blob` — сверка идентификаторов объектов git по каждому пути; `test_the_only_path_that_is_not_a_copy_is_the_merged_settings` — исключение ровно одно и названо |
| 3. CREATE shall not complete a structural unit without real content, and where no answer is available the unit shall not be created and the question shall be recorded in open threads. | механическая половина: `TestScaffoldInventory::test_the_scaffold_carries_no_collection` и `::test_the_scaffold_carries_no_exemplar`, `TestFirstCommit::test_the_commit_creates_all_eight_zones`; половина суждения: `tests/test_create_skill.py::TestSkillForm::test_it_forbids_generating_the_plausible` и `::test_it_sends_what_was_not_obtained_to_open_threads` |
| 4. The generated `CLAUDE.md` shall carry the zone map and the placement rule, and shall contain no file listing. | `tests/test_scaffold.py::TestGeneratedClaudeMd` — девять тестов: карта из `zones.ZONES`, права записи по строкам, порядок двух вопросов правила размещения, отсутствие токена с закрытым расширением. Девятый добавлен при исполнении: восемь пропускали кириллицу в каркасе, а секция 25 — правило, значит незыблемое №2 требует под него проверку |

**Про половину суждения в критерии 3.** «Настоящая запись» — суждение о
содержимом, и машинной проверки у него нет. Незыблемое №2 запрещает называть
это гейтом: проверено то, что каркас не везёт ни одной коллекции и ни одного
образца, и что скилл несёт запрет сочинять и адрес несостоявшихся ответов.
Того, что скилл этому следует, не доказывает ничто, кроме прогона с человеком.
Записано здесь, а не умолчано.

Волна закрыта, когда `./check` зелёный **и** `python3 dev/mutate.py` не
оставил ни одного выжившего. Дальше — `superpowers:requesting-code-review`.

**Отдаёт волне 4:** `scaffold/` — объект сравнения при обновлении версии
(§21: каркас новой версии разворачивается в `tmp/` и сравнивается с деревом);
`scripts/install_scaffold.py` — ADOPT дописывает недостающую форму тем же
кодом и тем же отказом писать поверх; `merge_settings` — слияние настроек
без потери чужих ключей; `scripts/boundary.py` — граница рабочего каталога
и поиск корня, теперь доступные из `scripts/` без импорта из `hooks/`.
ADOPT спрашивает границу, а не пишет свою: копий было бы три, и
`TestOneBoundaryDefinition` краснеет на второй.

**Отдаёт волне 5:** порог «файла сверх размера» — наблюдение о дереве, и его
место в слое спроса MAINTAIN, где обход дерева уже есть. `.gitignore` размера
выразить не умеет, и волна 3 не делает вид, что правило существует.
