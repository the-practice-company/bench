# Волна 5. MAINTAIN и расширение — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** режим, который чинит форму без спроса, показывает спрос и не
действует по нему, а всё, что записал, — доказывает.

**Architecture:** три слоя (форма механически, форма содержательно, спрос),
одна статичная поверхность формы, `content_diff` как доказательство «содержимое
не тронуто», `field_map` как доказательство «ничего не подставлено молча».

**Tech Stack:** Python 3 stdlib, git, файловая система.

---

## Состояние плана

Ничего не начато. Начинать с задачи 1.

Спека волны: `docs/superpowers/specs/2026-08-29-wave-5-maintain-design.md`.
Критерии выхода: `docs/roadmap.md`, «Волна 5». Общая спека — секции 19 и 20,
плюс 2, 5, 6, 7, 9, 24, 27.

**Зависимость от волны 4.** Задачи 7 и 9 зовут `drop`, `move` и `revert`;
задача 8 — `revert`. Волна 5 начинается после закрытия волны 4.

## Что переиспользуется, а не пишется заново

| что | откуда |
|---|---|
| зоны, классы находок, признак пути | `scripts/zones.py`, `scripts/findings.py`, `scripts/paths.py` |
| оба гейта как модули | `scripts/check_links.py`, `scripts/check_frontmatter.py` |
| резолвер ссылок и счёт R | `check_links.occurrences`, `check_links.count_resolvable` |
| разбор `views.base` | `scripts/basefile.py::parse_base` |
| граница рабочего каталога | `scripts/boundary.py` |
| эталон формы | `scaffold/` — третьего определения формы волна не заводит |
| мутации чужого дерева | `scripts/adopt/{move,drop,revert,tree}.py` |

## Два инварианта волны

> **1. Форма — закрытое перечисление. Всё остальное — содержимое, и MAINTAIN
> не изменяет его никогда.**

> **2. Второй прогон по тому же дереву не меняет ни байта.**

Второй нужен ровно потому, что первый доказуем только сравнением. Отчёт,
дописывающийся при каждом запуске, и починка, переставляющая ключи местами,
проходят проверку «содержимое не тронуто» и при этом делают дерево грязным на
каждом ходе — а грязное дерево по решению §8 значит «здесь работал человек».

## Долг, принятый от волны 4

`form_collection` строится здесь — генератор формы коллекции, которого не
хватало этапу 2 ADOPT. Задача 9. Обязательство записано в `docs/tracker.md`:
ADOPT зовёт **ту же функцию**, а не свою копию, и коммит 4 усыновления
закрывается вместе с этой задачей.

## Структура файлов

| файл | ответственность |
|---|---|
| `scripts/maintain/__init__.py` | пустой; пакет |
| `scripts/maintain/surface.py` | **поверхность формы** — статичное перечисление и предикаты по нему |
| `scripts/maintain/content_diff.py` | снимок дерева и сравнение с поверхностью; `content-modified` |
| `scripts/maintain/field_map.py` | TSV массовой мутации, дифф счётчиков |
| `scripts/maintain/mechanical.py` | слой «форма механически»: что чинится из находок гейтов |
| `scripts/maintain/structural.py` | слой «форма содержательно» |
| `scripts/maintain/demand.py` | слой «спрос»: числа и даты, без вердиктов |
| `scripts/maintain/run.py` | `maintain`: три слоя, само-проверка, откат, коммит |
| `scripts/maintain/form_collection.py` | форма коллекции: `README.md`, `views.base`, `items/` |
| `scripts/maintain/extend.py` | `add-collection`, `add-area`, `add-view` |
| `scripts/maintain/backfill.py` | `backfill` и три исхода на запись |
| `fixtures/maintain/` | репозиторий, построенный рецептом, с посаженным |
| `tests/maintain_fixture.py` | разворачивание фикстуры с git-историей и пиннингом дат |
| `skills/maintain-context-repo/`, `skills/extend-structure/`, `skills/drain-inbox/` | три скилла |

Команды зовутся так же, как у ADOPT:
`python3 scripts/maintain/<модуль>.py <корень> [аргументы]`.

## Что решено здесь и не переоткрывается

Каждый пункт — решение спеки волны, у которого в плане есть исполнитель.

1. **`--today` у MAINTAIN обязателен.** У гейтов волны 1 он необязателен; там
   его отсутствие меняет текст отчёта, здесь — удаляет папку.
2. **Порог включающий: удаляем при `≥ 30` дней.** Тест утверждает границу
   поимённо: 30 — удалена, 29 — нет.
3. **Архетип к поведению записей не приводится.** §19 велит молча; §20 относит
   выбор архетипа к суждению. Расхождение показывается числами.
4. **`unresolved` чинится только в форм-файлах.** Угаданная по basename ссылка
   — переписанный авторский текст.
5. **Вид, который ничего не отбирает, показывается, а не удаляется.**
   Предикат в общем виде требует движка фильтров Obsidian Bases, которого
   пакет не строит.
6. **Пустая зона не удаляется никогда.** Зон всегда восемь.
7. **`unknown` — единственный синтетический токен рецепта.** Введён волной 4,
   второго не заводится.

---

## Task 1: Фикстура `fixtures/maintain/` и её история

Репозиторий, **построенный рецептом** — в отличие от чужой фикстуры волны 4.
Каркас плюс коллекции, и в нём посажено двенадцать наблюдений. Git-история и
её даты собираются тестом во временном каталоге: в пакете лежат просто файлы.

Даты пиннятся через `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` — без этого порог
в 30 дней нечем проверить, а `st_mtime` от чекаута зависит и потому запрещён.

**Files:**
- Create: `fixtures/maintain/**`, `tests/maintain_fixture.py`
- Test: `tests/test_maintain_fixture.py`

- [ ] **Step 1: Написать падающий тест**

`tests/test_maintain_fixture.py`:

```python
"""Фикстура MAINTAIN: двенадцать посаженных наблюдений и пиннинг дат."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.maintain_fixture import FIXTURE, TOUCHED, materialise

# Точный состав. Потерянное свойство обязано уронить набор здесь, а не тихо
# ослабить восемь задач ниже.
PLANTED = (
    "зона из карты без папки: knowledge/",
    "папка верхнего уровня вне карты: vault/",
    "направление без строки в areas/README.md: areas/hiring",
    "коллекция registry, чьи записи двигают status: core/people",
    "две пустые коллекции по разные стороны порога: "
    "projects/stale и projects/fresh",
    "вид на пустую папку: areas/work/reviews/views.base",
    "запись без created, восстановимого из git: areas/work/journal/items/a.md",
    "запись без created, невосстановимого: areas/work/journal/items/b.md",
    "поле со словарём и дырой: projects/deals/items/two.md",
    "игнорируемый бинарь без ссылающейся записи: sources/dump.bin",
    "правило со ссылкой на переименованную папку: .claude/rules/areas.md",
    "форм-секция CLAUDE.md, правленная руками",
)


class TestStored(unittest.TestCase):
    def test_the_planted_list_is_documented_in_the_fixture(self):
        """Список посаженного лежит рядом с фикстурой, а не только в тесте:
        иначе через месяц никто не знает, что здесь намеренно, а что сломалось."""
        text = (FIXTURE / "ЧТО-ПОСАЖЕНО.md").read_text(encoding="utf-8")
        missing = [p for p in PLANTED if p.split(":")[0] not in text]
        self.assertEqual(missing, [])

    def test_the_map_names_eight_zones_and_one_of_them_has_no_folder(self):
        present = sorted(p.name for p in FIXTURE.iterdir() if p.is_dir()
                         and not p.name.startswith("."))
        self.assertIn("vault", present)
        self.assertNotIn("knowledge", present)


class TestMaterialised(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_every_pinned_path_carries_the_date_it_was_given(self):
        """Даты приходят из git, а не из файловой системы: чекаут переставляет
        `st_mtime`, и результат начал бы зависеть от того, когда гоняли набор.
        Это буквально мутация, пережившая проверку волны 1."""
        for rel, date in TOUCHED.items():
            out = subprocess.run(
                ["git", "log", "-1", "--format=%cs", "--", rel],
                cwd=str(self.root), capture_output=True, text=True, check=True)
            self.assertEqual(out.stdout.strip(), date, rel)

    def test_the_two_empty_collections_sit_on_opposite_sides_of_the_threshold(self):
        self.assertEqual(TOUCHED["projects/stale"], "2026-07-01")
        self.assertEqual(TOUCHED["projects/fresh"], "2026-08-28")

    def test_the_ignored_binary_is_ignored_and_present(self):
        out = subprocess.run(["git", "check-ignore", "sources/dump.bin"],
                             cwd=str(self.root), capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertTrue((self.root / "sources" / "dump.bin").exists())

    def test_the_tree_has_a_history_not_a_single_commit(self):
        """Слой спроса меряет последним коммитом, затронувшим путь. Один
        коммит на всё сделал бы фикстуру слепой к тому, ради чего заведена."""
        out = subprocess.run(["git", "rev-list", "--count", "HEAD"],
                             cwd=str(self.root), capture_output=True, text=True,
                             check=True)
        self.assertGreater(int(out.stdout.strip()), 3)
```

- [ ] **Step 2: Прогнать — падает**

Run: `python3 -m unittest tests.test_maintain_fixture -v`
Expected: `ModuleNotFoundError: No module named 'tests.maintain_fixture'`.

- [ ] **Step 3: Реализация — `tests/maintain_fixture.py`**

```python
"""Разворачивание фикстуры MAINTAIN с пиннингом дат коммитов.

Даты — свойство истории, а не файловой системы: `st_mtime` переставляется
чекаутом, и порог в 30 дней, посчитанный по нему, зависел бы от того, когда
гоняли набор. Пиннинг через `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` — тот же
приём, которым волна 2 собирает временный репозиторий подпроцессом.
"""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "maintain"

# Путь -> дата его последнего коммита. Порядок словаря и есть порядок
# коммитов: каждая запись — отдельный коммит со своей датой.
TOUCHED = {
    "CLAUDE.md": "2026-05-01",
    ".claude/rules/areas.md": "2026-05-01",
    "core/people": "2026-08-20",
    "areas/work/journal": "2026-08-25",
    "areas/work/reviews": "2026-06-10",
    "projects/deals": "2026-08-27",
    "projects/stale": "2026-07-01",
    "projects/fresh": "2026-08-28",
    "sources": "2026-08-15",
}


def _git(root, *args, date=None):
    env = dict(os.environ)
    if date is not None:
        stamp = "%sT12:00:00+00:00" % date
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
    return subprocess.run(["git", *args], cwd=str(root), env=env,
                          capture_output=True, text=True, check=True)


def materialise(base, name="maintain"):
    """Копия фикстуры в `base/name` с историей, где у каждого пути своя дата."""
    root = Path(base) / name
    shutil.copytree(FIXTURE, root)
    (root / "ЧТО-ПОСАЖЕНО.md").unlink()   # документация фикстуры, не её часть
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "maintain@example.invalid")
    _git(root, "config", "user.name", "maintain")
    for rel, date in TOUCHED.items():
        _git(root, "add", "-A", "--", rel)
        _git(root, "commit", "-q", "-m", "фикстура: %s" % rel, date=date)
    # Всё, что не попало в перечисление, — одним коммитом самой ранней даты:
    # иначе `git status` после разворачивания не чист, а грязное дерево
    # MAINTAIN читает как след человека и не трогает путь вовсе.
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--allow-empty", "-m", "фикстура: остальное",
         date="2026-05-01")
    return root
```

Порядок коммитов важен: `git commit` берёт дату из окружения, и последний
коммит, затронувший путь, — это последний коммит **в порядке исполнения**,
а не в порядке дат. Перечисление в `TOUCHED` идёт от ранних к поздним, и
финальный «остальное» датирован самой ранней — иначе он стал бы последним
касанием для всех путей сразу и слой спроса ослеп бы целиком.

- [ ] **Step 4: Реализация — содержимое фикстуры**

Каркас берётся из `scaffold/` — **копией, а не переписыванием**: третьего
определения формы волна не заводит. Поверх копии сажается двенадцать
наблюдений.

```bash
cp -R scaffold fixtures/maintain
rm -rf fixtures/maintain/knowledge          # зона из карты без папки
mkdir -p fixtures/maintain/vault            # папка верхнего уровня вне карты
```

Дальше — файлы. Для каждого посаженного наблюдения ровно один артефакт:

`fixtures/maintain/vault/README.md`:

```markdown
# Vault

Папка верхнего уровня, которой нет в карте зон. Здесь она намеренно.
```

`fixtures/maintain/areas/hiring/README.md` — направление без строки в
`areas/README.md`:

```markdown
# Hiring

Направление есть в дереве, строки о нём в `areas/README.md` нет. Намеренно.
```

`fixtures/maintain/core/people/README.md` — коллекция `registry`, чьи записи
двигают `status`:

```markdown
---
archetype: registry
---

# Люди

Реестр. Записи при этом двигают `status` — намеренное расхождение архетипа
и поведения.
```

`fixtures/maintain/core/people/views.base`, `core/people/items/anna.md`,
`core/people/items/boris.md` — две записи с разными значениями `status`,
изменёнными между коммитами.

`fixtures/maintain/projects/stale/` и `projects/fresh/` — по `README.md` с
`archetype: pipeline`, `views.base` и **пустой** `items/`. Пустой каталог
git не хранит, поэтому в каждом лежит `items/.gitkeep`; тест задачи 6
утверждает, что `.gitkeep` записью не считается.

`fixtures/maintain/areas/work/reviews/views.base` — вид, чей
`file.inFolder("areas/work/reviews/items")` называет папку с нулём записей.

`fixtures/maintain/areas/work/journal/items/a.md` — без `created`, но с
историей, из которой он восстановим. `.../b.md` — без `created` и без
истории: файл добавляется коммитом «остальное», а тест задачи 10 требует от
`created` токен `unknown` по правилу «истории до усыновления нет». **Проверь
это утверждение при написании:** если у файла в фикстуре история есть,
`created` восстановим, и «невосстановимого» образца в фикстуре нет —
сообщи и предложи, как его сделать (например, файл, добавленный последним
коммитом, датированным тем же днём, что и `--today`).

`fixtures/maintain/projects/deals/README.md` объявляет словарь `status`;
`items/one.md` его несёт, `items/two.md` — нет (поле со словарём и дырой).

`fixtures/maintain/.gitignore` дописывает `sources/*.bin`;
`fixtures/maintain/sources/dump.bin` — игнорируемый бинарь, на который никто
не сослался.

`fixtures/maintain/.claude/rules/areas.md` — ссылка на переименованную папку.

`fixtures/maintain/CLAUDE.md` — секция `## Zone map` правлена руками
(одна строка отличается от каркасной).

`fixtures/maintain/ЧТО-ПОСАЖЕНО.md` — список двенадцати наблюдений с
объяснением каждого. Разворачивание его удаляет: это документация фикстуры,
а не её часть.

- [ ] **Step 5: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_maintain_fixture -v` затем `./check`

`fixtures/` пропускается проверкой пакета на верхнем уровне, так что
намеренно битое содержимое собственный `./check` не красит. Если красит —
это дефект периметра проверки пакета; **сообщи, не правь фикстуру.**

```bash
git add fixtures/maintain tests/maintain_fixture.py tests/test_maintain_fixture.py
git commit -m "волна 5: фикстура MAINTAIN — двенадцать наблюдений, даты из git"
```

---

## Task 2: Поверхность формы и `content_diff` — критерий 1

Волна 1 держит две формы доказательства «что именно не изменилось», и обе не
годятся здесь буквально: `check_read_only` хеширует **всё** дерево (годится
инструменту, который не пишет вовсе), `_check_tests_touched_product` хеширует
**названный набор каталогов** (годится, когда граница проходит по путям).
MAINTAIN пишет, и граница проходит **внутри файлов**.

Третья форма — не хеш, а сравнение с закрытым перечислением исключений.

**Ловушка, которую здесь обходят, названа явно.** Если множество исключений
выводить из того, что прогон записал, проверка становится тавтологией: она
исключит ровно то, что изменилось, и не покраснеет никогда. Поэтому
поверхность формы **статична и объявлена в модуле**, а из прогона берётся
только одно — таблица `field-map`, у которой есть собственная проверка на
сходимость счётчиков.

**Files:**
- Modify: `scripts/findings.py` (десять классов волны)
- Create: `scripts/maintain/__init__.py`, `scripts/maintain/surface.py`,
  `scripts/maintain/content_diff.py`
- Test: `tests/test_findings.py`, `tests/test_content_diff.py`

- [ ] **Step 1: Написать падающий тест на классы**

В `tests/test_findings.py`:

```python
class TestMaintainClasses(unittest.TestCase):
    def test_the_wave_carries_exactly_these_ten(self):
        self.assertEqual(list(findings.MAINTAIN_CLASSES), [
            "content-modified",
            "unexplained-count",
            "silent-substitution",
            "structure-without-content",
            "empty-collection",
            "declared-unused",
            "view-selects-nothing",
            "map-tree-divergence",
            "archetype-mismatch",
            "unreferenced-ignored-binary",
        ])

    def test_four_are_errors_and_six_are_reports(self):
        """Ошибка — про нарушенное обещание плагина о себе. Отчёт — про
        наблюдение о дереве, которое чинить не плагину."""
        by_severity = {}
        for cls in findings.MAINTAIN_CLASSES:
            by_severity.setdefault(findings.severity(cls), []).append(cls)
        self.assertEqual(sorted(by_severity["error"]), [
            "content-modified", "silent-substitution",
            "structure-without-content", "unexplained-count"])
        self.assertEqual(len(by_severity["report"]), 6)

    def test_no_class_named_demand_acted_on_exists(self):
        """Соблазн есть: имя выглядит как гарантия. Производителя у него в
        бою нет — это утверждение теста, — а имя без стоящего за ним
        поведения волна 1 уже оплачивала (`EXIT_TOOL_FAILED`)."""
        self.assertNotIn("demand-acted-on", findings.MAINTAIN_CLASSES)
```

- [ ] **Step 2: Реализация — десять классов в `scripts/findings.py`**

```python
MAINTAIN_CLASSES = (
    "content-modified",
    "unexplained-count",
    "silent-substitution",
    "structure-without-content",
    "empty-collection",
    "declared-unused",
    "view-selects-nothing",
    "map-tree-divergence",
    "archetype-mismatch",
    "unreferenced-ignored-binary",
)
```

и в `_SEVERITY`:

```python
    # Четыре ошибки — про нарушенное обещание плагина о себе: прогон тронул
    # содержимое, счётчики не сошлись, значение записано молча, единица
    # доведена до диска без записи. Каждая означает, что режиму нельзя
    # верить дальше.
    "content-modified": "error",
    "unexplained-count": "error",
    "silent-substitution": "error",
    "structure-without-content": "error",
    # Шесть отчётов — наблюдения о дереве. Чинить их либо не плагину
    # (архетип, карта, бинарь), либо нечем детерминированно.
    "empty-collection": "report",
    "declared-unused": "report",
    "view-selects-nothing": "report",
    "map-tree-divergence": "report",
    "archetype-mismatch": "report",
    "unreferenced-ignored-binary": "report",
```

- [ ] **Step 3: Написать падающий тест на поверхность и `content_diff`**

`tests/test_content_diff.py`:

```python
"""Критерий 1: чем доказывается, что содержимое не изменено."""

import tempfile
import unittest
from pathlib import Path

from scripts.maintain import content_diff, surface
from tests.maintain_fixture import materialise


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


class TestSurfaceIsStatic(unittest.TestCase):
    """Ловушка, ради которой поверхность объявлена, а не выведена."""

    def test_the_surface_is_a_literal_and_not_derived_from_a_run(self):
        """Выведенная из того, что прогон записал, проверка становится
        тавтологией: исключает ровно изменившееся и не краснеет никогда."""
        self.assertEqual(
            [entry.pattern for entry in surface.SURFACE],
            ["**/views.base",
             "**/README.md#frontmatter:archetype,values",
             ".claude/rules/*.md",
             "CLAUDE.md#section:Zone map,Placement rule",
             "areas/README.md#table",
             "*/README.md#absent",
             "**/items/*.md#frontmatter:absent-key",
             ".gitignore#append",
             ".claude/settings.json#merge:permissions.deny,claudeMdExcludes",
             ".twinkle-repo-builder#json:version",
             "OPEN-THREADS.md#append"])

    def test_the_body_of_a_record_is_not_on_the_surface(self):
        self.assertFalse(surface.covers("areas/work/journal/items/a.md", "body"))

    def test_core_is_never_on_the_surface(self):
        for what in ("body", "frontmatter-value", "bytes"):
            self.assertFalse(surface.covers("core/me.md", what), what)


class TestContentDiff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)
        self.before = content_diff.snapshot(self.root)

    def _diff(self, field_map=()):
        return content_diff.compare(self.before,
                                    content_diff.snapshot(self.root),
                                    field_map=field_map)

    def test_an_untouched_tree_produces_nothing(self):
        self.assertEqual(places(self._diff()), [])

    def test_rewriting_a_record_body_is_content_modified(self):
        path = self.root / "areas" / "work" / "journal" / "items" / "a.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nдописано\n",
                        encoding="utf-8")
        self.assertEqual(places(self._diff()), [
            ("areas/work/journal/items/a.md", 1, "content-modified",
             "тело записи изменилось")])

    def test_changing_an_existing_frontmatter_value_is_content_modified(self):
        path = self.root / "projects" / "deals" / "items" / "one.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("status: open", "status: decided"),
                        encoding="utf-8")
        self.assertEqual([f[2] for f in places(self._diff())],
                         ["content-modified"])

    def test_removing_a_frontmatter_key_is_content_modified(self):
        path = self.root / "projects" / "deals" / "items" / "one.md"
        text = path.read_text(encoding="utf-8")
        path.write_text("\n".join(l for l in text.split("\n")
                                  if not l.startswith("status:")),
                        encoding="utf-8")
        self.assertEqual([f[2] for f in places(self._diff())],
                         ["content-modified"])

    def test_rewriting_a_views_base_is_not_content_modified(self):
        """`views.base` целиком принадлежит плагину: §13 прямо об этом."""
        path = self.root / "projects" / "deals" / "views.base"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual(places(self._diff()), [])

    def test_a_new_frontmatter_key_is_legal_only_with_a_field_map_row(self):
        """Последняя строка правил сравнения — то, что делает `field-map`
        несущим: критерий 5 и критерий 1 держатся одним механизмом."""
        rel = "areas/work/journal/items/a.md"
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("---\n", "---\ncreated: 2026-08-25\n", 1),
                        encoding="utf-8")
        self.assertEqual([f[2] for f in places(self._diff())],
                         ["content-modified"])
        row = (rel, "created", "", "2026-08-25", "computed", "git-first-commit")
        self.assertEqual(places(self._diff(field_map=[row])), [])

    def test_a_field_map_row_with_a_different_value_does_not_excuse_it(self):
        """Иначе таблица оправдывала бы что угодно, назвав поле."""
        rel = "areas/work/journal/items/a.md"
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("---\n", "---\ncreated: 1999-01-01\n", 1),
                        encoding="utf-8")
        row = (rel, "created", "", "2026-08-25", "computed", "git-first-commit")
        self.assertEqual([f[2] for f in places(self._diff(field_map=[row]))],
                         ["content-modified"])

    def test_a_disappeared_file_is_content_modified(self):
        (self.root / "core" / "people" / "items" / "anna.md").unlink()
        self.assertEqual([f[2] for f in places(self._diff())],
                         ["content-modified"])

    def test_an_empty_collection_removed_under_the_deletion_predicate_is_not(self):
        """Единственное удаление, которое MAINTAIN делает сам. Пустая
        коллекция не может содержать содержимого по определению."""
        for path in sorted((self.root / "projects" / "stale").rglob("*"),
                           reverse=True):
            if path.is_file():
                path.unlink()
        self.assertEqual(
            places(content_diff.compare(
                self.before, content_diff.snapshot(self.root),
                deleted=("projects/stale",))), [])
```

- [ ] **Step 4: Реализация — `scripts/maintain/surface.py`**

```python
#!/usr/bin/env python3
"""Поверхность формы: единственное, что MAINTAIN вправе записать.

Статична и объявлена здесь литералом. Выведенная из того, что прогон
записал, она сделала бы `content_diff` тавтологией: проверка исключила бы
ровно то, что изменилось, и не покраснела бы никогда.

Всё, чего в перечислении нет, — содержимое: тело записи, значение
существующего поля, проза README, `.link-allow`, вложения, любой файл в
`core`, `sources`, `knowledge`, `inbox`.
"""

import sys
from fnmatch import fnmatchcase
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import zones


class Entry:
    """Строка поверхности: путь и гранулярность правки."""

    __slots__ = ("pattern", "what", "why")

    def __init__(self, pattern, what, why):
        self.pattern = pattern
        self.what = what
        self.why = why


SURFACE = (
    Entry("**/views.base", "bytes",
          "вид принадлежит плагину целиком (§13)"),
    Entry("**/README.md#frontmatter:archetype,values", "frontmatter-value",
          "два ключа объявления коллекции; тело README не трогается"),
    Entry(".claude/rules/*.md", "bytes",
          "правила рецепта принадлежат плагину целиком"),
    Entry("CLAUDE.md#section:Zone map,Placement rule", "section",
          "форм-секции побайтово из каркаса; остальное — авторское"),
    Entry("areas/README.md#table", "table-row",
          "строка таблицы — форма; фраза назначения в ней — авторская"),
    Entry("*/README.md#absent", "create",
          "README зоны создаётся, если файла нет"),
    Entry("**/items/*.md#frontmatter:absent-key", "frontmatter-add",
          "добавление отсутствующего ключа; существующее не переписывается"),
    Entry(".gitignore#append", "append",
          "дописывание строк каркаса; авторские не удаляются"),
    Entry(".claude/settings.json#merge:permissions.deny,claudeMdExcludes",
          "merge", "слияние без дублей"),
    Entry(".twinkle-repo-builder#json:version", "json-value",
          "значение версии рецепта"),
    Entry("OPEN-THREADS.md#append", "append",
          "дописывание; существующие строки не изменяются"),
)

# Зоны, где формы нет вовсе: что бы там ни лежало, это содержимое.
NEVER = frozenset(zones.READ_ONLY | {"core", "sources", "inbox"})


def covers(rel, what):
    """Разрешает ли поверхность правку такого рода по этому пути."""
    zone = zones.zone_of(rel)
    if zone in NEVER:
        return False
    for entry in SURFACE:
        pattern = entry.pattern.split("#")[0]
        if entry.what != what:
            continue
        if fnmatchcase(rel, pattern) or fnmatchcase(rel, pattern.replace("**/", "")):
            return True
    return False
```

`fnmatchcase` с `**/` работает не так, как ожидается: `*` в `fnmatch`
пересекает косые. Поэтому вторая форма сравнения — без префикса. Если это
даёт ложные совпадения на глубоких путях, **замени сопоставление на
посегментное и скажи об этом**: подгонять поверхность под сопоставитель
нельзя, она отсуждена.

- [ ] **Step 5: Реализация — `scripts/maintain/content_diff.py`**

```python
#!/usr/bin/env python3
"""Снимок дерева и сравнение с поверхностью формы.

Третья форма доказательства «что именно не изменилось». Первые две — из
волны 1: `check_read_only` хеширует всё дерево, `_check_tests_touched_product`
— названные каталоги. MAINTAIN пишет, и граница проходит внутри файлов,
поэтому здесь не хеш, а сравнение с закрытым перечислением исключений.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter
from scripts.findings import Finding
from scripts.maintain import surface


class Shot:
    __slots__ = ("bytes", "fields", "body")

    def __init__(self, raw, fields, body):
        self.bytes = raw
        self.fields = fields
        self.body = body


def _split(raw):
    """(поля, тело). Неразбираемый frontmatter — пустые поля и всё в тело:
    угадывать здесь нечего, а сравнение байтов всё равно состоится."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {}, raw
    try:
        fields = parse_frontmatter(text)
    except FrontmatterError:
        return {}, text
    if not fields:
        return {}, text
    _, _, rest = text.partition("---")
    _, _, body = rest.partition("---")
    return fields, body


def snapshot(root):
    """Путь -> Shot по всем файлам дерева, кроме `.git/`."""
    root = Path(root)
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/") or not path.is_file():
            continue
        raw = path.read_bytes()
        fields, body = _split(raw) if rel.endswith(".md") else ({}, raw)
        out[rel] = Shot(raw, fields, body)
    return out


def compare(before, after, field_map=(), deleted=()):
    """`content-modified` по правилам сравнения спеки волны.

    `field_map` — единственное, что берётся из прогона, и берётся оно узко:
    строка оправдывает **появление** ключа с **этим** значением, и ничего
    больше. Иначе таблица оправдывала бы что угодно, назвав поле.
    """
    allowed = {(row[0], row[1]): row[3] for row in field_map}
    findings = []

    def modified(rel, detail):
        findings.append(Finding("content-modified", rel, 1, detail))

    for rel, shot in sorted(before.items()):
        if any(rel == d or rel.startswith(d + "/") for d in deleted):
            continue
        if rel not in after:
            modified(rel, "файл исчез")
            continue
        now = after[rel]
        if shot.bytes == now.bytes:
            continue
        if surface.covers(rel, "bytes"):
            continue
        if shot.body != now.body:
            modified(rel, "тело записи изменилось")
            continue
        for key, value in sorted(shot.fields.items()):
            if key not in now.fields:
                modified(rel, "ключ frontmatter исчез: %s" % key)
            elif now.fields[key] != value:
                modified(rel, "значение поля изменилось: %s" % key)
        for key, value in sorted(now.fields.items()):
            if key in shot.fields:
                continue
            expected = allowed.get((rel, key))
            if expected is None or str(expected) != str(value):
                modified(rel, "поле появилось мимо field-map: %s" % key)
    return findings
```

- [ ] **Step 6: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_findings tests.test_content_diff -v`
затем `./check`

```bash
git add scripts/findings.py scripts/maintain tests/test_findings.py \
        tests/test_content_diff.py
git commit -m "волна 5: поверхность формы литералом и content_diff; критерий 1"
```

---

## Task 3: `field_map` и дифф счётчиков — критерий 5

Требование §20 к любой массовой мутации. Массовая — изменяющая больше одного
уже существующего файла; создание новых под определение не подпадает.

Формат и модуль **один на все мутации волн 4 и 5**, а не свой у каждой
команды: две копии парсера, одна из которых не исполняется никогда, — цена,
которую спека уже измерила.

**Ожидаемое считается до мутации** из множества записей коллекции — того же,
которое выводит гейт frontmatter из `file.inFolder(...)`. Фактическое — число
строк. Расхождение обязано нести объясняющий токен из закрытого списка.
Расхождение без токена — `unexplained-count`. Это и есть исполняемая форма
фразы «каждое расхождение объяснено»: без неё она осталась бы дисциплиной, а
незыблемое №2 такие правила не считает существующими.

**Files:**
- Create: `scripts/maintain/field_map.py`
- Test: `tests/test_field_map.py`

- [ ] **Step 1: Написать падающий тест**

`tests/test_field_map.py`:

```python
"""Критерий 5: машинная таблица массовой мутации и дифф счётчиков."""

import tempfile
import unittest
from pathlib import Path

from scripts.maintain import field_map
from tests.maintain_fixture import materialise


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


ROWS = (
    ("areas/work/journal/items/a.md", "created", "", "2026-08-25",
     "computed", "git-first-commit"),
    ("areas/work/journal/items/b.md", "created", "", "unknown",
     "synthetic", "no-rule"),
)


class TestFormat(unittest.TestCase):
    def test_the_columns_are_these_in_this_order(self):
        self.assertEqual(list(field_map.COLUMNS),
                         ["path", "field", "before", "after", "origin", "rule"])

    def test_the_table_is_tsv_sorted_by_path_with_a_header(self):
        text = field_map.render(ROWS)
        lines = text.rstrip("\n").split("\n")
        self.assertEqual(lines[0], "\t".join(field_map.COLUMNS))
        self.assertEqual([l.split("\t")[0] for l in lines[1:]],
                         sorted(r[0] for r in ROWS))

    def test_the_file_name_never_carries_a_date(self):
        """Метка времени в имени вернула бы часы и сломала побайтовую
        воспроизводимость теста. Перезапись прежнего файла законна: зона
        транзитная, прошлый прогон лежит в git."""
        name = field_map.name("backfill", ("areas/work/journal", "created"))
        self.assertEqual(name, "tmp/field-map-backfill-areas-work-journal-created.tsv")
        self.assertNotRegex(name, r"\d{4}-\d{2}-\d{2}")

    def test_the_three_origins_are_a_closed_set(self):
        self.assertEqual(list(field_map.ORIGINS),
                         ["computed", "synthetic", "deferred"])

    def test_no_absolute_path_can_enter_the_table(self):
        with self.assertRaises(ValueError):
            field_map.render([("/Users/кто-то/a.md", "created", "", "x",
                               "computed", "git-first-commit")])


class TestCounts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_matching_counts_produce_nothing(self):
        expected = ["a.md", "b.md"]
        rows = [("%s" % name, "created", "", "x", "computed", "r")
                for name in expected]
        self.assertEqual(places(field_map.reconcile(expected, rows, {})), [])

    def test_a_shortfall_with_a_token_is_explained(self):
        expected = ["a.md", "b.md"]
        rows = [("a.md", "created", "", "x", "computed", "r")]
        self.assertEqual(
            places(field_map.reconcile(expected, rows, {"b.md": "undecodable"})),
            [])

    def test_a_shortfall_without_a_token_is_unexplained_count(self):
        expected = ["a.md", "b.md"]
        rows = [("a.md", "created", "", "x", "computed", "r")]
        self.assertEqual(places(field_map.reconcile(expected, rows, {})), [
            ("b.md", 1, "unexplained-count",
             "запись ожидалась в таблице и её там нет, объяснения тоже")])

    def test_a_token_outside_the_closed_list_is_itself_unexplained(self):
        """Свободный токен позволил бы объяснить что угодно словом."""
        expected = ["a.md"]
        self.assertEqual(
            [f[2] for f in places(field_map.reconcile(expected, [],
                                                      {"a.md": "устал"}))],
            ["unexplained-count"])

    def test_the_closed_list_of_tokens(self):
        self.assertEqual(list(field_map.TOKENS),
                         ["undecodable", "unparseable-frontmatter",
                          "not-a-record", "dirty-path"])


class TestSilentSubstitution(unittest.TestCase):
    def test_a_deferred_row_absent_from_the_report_is_a_finding(self):
        """`deferred` больше нуля при пустом разделе отчёта — то самое
        молчание, ради запрета которого заведён незыблемый №4."""
        rows = [("a.md", "status", "", "", "deferred", "vocabulary-declared")]
        self.assertEqual(places(field_map.audit(rows, report_section="")), [
            ("a.md", 1, "silent-substitution",
             "отложено и не названо в отчёте: status")])

    def test_a_deferred_row_named_in_the_report_is_fine(self):
        rows = [("a.md", "status", "", "", "deferred", "vocabulary-declared")]
        self.assertEqual(field_map.audit(rows, report_section="a.md status"), [])

    def test_a_written_value_absent_from_the_table_is_a_finding(self):
        """Второй производитель класса: значение на диске есть, строки нет."""
        self.assertEqual(
            [f[2] for f in places(field_map.audit([], report_section="",
                                                  written=[("a.md", "created")]))],
            ["silent-substitution"])
```

- [ ] **Step 2: Реализация — `scripts/maintain/field_map.py`**

```python
#!/usr/bin/env python3
"""Машинная таблица массовой мутации и сходимость счётчиков.

Один формат и один модуль на все мутации волн 4 и 5. Формат на команду
отвергнут ценой, которую спека уже измерила: две копии парсера, одна из
которых не исполняется никогда.

TSV с заголовком, сортировка по пути, ноль абсолютных путей, часы не
читаются — те же правила, что у отчётов гейтов и у `scan-tree`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import paths as pathlib_rules
from scripts.findings import Finding

COLUMNS = ("path", "field", "before", "after", "origin", "rule")

# Три исхода на запись, и ни одного четвёртого.
ORIGINS = ("computed", "synthetic", "deferred")

# Закрытый список объясняющих токенов. Свободный токен позволил бы
# объяснить расхождение любым словом, то есть не объяснить ничем.
TOKENS = ("undecodable", "unparseable-frontmatter", "not-a-record", "dirty-path")


def name(operation, arguments):
    """Имя файла таблицы: из операции и аргументов, **никогда** из даты.

    Метка времени вернула бы часы и сломала побайтовую воспроизводимость.
    Перезапись прежнего файла законна: `tmp/` транзитна, прошлый прогон
    лежит в git.
    """
    parts = [operation] + [str(a).replace("/", "-") for a in arguments]
    return "tmp/field-map-%s.tsv" % "-".join(parts)


def render(rows):
    out = ["\t".join(COLUMNS)]
    for row in sorted(rows):
        if len(row) != len(COLUMNS):
            raise ValueError("строка таблицы не той ширины: %r" % (row,))
        if pathlib_rules.escapes_root(row[0]):
            raise ValueError("абсолютный путь в таблице: %r" % (row[0],))
        if row[4] not in ORIGINS:
            raise ValueError("происхождение вне закрытого множества: %r" % (row[4],))
        out.append("\t".join(str(cell) for cell in row))
    return "\n".join(out) + "\n"


def reconcile(expected, rows, explained):
    """`unexplained-count`: ожидалось, в таблице нет, объяснения тоже нет.

    Ожидаемое считается **до** мутации из множества записей коллекции — того
    же, которое выводит гейт frontmatter из `file.inFolder(...)`.
    """
    present = {row[0] for row in rows}
    findings = []
    for rel in sorted(expected):
        if rel in present:
            continue
        token = explained.get(rel)
        if token in TOKENS:
            continue
        findings.append(Finding(
            "unexplained-count", rel, 1,
            "запись ожидалась в таблице и её там нет, объяснения тоже"))
    return findings


def audit(rows, report_section, written=()):
    """`silent-substitution`: два производителя, оба про молчание.

    Первый — `deferred` без строки в отчёте: значение не записано и об этом
    никому не сказано. Второй — значение на диске без строки в таблице:
    записано и не названо.
    """
    findings = []
    for row in sorted(rows):
        if row[4] != "deferred":
            continue
        if row[0] in report_section and row[1] in report_section:
            continue
        findings.append(Finding("silent-substitution", row[0], 1,
                                "отложено и не названо в отчёте: %s" % row[1]))
    known = {(row[0], row[1]) for row in rows}
    for rel, field in sorted(written):
        if (rel, field) not in known:
            findings.append(Finding("silent-substitution", rel, 1,
                                    "значение записано мимо таблицы: %s" % field))
    return findings
```

- [ ] **Step 3: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_field_map -v` затем `./check`

```bash
git add scripts/maintain/field_map.py tests/test_field_map.py
git commit -m "волна 5: field-map и сходимость счётчиков; критерий 5"
```

---

## Task 4: Слой «форма механически»

MAINTAIN зовёт оба гейта и чинит то, что чинится детерминированно. Таблица
короче, чем звучит §19.

| класс находки | что делает MAINTAIN |
|---|---|
| `unresolved` в `views.base`, `.claude/rules/*.md`, форм-секциях `CLAUDE.md` | чинит: файл принадлежит плагину (§13 прямо об этом) |
| `unresolved` в теле записи, в прозе README, в `core` | **отчёт** |
| `missing-required` | backfill по правилу задачи 10, иначе отчёт |
| `value-outside-vocabulary` | **отчёт всегда.** И значение, и словарь — авторские |
| `md-link-to-file` | отчёт: конвертация — отдельная массовая мутация (§13) |
| `dead-allow`, `broad-allow` | отчёт: у строки аллоулиста обязана быть причина |
| `link-to-transient`, `escapes-root`, `ambiguous`, `orphan`, `undecodable` | отчёт |
| `unparseable` | отчёт с номером строки |

**Чинить `unresolved` везде, где цель однозначна по basename, — отвергнуто.**
Это ровно тот класс, где неверная догадка тиха: ссылка начинает резолвиться,
гейт зеленеет, а указывает она не туда, куда автор писал.

**Чем чинится форм-файл.** Не правкой ссылки, а **возвратом файла к эталону**:
`.claude/rules/*.md` и форм-секции `CLAUDE.md` берутся из `scaffold/` побайтово.
`views.base` чинится иначе — переписыванием пути в `file.inFolder(...)` на
существующий, если коллекция переехала; если цели нет вовсе, это отчёт.

**Files:**
- Create: `scripts/maintain/mechanical.py`
- Test: `tests/test_mechanical.py`

- [ ] **Step 1: Написать падающий тест**

`tests/test_mechanical.py`:

```python
"""Слой «форма механически»: что чинится, что уходит в отчёт."""

import tempfile
import unittest
from pathlib import Path

from scripts.maintain import mechanical
from tests.maintain_fixture import materialise

SCAFFOLD = Path(__file__).resolve().parent.parent / "scaffold"


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


class TestWhatIsFixed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_rule_file_is_returned_to_the_scaffold_byte_for_byte(self):
        """Правило рецепта принадлежит плагину целиком. Чинится не ссылка,
        а файл: эталон один — `scaffold/`."""
        fixed, findings, skipped = mechanical.run(self.root)
        self.assertIn(".claude/rules/areas.md", fixed)
        self.assertEqual(
            (self.root / ".claude" / "rules" / "areas.md").read_bytes(),
            (SCAFFOLD / ".claude" / "rules" / "areas.md").read_bytes())

    def test_a_hand_edited_form_section_of_claude_md_is_restored(self):
        fixed, _, _ = mechanical.run(self.root)
        self.assertIn("CLAUDE.md", fixed)
        text = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        reference = (SCAFFOLD / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(mechanical.section(reference, "Zone map"),
                      text)

    def test_prose_outside_the_form_sections_survives_the_restore(self):
        """Секция целиком — это секция, а не файл. Авторская проза рядом
        с формой остаётся."""
        path = self.root / "CLAUDE.md"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n## Мой раздел\n\nАвторский текст.\n", encoding="utf-8")
        mechanical.run(self.root)
        self.assertIn("Авторский текст.", path.read_text(encoding="utf-8"))


class TestWhatIsReported(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_an_unresolved_link_in_a_record_body_is_reported_not_guessed(self):
        """Неверная догадка здесь тиха: ссылка начинает резолвиться, гейт
        зеленеет, а указывает она не туда, куда автор писал."""
        path = self.root / "areas" / "work" / "journal" / "items" / "a.md"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\nСм. [[несуществующая-цель]].\n", encoding="utf-8")
        fixed, findings, skipped = mechanical.run(self.root)
        self.assertNotIn("areas/work/journal/items/a.md", fixed)
        self.assertIn("unresolved", [f[2] for f in places(findings)])
        self.assertIn("[[несуществующая-цель]]",
                      path.read_text(encoding="utf-8"))

    def test_a_value_outside_the_vocabulary_is_always_a_report(self):
        """И значение, и словарь авторские."""
        path = self.root / "projects" / "deals" / "items" / "one.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("status: open", "status: придумал"),
                        encoding="utf-8")
        fixed, findings, skipped = mechanical.run(self.root)
        self.assertNotIn("projects/deals/items/one.md", fixed)
        self.assertIn("value-outside-vocabulary", [f[2] for f in places(findings)])

    def test_the_allowlist_is_never_written(self):
        (self.root / ".link-allow").write_text(
            "черновики/*  # временно\n", encoding="utf-8")
        before = (self.root / ".link-allow").read_bytes()
        mechanical.run(self.root)
        self.assertEqual((self.root / ".link-allow").read_bytes(), before)


class TestDirtyPaths(unittest.TestCase):
    def test_a_path_with_uncommitted_changes_is_not_touched(self):
        """Иначе собственный откат снёс бы работу человека. Это же правило
        §8 читает незакоммиченное как след человека."""
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp)
            path = root / ".claude" / "rules" / "areas.md"
            path.write_text("правка человека\n", encoding="utf-8")
            fixed, findings, skipped = mechanical.run(root)
            self.assertNotIn(".claude/rules/areas.md", fixed)
            self.assertEqual(path.read_text(encoding="utf-8"), "правка человека\n")
            self.assertEqual(skipped, [".claude/rules/areas.md"])
```

- [ ] **Step 2: Реализация — `scripts/maintain/mechanical.py`**

```python
#!/usr/bin/env python3
"""Слой «форма механически»: оба гейта плюс детерминированные починки.

Чинится не находка, а **файл**: форм-файл возвращается к эталону из
`scaffold/`. Третьего определения формы волна не заводит.

Что не чинится — уходит в отчёт целиком, вместе с находкой гейта. Чинить
`unresolved` по догадке о basename отвергнуто: ссылка начнёт резолвиться,
гейт позеленеет, а указывать будет не туда, куда автор писал.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import check_frontmatter, check_links
from scripts.adopt import tree
from scripts.findings import Finding

ROOT = Path(__file__).resolve().parent.parent.parent
SCAFFOLD = ROOT / "scaffold"

# Форм-файлы, принадлежащие плагину целиком. Их починка — побайтовый
# возврат к эталону.
WHOLE_FILE = (".claude/rules/",)

# Секции `CLAUDE.md`, принадлежащие плагину. Остальное в файле — авторское.
FORM_SECTIONS = ("Zone map", "Placement rule")

_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.M)


def section(text, title):
    """Секция markdown целиком, вместе с заголовком, или пустая строка."""
    matches = list(_HEADING.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1) != title:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[match.start():end]
    return ""


def _dirty(root):
    """Пути с незакоммиченными изменениями. Их MAINTAIN не трогает."""
    out = set()
    for line in tree.git_lines(root, "status", "--porcelain"):
        out.add(line[3:].strip())
    return out


def run(root):
    """(исправленные пути, находки, пропущенные грязные пути).

    Пропущенное — **строка отчёта, а не находка**: класс утверждал бы, что
    что-то не так с деревом, а не так здесь ровно ничего — просто путь
    сейчас в работе у человека. Спека волны так и говорит: «такой путь
    уходит в отчёт». Заводить под это одиннадцатый класс значило бы завести
    имя без стоящего за ним нарушения.
    """
    root = Path(root)
    dirty = _dirty(root)
    fixed, findings, skipped = [], [], []

    findings.extend(check_links.scan(root).findings)
    findings.extend(check_frontmatter.scan(root).findings)

    for path in sorted(SCAFFOLD.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(SCAFFOLD).as_posix()
        if not rel.startswith(WHOLE_FILE):
            continue
        target = root / rel
        if rel in dirty:
            skipped.append(rel)
            continue
        if not target.exists() or target.read_bytes() != path.read_bytes():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            fixed.append(rel)

    claude = root / "CLAUDE.md"
    if claude.exists() and "CLAUDE.md" not in dirty:
        text = claude.read_text(encoding="utf-8")
        reference = (SCAFFOLD / "CLAUDE.md").read_text(encoding="utf-8")
        changed = text
        for title in FORM_SECTIONS:
            want = section(reference, title)
            have = section(changed, title)
            if want and have and want != have:
                changed = changed.replace(have, want, 1)
        if changed != text:
            claude.write_text(changed, encoding="utf-8")
            fixed.append("CLAUDE.md")
    elif claude.exists():
        skipped.append("CLAUDE.md")

    return sorted(fixed), findings, sorted(skipped)
```

- [ ] **Step 3: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_mechanical -v` затем `./check`

```bash
git add scripts/maintain/mechanical.py tests/test_mechanical.py
git commit -m "волна 5: слой формы механически — эталон один, догадок нет"
```

---

## Task 5: Слой «форма содержательно»

Чего гейт не видит. Четыре наблюдения, и **ни одно из них не чинится молча**,
кроме одного — отсутствующей папки зоны.

| наблюдение | класс | почему не молча |
|---|---|---|
| зона есть в карте, папки нет | — | **чинится молча:** папка и `README.md` из каркаса. Аддитивно, зоны фиксированы |
| папка верхнего уровня есть, в карте нет | `map-tree-divergence` | «починка» — либо правка фиксированной карты (запрещено §9), либо переезд содержимого (§1, авторство) |
| направление в `areas/` без строки в `areas/README.md` | `map-tree-divergence` | фраза назначения авторская |
| объявленный архетип против поведения записей | `archetype-mismatch` | §20 относит выбор архетипа к суждению |
| бинарь вне git, на который никто не сослался | `unreferenced-ignored-binary` | запись за автора не пишется |

**Архетип показывается числами, а не приводится.** Поведение вычислимо:
правился ли файл после первого коммита; менялось ли значение `status` между
коммитами. Это честная половина требования §19. Тихая смена
`journal → pipeline` сделала бы `status` обязательным, то есть починка формы
произвела бы N новых ошибок гейта.

**Порога в байтах у бинаря нет.** Предикат — не «сверх порога», а
«игнорируется git и на него никто не сослался». Порог §7 управляет решением
автора о `.gitignore`; MAINTAIN наблюдает следствие, а не причину.

**Источник списка игнорируемого проверен на живом git.**
`git status --ignored --porcelain` схлопывает каталог, где игнорируется всё
содержимое, в одну строку `sources/` — и файл внутри него не попадает в
отчёт вовсе. `--ignored=matching` схлопывает `big/` по тому же поводу.
Поимённо файлы отдаёт только
`git ls-files --others --ignored --exclude-standard`; строка с косой на
конце в его выводе — вложенный репозиторий, в который git не спускается.

**Files:**
- Create: `scripts/maintain/structural.py`
- Test: `tests/test_structural.py`

- [ ] **Step 1: Написать падающий тест**

`tests/test_structural.py`:

```python
"""Слой «форма содержательно»: четыре наблюдения и одна молчаливая починка."""

import tempfile
import unittest
from pathlib import Path

from scripts import zones
from scripts.maintain import structural
from tests.maintain_fixture import materialise


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


class TestSilentFix(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_zone_from_the_map_without_a_folder_is_created(self):
        """Аддитивно и без суждения: зон всегда восемь, и это фиксировано §9."""
        self.assertFalse((self.root / "knowledge").exists())
        created, findings = structural.run(self.root)
        self.assertEqual(created, ["knowledge", "knowledge/README.md"])
        self.assertTrue((self.root / "knowledge" / "README.md").exists())

    def test_all_eight_zones_exist_after_the_run(self):
        structural.run(self.root)
        present = {p.name for p in self.root.iterdir() if p.is_dir()}
        self.assertEqual(sorted(z for z in zones.ZONES if z not in present), [])


class TestReported(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)
        _, self.findings = structural.run(self.root)

    def test_a_top_level_folder_outside_the_map_is_reported_not_moved(self):
        """«Починка» была бы либо правкой фиксированной карты (§9), либо
        переездом содержимого (§1). Ни то ни другое плагину не принадлежит."""
        self.assertIn(("vault", 1, "map-tree-divergence",
                       "папка верхнего уровня, которой нет в карте зон"),
                      places(self.findings))
        self.assertTrue((self.root / "vault").exists())

    def test_a_direction_without_a_line_in_areas_readme_is_reported(self):
        self.assertIn(("areas/hiring", 1, "map-tree-divergence",
                       "направление без строки в areas/README.md"),
                      places(self.findings))

    def test_the_archetype_mismatch_carries_numbers_not_a_verdict(self):
        """Честная половина требования §19: поведение вычислимо, значит
        показывается. Приведение отвергнуто — §20 относит выбор архетипа
        к суждению, а смена архетипа производит N ошибок гейта."""
        mismatch = [f for f in places(self.findings) if f[2] == "archetype-mismatch"]
        self.assertEqual([f[0] for f in mismatch], ["core/people"])
        self.assertRegex(mismatch[0][3], r"registry.*status.*\d+")

    def test_the_archetype_is_not_rewritten(self):
        text = (self.root / "core" / "people" / "README.md").read_text(encoding="utf-8")
        self.assertIn("archetype: registry", text)

    def test_an_ignored_binary_nobody_links_to_is_reported(self):
        """Предикат — не «сверх порога», а «игнорируется git и на него никто
        не сослался». Порога в байтах волна не заводит и не наследует."""
        self.assertIn(("sources/dump.bin", 1, "unreferenced-ignored-binary",
                       "файл вне git, на него никто не сослался"),
                      places(self.findings))

    def test_nothing_but_the_missing_zone_appeared_on_disk(self):
        """Слой показывает; создаёт он ровно одно — недостающую зону."""
        self.assertFalse((self.root / "areas" / "hiring" / "README.md")
                         .read_text(encoding="utf-8").startswith("<!-- "))


class TestReadOnlyExceptTheZone(unittest.TestCase):
    def test_a_second_run_changes_nothing(self):
        """Инвариант 2 волны: второй прогон не меняет ни байта."""
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp)
            structural.run(root)
            def digest():
                h = hashlib.sha256()
                for path in sorted(p for p in root.rglob("*") if p.is_file()):
                    if ".git/" in path.as_posix():
                        continue
                    h.update(path.relative_to(root).as_posix().encode("utf-8"))
                    h.update(path.read_bytes())
                return h.hexdigest()
            before = digest()
            structural.run(root)
            self.assertEqual(digest(), before)
```

- [ ] **Step 2: Реализация — `scripts/maintain/structural.py`**

```python
#!/usr/bin/env python3
"""Слой «форма содержательно»: чего гейт не видит.

Молча чинится ровно одно — отсутствующая папка зоны, и только потому, что
зон всегда восемь и они фиксированы §9. Всё остальное показывается:
«починка» была бы либо правкой фиксированной карты, либо переездом
содержимого, а ни то ни другое плагину не принадлежит.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import check_links, zones
from scripts.adopt import tree
from scripts.basefile import parse_base
from scripts.findings import Finding
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter

ROOT = Path(__file__).resolve().parent.parent.parent
SCAFFOLD = ROOT / "scaffold"


def _directions(root):
    base = root / "areas"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


def _listed_directions(root):
    readme = root / "areas" / "README.md"
    if not readme.exists():
        return set()
    text = readme.read_text(encoding="utf-8")
    return set(re.findall(r"\[\[areas/([^/\]]+)", text)) | \
        set(re.findall(r"`([\w-]+)`", text))


def _archetype_behaviour(root, collection):
    """Числа о поведении записей: правок после первого коммита и смен status.

    Вычислимо из git, поэтому показывается. Приведение архетипа к поведению
    отвергнуто: §20 относит выбор архетипа к суждению, а смена архетипа
    делает `status` обязательным — то есть тихая починка формы производит
    N новых ошибок гейта.
    """
    edits = statuses = 0
    items = root / collection / "items"
    for path in sorted(items.glob("*.md")) if items.is_dir() else []:
        rel = path.relative_to(root).as_posix()
        commits = tree.git_lines(root, "log", "--format=%H", "--", rel)
        if len(commits) > 1:
            edits += 1
        values = tree.git_lines(root, "log", "-S", "status:", "--format=%H",
                                "--", rel)
        if len(values) > 1:
            statuses += 1
    return edits, statuses


def _collections(root):
    out = []
    for readme in sorted(root.rglob("README.md")):
        rel = readme.parent.relative_to(root).as_posix()
        if not (readme.parent / "views.base").exists():
            continue
        try:
            fields = parse_frontmatter(readme.read_text(encoding="utf-8"))
        except (FrontmatterError, UnicodeDecodeError):
            continue
        if fields.get("archetype"):
            out.append((rel, fields["archetype"]))
    return out


def run(root):
    """(созданные пути, находки)."""
    root = Path(root)
    created, findings = [], []

    for zone in zones.ZONES:
        target = root / zone
        if target.is_dir():
            continue
        target.mkdir(parents=True)
        created.append(zone)
        reference = SCAFFOLD / zone / "README.md"
        if reference.exists():
            (target / "README.md").write_bytes(reference.read_bytes())
            created.append("%s/README.md" % zone)

    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if entry.name in zones.ZONES:
            continue
        findings.append(Finding("map-tree-divergence", entry.name, 1,
                                "папка верхнего уровня, которой нет в карте зон"))

    listed = _listed_directions(root)
    for direction in _directions(root):
        if direction in listed:
            continue
        findings.append(Finding("map-tree-divergence", "areas/%s" % direction, 1,
                                "направление без строки в areas/README.md"))

    for collection, archetype in _collections(root):
        edits, statuses = _archetype_behaviour(root, collection)
        if archetype == "registry" and statuses:
            findings.append(Finding(
                "archetype-mismatch", collection, 1,
                "объявлен registry, у %d записей менялось значение status "
                "(правок после первого коммита: %d)" % (statuses, edits)))
        elif archetype == "journal" and edits:
            findings.append(Finding(
                "archetype-mismatch", collection, 1,
                "объявлен journal, %d записей правились после первого "
                "коммита (смен status: %d)" % (edits, statuses)))

    referenced = set()
    occs, _ = check_links.occurrences(root)
    for hit in occs:
        referenced.update(hit.candidates)
    # Источник — `ls-files`, а не `status --ignored`: последний схлопывает
    # игнорируемый каталог в одну строку (`sources/`), и файл внутри него
    # исчезает из отчёта целиком. Измерено: каталог, где игнорируется всё
    # содержимое, отдаётся именно так, и `sources/dump.bin` не виден.
    # Строка с косой на конце — вложенный репозиторий: git в него не
    # спускается, а `foreign-repo` — не бинарь и не наша забота здесь.
    for rel in tree.git_lines(root, "ls-files", "--others", "--ignored",
                              "--exclude-standard"):
        if rel.endswith("/") or rel in referenced:
            continue
        if not (root / rel).is_file():
            continue
        findings.append(Finding("unreferenced-ignored-binary", rel, 1,
                                "файл вне git, на него никто не сослался"))

    return sorted(created), findings
```

`for occ, _ in [check_links.occurrences(root)]` — уродливая форма
распаковки. Напиши `occs, _ = check_links.occurrences(root)` и цикл по
`occs`. Оставь остальное как есть.

- [ ] **Step 3: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_structural -v` затем `./check`

```bash
git add scripts/maintain/structural.py tests/test_structural.py
git commit -m "волна 5: слой формы содержательно — архетип числами, не приведением"
```

---

## Task 6: Слой «спрос» — числа и даты, без вердиктов

Объявленное и неиспользуемое. Мерится из git по **структурным единицам** —
восемь зон, направления, коллекции. Единиц десятки, а не тысячи; по файлам
git не опрашивается никогда.

**Слой печатает числа и даты, а не вердикты.** Ни «протухло», ни «мало», ни
«пора». §27 отверг меру потому, что порога назвать нельзя, — и это остаётся
верным: разница между показом и мерой в том, кто делает вывод.

**Слой слеп после ADOPT, и это называется вслух.** Спрос мерится последним
коммитом, затронувшим путь; после усыновления у каждого пути последний коммит
— сегодняшний, потому что история начинается коммитом «как было». Единица, у
которой история короче порога, получает токен `history-starts-<дата>` вместо
числа дней. Тот же запрет молчаливой заглушки, что `no-git` у `scan-tree` и
`unknown` у `created`.

**Files:**
- Create: `scripts/maintain/demand.py`
- Test: `tests/test_demand.py`

- [ ] **Step 1: Написать падающий тест**

`tests/test_demand.py`:

```python
"""Слой спроса: показывает и не действует."""

import tempfile
import unittest
from pathlib import Path

from scripts.maintain import demand
from tests.maintain_fixture import materialise


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


class TestObservations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)
        self.report, self.findings = demand.run(self.root, today="2026-08-29")

    def test_both_empty_collections_are_named(self):
        empty = [f for f in places(self.findings) if f[2] == "empty-collection"]
        self.assertEqual([f[0] for f in empty], ["projects/fresh", "projects/stale"])

    def test_a_view_selecting_an_empty_folder_is_named(self):
        self.assertIn(("areas/work/reviews", 1, "view-selects-nothing",
                       "file.inFolder называет папку с нулём записей: "
                       "areas/work/reviews/items"),
                      places(self.findings))

    def test_a_declared_direction_without_material_is_named(self):
        declared = [f for f in places(self.findings) if f[2] == "declared-unused"]
        self.assertIn("areas/hiring", [f[0] for f in declared])

    def test_the_report_carries_dates_and_no_verdicts(self):
        """§27 отверг меру потому, что порога назвать нельзя. Показ — не мера:
        разница в том, кто делает вывод."""
        for word in ("протухл", "устарел", "пора", "мало", "слишком"):
            self.assertNotIn(word, self.report.lower(), word)
        self.assertIn("2026-07-01", self.report)

    def test_nothing_on_disk_changed(self):
        """Read-only доказывается хешем дерева, как у гейтов волны 1."""
        import hashlib
        def digest():
            h = hashlib.sha256()
            for path in sorted(p for p in self.root.rglob("*") if p.is_file()):
                if ".git/" in path.as_posix():
                    continue
                h.update(path.relative_to(self.root).as_posix().encode("utf-8"))
                h.update(path.read_bytes())
            return h.hexdigest()
        before = digest()
        demand.run(self.root, today="2026-08-29")
        self.assertEqual(digest(), before)


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

    def test_a_history_shorter_than_the_threshold_says_so_instead_of_a_number(self):
        """После ADOPT у каждого пути последний коммит — сегодняшний. Слой не
        имеет права отчитаться, что всё свежее."""
        self.assertEqual(demand.age(self.root, "projects/stale", "2026-05-15"),
                         "history-starts-2026-05-01")

    def test_a_submodule_pin_date_is_shown_without_a_verdict(self):
        """Самый слабый пункт волны и первый кандидат на снятие. Локальный
        git, без сети, без порога, без вердикта."""
        report, _ = demand.run(self.root, today="2026-08-29")
        self.assertIn("пин", report)
```

- [ ] **Step 2: Реализация — `scripts/maintain/demand.py`**

```python
#!/usr/bin/env python3
"""Слой спроса: объявленное и неиспользуемое, числами и датами.

Ни «протухло», ни «мало», ни «пора». §27 отверг меру потому, что порога
назвать нельзя, и это остаётся верным: разница между показом и мерой в том,
кто делает вывод.

Часы не читаются. «Сегодня» приходит параметром и обязателен, «последнее
касание» — из git. `st_mtime` запрещён: чекаут его переставляет, и результат
начинает зависеть от того, когда гоняли набор.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import zones
from scripts.adopt import tree
from scripts.basefile import parse_base
from scripts.findings import Finding

HISTORY_STARTS = "history-starts-%s"


def _iso(text):
    year, month, day = (int(part) for part in text.split("-"))
    return date(year, month, day)


def _first_commit_date(root):
    dates = tree.git_lines(root, "log", "--date=short", "--format=%cd", "--reverse")
    return dates[0] if dates else None


def age(root, rel, today):
    """Дней с последнего коммита, затронувшего путь, либо токен начала истории.

    Токен вместо числа — когда сама история короче того, о чём спрашивают.
    После ADOPT у каждого пути последний коммит сегодняшний, и число «ноль
    дней» было бы правдоподобной неправдой.
    """
    root = Path(root)
    touched = tree.git_lines(root, "log", "-1", "--date=short", "--format=%cd",
                             "--", rel)
    if not touched:
        return None
    days = (_iso(today) - _iso(touched[0])).days
    started = _first_commit_date(root)
    if started is not None and (_iso(today) - _iso(started)).days < days + 1:
        return HISTORY_STARTS % started
    return days


def _records(root, collection):
    items = Path(root) / collection / "items"
    if not items.is_dir():
        return []
    # `.gitkeep` записью не является: он существует только потому, что git
    # не хранит пустых каталогов.
    return sorted(p.name for p in items.glob("*.md"))


def _collections(root):
    root = Path(root)
    return sorted(p.parent.relative_to(root).as_posix()
                  for p in root.rglob("views.base"))


def run(root, today):
    """(отчёт, находки). Ничего не пишет на диск."""
    root = Path(root)
    findings, lines = [], []

    for collection in _collections(root):
        records = _records(root, collection)
        touched = age(root, collection, today)
        lines.append("%s: записей %d, последнее касание %s"
                     % (collection, len(records), touched))
        if not records:
            findings.append(Finding("empty-collection", collection, 1,
                                    "виды есть, записей ноль"))
        base = parse_base((root / collection / "views.base")
                          .read_text(encoding="utf-8"))
        for folder in sorted(base.folders):
            target = root / folder
            if target.is_dir() and not sorted(target.glob("*.md")):
                findings.append(Finding(
                    "view-selects-nothing", collection, 1,
                    "file.inFolder называет папку с нулём записей: %s" % folder))

    for zone in zones.ZONES:
        target = root / zone
        if not target.is_dir():
            continue
        material = [p for p in target.rglob("*.md") if p.name != "README.md"]
        lines.append("%s: материала %d, последнее касание %s"
                     % (zone, len(material), age(root, zone, today)))
        if not material:
            findings.append(Finding("declared-unused", zone, 1,
                                    "зона объявлена, материала нет"))

    areas = root / "areas"
    for direction in sorted(p.name for p in areas.iterdir()
                            if areas.is_dir() and p.is_dir()):
        rel = "areas/%s" % direction
        material = [p for p in (root / rel).rglob("*.md") if p.name != "README.md"]
        if not material:
            findings.append(Finding("declared-unused", rel, 1,
                                    "направление объявлено, материала нет"))

    for line in tree.git_lines(root, "submodule", "status"):
        parts = line.split()
        if len(parts) < 2:
            continue
        pinned = tree.git_lines(root, "log", "-1", "--date=short", "--format=%cd",
                                "--", parts[1])
        lines.append("пин сабмодуля %s: %s"
                     % (parts[1], pinned[0] if pinned else "нет коммита"))

    return "\n".join(lines) + "\n", findings
```

- [ ] **Step 3: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_demand -v` затем `./check`

Число 59 в `test_the_age_is_counted_from_git_and_not_from_the_file_system`
посчитано от 2026-07-01 до 2026-08-29. **Пересчитай при написании** и
поправь, если разошлось; литерал здесь честнее вызова `date`, потому что
тест не должен уметь считать так же, как считает продукт.

```bash
git add scripts/maintain/demand.py tests/test_demand.py
git commit -m "волна 5: слой спроса — числа, даты и токен вместо ноля дней"
```

---

## Task 7: Пустая коллекция и порог — критерий 2

> **MAINTAIN shall show demand and shall not act on it.**

Ровно один порог всё-таки назван, и граница проходит не там, где кажется.
Порог нужен не показу, а **действию**: удалению пустой коллекции. У показа
цены ошибки нет, у удаления есть. Поэтому §19 вправе назвать 30 дней, а §27
вправе отказать в пороге — они говорят о разных вещах.

Пустая коллекция не может содержать содержимого по определению, поэтому
удаление не пересекает линию ответственности.

**Удаляет `drop` волны 4, второго скрипта не заводится.** У `drop` появляется
вторая форма авторизации: вместо строки плана — предикат пустоты и порога,
который скрипт **вычисляет сам**, а не принимает флагом. Форма та же, что у
`check-plan`: авторизация — проверенный факт, а не доверие вызывающему.

**Порог включающий: удаляем при `≥ 30` дней.**

**Files:**
- Modify: `scripts/adopt/drop.py` (вторая форма авторизации)
- Create: `scripts/maintain/prune.py`
- Test: `tests/test_prune.py`, `tests/test_drop.py`

- [ ] **Step 1: Написать падающий тест**

`tests/test_prune.py`:

```python
"""Критерий 2: показывает спрос и не действует по нему."""

import tempfile
import unittest
from pathlib import Path

from scripts.maintain import content_diff, prune
from tests.maintain_fixture import materialise


def dirs(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                  if p.is_dir() and ".git" not in p.parts)


class TestThreshold(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_only_the_collection_past_the_threshold_is_removed(self):
        """Соблазнительный случай не выдуман: обе коллекции пусты, кодовый
        путь удаления существует и авторизован, удерживает только порог."""
        removed, report = prune.run(self.root, today="2026-08-29")
        self.assertEqual(removed, ["projects/stale"])
        self.assertFalse((self.root / "projects" / "stale").exists())
        self.assertTrue((self.root / "projects" / "fresh").exists())

    def test_the_set_of_directories_changed_by_exactly_one(self):
        before = set(dirs(self.root))
        prune.run(self.root, today="2026-08-29")
        after = set(dirs(self.root))
        self.assertEqual(sorted(before - after),
                         ["projects/stale", "projects/stale/items"])
        self.assertEqual(after - before, set())

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
        self.assertEqual(prune.run(self.root, today="2026-07-31")[0],
                         ["projects/stale"])

    def test_a_collection_with_a_record_is_never_removed(self):
        removed, _ = prune.run(self.root, today="2030-01-01")
        self.assertNotIn("core/people", removed)
        self.assertNotIn("areas/work/journal", removed)

    def test_an_empty_zone_is_never_removed(self):
        """Зон всегда восемь."""
        removed, _ = prune.run(self.root, today="2030-01-01")
        self.assertEqual([r for r in removed if "/" not in r], [])

    def test_both_collections_are_named_in_the_report(self):
        removed, report = prune.run(self.root, today="2026-08-29")
        self.assertIn("projects/stale", report)
        self.assertIn("projects/fresh", report)


class TestFalsifiers(unittest.TestCase):
    """Три реализации, обязанные покраснеть. Каждая — подменённая функция,
    а не испорченное заранее дерево: фальсифицируется код, а не вход."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_prune_without_a_threshold_removes_both(self):
        """Первый: удаляющий обе. Кодовый путь удаления существует и
        авторизован; удерживает только порог."""
        with mock.patch.object(prune, "THRESHOLD_DAYS", 0):
            removed, _ = prune.run(self.root, today="2026-08-29")
        self.assertEqual(removed, ["projects/fresh", "projects/stale"])

    def test_reading_the_clock_instead_of_today_changes_the_answer(self):
        """Второй: `datetime.now()` вместо параметра. Подменяем возраст на
        тот, который дала бы сегодняшняя дата, — ответ обязан разойтись."""
        with mock.patch.object(demand, "age", lambda root, rel, today: 0):
            removed, _ = prune.run(self.root, today="2026-08-29")
        self.assertEqual(removed, [])

    def test_st_mtime_instead_of_git_gives_a_different_age(self):
        """Третий, и он измерен: чекаут переставляет `st_mtime`, поэтому
        возраст, посчитанный по нему, у только что развёрнутой фикстуры
        нулевой — а git знает 2026-07-01."""
        path = self.root / "projects" / "stale"
        by_mtime = (date(2026, 8, 29)
                    - date.fromtimestamp(path.stat().st_mtime)).days
        self.assertLess(by_mtime, prune.THRESHOLD_DAYS)
        self.assertEqual(demand.age(self.root, "projects/stale", "2026-08-29"),
                         59)

    def test_shifting_the_boundary_by_one_changes_the_verdict(self):
        """Четвёртый: порог, сдвинутый на день. Граница включающая."""
        with mock.patch.object(prune, "THRESHOLD_DAYS", 60):
            self.assertEqual(prune.run(self.root, today="2026-08-29")[0], [])
```

Дополнить импорты файла: `from datetime import date`,
`from unittest import mock`, `from scripts.maintain import demand`.

- [ ] **Step 2: Реализация — вторая форма авторизации у `drop`**

В `scripts/adopt/drop.py` добавить:

```python
def run_authorised(root, source, reason):
    """Удаление, авторизованное **проверенным фактом**, а не строкой плана.

    Вызывающий передаёт причину строкой; сам факт проверяется здесь заново.
    Форма та же, что у `check-plan`: авторизация — это проверенный факт, а
    не доверие вызывающему.
    """
```

Реализация повторяет `run`, но вместо `agreed_line` зовёт предикат,
переданный вызывающим и **перепроверяемый**: путь существует, лежит в HEAD,
внутри корня, и `reason` — из закрытого множества причин.

- [ ] **Step 3: Реализация — `scripts/maintain/prune.py`**

```python
#!/usr/bin/env python3
"""Единственное удаление, которое MAINTAIN делает сам.

Пустая коллекция не может содержать содержимого по определению, поэтому
удаление не пересекает линию ответственности. Порог включающий: `≥ 30` дней.

Обе даты приходят извне процесса. `--today` обязателен: у гейта отсутствие
даты меняет текст отчёта, здесь — удаляет папку. Умолчание из системных
часов вернуло бы в мутирующий режим ту самую зависимость, которую волна 1
выкорчёвывала дважды.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import drop
from scripts.findings import EXIT_OK
from scripts.maintain import demand

THRESHOLD_DAYS = 30
REASON = "пустая коллекция за порогом"


def run(root, today):
    """(удалённые пути, отчёт)."""
    root = Path(root)
    removed, lines = [], []
    for collection in demand._collections(root):
        records = demand._records(root, collection)
        touched = demand.age(root, collection, today)
        if records:
            continue
        lines.append("%s: пуста, последнее касание %s" % (collection, touched))
        if not isinstance(touched, int) or touched < THRESHOLD_DAYS:
            continue
        report, code = drop.run_authorised(root, collection, REASON)
        if code == EXIT_OK:
            removed.append(collection)
            lines.append("удалена: %s (%d дней)" % (collection, touched))
        else:
            lines.append(report.strip())
    return sorted(removed), "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="remove empty collections past the threshold")
    parser.add_argument("root")
    parser.add_argument("--today", required=True,
                        help="обязателен: здесь дата удаляет папку, а не меняет текст")
    args = parser.parse_args(argv)
    removed, report = run(args.root, args.today)
    sys.stdout.write(report)
    return EXIT_OK
```

`demand._collections` и `demand._records` — служебные имена. Либо сделай их
публичными в `demand.py`, либо перенеси в общий модуль; импорт подчёркнутого
имени между модулями пакета — та цена, которую волна 1 уже платила осознанно
(`check_package` импортирует `_ignored`), но здесь она не обязательна.

- [ ] **Step 4: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_prune tests.test_drop -v` затем `./check`

```bash
git add scripts/adopt/drop.py scripts/maintain/prune.py \
        tests/test_prune.py tests/test_drop.py
git commit -m "волна 5: порог пустой коллекции, вторая форма авторизации drop"
```

---

## Task 8: `maintain` целиком — само-проверка, откат, коммит

**Проверка исполняется в бою, а не только в тестах.** MAINTAIN снимает «до»,
применяет починки, зовёт `content_diff`, и на любой находке `content-modified`
**откатывает себя целиком** через `revert` волны 4 и отчитывается отказом.

Покрыть критерий одними тестами на фикстуре — отвергнуто: тесты доказывают
поведение на фикстуре, а режим по построению работает без присмотра на
репозитории, полном авторской работы. Проверка, которой там нет, там и не
работает.

**Полное множество изменённых путей берётся из `git status --porcelain`** до
и после, а не из намерений модуля. Запись, о которой модуль не отчитался,
видна именно так и стоит один вызов git.

**MAINTAIN коммитит свои починки отдельным коммитом.** Иначе `SessionStart`
следующей сессии прочитает их как работу человека (§8), а `Stop` увидит
незакоммиченное. `git add` — **только по путям, которые MAINTAIN записал,
никогда `-A`**.

**Files:**
- Create: `scripts/maintain/run.py`
- Test: `tests/test_maintain_run.py`

- [ ] **Step 1: Написать падающий тест**

`tests/test_maintain_run.py`:

```python
"""MAINTAIN целиком: три слоя, само-проверка, откат, отдельный коммит."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from scripts.maintain import run as maintain
from tests.maintain_fixture import materialise


def digest(root):
    h = hashlib.sha256()
    for path in sorted(p for p in Path(root).rglob("*") if p.is_file()):
        if ".git/" in path.as_posix():
            continue
        h.update(path.relative_to(root).as_posix().encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()


class TestRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_it_commits_its_own_fixes_separately(self):
        """Иначе `SessionStart` следующей сессии прочитает их как работу
        человека, а `Stop` увидит незакоммиченное."""
        before = tree.head(self.root)
        report, code = maintain.run(self.root, today="2026-08-29")
        self.assertEqual(code, EXIT_OK, report)
        self.assertNotEqual(tree.head(self.root), before)
        subject = tree.git_lines(self.root, "log", "-1", "--format=%s")[0]
        self.assertIn("MAINTAIN", subject)

    def test_the_commit_names_only_the_paths_maintain_wrote(self):
        """`git add -A` подобрал бы чужое незакоммиченное. Правило волны 2."""
        (self.root / "core" / "черновик.md").write_text("моё\n", encoding="utf-8")
        maintain.run(self.root, today="2026-08-29")
        touched = tree.git_lines(self.root, "show", "--name-only", "--format=",
                                 "HEAD")
        self.assertNotIn("core/черновик.md", touched)

    def test_the_tree_is_clean_of_maintain_after_the_run(self):
        maintain.run(self.root, today="2026-08-29")
        dirty = [l for l in tree.git_lines(self.root, "status", "--porcelain")]
        self.assertEqual([l for l in dirty if "черновик" not in l], [])

    def test_a_second_run_changes_not_one_byte(self):
        """Инвариант 2 волны. Отчёт, дописывающийся при каждом запуске, и
        починка, переставляющая ключи, проходят «содержимое не тронуто» и
        при этом делают дерево грязным на каждом ходе."""
        maintain.run(self.root, today="2026-08-29")
        before = digest(self.root)
        head = tree.head(self.root)
        maintain.run(self.root, today="2026-08-29")
        self.assertEqual(digest(self.root), before)
        self.assertEqual(tree.head(self.root), head)

    def test_open_threads_is_appended_idempotently(self):
        maintain.run(self.root, today="2026-08-29")
        first = (self.root / "OPEN-THREADS.md").read_bytes()
        maintain.run(self.root, today="2026-08-29")
        self.assertEqual((self.root / "OPEN-THREADS.md").read_bytes(), first)

    def test_the_report_has_three_sections_and_a_field_map_link(self):
        report, _ = maintain.run(self.root, today="2026-08-29")
        for title in ("Форма механически", "Форма содержательно", "Спрос"):
            self.assertIn(title, report)

    def test_the_report_carries_no_absolute_path_and_no_clock(self):
        report, _ = maintain.run(self.root, today="2026-08-29")
        self.assertNotIn(str(self.root), report)


class TestSelfCheck(unittest.TestCase):
    """Само-проверка в бою. Продукт не несёт ни одного крючка ради теста:
    портит содержимое подменённый слой, а не флаг в сигнатуре."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_run_that_touches_content_rolls_itself_back_and_refuses(self):
        """Тесты доказывают поведение на фикстуре, а режим работает без
        присмотра на репозитории, полном авторской работы. Проверка, которой
        там нет, там и не работает."""
        rel = "areas/work/journal/items/a.md"

        def sabotage(root):
            path = Path(root) / rel
            path.write_text(path.read_text(encoding="utf-8") + "\nдописано\n",
                            encoding="utf-8")
            return [rel], [], []

        before = digest(self.root)
        head = tree.head(self.root)
        with mock.patch.object(maintain.mechanical, "run", sabotage):
            report, code = maintain.run(self.root, today="2026-08-29")
        self.assertEqual(code, EXIT_VIOLATION, report)
        self.assertIn("content-modified", report)
        self.assertIn("откатил себя", report)
        self.assertEqual(digest(self.root), before)
        self.assertEqual(tree.head(self.root), head)
```

Дополнить импорты файла: `from unittest import mock`.

- [ ] **Step 2: Реализация — `scripts/maintain/run.py`**

```python
#!/usr/bin/env python3
"""MAINTAIN: три слоя, само-проверка, откат, отдельный коммит.

Порядок обязателен: снимок «до» снимается раньше первой починки, иначе
доказывать нечем. На любой находке `content-modified` прогон откатывает
себя целиком через `revert` волны 4 — не потому, что откат красив, а потому,
что режим работает без присмотра на репозитории, полном авторской работы.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import revert, tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION, Report
from scripts.maintain import content_diff, demand, mechanical, prune, structural

SECTIONS = ("Форма механически", "Форма содержательно", "Спрос")
COMMIT_SUBJECT = "MAINTAIN: починки формы"
THREADS = "OPEN-THREADS.md"


def _append_threads(root, suggestions):
    """Дописывание идемпотентно: у предложения стабильный ключ (класс плюс
    путь), уже присутствующее не дописывается."""
    path = Path(root) / THREADS
    text = path.read_text(encoding="utf-8") if path.exists() else "# Open threads\n"
    added = []
    for key, line in sorted(suggestions):
        if key in text:
            continue
        added.append("- %s <!-- %s -->" % (line, key))
    if not added:
        return False
    path.write_text(text.rstrip("\n") + "\n" + "\n".join(added) + "\n",
                    encoding="utf-8")
    return True


def run(root, today):
    root = Path(root)
    before = content_diff.snapshot(root)
    dirty_before = set(tree.git_lines(root, "status", "--porcelain"))

    fixed, mech_findings, skipped = mechanical.run(root)
    created, struct_findings = structural.run(root)
    removed, prune_report = prune.run(root, today=today)
    demand_report, demand_findings = demand.run(root, today=today)

    suggestions = [("%s %s" % (f.cls, f.path), "%s: %s" % (f.path, f.detail))
                   for f in struct_findings + demand_findings]
    threads_written = _append_threads(root, suggestions)

    written = sorted(set(fixed) | set(created) | ({THREADS} if threads_written else set()))
    violations = content_diff.compare(before, content_diff.snapshot(root),
                                      deleted=removed)
    if violations:
        revert.run(root, sorted(set(written) | set(removed)) or ["."])
        return (Report(violations).render() +
                "\nпрогон откатил себя целиком\n"), EXIT_VIOLATION

    if written or removed:
        tree.git(root, "add", "--", *(written + removed))
        tree.git(root, "commit", "-q", "-m", COMMIT_SUBJECT)

    dirty_after = set(tree.git_lines(root, "status", "--porcelain"))
    unexpected = sorted(dirty_after - dirty_before)

    out = ["## %s" % SECTIONS[0],
           Report(mech_findings).render(),
           "исправлено: %s" % (", ".join(fixed) or "ничего"),
           "пропущено как незакоммиченное: %s" % (", ".join(skipped) or "ничего"),
           "## %s" % SECTIONS[1],
           Report(struct_findings).render(),
           "создано: %s" % (", ".join(created) or "ничего"),
           "## %s" % SECTIONS[2],
           demand_report.rstrip("\n"),
           prune_report.rstrip("\n"),
           Report(demand_findings).render()]
    if unexpected:
        out.append("незакоммиченное после прогона: %s" % ", ".join(unexpected))
    return "\n".join(part for part in out if part) + "\n", EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="fix form, show demand")
    parser.add_argument("root")
    parser.add_argument("--today", required=True)
    args = parser.parse_args(argv)
    report, code = run(args.root, args.today)
    sys.stdout.write(report)
    return code
```

- [ ] **Step 3: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_maintain_run -v` затем `./check`

```bash
git add scripts/maintain/run.py tests/test_maintain_run.py
git commit -m "волна 5: MAINTAIN целиком — само-проверка в бою и откат себя"
```

---

## Task 9: `form_collection` и `extend-structure` — критерий 3

> **`extend-structure` shall not create a structural unit without content.**

**Порядок обратный тому, как читается §20: сначала запись, потом единица.**
`add-collection` принимает первую настоящую запись **входом** и до её
появления не создаёт ни папки, ни `README.md`. Развернуть скелет, затем
спросить, затем откатить — отвергнуто: откат безопасен, но оборванный прогон
оставляет пустую коллекцию, а пустая коллекция «не сигналит ничем» (§17).
Единственный способ, которым инвариант выполняется механически, — не
создавать до того.

**Это же закрывает долг волны 4.** `form_collection` — тот генератор формы,
которого не хватало этапу 2 ADOPT. ADOPT зовёт **эту** функцию, а не свою
копию.

**`add-view` отказывается на виде, который ничего не отберёт.** Иначе
`extend-structure` заводит ровно то, что слой спроса тут же покажет мёртвым.
Проверяется только статически разрешимый случай — папка из
`file.inFolder(...)` пуста; фильтр не вычисляется. Движка фильтров Obsidian
Bases пакет не строит, и реализация фильтра по догадке, на основании которой
**удаляется** авторский вид, — худший обмен в этой волне.

**`add-area` правит `areas/README.md`.** §20 освобождает от обновления только
`CLAUDE.md`, а §4 требует, чтобы README зоны `areas` нёс перечисление
направлений с фразой назначения. Не обновлять его — завести источник дрейфа
по построению.

**Files:**
- Modify: `scaffold/areas/README.md` (заголовок перечисления)
- Create: `scripts/maintain/form_collection.py`, `scripts/maintain/extend.py`
- Test: `tests/test_form_collection.py`, `tests/test_extend.py`,
  `tests/test_scaffold.py`

- [ ] **Step 1: Правка каркаса**

`scaffold/areas/README.md` сегодня несёт фразу «Nothing here yet» и **не
несёт заголовка перечисления**. Заголовок добавляется, фраза переезжает под
него как единственная строка «пусто».

Маркеры-комментарии вокруг машинной области отвергнуты: невидимая в Obsidian
разметка, второго такого синтаксиса в рецепте нет, а заголовок уже есть и уже
английский по §25.

```markdown
## Directions

Nothing here yet.
```

Утверждение в `tests/test_scaffold.py`:

```python
    def test_the_areas_readme_carries_the_directions_heading(self):
        """`add-area` дописывает строку под фиксированный заголовок. Без него
        перечисление негде вести, и §4 остаётся невыполнимым."""
        text = (SCAFFOLD / "areas" / "README.md").read_text(encoding="utf-8")
        self.assertIn("\n## Directions\n", text)
```

- [ ] **Step 2: Написать падающий тест на `form_collection`**

`tests/test_form_collection.py`:

```python
"""Форма коллекции: три архетипа, готовый вид, ни одной пустой единицы."""

import tempfile
import unittest
from pathlib import Path

from scripts import check_frontmatter, check_links
from scripts.basefile import parse_base
from scripts.frontmatter import parse as parse_frontmatter
from scripts.maintain import form_collection

RECORD = """\
---
type: deal
created: 2026-08-29
status: open
---

# Первая сделка

Настоящая запись, а не заглушка.
"""


class TestForm(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _make(self, archetype="pipeline"):
        return form_collection.create(
            self.root, "projects/deals", archetype,
            record_name="first.md", record_text=RECORD)

    def test_the_three_archetypes_are_a_closed_set(self):
        self.assertEqual(list(form_collection.ARCHETYPES),
                         ["journal", "pipeline", "registry"])

    def test_it_creates_readme_views_and_the_record(self):
        created = self._make()
        self.assertEqual(created, [
            "projects/deals",
            "projects/deals/README.md",
            "projects/deals/items",
            "projects/deals/items/first.md",
            "projects/deals/views.base",
        ])

    def test_without_a_record_nothing_reaches_the_disk(self):
        """Критерий 3. Развернуть скелет и откатить отвергнуто: оборванный
        прогон оставляет пустую коллекцию, а она не сигналит ничем."""
        with self.assertRaises(form_collection.NoContent):
            form_collection.create(self.root, "projects/deals", "pipeline",
                                   record_name=None, record_text=None)
        self.assertFalse((self.root / "projects").exists())

    def test_an_archetype_outside_the_set_creates_nothing(self):
        with self.assertRaises(ValueError):
            form_collection.create(self.root, "projects/deals", "дневничок",
                                   record_name="first.md", record_text=RECORD)
        self.assertFalse((self.root / "projects").exists())

    def test_the_readme_declares_the_archetype_and_the_pipeline_vocabulary(self):
        self._make("pipeline")
        fields = parse_frontmatter(
            (self.root / "projects" / "deals" / "README.md")
            .read_text(encoding="utf-8"))
        self.assertEqual(fields["archetype"], "pipeline")
        self.assertEqual(fields["values"]["status"], ["open", "decided", "revisited"])

    def test_a_journal_declares_no_vocabulary(self):
        """Словарь принадлежит конвейеру. У журнала статуса нет вовсе."""
        form_collection.create(self.root, "areas/work/journal", "journal",
                               record_name="a.md", record_text=RECORD)
        fields = parse_frontmatter(
            (self.root / "areas" / "work" / "journal" / "README.md")
            .read_text(encoding="utf-8"))
        self.assertNotIn("values", fields)

    def test_the_view_points_at_the_items_folder_of_this_collection(self):
        self._make()
        base = parse_base((self.root / "projects" / "deals" / "views.base")
                          .read_text(encoding="utf-8"))
        self.assertEqual(sorted(base.folders), ["projects/deals/items"])

    def test_both_gates_are_silent_on_what_it_produced(self):
        """Форма, которую производит плагин, обязана проходить гейты плагина.
        Красное здесь — дефект пакета, а не инстанса."""
        self._make()
        self.assertEqual(
            [(f.path, f.line, f.cls, f.detail)
             for f in check_links.scan(self.root).findings], [])
        self.assertEqual(
            [(f.path, f.line, f.cls, f.detail)
             for f in check_frontmatter.scan(self.root).findings], [])
```

- [ ] **Step 3: Реализация — `scripts/maintain/form_collection.py`**

```python
#!/usr/bin/env python3
"""Форма коллекции: `README.md`, `views.base`, `items/` и первая запись.

Порядок обратный тому, как читается §20: сначала запись, потом единица.
Развернуть скелет, спросить и откатить отвергнуто — оборванный прогон
оставил бы пустую коллекцию, а пустая коллекция не сигналит ничем (§17).

Один генератор на две волны: этап 2 ADOPT зовёт эту же функцию.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Архетип зарабатывает существование готовым видом и готовым гейтом, а не
# шаблоном контента (§5). Множество закрыто.
ARCHETYPES = ("journal", "pipeline", "registry")

# Словарь принадлежит конвейеру. У журнала статуса нет вовсе, у реестра
# выраженного жизненного цикла нет по определению.
VOCABULARIES = {"pipeline": ("open", "decided", "revisited")}

# Форма вида — та же, что у фикстур волны 1 (`fixtures/green/decisions/
# views.base`): `filters` верхним уровнем, `views` со `groupBy` и `order`.
# Форма с блоком `sort:` разобрана и **отвергнута**: `_identifiers` в
# `scripts/basefile.py` вытаскивает из неё `property`, `direction` и `DESC`
# как имена полей, и гейт frontmatter начинает требовать их от каждой
# записи. Проверено разбором, а не выведено из документации.
_VIEW = {
    "journal": ("По дате", "created"),
    "pipeline": ("По статусу", "status"),
    "registry": ("По типу", "type"),
}


class NoContent(Exception):
    """Единица не заводится без содержимого. Это инвариант, а не ошибка ввода."""


def _readme(collection, archetype):
    title = collection.rsplit("/", 1)[-1]
    lines = ["---", "archetype: %s" % archetype]
    vocabulary = VOCABULARIES.get(archetype)
    if vocabulary:
        lines.append("values:")
        lines.append("  status:")
        lines.extend("    - %s" % value for value in vocabulary)
    lines.extend(["---", "", "# %s" % title, "",
                  "Коллекция архетипа `%s`." % archetype, ""])
    return "\n".join(lines)


def _views(collection, archetype):
    name, group = _VIEW[archetype]
    lines = [
        "filters:",
        "  and:",
        '    - file.inFolder("%s/items")' % collection,
        "views:",
        "  - type: table",
        "    name: %s" % name,
        "    groupBy: %s" % group,
        "    order:",
        "      - created",
        "",
    ]
    return "\n".join(lines)


def create(root, collection, archetype, record_name, record_text):
    """(созданные пути). Ничего не пишет, пока не проверено всё."""
    if archetype not in ARCHETYPES:
        raise ValueError("архетип вне закрытого множества: %r" % (archetype,))
    if not record_name or not (record_text or "").strip():
        raise NoContent("первая настоящая запись обязательна: %s" % collection)
    root = Path(root)
    base = root / collection
    if base.exists():
        raise ValueError("путь уже занят: %s" % collection)

    created = [collection]
    (base / "items").mkdir(parents=True)
    (base / "README.md").write_text(_readme(collection, archetype),
                                    encoding="utf-8")
    created.append("%s/README.md" % collection)
    created.append("%s/items" % collection)
    (base / "items" / record_name).write_text(record_text, encoding="utf-8")
    created.append("%s/items/%s" % (collection, record_name))
    (base / "views.base").write_text(_views(collection, archetype),
                                     encoding="utf-8")
    created.append("%s/views.base" % collection)
    return sorted(created)
```

Форма `views.base` проверена разбором до написания плана. `parse_base` на
ней даёт: pipeline — `required={status}`, `known={created}`; journal —
`required={created}`; registry — `required={type}`. Все три требования
покрыты стартовым набором `check_frontmatter.STARTER_ALWAYS` и правилом
архетипа `pipeline`, поэтому гейт frontmatter на свежей коллекции молчит.
Если у тебя выходит иначе — это расхождение, и оно идёт в отчёт.

- [ ] **Step 4: Написать падающий тест на `extend`**

`tests/test_extend.py`:

```python
"""Критерий 3: единица не заводится без содержимого. Три команды."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.findings import EXIT_OK, EXIT_VIOLATION
from scripts.maintain import extend
from tests.maintain_fixture import materialise
from tests.test_form_collection import RECORD


class TestAddCollection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_with_a_record_the_collection_appears(self):
        report, code = extend.add_collection(
            self.root, "projects/leads", "pipeline",
            record_name="first.md", record_text=RECORD)
        self.assertEqual(code, EXIT_OK, report)
        self.assertTrue((self.root / "projects" / "leads" / "views.base").exists())

    def test_headless_without_a_record_creates_nothing_and_asks(self):
        """Критерий 3, и он проверяется отсутствием на диске, а не намерением."""
        report, code = extend.add_collection(
            self.root, "projects/leads", "pipeline",
            record_name=None, record_text=None)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertFalse((self.root / "projects" / "leads").exists())
        threads = (self.root / "OPEN-THREADS.md").read_text(encoding="utf-8")
        self.assertIn("projects/leads", threads)

    def test_the_post_condition_catches_a_unit_that_reached_the_disk_empty(self):
        """`structure-without-content` — постусловие команды, а не обход
        дерева. Обходом он ловил бы и пустые коллекции слоя спроса, у которых
        свой класс: `empty-collection` — наблюдение о дереве,
        `structure-without-content` — нарушенное обещание команды о себе.

        Проверяется подменённым генератором: команда обязана заметить, что
        то, что она создала, содержимого не несёт, и откатить."""
        def empty(root, collection, archetype, record_name, record_text):
            (Path(root) / collection / "items").mkdir(parents=True)
            return [collection, "%s/items" % collection]

        with mock.patch.object(extend.form_collection, "create", empty):
            report, code = extend.add_collection(
                self.root, "projects/ghost", "pipeline",
                record_name="first.md", record_text=RECORD)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("structure-without-content", report)
        self.assertFalse((self.root / "projects" / "ghost").exists())

    def test_an_empty_collection_of_the_fixture_is_not_this_class(self):
        """Разведение двух классов проверяется, а не декларируется."""
        report, code = extend.add_collection(
            self.root, "projects/leads", "pipeline",
            record_name="first.md", record_text=RECORD)
        self.assertNotIn("structure-without-content", report)


class TestAddArea(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_direction_with_a_purpose_gets_a_folder_and_a_row(self):
        """§4 требует от README зоны `areas` перечисления с фразой назначения.
        Не обновлять его — завести источник дрейфа по построению."""
        report, code = extend.add_area(self.root, "sales", "Продажи и сделки.")
        self.assertEqual(code, EXIT_OK, report)
        self.assertTrue((self.root / "areas" / "sales" / "README.md").exists())
        listing = (self.root / "areas" / "README.md").read_text(encoding="utf-8")
        self.assertIn("Продажи и сделки.", listing)
        self.assertLess(listing.index("## Directions"),
                        listing.index("Продажи и сделки."))

    def test_without_a_purpose_neither_the_folder_nor_the_row_appears(self):
        """Содержимое у направления при заведении и есть его назначение."""
        report, code = extend.add_area(self.root, "sales", "")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertFalse((self.root / "areas" / "sales").exists())
        self.assertNotIn("sales",
                         (self.root / "areas" / "README.md").read_text(encoding="utf-8"))

    def test_a_taken_name_is_refused(self):
        report, code = extend.add_area(self.root, "hiring", "Найм.")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("имя занято", report)

    def test_a_name_that_is_not_a_folder_name_is_refused(self):
        report, code = extend.add_area(self.root, "продажи/сделки", "Х.")
        self.assertEqual(code, EXIT_VIOLATION)


class TestAddView(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_view_over_an_empty_folder_is_refused(self):
        """Иначе `extend-structure` заводит ровно то, что слой спроса тут же
        покажет мёртвым."""
        report, code = extend.add_view(self.root, "areas/work/reviews",
                                       name="Всё")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("папка с нулём записей", report)

    def test_a_collection_without_views_base_is_refused(self):
        report, code = extend.add_view(self.root, "core", name="Всё")
        self.assertEqual(code, EXIT_VIOLATION)

    def test_a_taken_view_name_is_refused(self):
        report, code = extend.add_view(self.root, "core/people", name="По типу")
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("имя вида занято", report)

    def test_the_filter_is_never_evaluated(self):
        """Проверяется только статически разрешимый случай. Движка фильтров
        Obsidian Bases пакет не строит и не собирается."""
        self.assertFalse(hasattr(extend, "evaluate_filter"))
```

- [ ] **Step 5: Реализация — `scripts/maintain/extend.py`**

Четыре команды, одна процедура. Каждая: проверить всё, потом писать; отказ —
код 2 с названной причиной и вопросом в `OPEN-THREADS.md`.

```python
#!/usr/bin/env python3
"""`extend-structure`: заводит единицу только вместе с её содержимым.

Порядок обратный §20: сначала запись, потом единица. Инвариант выполняется
механически ровно одним способом — не создавать до того.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.basefile import parse_base
from scripts.findings import EXIT_OK, EXIT_VIOLATION, Finding
from scripts.maintain import form_collection

DIRECTIONS_HEADING = "## Directions"
_NAME = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")
THREADS = "OPEN-THREADS.md"


def _ask(root, key, question):
    """Вопрос в открытые нити. Идемпотентно: у вопроса стабильный ключ."""
    path = Path(root) / THREADS
    text = path.read_text(encoding="utf-8") if path.exists() else "# Open threads\n"
    if key in text:
        return
    path.write_text(text.rstrip("\n") + "\n- %s <!-- %s -->\n" % (question, key),
                    encoding="utf-8")


def _remove(root, collection):
    """Снос только что созданного. Обратимо по построению: до команды тут
    не было ничего, поэтому чужого содержимого здесь быть не может."""
    base = Path(root) / collection
    for path in sorted(base.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    if base.exists():
        base.rmdir()


def add_collection(root, collection, archetype, record_name, record_text):
    root = Path(root)
    try:
        form_collection.create(root, collection, archetype,
                               record_name, record_text)
    except form_collection.NoContent:
        _ask(root, "add-collection %s" % collection,
             "какая первая настоящая запись ляжет в %s" % collection)
        return ("отказ: коллекция не заводится без первой записи: %s\n"
                % collection), EXIT_VIOLATION
    except ValueError as error:
        return "отказ: %s\n" % error, EXIT_VIOLATION

    # Постусловие, а не обход дерева. Обходом класс ловил бы и пустые
    # коллекции слоя спроса, у которых своё имя (`empty-collection`):
    # то — наблюдение о дереве, это — нарушенное обещание команды о себе.
    items = root / collection / "items"
    if not (items.is_dir() and sorted(items.glob("*.md"))):
        _remove(root, collection)
        return (Report([Finding("structure-without-content", collection, 1,
                                "единица дошла до диска без записи")]).render()
                + "\nсоздание отменено\n"), EXIT_VIOLATION
    return "заведена коллекция: %s\n" % collection, EXIT_OK


def add_area(root, name, purpose):
    root = Path(root)
    if not _NAME.match(name):
        return "отказ: не имя папки: %s\n" % name, EXIT_VIOLATION
    if (root / "areas" / name).exists():
        return "отказ: имя занято: %s\n" % name, EXIT_VIOLATION
    if not (purpose or "").strip():
        _ask(root, "add-area %s" % name,
             "какое назначение у направления %s" % name)
        return ("отказ: направление не заводится без фразы назначения: %s\n"
                % name), EXIT_VIOLATION

    readme = root / "areas" / "README.md"
    text = readme.read_text(encoding="utf-8")
    if DIRECTIONS_HEADING not in text:
        return "отказ: в areas/README.md нет заголовка перечисления\n", EXIT_VIOLATION
    (root / "areas" / name).mkdir(parents=True)
    (root / "areas" / name / "README.md").write_text(
        "# %s\n\n%s\n" % (name, purpose.strip()), encoding="utf-8")
    head, _, tail = text.partition(DIRECTIONS_HEADING)
    row = "- [[areas/%s/README|%s]] — %s" % (name, name, purpose.strip())
    body = [l for l in tail.split("\n") if l.strip() != "Nothing here yet."]
    body.insert(1, row)
    readme.write_text(head + DIRECTIONS_HEADING + "\n".join(body),
                      encoding="utf-8")
    return "заведено направление: areas/%s\n" % name, EXIT_OK


def add_view(root, collection, name):
    root = Path(root)
    base_path = root / collection / "views.base"
    if not base_path.exists():
        return "отказ: у %s нет views.base\n" % collection, EXIT_VIOLATION
    text = base_path.read_text(encoding="utf-8")
    if "name: %s" % name in text:
        return "отказ: имя вида занято: %s\n" % name, EXIT_VIOLATION
    base = parse_base(text)
    for folder in sorted(base.folders):
        target = root / folder
        empty = not target.is_dir() or not sorted(target.glob("*.md"))
        if empty:
            return ("отказ: file.inFolder называет папку с нулём записей: %s\n"
                    % folder), EXIT_VIOLATION
    base_path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    return "добавлен вид: %s\n" % name, EXIT_OK
```

Дополнить импорты модуля: `from scripts.findings import Report`.

`add_view` в этом сниппете дописывает только перевод строки — вид как
таковой не добавляется. Это заглушка: **напиши настоящую вставку вида** в
`views.base` той же формой, что `form_collection._views`, с именем из
аргумента. Отказы, которые тесты утверждают, от этого не меняются.

- [ ] **Step 6: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_form_collection tests.test_extend tests.test_scaffold -v`
затем `./check`

```bash
git commit -- scaffold/areas/README.md scripts/maintain/form_collection.py \
  scripts/maintain/extend.py tests/test_form_collection.py \
  tests/test_extend.py tests/test_scaffold.py \
  -m "волна 5: форма коллекции и extend-structure; критерий 3"
```

---

## Task 10: `backfill` и незыблемое №4 — критерий 4

> **`backfill` shall not write a synthetic value silently, and an
> unrecoverable value shall either be marked synthetic or sent to the report.**

Три исхода на запись, и ни одного четвёртого:

| исход | когда | что на диске | в `field-map` |
|---|---|---|---|
| `computed` | у поля есть именованное правило и оно дало значение | настоящее значение | правило поимённо |
| `synthetic` | правила нет **и** словарь у поля не объявлен | токен `unknown` | `no-rule` |
| `deferred` | правила нет **и** словарь объявлен | **ничего не пишется** | `vocabulary-declared`, запись в отчёте |

**Почему словарь разводит вторую и третью ветку.** `unknown` в поле с
объявленным словарём — это `value-outside-vocabulary`, то есть починка,
производящая ошибку гейта. `status` попадает под это всегда: §2 называет его
невосстановимым по определению. Значит `backfill status` не пишет ничего и
уходит в отчёт — не по особому правилу, а по общему.

**MAINTAIN зовёт backfill не всегда.** §19 относит backfill к молчаливому;
здесь это сужено: **молча — только когда все записи попадают в `computed`.**
Появилась хоть одна `synthetic` или `deferred` — не пишется ничего, поле
уходит в отчёт, backfill исполняет `extend-structure` по запросу. Довод:
backfill трогает каждую запись коллекции, и режим без присмотра не имеет
права проштамповать `unknown` по двумстам файлам, не имея кому это сказать.

**Files:**
- Create: `scripts/maintain/backfill.py`
- Test: `tests/test_backfill.py`

- [ ] **Step 1: Написать падающий тест**

`tests/test_backfill.py`:

```python
"""Критерий 4: ничего не подставлено молча, и каждое значение проверяемо."""

import tempfile
import unittest
from pathlib import Path

from scripts.adopt import tree
from scripts.frontmatter import parse as parse_frontmatter
from scripts.maintain import backfill
from tests.maintain_fixture import materialise


class TestOutcomes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_the_three_outcomes_and_no_fourth(self):
        self.assertEqual(list(backfill.OUTCOMES),
                         ["computed", "synthetic", "deferred"])

    def test_the_named_rules_are_these(self):
        self.assertEqual(sorted(backfill.RULES),
                         ["body-words", "filename-date", "filename-source",
                          "git-first-commit"])

    def test_a_field_with_a_declared_vocabulary_is_deferred_not_stamped(self):
        """`unknown` в поле со словарём — это `value-outside-vocabulary`,
        то есть починка, производящая ошибку гейта. §2 называет `status`
        невосстановимым по определению."""
        rows, report = backfill.run(self.root, "projects/deals", "status")
        origins = {row[4] for row in rows}
        self.assertEqual(origins, {"deferred"})
        self.assertEqual(
            parse_frontmatter((self.root / "projects" / "deals" / "items"
                               / "two.md").read_text(encoding="utf-8"))
            .get("status"), None)
        self.assertIn("projects/deals/items/two.md", report)

    def test_the_exact_list_of_rows_for_created(self):
        """Точный список кортежей, и каждое `computed` пересчитывается
        независимо из git."""
        rows, _ = backfill.run(self.root, "areas/work/journal", "created")
        self.assertEqual(
            [(r[0], r[1], r[3], r[4], r[5]) for r in rows],
            [("areas/work/journal/items/a.md", "created", "2026-08-25",
              "computed", "git-first-commit"),
             ("areas/work/journal/items/b.md", "created", "unknown",
              "synthetic", "no-rule")])

    def test_each_computed_value_is_recomputed_independently(self):
        rows, _ = backfill.run(self.root, "areas/work/journal", "created")
        for row in rows:
            if row[4] != "computed":
                continue
            dates = tree.git_lines(self.root, "log", "--date=short",
                                   "--format=%cd", "--reverse", "--", row[0])
            self.assertEqual(row[3], dates[0], row[0])


class TestNothingIsOverwritten(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_collection_where_everyone_has_the_field_produces_nothing(self):
        """Фальсификатор — backfill, переписывающий существующее."""
        before = {p: p.read_bytes() for p in
                  (self.root / "core" / "people" / "items").glob("*.md")}
        rows, _ = backfill.run(self.root, "core/people", "type")
        self.assertEqual(rows, [])
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw, path.name)


class TestMaintainCallsItNarrowly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_one_unrecoverable_record_stops_the_whole_collection(self):
        """Фальсификатор спеки: девять из десяти восстановимы, одна нет.
        Не записано **ни одной**, и запись названа в отчёте."""
        before = {p: p.read_bytes() for p in
                  (self.root / "areas" / "work" / "journal" / "items").glob("*.md")}
        written, report = backfill.run_silently(self.root,
                                                "areas/work/journal", "created")
        self.assertEqual(written, [])
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw, path.name)
        self.assertIn("b.md", report)

    def test_a_fully_computable_collection_is_filled_silently(self):
        (self.root / "areas" / "work" / "journal" / "items" / "b.md").unlink()
        tree.git(self.root, "commit", "-q", "-am", "убрали невосстановимую")
        written, _ = backfill.run_silently(self.root, "areas/work/journal",
                                           "created")
        self.assertEqual(written, ["areas/work/journal/items/a.md"])
```

- [ ] **Step 2: Реализация — `scripts/maintain/backfill.py`**

```python
#!/usr/bin/env python3
"""`backfill`: три исхода на запись и ни одного четвёртого.

`unknown` — единственный синтетический токен рецепта, введённый волной 4 для
`created` без истории. Второго не заводится. Он не является датой и не
станет ею никогда — именно то свойство, ради которого §20 запрещает
молчаливую подстановку: подставленное значение от настоящего неотличимо,
`unknown` отличим всегда.

Помечать синтетику соседним полем-списком отвергнуто: второй учёт того же
факта, а §22 уже запретил хранить выводимое. Токен на месте самодостаточен,
происхождение лежит в `field-map`.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import tree
from scripts.adopt.dates import UNKNOWN
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter

OUTCOMES = ("computed", "synthetic", "deferred")

_DATE_IN_NAME = re.compile(r"\A(\d{4}-\d{2}-\d{2})")


def _git_first_commit(root, rel, _text):
    dates = tree.git_lines(root, "log", "--date=short", "--format=%cd",
                           "--reverse", "--", rel)
    return dates[0] if dates else None


def _filename_date(_root, rel, _text):
    match = _DATE_IN_NAME.match(Path(rel).name)
    return match.group(1) if match else None


def _filename_source(_root, rel, _text):
    stem = Path(rel).stem
    return stem.split("--", 1)[0] if "--" in stem else None


def _body_words(_root, _rel, text):
    body = text.split("---", 2)[-1]
    return str(len(body.split()))


# Правила поимённо. Множество расширяется по потребителю, §2 задаёт правило.
RULES = {
    "git-first-commit": _git_first_commit,
    "filename-date": _filename_date,
    "filename-source": _filename_source,
    "body-words": _body_words,
}

# Какое правило пробуется для какого поля, по порядку.
FOR_FIELD = {
    "created": ("git-first-commit", "filename-date"),
    "source": ("filename-source",),
    "words": ("body-words",),
}


def _vocabulary(root, collection, field):
    readme = Path(root) / collection / "README.md"
    if not readme.exists():
        return None
    try:
        fields = parse_frontmatter(readme.read_text(encoding="utf-8"))
    except (FrontmatterError, UnicodeDecodeError):
        return None
    values = fields.get("values") or {}
    return values.get(field)


def plan(root, collection, field):
    """Строки `field-map` **до** записи. Ничего не пишет."""
    root = Path(root)
    vocabulary = _vocabulary(root, collection, field)
    items = root / collection / "items"
    rows = []
    for path in sorted(items.glob("*.md")) if items.is_dir() else []:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
            fields = parse_frontmatter(text)
        except (FrontmatterError, UnicodeDecodeError):
            continue
        if field in fields and str(fields[field]).strip():
            continue
        value = None
        used = None
        for name in FOR_FIELD.get(field, ()):
            value = RULES[name](root, rel, text)
            if value is not None:
                used = name
                break
        if value is not None:
            rows.append((rel, field, "", value, "computed", used))
        elif vocabulary:
            rows.append((rel, field, "", "", "deferred", "vocabulary-declared"))
        else:
            rows.append((rel, field, "", UNKNOWN, "synthetic", "no-rule"))
    return rows


def _write(root, rows):
    written = []
    for rel, field, _before, value, origin, _rule in rows:
        if origin == "deferred":
            continue
        path = Path(root) / rel
        text = path.read_text(encoding="utf-8")
        head, delimiter, rest = text.partition("---\n")
        path.write_text("%s%s%s: %s\n%s" % (head, delimiter, field, value, rest),
                        encoding="utf-8")
        written.append(rel)
    return sorted(written)


def run(root, collection, field):
    """(строки таблицы, отчёт). Пишет всё, что не `deferred`."""
    rows = plan(root, collection, field)
    _write(root, rows)
    deferred = [row[0] for row in rows if row[4] == "deferred"]
    report = "отложено, значение принадлежит автору:\n%s\n" % "\n".join(deferred) \
        if deferred else ""
    return rows, report


def run_silently(root, collection, field):
    """Что MAINTAIN вправе сделать без спроса: **только полностью вычислимое**.

    §19 относит backfill к молчаливому. Здесь это сужено: backfill трогает
    каждую запись коллекции, и режим без присмотра не имеет права
    проштамповать `unknown` по двумстам файлам, не имея кому это сказать.
    """
    rows = plan(root, collection, field)
    unclear = [row for row in rows if row[4] != "computed"]
    if unclear:
        return [], ("backfill %s не выполнен молча: невычислимо у %d записей\n%s\n"
                    % (field, len(unclear),
                       "\n".join(row[0] for row in unclear)))
    return _write(root, rows), ""
```

- [ ] **Step 3: Прогнать и закоммитить**

Run: `python3 -m unittest tests.test_backfill -v` затем `./check`

```bash
git commit -- scripts/maintain/backfill.py tests/test_backfill.py \
  -m "волна 5: backfill — три исхода, молча только вычислимое; критерий 4"
```

---

## Task 11: `drain-inbox` и три скилла

`drain-inbox` — пятый скилл спеки, не названный ни одной волной; прогон
отдал его сюда, потому что он, как MAINTAIN и `extend-structure`,
интерпретирует накопившееся и выбирает исход.

| исход §6 | суждение | механика |
|---|---|---|
| стало записью | зона и коллекция по правилу размещения; архетип | `move` волны 4; `created` — из даты в имени файла (§6 её гарантирует), `type` — из целевой коллекции |
| растворилось | что именно впитать и куда | правка существующих записей — **авторство**, делается в диалоге, не скриптом |
| это было сырьё | получено, а не написано (§1) | `move` в `sources`, производное несёт `source` |
| отвергнуто | ценность | удаление; содержимое остаётся в git |

**Без собеседника исполняются только два исхода из четырёх.** «Растворилось»
и «отвергнуто» требуют вывода о ценности содержимого — линия
ответственности отдаёт его автору. Элемент остаётся в inbox и уходит в
отчёт. Инвариант §6 этим не нарушен: «элемент, лежащий в inbox, неразобран
по определению», а он и не был разобран.

`drain-inbox` — **единственный из трёх скиллов волны, который трогает
содержимое**, и делает это только с автором. MAINTAIN не зовёт его никогда.

**`destructive-example` расширяется на все три скилла.** Правило заведено
потому, что разрушающий пример в инструкции рано или поздно исполнят
буквально, и это верно для скилла, удаляющего коллекцию и элемент inbox, не
меньше, чем для ADOPT.

**Files:**
- Modify: `scripts/check_package.py` (`_is_adopt_file` → предикат на три скилла)
- Create: `skills/maintain-context-repo/`, `skills/extend-structure/`,
  `skills/drain-inbox/` — по `SKILL.md` и `eval.txt`
- Test: `tests/test_check_package.py`, `tests/test_maintain_skills.py`

- [ ] **Step 1: Написать падающий тест на периметр `destructive-example`**

В `tests/test_check_package.py`:

```python
class TestMutatingSkillPerimeter(unittest.TestCase):
    """Периметр разрушающих примеров — все скиллы, которые мутируют дерево."""

    def test_the_perimeter_names_these_four(self):
        self.assertEqual(sorted(check_package.MUTATING_SKILLS),
                         ["adopt", "drain-inbox", "extend-structure",
                          "maintain-context-repo"])

    def test_each_of_them_is_inside_the_perimeter(self):
        for name in check_package.MUTATING_SKILLS:
            self.assertTrue(
                check_package._is_mutating_skill("skills/%s/SKILL.md" % name), name)

    def test_a_prefix_match_is_enough_for_adopt(self):
        """`skills/adopt/` и `skills/adopt-context-repo/` — оба усыновление.
        Требование дефиса однажды выключало класс целиком."""
        for rel in ("skills/adopt/SKILL.md", "skills/adopt-context-repo/SKILL.md"):
            self.assertTrue(check_package._is_mutating_skill(rel), rel)

    def test_a_read_only_skill_is_outside(self):
        self.assertFalse(
            check_package._is_mutating_skill("skills/create-context-repo/SKILL.md"))

    def test_a_file_named_after_a_skill_does_not_join_the_perimeter(self):
        """Скилл `drain-inbox` с заметкой `maintain-context-repo.md` внутри
        другого скилла усыновлением не становится."""
        self.assertFalse(
            check_package._is_mutating_skill("skills/other/maintain-context-repo.md"))
```

- [ ] **Step 2: Реализация — переименовать и расширить предикат**

```python
# Скиллы, мутирующие дерево. Правило `destructive-example` заведено потому,
# что разрушающий пример в инструкции рано или поздно исполнят буквально, —
# и это верно для скилла, удаляющего коллекцию и элемент inbox, не меньше,
# чем для усыновления.
MUTATING_SKILLS = ("adopt", "drain-inbox", "extend-structure",
                   "maintain-context-repo")


def _is_mutating_skill(rel):
    """Файл внутри мутирующего скилла, на любой глубине вложенности.

    `startswith("adopt-")` требовал дефиса: каталог `skills/adopt/` — самое
    естественное имя — выключал класс целиком. Имя файла из проверки
    исключено: скилл `drain-inbox` с заметкой `adopt.md` усыновлением
    не становится.
    """
    parts = rel.split("/")
    if parts[0] != "skills":
        return False
    return any(part == name or part.startswith(name + "-")
               for part in parts[1:-1] for name in MUTATING_SKILLS)
```

Старое имя `_is_adopt_file` заменяется во всех местах вызова; тесты волны 1,
зовущие его напрямую, обновляются. **Если такой тест проверяет что-то, чего
не проверяет новый предикат, — сообщи, не удаляй.**

- [ ] **Step 3: Три скилла**

`skills/maintain-context-repo/SKILL.md`:

```markdown
---
name: maintain-context-repo
description: Fix the form of a context repository without asking, show what is declared and unused, and never touch content.
---

# Поддержание репозитория

Форму правит плагин молча. Содержимое не трогает без автора — ни тела
записей, ни значений существующих полей, ни прозы README.

## Что происходит за один прогон

1. **Форма механически.** Оба гейта; чинится то, что принадлежит плагину:
   `views.base`, `.claude/rules/*.md`, форм-секции `CLAUDE.md`.
2. **Форма содержательно.** Недостающая папка зоны создаётся. Папка вне
   карты, направление без строки, архетип против поведения записей и
   бинарь вне git — показываются.
3. **Спрос.** Числа и даты: где объявлено и не наполнено. Ни «протухло»,
   ни «пора» — вывод делает автор.

Прогон проверяет себя до собственного коммита и на любом изменении
содержимого откатывает себя целиком.

## Дата обязательна

`--today ГГГГ-ММ-ДД`. Здесь дата не меняет текст отчёта — она удаляет
пустую коллекцию, прожившую тридцать дней. Умолчание из системных часов
вернуло бы в мутирующий режим ту зависимость, которую волна 1 выкорчёвывала
дважды.

## Чего этот скилл не делает

- не чинит ссылку в теле записи: угаданная цель — переписанный авторский текст;
- не приводит архетип к поведению записей: выбор архетипа — суждение автора;
- не удаляет вид: предикат «ничего не отбирает» требует движка фильтров;
- не удаляет ничего непустого — ни зону, ни направление, ни коллекцию;
- не пишет `.link-allow` и не конвертирует markdown-ссылки;
- не зовёт `drain-inbox` никогда.

## Команда

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/maintain/run.py" . --today 2026-08-29
```
```

`skills/extend-structure/SKILL.md` — четыре команды, у каждой названы триггер,
условие отказа и поведение при отсутствии содержимого. Ключевая фраза,
которая обязана в нём стоять: **сначала запись, потом единица**.

`skills/drain-inbox/SKILL.md` — четыре исхода §6, и явно: без собеседника
исполняются два из четырёх.

У каждого — `eval.txt` с фразами срабатывания на обоих языках, не меньше
четырёх строк, ни одна не начинается с решётки.

**Перед записью прогони по каждому тексту `DESTRUCTIVE`** из
`scripts/check_package.py`: операции называются командными токенами
(`drop`, `move`, `revert`), а не командами git, которые они заворачивают.

- [ ] **Step 4: Тест на три скилла**

`tests/test_maintain_skills.py` — по образцу `tests/test_adopt_skill.py`
волны 4, на три каталога: проверка пакета молчит; ни одна строка не несёт
разрушающей команды; каждый вызов скрипта идёт через `${CLAUDE_PLUGIN_ROOT}`;
`name` во frontmatter равен имени каталога; `eval.txt` непуст и не из одних
комментариев.

Плюс два утверждения, которых у волны 4 нет:

```python
    def test_maintain_names_the_mandatory_date(self):
        """Пропущенная в инструкции, она пропущена и в вызове."""
        text = (SKILLS / "maintain-context-repo" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--today", text)

    def test_extend_states_the_order_record_before_unit(self):
        text = (SKILLS / "extend-structure" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("сначала запись, потом единица", text.lower())
```

- [ ] **Step 5: Прогнать и закоммитить**

Run: `./check`

```bash
git commit -- scripts/check_package.py skills tests/test_check_package.py \
  tests/test_maintain_skills.py \
  -m "волна 5: три скилла и периметр разрушающих примеров на все мутирующие"
```

---

## Task 12: Мутации волны и документы

Зелёный `./check` волну не закрывает. Закрывает он её вместе с мутациями:
посаженное нарушение обязано покраснеть в **названном** тесте.

**Files:**
- Modify: `dev/mutate.py`, `docs/gate-coverage.md`, `docs/criteria-coverage.md`,
  `docs/roadmap.md`, `docs/tracker.md`, `CLAUDE.md`,
  `docs/superpowers/specs/2026-08-29-wave-5-maintain-design.md`

- [ ] **Step 1: Мутации волны**

Десять кандидатов спеки, каждый с названным ожидаемым тестом:

| # | что портится | обязан покраснеть |
|---|---|---|
| в5 К1а | MAINTAIN чинит `unresolved` в теле записи | `tests/test_mechanical.py::TestWhatIsReported::test_an_unresolved_link_in_a_record_body_is_reported_not_guessed` |
| в5 К1б | поверхность формы выводится из прогона, а не объявлена | `tests/test_content_diff.py::TestSurfaceIsStatic::test_the_surface_is_a_literal_and_not_derived_from_a_run` |
| в5 К2а | `--today` получает умолчание из часов | `tests/test_demand.py::TestAges::test_today_is_mandatory` |
| в5 К2б | возраст считается по `st_mtime` | `tests/test_prune.py::TestFalsifiers::test_st_mtime_instead_of_git_gives_a_different_age` |
| в5 К2в | порог сдвинут на день | `tests/test_prune.py::TestThreshold::test_exactly_thirty_days_is_removed_and_twenty_nine_is_not` |
| в5 К3 | `add-view` перестаёт проверять пустоту папки | `tests/test_extend.py::TestAddView::test_a_view_over_an_empty_folder_is_refused` |
| в5 К3б | `add-area` не трогает `areas/README.md` | `tests/test_extend.py::TestAddArea::test_a_direction_with_a_purpose_gets_a_folder_and_a_row` |
| в5 К4а | backfill переписывает существующее значение | `tests/test_backfill.py::TestNothingIsOverwritten::test_a_collection_where_everyone_has_the_field_produces_nothing` |
| в5 К4б | backfill пишет `unknown` в поле со словарём | `tests/test_backfill.py::TestOutcomes::test_a_field_with_a_declared_vocabulary_is_deferred_not_stamped` |
| в5 К5 | `field_map` молча пропускает неразобранную запись | `tests/test_field_map.py::TestCounts::test_a_shortfall_without_a_token_is_unexplained_count` |
| в5 Д1 | дописывание в `OPEN-THREADS.md` без ключа | `tests/test_maintain_run.py::TestRun::test_open_threads_is_appended_idempotently` |

Run: `python3 dev/mutate.py`
Expected: **40 мутаций: убита — 40, ВЫЖИЛА — 0** (23 из волн 1–3, шесть из
волны 4, одиннадцать отсюда). Выжившая мутация закрытие волны останавливает.

- [ ] **Step 2: `docs/gate-coverage.md` — десять классов волны**

Строка на класс с цитатой на живой тест. Механизм, а не соглашение:
`tests/test_gate_coverage.py` роняет набор на выдуманном имени теста.

- [ ] **Step 3: `docs/criteria-coverage.md` — пять критериев волны 5**

| критерий | чем закрыт |
|---|---|
| 1. чинит форму и не изменяет содержимое | `tests/test_content_diff.py` плюс `tests/test_maintain_run.py::TestSelfCheck` |
| 2. показывает спрос и не действует по нему | `tests/test_prune.py::TestThreshold` и `TestFalsifiers` (четыре) |
| 3. не заводит единицу без содержимого | `tests/test_extend.py`, `tests/test_form_collection.py::TestForm::test_without_a_record_nothing_reaches_the_disk` |
| 4. `backfill` не пишет синтетику молча | `tests/test_backfill.py::TestOutcomes`, `TestMaintainCallsItNarrowly` |
| 5. `field-map` и дифф счётчиков | `tests/test_field_map.py` |

- [ ] **Step 4: Правки спеки волны 5**

Семь расхождений спеки волны с общей спекой уже перечислены в самой спеке
волны и правки общей спеки **требуют**. Плюс расхождения, найденные при
исполнении. Каждое — отдельный коммит с пометкой «принято агентом» и строкой
в `docs/tracker.md`.

- [ ] **Step 5: Долг волны 4 закрыт**

`docs/tracker.md`, раздел «Этап 2 ADOPT передан волне 5»: отметить, что
`form_collection` построен и ADOPT зовёт его. Если этап 2 усыновления в этой
волне так и не собран целиком, **скажи об этом прямо** и оставь долг
открытым — закрывать его отметкой без кода нельзя.

- [ ] **Step 6: `docs/roadmap.md`, `docs/tracker.md`, `CLAUDE.md`**

- roadmap: волна 5 закрыта, пять критериев отмечены;
- tracker: решения агента, расхождения, открытые вопросы;
- `CLAUDE.md`: в таблице волн у волны 5 появляется план.

- [ ] **Step 7: Финальный прогон и коммит**

Run: `./check` и `python3 dev/mutate.py`

```bash
git commit -- docs CLAUDE.md dev/mutate.py \
  -m "волна 5: мутации, покрытие классов и критериев, документы"
```

---

## Закрытие волны

- [ ] `./check` — код 0;
- [ ] `python3 dev/mutate.py` — 40 из 40 убиты, ни одной выжившей;
- [ ] пять критериев `docs/roadmap.md` закрыты названными тестами, у каждого
      есть фальсификатор;
- [ ] десять классов находок в `docs/gate-coverage.md` с цитатами на живые тесты;
- [ ] проверка пакета молчит о трёх новых скиллах;
- [ ] второй прогон MAINTAIN по фикстуре не меняет ни байта;
- [ ] долг волны 4 (`form_collection`, этап 2 ADOPT) закрыт кодом или
      явно оставлен открытым в трекере.

**Чего закрытие волны не утверждает.** Три утверждения фальсификации рецепта
(§27) названы, но построено из них одно — Ф2, «дерево, построенное рецептом,
зелено на каждом коммите», и то потому, что механизма не требует. Ф1 имеет
механизм (`empty-collection`), но собственного отчёта не получает. Ф3 —
«каждый молчаливый акт MAINTAIN тот, о котором автор не хотел бы, чтобы его
спрашивали» — не строится: живого инстанса нет, измерять нечего, а
незыблемое №3 запрещает механизм под непредъявленную поломку.

**Названный остаток.** Пин `knowledge/` может быть годовалым, и рецепт
скажет об этом только дату, без вердикта. Это самый слабый пункт волны и
первый кандидат на снятие, если окажется, что строку никто не читает.
