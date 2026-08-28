# Волна 1: гейты и проверка пакета — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать два гейта (ссылки и frontmatter), проверку пакета и общий слой определений, на которых стоят волны 2 и 3, — так, чтобы каждая находка была доказана фикстурой с точным списком.

**Architecture:** Пакет плагина Claude Code. Ядро — четыре библиотечных модуля (`zones`, `frontmatter`, `paths`, `findings`), поверх них три исполняемых скрипта-гейта, каждый со своим CLI и кодом возврата. Никакого движка: всё статический разбор текста. Определения зон, имена классов находок, `permissions.deny` и коды возврата живут ровно в одном месте — волны 2 и 3 их импортируют и не копируют.

**Tech Stack:** Python 3 stdlib (`unittest`, `pathlib`, `re`, `unicodedata`, `argparse`, `json`), git, POSIX shell. Ноль внешних зависимостей — это незыблемое №5.

**Спека:** `docs/superpowers/specs/2026-08-08-context-repo-plugin-design.md`, секции 1, 2, 13, 14, 16 и «Общее для гейтов».
**Критерии выхода волны:** `docs/roadmap.md`, раздел «Волна 1».

## Состояние плана

**Задачи 1–15 исполнены** — код в дереве, `./check` зелёный, 117 тестов,
галочки проставлены. Перечитывать и переисполнять их не нужно.

**Начинать с задачи 16.** Задачи 16–23 закрывают дыры, которые нашла
состязательная проверка уже после того, как `./check` позеленел: зелёный
набор не краснел на посаженном нарушении, значит проверка в этих местах
слепа. Порядок и три решения, ждущие автора, — в разделе «Задачи 16–23».

---

## Структура файлов

| файл | ответственность |
|---|---|
| `.claude-plugin/plugin.json` | манифест: имя и версия |
| `scripts/zones.py` | **единственное** определение восьми зон, прав записи, `deny`-паттернов |
| `scripts/findings.py` | классы находок, тип `Finding`, детерминированный отчёт, коды возврата |
| `scripts/frontmatter.py` | разбор frontmatter из stdlib; принимает то, что пишет Obsidian Properties; никогда не угадывает |
| `scripts/paths.py` | признак «токен — путь», нормализация, проверка выхода за корень |
| `scripts/basefile.py` | разбор `views.base`: пути фильтров, свойства по уровням требования, формулы |
| `scripts/check_links.py` | гейт ссылок: семь классов |
| `scripts/check_frontmatter.py` | гейт frontmatter: контракт из видов |
| `scripts/check_package.py` | проверка пакета перед выпуском |
| `check` | единственная команда проверки: тесты + проверка пакета, один код возврата |
| `fixtures/broken/` | битая фикстура: все классы обоих гейтов сразу |
| `fixtures/green/` | зелёный образец: гейты обязаны молчать |
| `tests/test_*.py` | утверждают точный список находок, не «что-то нашлось» |

Границы намеренные: `zones` ничего не импортирует и потому не может зациклиться с гейтами; `findings` не знает про файловую систему; гейты не знают друг о друге. Волна 2 (хуки) импортирует `zones`, `paths`, `findings` и зовёт гейты как подпроцессы — то есть её отказ не может изменить их поведение.

---

### Task 1: Скелет пакета и `./check`

Ходячий скелет: `./check` обязан работать с первого коммита, иначе волну нечем проверить.

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `check`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `scripts/__init__.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_smoke.py`:

```python
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestManifest(unittest.TestCase):
    def test_plugin_manifest_has_name_and_version(self):
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "twinkle-repo-builder")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_smoke -v`
Expected: FAIL — `FileNotFoundError: .claude-plugin/plugin.json`

- [x] **Step 3: Минимальная реализация**

`.claude-plugin/plugin.json`:

```json
{
  "name": "twinkle-repo-builder",
  "version": "0.1.0",
  "description": "Creates, adopts and maintains context repositories"
}
```

`scripts/__init__.py` и `tests/__init__.py` — пустые файлы.

`check`:

```sh
#!/bin/sh
# verify_cmd прогона. Один код возврата на всё: тесты плюс проверка пакета.
set -e
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -t . -q
python3 scripts/check_package.py .
```

- [x] **Step 4: Сделать исполняемым и прогнать**

Run: `chmod +x check && python3 -m unittest tests.test_smoke -v`
Expected: PASS (1 test)

`./check` на этом шаге ещё падает: `check_package.py` не существует. Так и задумано — Task 14 его закрывает. До тех пор `verify_cmd` красный, и это честно.

- [x] **Step 5: Коммит**

```bash
git add .claude-plugin/plugin.json check scripts/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "wave1: манифест пакета и точка входа verify_cmd"
```

---

### Task 2: Модуль зон — единственное определение

**Files:**
- Create: `scripts/zones.py`
- Create: `tests/test_zones.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_zones.py`:

```python
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


class TestSingleDefinition(unittest.TestCase):
    """Критерий выхода волны: второе определение восьми зон валит тест.

    Эвристика намеренно грубая — файл, перечисляющий шесть и более имён зон
    строковыми литералами, почти наверняка держит свою копию таблицы.
    Спека измерила цену обратного: три разошедшиеся таблицы зон в одном
    репозитории.
    """

    def test_no_second_zone_table_in_package(self):
        names = set(zones.ZONES)
        offenders = []
        for path in sorted(ROOT.glob("scripts/*.py")):
            if path.name == "zones.py":
                continue
            text = path.read_text(encoding="utf-8")
            hits = {n for n in names if f'"{n}"' in text or f"'{n}'" in text}
            if len(hits) >= 6:
                offenders.append(f"{path.name}: {sorted(hits)}")
        self.assertEqual(offenders, [], "второе определение зон — импортируй scripts.zones")
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_zones -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.zones'`

- [x] **Step 3: Реализация**

`scripts/zones.py`:

```python
"""Единственное определение зон рецепта.

Волны 2 и 3 импортируют отсюда и не заводят своих копий: тест
tests/test_zones.py::TestSingleDefinition падает, если копия появилась.
Секция 1 спеки — источник значений.
"""

from pathlib import PurePosixPath

# Семантическая ось: про что оно.
SEMANTIC = ("core", "areas", "projects", "knowledge")
# Конвейерная ось: в каком состоянии обработки оно находится.
PIPELINE = ("inbox", "sources", "tmp", "decisions")
ZONES = SEMANTIC + PIPELINE

# Содержимое исчезает по построению, поэтому ссылка сюда из долгоживущей
# зоны — отложенная поломка, а не риск (класс link-to-transient).
TRANSIENT = frozenset({"tmp", "inbox"})
LONG_LIVED = frozenset(SEMANTIC)

# Только добавление: правка существующего — предупреждение или блок (секция 15).
ADD_ONLY = frozenset({"inbox", "sources", "decisions"})
# Чужие git-сабмодули: не пишем вообще.
READ_ONLY = frozenset({"knowledge"})

# Статически закрывается в settings.json целевого репозитория.
DENY_PATTERNS = ("knowledge/*/**",)


def zone_of(path):
    """Зона, которой принадлежит путь, или None.

    Смотрит только на первый сегмент: зоны живут в корне и нигде больше.
    """
    parts = PurePosixPath(str(path).replace("\\", "/")).parts
    if not parts:
        return None
    return parts[0] if parts[0] in ZONES else None
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_zones -v`
Expected: PASS (5 tests)

- [x] **Step 5: Коммит**

```bash
git add scripts/zones.py tests/test_zones.py
git commit -m "wave1: модуль зон, единственное определение с тестом на копии"
```

---

### Task 3: Классы находок и детерминированный отчёт

**Files:**
- Create: `scripts/findings.py`
- Create: `tests/test_findings.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_findings.py`:

```python
import unittest

from scripts.findings import EXIT_OK, EXIT_VIOLATION, Finding, Report


class TestFinding(unittest.TestCase):
    def test_link_gate_classes_are_closed(self):
        from scripts.findings import LINK_CLASSES
        self.assertEqual(
            set(LINK_CLASSES),
            {"unresolved", "md-link-to-file", "link-to-transient",
             "escapes-root", "dead-allow", "ambiguous", "orphan"},
        )

    def test_severity_is_a_property_of_the_class_not_the_caller(self):
        from scripts.findings import severity
        self.assertEqual(severity("unresolved"), "error")
        self.assertEqual(severity("escapes-root"), "error")
        self.assertEqual(severity("dead-allow"), "error")
        self.assertEqual(severity("ambiguous"), "warning")
        self.assertEqual(severity("orphan"), "report")


class TestReportDeterminism(unittest.TestCase):
    def test_same_findings_in_any_order_render_identically(self):
        a = Finding("unresolved", "areas/b.md", 12, "[[nope]]")
        b = Finding("md-link-to-file", "areas/a.md", 3, "[x](y.md)")
        self.assertEqual(Report([a, b]).render(), Report([b, a]).render())

    def test_render_has_no_absolute_paths(self):
        r = Report([Finding("unresolved", "areas/b.md", 12, "[[nope]]")]).render()
        self.assertNotIn("/Users/", r)
        self.assertTrue(r.startswith("areas/b.md:12"), r)

    def test_exit_code_is_violation_only_for_errors(self):
        self.assertEqual(Report([]).exit_code(), EXIT_OK)
        self.assertEqual(Report([Finding("ambiguous", "a.md", 1, "x")]).exit_code(), EXIT_OK)
        self.assertEqual(Report([Finding("orphan", "a.md", 1, "x")]).exit_code(), EXIT_OK)
        self.assertEqual(
            Report([Finding("unresolved", "a.md", 1, "x")]).exit_code(), EXIT_VIOLATION
        )

    def test_counts_by_class_are_what_tests_assert_against(self):
        r = Report([
            Finding("unresolved", "a.md", 1, "x"),
            Finding("unresolved", "b.md", 2, "y"),
            Finding("ambiguous", "c.md", 3, "z"),
        ])
        self.assertEqual(r.counts(), {"unresolved": 2, "ambiguous": 1})
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_findings -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.findings'`

- [x] **Step 3: Реализация**

`scripts/findings.py`:

```python
"""Классы находок, их тяжесть, детерминированный отчёт и коды возврата.

Коды взяты из секции 15: 2 — нарушение, 0 — всё остальное, включая
случай «инструмент не смог запуститься». Различие между «нашёл нарушение»
и «не смог проверить» несёт текст, а не код: молчащий отказ — та самая
поломка, что стоила чужому продукту трёх с половиной месяцев.
"""

EXIT_OK = 0
EXIT_VIOLATION = 2
EXIT_TOOL_FAILED = 0

LINK_CLASSES = (
    "unresolved",
    "md-link-to-file",
    "link-to-transient",
    "escapes-root",
    "dead-allow",
    "ambiguous",
    "orphan",
)

FRONTMATTER_CLASSES = (
    "missing-required",
    "value-outside-vocabulary",
    "unparseable",
)

_SEVERITY = {
    "unresolved": "error",
    "md-link-to-file": "error",
    "link-to-transient": "error",
    "escapes-root": "error",
    "dead-allow": "error",
    "ambiguous": "warning",
    "orphan": "report",
    "missing-required": "error",
    "value-outside-vocabulary": "error",
    "unparseable": "error",
}


def severity(cls):
    try:
        return _SEVERITY[cls]
    except KeyError:
        raise ValueError("неизвестный класс находки: %r" % (cls,))


class Finding:
    __slots__ = ("cls", "path", "line", "detail")

    def __init__(self, cls, path, line, detail):
        severity(cls)  # неизвестный класс падает здесь, а не в отчёте
        self.cls = cls
        self.path = str(path)
        self.line = int(line)
        self.detail = detail

    def key(self):
        return (self.path, self.line, self.cls, self.detail)

    def render(self):
        return "%s:%d %s %s" % (self.path, self.line, self.cls, self.detail)

    def __repr__(self):
        return "Finding(%r, %r, %r, %r)" % (self.cls, self.path, self.line, self.detail)

    def __eq__(self, other):
        return isinstance(other, Finding) and self.key() == other.key()

    def __hash__(self):
        return hash(self.key())


class Report:
    def __init__(self, findings):
        self.findings = list(findings)

    def counts(self):
        out = {}
        for f in self.findings:
            out[f.cls] = out.get(f.cls, 0) + 1
        return out

    def render(self):
        """Побайтово детерминирован: сортировка по ключу, пути относительные."""
        return "\n".join(f.render() for f in sorted(self.findings, key=Finding.key))

    def exit_code(self):
        for f in self.findings:
            if severity(f.cls) == "error":
                return EXIT_VIOLATION
        return EXIT_OK
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_findings -v`
Expected: PASS (5 tests)

- [x] **Step 5: Коммит**

```bash
git add scripts/findings.py tests/test_findings.py
git commit -m "wave1: классы находок, детерминированный отчёт, коды возврата"
```

---

### Task 4: Разбор frontmatter из stdlib

Модуль обязан принимать то, что пишет Obsidian Properties, и **никогда не угадывать**: непонятое поле с потребителем — громкий отказ с номером строки, непонятое без потребителя — молчание.

**Files:**
- Create: `scripts/frontmatter.py`
- Create: `tests/test_frontmatter.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_frontmatter.py`:

```python
import unittest

from scripts.frontmatter import FrontmatterError, parse


class TestParse(unittest.TestCase):
    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(parse("# Заголовок\n\nтекст\n"), {})

    def test_simple_scalars(self):
        text = "---\ntype: decision\nstatus: open\n---\n\nтело\n"
        self.assertEqual(parse(text), {"type": "decision", "status": "open"})

    def test_quoted_values_lose_their_quotes(self):
        text = '---\ncreated: "2026-07-14"\ndescription: \'а: б\'\n---\n'
        self.assertEqual(parse(text), {"created": "2026-07-14", "description": "а: б"})

    def test_flow_list_is_what_obsidian_properties_writes(self):
        text = "---\ntags: [найм, продукт]\n---\n"
        self.assertEqual(parse(text), {"tags": ["найм", "продукт"]})

    def test_block_list(self):
        text = "---\ntags:\n  - найм\n  - продукт\n---\n"
        self.assertEqual(parse(text), {"tags": ["найм", "продукт"]})

    def test_nested_map_is_how_values_are_declared(self):
        text = "---\narchetype: конвейер\nvalues:\n  status: [open, decided, revisited]\n---\n"
        self.assertEqual(
            parse(text),
            {"archetype": "конвейер", "values": {"status": ["open", "decided", "revisited"]}},
        )

    def test_empty_value_is_none_not_empty_string(self):
        self.assertEqual(parse("---\ncreated:\n---\n"), {"created": None})

    def test_comment_and_blank_lines_are_skipped(self):
        text = "---\n# комментарий\n\ntype: note\n---\n"
        self.assertEqual(parse(text), {"type": "note"})


class TestNeverGuesses(unittest.TestCase):
    def test_unclosed_frontmatter_raises_with_line(self):
        with self.assertRaises(FrontmatterError) as ctx:
            parse("---\ntype: note\n\nтело без закрытия\n")
        self.assertEqual(ctx.exception.line, 1)

    def test_block_scalar_raises_with_its_line(self):
        text = "---\ntype: note\nbody: |\n  многострочное\n---\n"
        with self.assertRaises(FrontmatterError) as ctx:
            parse(text)
        self.assertEqual(ctx.exception.line, 3)

    def test_tab_indent_raises_rather_than_being_normalised(self):
        text = "---\ntags:\n\t- a\n---\n"
        with self.assertRaises(FrontmatterError) as ctx:
            parse(text)
        self.assertEqual(ctx.exception.line, 3)

    def test_two_space_indent_is_not_required(self):
        """Существующий парсер в изученном аналоге требовал ровно двух пробелов
        и молча сбрасывал состояние на всём остальном. Здесь — любой отступ."""
        text = "---\ntags:\n    - a\n---\n"
        self.assertEqual(parse(text), {"tags": ["a"]})
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_frontmatter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.frontmatter'`

- [x] **Step 3: Реализация**

`scripts/frontmatter.py`:

```python
"""Разбор frontmatter без зависимостей.

Принимает подмножество YAML, которое реально пишет Obsidian Properties:
скаляры, кавычки, flow-списки, блочные списки, одну вложенную мапу.
Всё, чего не понимает, — исключение с номером строки. Молчаливого
сброса состояния нет: угадавший парсер хуже отсутствующего.
"""

import re

_DELIM = "---"
_KEY = re.compile(r"^(?P<indent>[ ]*)(?P<key>[^:#\s][^:]*):(?P<rest>.*)$")
_ITEM = re.compile(r"^(?P<indent>[ ]*)-\s+(?P<value>.*)$")


class FrontmatterError(Exception):
    def __init__(self, message, line):
        super().__init__("%s (строка %d)" % (message, line))
        self.line = line


def _scalar(raw, lineno):
    raw = raw.strip()
    if raw == "":
        return None
    if raw[0] in "|>":
        raise FrontmatterError("блочный скаляр не поддерживается", lineno)
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if inner == "":
            return []
        return [_scalar(part, lineno) for part in inner.split(",")]
    return raw


def parse(text):
    """dict полей. Пустой dict, если frontmatter нет вовсе."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != _DELIM:
        return {}

    body = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            body = lines[1:i]
            break
    if body is None:
        raise FrontmatterError("frontmatter не закрыт", 1)

    out = {}
    pending_key = None      # ключ, ждущий блочного списка или вложенной мапы
    pending_indent = 0

    for offset, line in enumerate(body):
        lineno = offset + 2  # +1 за разделитель, +1 за счёт с единицы
        if "\t" in line:
            raise FrontmatterError("табуляция в отступе", lineno)
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue

        item = _ITEM.match(line)
        if item:
            if pending_key is None:
                raise FrontmatterError("элемент списка без ключа", lineno)
            target = out[pending_key]
            if not isinstance(target, list):
                raise FrontmatterError("элемент списка после скаляра", lineno)
            target.append(_scalar(item.group("value"), lineno))
            continue

        match = _KEY.match(line)
        if not match:
            raise FrontmatterError("строка не разобрана", lineno)

        indent = len(match.group("indent"))
        key = match.group("key").strip()
        rest = match.group("rest")

        if indent > pending_indent and pending_key is not None:
            holder = out[pending_key]
            if not isinstance(holder, dict):
                if holder in (None, []):
                    holder = {}
                    out[pending_key] = holder
                else:
                    raise FrontmatterError("вложенная мапа после скаляра", lineno)
            holder[key] = _scalar(rest, lineno)
            continue

        value = _scalar(rest, lineno)
        out[key] = value
        if value is None:
            out[key] = []          # может стать списком или мапой
            pending_key = key
            pending_indent = indent
        else:
            pending_key = None
            pending_indent = indent

    # Ключи, за которыми так ничего и не пришло, — пустые, а не пустые списки.
    for key, value in list(out.items()):
        if value == []:
            out[key] = None
    return out
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_frontmatter -v`
Expected: PASS (12 tests)

Если `test_empty_value_is_none_not_empty_string` или `test_block_list` падают — дело в финальной нормализации пустых списков: список, в который что-то положили, пустым не остаётся, а ключ без продолжения обязан стать `None`. Правь только этот блок.

- [x] **Step 5: Коммит**

```bash
git add scripts/frontmatter.py tests/test_frontmatter.py
git commit -m "wave1: парсер frontmatter из stdlib, громкий отказ вместо угадывания"
```

---

### Task 5: Пути — признак и граница корня

**Files:**
- Create: `scripts/paths.py`
- Create: `tests/test_paths.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_paths.py`:

```python
import unittest

from scripts.paths import escapes_root, is_path_token, normalise


class TestPathToken(unittest.TestCase):
    def test_slash_makes_it_a_path(self):
        self.assertTrue(is_path_token("scripts/move.py"))
        self.assertTrue(is_path_token("areas/hiring/"))

    def test_known_extension_makes_it_a_path(self):
        self.assertTrue(is_path_token("hooks.json"))
        self.assertTrue(is_path_token("views.base"))
        self.assertTrue(is_path_token("SKILL.md"))

    def test_leading_slash_or_tilde_is_a_path_and_will_be_reported(self):
        self.assertTrue(is_path_token("/etc/hosts"))
        self.assertTrue(is_path_token("~/notes.md"))

    def test_bare_words_are_not_paths(self):
        for token in ("grep", "archetype", "status", "git", "mv"):
            self.assertFalse(is_path_token(token), token)

    def test_versions_and_durations_are_not_paths(self):
        """Закрытый список расширений, а не «есть точка»."""
        for token in ("0.05", "v1.2", "3.14", "0.05 с"):
            self.assertFalse(is_path_token(token), token)


class TestRootBoundary(unittest.TestCase):
    def test_absolute_path_escapes(self):
        self.assertTrue(escapes_root("/etc/hosts", base="areas/hiring"))
        self.assertTrue(escapes_root("~/notes.md", base="areas"))

    def test_dotdot_above_root_escapes(self):
        self.assertTrue(escapes_root("../../outside.md", base="areas/hiring"))

    def test_dotdot_inside_root_is_fine(self):
        self.assertFalse(escapes_root("../core/me.md", base="areas/hiring"))

    def test_normalisation_happens_before_comparison(self):
        """Сравнение по префиксу строки ловится собственным `..`."""
        self.assertFalse(escapes_root("areas/../core/me.md", base=""))
        self.assertTrue(escapes_root("areas/../../x.md", base=""))

    def test_urls_are_not_paths_and_never_escape(self):
        for url in ("https://example.com", "mailto:a@b.c", "tel:+70000000000"):
            self.assertFalse(escapes_root(url, base="areas"))
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_paths -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.paths'`

- [x] **Step 3: Реализация**

`scripts/paths.py`:

```python
"""Признак «токен — путь» и граница корня репозитория.

Секция 13: в backtick'ах лежит и путь, и имя команды. Без признака гейт
либо ругается на `grep`, либо молчит про `scripts/check_links.py`.
Признак синтаксический, потому что он нужен машине.
"""

import posixpath
import unicodedata

# Закрытый список, а не «есть точка»: 0.05 с и v1.2 файлами не являются.
PATH_EXTENSIONS = (".md", ".py", ".sh", ".json", ".base", ".yml", ".yaml", ".txt")

URL_SCHEMES = ("https:", "http:", "mailto:", "tel:")


def is_url(token):
    return token.startswith(URL_SCHEMES)


def is_path_token(token):
    token = token.strip()
    if not token or is_url(token):
        return False
    if token.startswith("/") or token.startswith("~"):
        return True
    if "/" in token:
        return True
    return token.endswith(PATH_EXTENSIONS)


def normalise(target, base=""):
    """Путь от корня репозитория, приведённый: NFC, POSIX, `..` схлопнуты.

    Возвращает строку, которая может начинаться с `..`, — это и есть сигнал
    выхода за корень.
    """
    target = unicodedata.normalize("NFC", str(target).replace("\\", "/"))
    if target.startswith("/") or target.startswith("~"):
        return target
    joined = posixpath.join(base, target) if base else target
    return posixpath.normpath(joined)


def escapes_root(target, base=""):
    """Выводит ли ссылка за корень репозитория.

    Абсолютный путь, `~`, и любой `..`, переживший нормализацию.
    URL не путь и потому не выходит никуда.
    """
    target = target.strip()
    if is_url(target) or target.startswith("#"):
        return False
    if target.startswith("/") or target.startswith("~"):
        return True
    normalised = normalise(target, base)
    return normalised == ".." or normalised.startswith("../")
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_paths -v`
Expected: PASS (10 tests)

- [x] **Step 5: Коммит**

```bash
git add scripts/paths.py tests/test_paths.py
git commit -m "wave1: признак пути и граница корня репозитория"
```

---

### Task 6: Разбор `views.base`

Гейту нужен **сканер, а не движок**: какие пути и имена свойств упомянуты в виде. Ни одна проверка не вычисляет, попадает ли запись в вид.

**Files:**
- Create: `scripts/basefile.py`
- Create: `tests/test_basefile.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_basefile.py`:

```python
import unittest

from scripts.basefile import parse_base

SAMPLE = """filters:
  and:
    - file.inFolder("decisions/items")
    - 'type == "decision"'
formulas:
  age: 'now() - created'
views:
  - type: table
    name: Все решения
    order:
      - status
      - description
    groupBy: status
    sort:
      - created
"""


class TestBaseFile(unittest.TestCase):
    def test_folders_come_from_infolder_calls(self):
        base = parse_base(SAMPLE)
        self.assertEqual(base.folders, ["decisions/items"])

    def test_required_properties_are_the_ones_that_decide_visibility(self):
        base = parse_base(SAMPLE)
        self.assertEqual(base.required, {"type", "status", "created"})

    def test_known_properties_are_display_only(self):
        base = parse_base(SAMPLE)
        self.assertEqual(base.known, {"description"})

    def test_formula_names_are_not_record_fields(self):
        """Потребовать `age` от каждой записи — ложная ошибка на всей коллекции."""
        base = parse_base(SAMPLE)
        self.assertNotIn("age", base.required)
        self.assertNotIn("age", base.known)
        self.assertEqual(base.formulas, {"age"})

    def test_fields_used_inside_a_formula_inherit_its_consumer(self):
        text = (
            "formulas:\n"
            "  stale: 'reviewed'\n"
            "views:\n"
            "  - type: table\n"
            "    groupBy: stale\n"
        )
        base = parse_base(text)
        self.assertIn("reviewed", base.required)
        self.assertNotIn("stale", base.required)

    def test_empty_base_is_not_an_error(self):
        base = parse_base("")
        self.assertEqual(base.folders, [])
        self.assertEqual(base.required, set())
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_basefile -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.basefile'`

- [x] **Step 3: Реализация**

`scripts/basefile.py`:

```python
"""Статический разбор views.base.

Извлекает: пути фильтров, свойства с уровнем требования, имена формул.
Ничего не вычисляет — секция «Общее для гейтов»: гейту нужен сканер.
"""

import re

_INFOLDER = re.compile(r'file\.inFolder\(\s*["\']([^"\']+)["\']\s*\)')
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Где упомянуто поле — таково требование к нему (секция 14).
_REQUIRED_KEYS = ("filters", "sort", "groupBy")
_KNOWN_KEYS = ("order", "columnSize")

_STOPWORDS = {
    "and", "or", "not", "file", "inFolder", "type", "table", "cards", "list",
    "name", "true", "false", "null", "now", "date", "if", "then", "else",
}


class Base:
    def __init__(self, folders, required, known, formulas):
        self.folders = folders
        self.required = required
        self.known = known
        self.formulas = formulas


def _identifiers(chunk):
    return {m.group(0) for m in _IDENT.finditer(chunk)} - _STOPWORDS


def _section(text, key):
    """Грубая нарезка по ключу верхнего или вложенного уровня.

    Секция кончается на первой строке с отступом не больше, чем у ключа.
    """
    out = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(key + ":"):
            continue
        indent = len(line) - len(line.lstrip(" -"))
        out.append(stripped[len(key) + 1:])
        for follower in lines[i + 1:]:
            if follower.strip() == "":
                continue
            follower_indent = len(follower) - len(follower.lstrip(" -"))
            if follower_indent <= indent:
                break
            out.append(follower)
    return "\n".join(out)


def parse_base(text):
    folders = _INFOLDER.findall(text)

    formula_block = _section(text, "formulas")
    formulas = set()
    formula_fields = {}
    for line in formula_block.split("\n"):
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        name, expression = stripped.split(":", 1)
        name = name.strip().strip("-").strip()
        if not name:
            continue
        formulas.add(name)
        formula_fields[name] = _identifiers(expression)

    required = set()
    known = set()
    for key in _REQUIRED_KEYS:
        required |= _identifiers(_section(text, key))
    for key in _KNOWN_KEYS:
        known |= _identifiers(_section(text, key))

    # Формула — не поле записи. Её имя вычитается, а поля из её выражения
    # наследуют уровень требования того места, где формула употреблена.
    for name in formulas:
        if name in required:
            required.discard(name)
            required |= formula_fields.get(name, set())
        if name in known:
            known.discard(name)
            known |= formula_fields.get(name, set())

    known -= required
    return Base(folders, required, known, formulas)
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_basefile -v`
Expected: PASS (6 tests)

- [x] **Step 5: Коммит**

```bash
git add scripts/basefile.py tests/test_basefile.py
git commit -m "wave1: статический разбор views.base, формула не поле записи"
```

---

### Task 7: Битая фикстура и зелёный образец

Фикстуры пишутся **до** гейтов, которые их читают: иначе список находок подгоняется под то, что реализовалось.

**Files:**
- Create: `fixtures/broken/` (дерево, см. шаг 1)
- Create: `fixtures/green/` (дерево, см. шаг 2)
- Create: `fixtures/broken/ЧТО-ЗДЕСЬ-СЛОМАНО.md`

- [x] **Step 1: Собрать битую фикстуру**

Каждый файл несёт комментарий прямо в себе — «здесь намеренно нет frontmatter».

```bash
mkdir -p fixtures/broken/{core,areas/hiring,sources/transcripts/items,decisions/items,tmp,inbox,.claude/rules}

cat > fixtures/broken/ЧТО-ЗДЕСЬ-СЛОМАНО.md <<'EOF'
# Битая фикстура

Один намеренно сломанный репозиторий, покрывающий все классы обоих гейтов.
Точный список находок утверждается в tests/test_fixtures.py. Если гейт начал
ловить не то, тест обязан упасть — «гейт что-то нашёл» проверкой не является.
EOF

# unresolved
cat > fixtures/broken/areas/hiring/note.md <<'EOF'
---
type: note
---
Ссылка в никуда: [[несуществующая заметка]]
EOF

# md-link-to-file
cat > fixtures/broken/areas/hiring/md-link.md <<'EOF'
---
type: note
---
Так нельзя: [профиль](../../core/me.md)
EOF

# link-to-transient
cat > fixtures/broken/areas/hiring/transient.md <<'EOF'
---
type: note
---
Цель исчезнет по построению: [[tmp/plan]]
EOF

# escapes-root, два вида
cat > fixtures/broken/areas/hiring/escapes.md <<'EOF'
---
type: note
---
Абсолютный путь: `/Users/artem/notes.md`
Выше корня: [[../../../soseddniy-repo/file]]
EOF

# ambiguous: два файла с одним basename плюс bare-ссылка
cat > fixtures/broken/tmp/plan.md <<'EOF'
черновик
EOF
cat > fixtures/broken/areas/hiring/dup.md <<'EOF'
---
type: note
---
одноимённый номер один
EOF
cat > fixtures/broken/core/dup.md <<'EOF'
одноимённый номер два
EOF
cat > fixtures/broken/areas/hiring/bare.md <<'EOF'
---
type: note
---
Неоднозначно: [[dup]]
EOF

# backtick-токен, который путём не является: гейт обязан промолчать
cat > fixtures/broken/CLAUDE.md <<'EOF'
# Карта

Агент ходит `grep` и `git`, а скрипт зовётся `scripts/move.py` — его нет.
EOF

# rule-файл, ссылающийся на переименованную папку
cat > fixtures/broken/.claude/rules/areas.md <<'EOF'
---
description: Правило зоны areas
paths: ["areas/**"]
---
Записи кладутся в `areas/hiring/items/`, скрипт — `scripts/rename.py`.
EOF

# frontmatter: missing-required, value-outside-vocabulary, unparseable
cat > fixtures/broken/decisions/README.md <<'EOF'
---
archetype: конвейер
values:
  status: [open, decided, revisited]
---
# Решения
EOF
cat > fixtures/broken/decisions/views.base <<'EOF'
filters:
  and:
    - file.inFolder("decisions/items")
    - 'type == "decision"'
views:
  - type: table
    groupBy: status
    order:
      - description
EOF
cat > fixtures/broken/decisions/items/no-status.md <<'EOF'
---
type: decision
---
Поля status нет, а вид по нему группирует.
EOF
cat > fixtures/broken/decisions/items/bad-status.md <<'EOF'
---
type: decision
status: активно
---
Значение вне словаря коллекции.
EOF
cat > fixtures/broken/decisions/items/broken-yaml.md <<'EOF'
---
type: decision
status: open
body: |
  блочный скаляр не поддерживается
---
Поле с потребителем не разобралось — громкий отказ.
EOF

# orphan: сырьё, на которое никто не сослался
cat > fixtures/broken/sources/transcripts/items/2026-07-14-call.md <<'EOF'
---
type: transcript
date: 2026-07-14
---
Никто не сослался.
EOF

# аллоулист: строка без причины и мёртвая строка
cat > fixtures/broken/.link-allow <<'EOF'
# паттерн # причина
будущая-заметка
уже-не-нужное # цель давно создана, строка не исключает ничего
EOF
```

- [x] **Step 2: Собрать зелёный образец**

```bash
mkdir -p fixtures/green/{core,decisions/items}

cat > fixtures/green/CLAUDE.md <<'EOF'
# Карта

Зоны: `core/`, `decisions/`. Агент ходит `grep`, перемещает через `scripts/move.py`.
EOF

cat > fixtures/green/core/me.md <<'EOF'
Ядро. Ссылка на решение: [[decisions/items/2026-07-01-zones]]
EOF

cat > fixtures/green/decisions/README.md <<'EOF'
---
archetype: конвейер
values:
  status: [open, decided, revisited]
---
# Решения

Сюда попадает выбор, у которого была названная альтернатива.
EOF

cat > fixtures/green/decisions/views.base <<'EOF'
filters:
  and:
    - file.inFolder("decisions/items")
    - 'type == "decision"'
views:
  - type: table
    groupBy: status
    order:
      - description
EOF

cat > fixtures/green/decisions/items/2026-07-01-zones.md <<'EOF'
---
type: decision
status: decided
created: "2026-07-01"
description: Две оси вместо одной
---
Альтернативой была одна семантическая ось.
EOF

mkdir -p fixtures/green/scripts && cat > fixtures/green/scripts/move.py <<'EOF'
# заглушка пути, на который ссылается CLAUDE.md образца
EOF
```

- [x] **Step 3: Проверить, что дерево на месте**

Run: `find fixtures -type f | sort | wc -l`
Expected: `22`

- [x] **Step 4: Коммит**

```bash
git add fixtures
git commit -m "wave1: битая фикстура на все классы и зелёный образец"
```

---

### Task 8: Гейт ссылок — извлечение и `unresolved`

**Files:**
- Create: `scripts/check_links.py`
- Create: `tests/test_check_links.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_check_links.py`:

```python
import unittest
from pathlib import Path

from scripts.check_links import extract_links, scan

ROOT = Path(__file__).resolve().parent.parent
BROKEN = ROOT / "fixtures" / "broken"
GREEN = ROOT / "fixtures" / "green"


class TestExtraction(unittest.TestCase):
    def test_wikilink_shapes(self):
        text = "[[a]] [[b#заголовок]] [[c^блок]] [[d|алиас]] ![[e]]"
        self.assertEqual(
            [l.target for l in extract_links(text)], ["a", "b", "c", "d", "e"]
        )

    def test_code_blocks_are_cut_before_parsing(self):
        text = "```\n[[внутри кода]]\n```\n[[снаружи]]\n"
        self.assertEqual([l.target for l in extract_links(text)], ["снаружи"])

    def test_inline_code_is_cut_too(self):
        self.assertEqual([l.target for l in extract_links("`[[нет]]` [[да]]")],
                         ["да"])

    def test_line_numbers_are_one_based(self):
        links = extract_links("первая\n[[цель]]\n")
        self.assertEqual(links[0].line, 2)


class TestUnresolved(unittest.TestCase):
    def test_green_sample_is_silent(self):
        report = scan(GREEN)
        self.assertEqual(report.counts(), {})

    def test_broken_fixture_reports_unresolved(self):
        report = scan(BROKEN)
        self.assertGreaterEqual(report.counts().get("unresolved", 0), 1)
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.check_links'`

- [x] **Step 3: Реализация**

`scripts/check_links.py`:

```python
#!/usr/bin/env python3
"""Гейт ссылок.

Классы: unresolved, md-link-to-file, link-to-transient, escapes-root,
dead-allow, ambiguous, orphan. Секция 13 спеки.
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import paths as pathlib_rules
from scripts import zones
from scripts.findings import Finding, Report

_FENCE = re.compile(r"```.*?```", re.S)
_INLINE = re.compile(r"`[^`\n]*`")
_WIKILINK = re.compile(r"!?\[\[([^\]\n]+)\]\]")
_MDLINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")

SCANNED_FOR_TOKENS = ("CLAUDE.md", "README.md", "SKILL.md")


class Link:
    __slots__ = ("target", "line", "raw", "kind")

    def __init__(self, target, line, raw, kind):
        self.target = target
        self.line = line
        self.raw = raw
        self.kind = kind


def _blank_code(text):
    """Вырезает код, сохраняя переводы строк, чтобы номера не поехали."""
    def keep_newlines(match):
        return re.sub(r"[^\n]", " ", match.group(0))
    return _INLINE.sub(keep_newlines, _FENCE.sub(keep_newlines, text))


def extract_links(text):
    clean = _blank_code(text)
    out = []
    for lineno, line in enumerate(clean.split("\n"), start=1):
        for match in _WIKILINK.finditer(line):
            target = match.group(1).split("|")[0].split("#")[0].split("^")[0].strip()
            out.append(Link(target, lineno, match.group(0), "wikilink"))
        for match in _MDLINK.finditer(line):
            out.append(Link(match.group(1).strip(), lineno, match.group(0), "mdlink"))
    return out


def _index(root):
    """basename без расширения -> список относительных путей."""
    index = {}
    for path in root.rglob("*.md"):
        rel = path.relative_to(root).as_posix()
        stem = unicodedata.normalize("NFC", path.stem)
        index.setdefault(stem, []).append(rel)
        index.setdefault(unicodedata.normalize("NFC", rel[:-3]), []).append(rel)
    return index


def scan(root, today=None):
    root = Path(root)
    index = _index(root)
    findings = []

    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        parent = Path(rel).parent
        base = "" if parent == Path(".") else parent.as_posix()
        text = path.read_text(encoding="utf-8")
        for link in extract_links(text):
            if link.kind == "mdlink":
                continue  # Task 9
            target = unicodedata.normalize("NFC", link.target)
            if "/" in target:
                candidates = [p for p in index.get(target, [])]
            else:
                candidates = index.get(target, [])
            if not candidates:
                findings.append(Finding("unresolved", rel, link.line, link.raw))

    return Report(findings)


def main(argv=None):
    parser = argparse.ArgumentParser(description="link gate")
    parser.add_argument("root")
    parser.add_argument("--today", default=None,
                        help="дата явным параметром: без неё у проверки не бывает фикстуры")
    args = parser.parse_args(argv)
    report = scan(args.root, today=args.today)
    rendered = report.render()
    if rendered:
        print(rendered)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: PASS (6 tests)

- [x] **Step 5: Коммит**

```bash
git add scripts/check_links.py tests/test_check_links.py
git commit -m "wave1: гейт ссылок, извлечение и класс unresolved"
```

---

### Task 9: Гейт ссылок — `md-link-to-file`, `link-to-transient`, `escapes-root`

**Files:**
- Modify: `scripts/check_links.py`
- Modify: `tests/test_check_links.py`

- [x] **Step 1: Дописать падающие тесты**

Добавить в `tests/test_check_links.py`:

```python
class TestForbiddenShapes(unittest.TestCase):
    def test_markdown_link_to_local_file_is_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("md-link-to-file"), 1)

    def test_external_url_is_allowed(self):
        from scripts.check_links import classify_mdlink
        self.assertIsNone(classify_mdlink("https://example.com"))
        self.assertIsNone(classify_mdlink("mailto:a@b.c"))
        self.assertIsNone(classify_mdlink("#якорь"))
        self.assertEqual(classify_mdlink("../core/me.md"), "md-link-to-file")

    def test_link_from_long_lived_zone_into_transient_is_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("link-to-transient"), 1)

    def test_escaping_root_is_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("escapes-root"), 2)
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_links.TestForbiddenShapes -v`
Expected: FAIL — `AssertionError: None != 1`

- [x] **Step 3: Реализация**

В `scripts/check_links.py` добавить функцию и включить её в `scan`:

```python
def classify_mdlink(target):
    """None, если markdown-ссылка допустима; иначе класс находки."""
    target = target.strip()
    if pathlib_rules.is_url(target) or target.startswith("#"):
        return None
    return "md-link-to-file"


def _transient_violation(source_rel, target):
    """Ссылка из долгоживущей зоны в исчезающую — отложенная поломка."""
    source_zone = zones.zone_of(source_rel)
    target_zone = zones.zone_of(target)
    if source_zone in zones.LONG_LIVED and target_zone in zones.TRANSIENT:
        return True
    return False
```

Заменить тело цикла по ссылкам в `scan` на:

```python
        for link in extract_links(text):
            target = unicodedata.normalize("NFC", link.target)

            if pathlib_rules.escapes_root(target, base=base):
                findings.append(Finding("escapes-root", rel, link.line, link.raw))
                continue

            if link.kind == "mdlink":
                cls = classify_mdlink(target)
                if cls:
                    findings.append(Finding(cls, rel, link.line, link.raw))
                continue

            if _transient_violation(rel, target):
                findings.append(Finding("link-to-transient", rel, link.line, link.raw))
                continue

            candidates = index.get(target, [])
            if not candidates:
                findings.append(Finding("unresolved", rel, link.line, link.raw))
```

Плюс сбор backtick-токенов из `CLAUDE.md`, `README.md`, `SKILL.md` и `.claude/rules/*.md` — после цикла по markdown-файлам:

```python
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        is_rule = rel.startswith(".claude/rules/")
        if path.name not in SCANNED_FOR_TOKENS and not is_rule:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.split("\n"), start=1):
            for token in _INLINE.findall(line):
                token = token.strip("`").strip()
                if not pathlib_rules.is_path_token(token):
                    continue
                if pathlib_rules.escapes_root(token, base=""):
                    findings.append(Finding("escapes-root", rel, lineno, "`%s`" % token))
                    continue
                if not (root / token).exists():
                    findings.append(Finding("unresolved", rel, lineno, "`%s`" % token))
```

- [x] **Step 4: Дописать периметр и `settings*.json`**

Спека называет два места, которых в коде выше нет.

**Периметр задаёт `.gitignore`**, плюс отдельно исключается `archive/`, если он
есть в принимаемом репозитории: все 16 битых ссылок в замере сидели там, это
Notion-экспорт с percent-encoding, и без исключения первый прогон ADOPT даёт
стену шума. Добавить в `scripts/check_links.py`:

```python
def _ignored(root):
    """Префиксы, в которые гейт не заходит: .gitignore плюс archive/."""
    prefixes = {".git/", "archive/"}
    ignore = root / ".gitignore"
    if ignore.exists():
        for line in ignore.read_text(encoding="utf-8").split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("!"):
                prefixes.add(line.rstrip("/") + "/")
    return tuple(sorted(prefixes))


def _in_perimeter(rel, ignored):
    return not rel.startswith(ignored)
```

и обернуть оба обхода: `if not _in_perimeter(rel, ignored): continue`.

**`.claude/settings*.json`** — пути к скриптам в хуках и `permissions`.
Строка ловит измеренную гниль: в the-practice-executive `settings.local.json`
ссылается на `.claude/scripts/*.sh`, которой нет.

```python
def _settings_paths(root, ignored):
    out = []
    for path in sorted(root.glob(".claude/settings*.json")):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.split("\n"), start=1):
            for token in re.findall(r'"([^"]+)"', line):
                if not pathlib_rules.is_path_token(token):
                    continue
                if pathlib_rules.escapes_root(token, base=""):
                    out.append(Finding("escapes-root", rel, lineno, token))
                elif not (root / token).exists():
                    out.append(Finding("unresolved", rel, lineno, token))
    return out
```

Тест дописать в `tests/test_check_links.py`:

```python
class TestPerimeter(unittest.TestCase):
    def test_settings_json_paths_are_checked(self):
        import json, tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "settings.local.json").write_text(
                json.dumps({"hooks": {"cmd": ".claude/scripts/missing.sh"}}), encoding="utf-8")
            self.assertEqual(scan(root).counts().get("unresolved"), 1)

    def test_archive_is_outside_the_perimeter(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            (root / "archive").mkdir()
            (root / "archive" / "old.md").write_text("[[в никуда]]\n", encoding="utf-8")
            self.assertEqual(scan(root).counts(), {})
```

- [x] **Step 5: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: PASS (12 tests)

- [x] **Step 6: Коммит**

```bash
git add scripts/check_links.py tests/test_check_links.py
git commit -m "wave1: md-link-to-file, link-to-transient, escapes-root, периметр и settings.json"
```

---

### Task 10: Гейт ссылок — `ambiguous`, аллоулист и `dead-allow`

**Files:**
- Modify: `scripts/check_links.py`
- Modify: `tests/test_check_links.py`

- [x] **Step 1: Дописать падающие тесты**

```python
class TestAmbiguous(unittest.TestCase):
    def test_two_candidates_make_a_warning_not_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("ambiguous"), 1)
        self.assertEqual(report.exit_code(), 2)  # из-за ошибок, не из-за ambiguous

    def test_matching_names_alone_are_not_a_finding(self):
        """Класс — про ссылку, которая резолвится в двух, а не про совпадение имён."""
        from scripts.check_links import scan
        report = scan(GREEN)
        self.assertNotIn("ambiguous", report.counts())


class TestAllowlist(unittest.TestCase):
    def test_line_without_reason_fails_the_gate(self):
        report = scan(BROKEN)
        self.assertGreaterEqual(report.counts().get("dead-allow", 0), 1)

    def test_dead_entry_fails_the_gate(self):
        from scripts.check_links import parse_allowlist
        entries = parse_allowlist("будущая\nстарая # причина\n")
        self.assertEqual([e.pattern for e in entries], ["будущая", "старая"])
        self.assertIsNone(entries[0].reason)
        self.assertEqual(entries[1].reason, "причина")
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_links.TestAllowlist -v`
Expected: FAIL — `ImportError: cannot import name 'parse_allowlist'`

- [x] **Step 3: Реализация**

Добавить в `scripts/check_links.py`:

```python
ALLOWLIST_NAME = ".link-allow"


class AllowEntry:
    __slots__ = ("pattern", "reason", "line", "used")

    def __init__(self, pattern, reason, line):
        self.pattern = pattern
        self.reason = reason
        self.line = line
        self.used = False


def parse_allowlist(text):
    entries = []
    for lineno, raw in enumerate(text.split("\n"), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "#" in stripped:
            pattern, reason = stripped.split("#", 1)
            entries.append(AllowEntry(pattern.strip(), reason.strip() or None, lineno))
        else:
            entries.append(AllowEntry(stripped, None, lineno))
    return entries
```

В `scan`: загрузить аллоулист, гасить им `unresolved`, отмечая `used`, и после обхода выдать `dead-allow` на строки без причины и на неиспользованные:

```python
    allow_path = root / ALLOWLIST_NAME
    allow = parse_allowlist(allow_path.read_text(encoding="utf-8")) if allow_path.exists() else []

    def allowed(target):
        for entry in allow:
            if entry.pattern and entry.pattern in target:
                entry.used = True
                return True
        return False
```

`unresolved` заводится только если `not allowed(target)`. После цикла:

```python
    for entry in allow:
        if entry.reason is None:
            findings.append(Finding("dead-allow", ALLOWLIST_NAME, entry.line,
                                    "строка без причины: %s" % entry.pattern))
        elif not entry.used:
            findings.append(Finding("dead-allow", ALLOWLIST_NAME, entry.line,
                                    "правило ничего не исключает, удалите: %s" % entry.pattern))
```

`ambiguous` — в месте резолва:

```python
            candidates = index.get(target, [])
            if len(candidates) > 1:
                findings.append(Finding("ambiguous", rel, link.line,
                                        "%s → %s" % (link.raw, ", ".join(sorted(candidates)))))
            elif not candidates and not allowed(target):
                findings.append(Finding("unresolved", rel, link.line, link.raw))
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: PASS (14 tests)

- [x] **Step 5: Коммит**

```bash
git add scripts/check_links.py tests/test_check_links.py
git commit -m "wave1: ambiguous и гигиена аллоулиста"
```

---

### Task 11: Гейт ссылок — `orphan` по объявлению

Сирота считается **не везде**, а там, где отсутствие входящей ссылки что-то значит: зона `sources` по конвенции и коллекция, объявившая `archetype: реестр`.

**Files:**
- Modify: `scripts/check_links.py`
- Modify: `tests/test_check_links.py`

- [x] **Step 1: Дописать падающий тест**

```python
class TestOrphan(unittest.TestCase):
    def test_unreferenced_source_is_a_report_not_an_error(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("orphan"), 1)

    def test_orphan_does_not_change_the_exit_code_on_its_own(self):
        from scripts.findings import Finding, Report
        self.assertEqual(Report([Finding("orphan", "sources/a.md", 1, "x")]).exit_code(), 0)

    def test_records_outside_sources_and_registries_are_not_counted(self):
        report = scan(GREEN)
        self.assertNotIn("orphan", report.counts())
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_links.TestOrphan -v`
Expected: FAIL — `AssertionError: None != 1`

- [x] **Step 3: Реализация**

```python
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter

REGISTRY_ARCHETYPE = "реестр"


def _orphan_perimeter(root):
    """Пути, где отсутствие входящей ссылки означает что-то определённое."""
    perimeter = set()
    for path in root.rglob("*.md"):
        rel = path.relative_to(root).as_posix()
        if zones.zone_of(rel) == "sources" and "/items/" in rel:
            perimeter.add(rel)
    for readme in root.rglob("README.md"):
        try:
            fields = parse_frontmatter(readme.read_text(encoding="utf-8"))
        except FrontmatterError:
            continue
        if fields.get("archetype") != REGISTRY_ARCHETYPE:
            continue
        items = readme.parent / "items"
        for path in items.rglob("*.md") if items.exists() else []:
            perimeter.add(path.relative_to(root).as_posix())
    return perimeter
```

Множество `referenced` собирается по ходу основного цикла — его до сих пор
не было, завести придётся здесь. Рядом с местом, где ссылка резолвится:

```python
    referenced = set()          # объявить рядом с findings, в начале scan
    ...
            candidates = index.get(target, [])
            for candidate in candidates:
                referenced.add(candidate)          # относительный путь цели
                referenced.add(Path(candidate).stem)
```

И в конце `scan`:

```python
    for rel in sorted(_orphan_perimeter(root)):
        stem = rel[:-3]
        if stem in referenced or Path(rel).stem in referenced:
            continue
        findings.append(Finding("orphan", rel, 1, "на файл никто не сослался"))
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: PASS (17 tests)

- [x] **Step 5: Коммит**

```bash
git add scripts/check_links.py tests/test_check_links.py
git commit -m "wave1: orphan по объявлению, а не обобщением"
```

---

### Task 12: Гейт frontmatter

**Files:**
- Create: `scripts/check_frontmatter.py`
- Create: `tests/test_check_frontmatter.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_check_frontmatter.py`:

```python
import unittest
from pathlib import Path

from scripts.check_frontmatter import scan

ROOT = Path(__file__).resolve().parent.parent
BROKEN = ROOT / "fixtures" / "broken"
GREEN = ROOT / "fixtures" / "green"


class TestContract(unittest.TestCase):
    def test_green_sample_is_silent(self):
        self.assertEqual(scan(GREEN).counts(), {})

    def test_missing_required_field(self):
        """Три: status у no-status.md плюс created у обеих разобравшихся записей.

        `created` требует стартовый набор секции 2, а не вид, — поэтому
        находка появляется и там, где вид поле не упоминает.
        """
        self.assertEqual(scan(BROKEN).counts().get("missing-required"), 3)

    def test_value_outside_vocabulary(self):
        self.assertEqual(scan(BROKEN).counts().get("value-outside-vocabulary"), 1)

    def test_unparseable_with_consumer_reports_the_line(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("unparseable"), 1)
        line = [f for f in report.findings if f.cls == "unparseable"][0]
        self.assertEqual(line.line, 4)

    def test_perimeter_is_records_of_collections_only(self):
        """core, папки документов и вложения не проверяются вовсе."""
        report = scan(BROKEN)
        touched = {f.path for f in report.findings}
        self.assertTrue(all(p.startswith("decisions/items/") for p in touched), touched)

    def test_field_with_no_consumer_is_silence(self):
        from scripts.check_frontmatter import check_record
        from scripts.basefile import parse_base
        base = parse_base('filters:\n  - file.inFolder("x")\n')
        fields = {"type": "note", "created": "2026-07-01", "случайное": 1}
        self.assertEqual(check_record("x/a.md", fields, base, {}), [])
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_frontmatter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.check_frontmatter'`

- [x] **Step 3: Реализация**

`scripts/check_frontmatter.py`:

```python
#!/usr/bin/env python3
"""Гейт frontmatter: контракт выводится из видов, а не из схемы."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.basefile import parse_base
from scripts.findings import Finding, Report
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter


# Секция 2: третий источник контракта наравне с видом и README коллекции.
# type и created — всегда; status и description приходят из архетипа,
# поэтому здесь их нет: у журнальной записи жизненного цикла не бывает,
# и требовать у неё статус — требовать поле, которого не существует.
STARTER_ALWAYS = ("type", "created")


def check_record(rel, fields, base, vocabulary):
    out = []
    for name in STARTER_ALWAYS:
        if name not in fields or fields[name] is None:
            out.append(Finding("missing-required", rel, 1,
                               "стартовый набор: поле %s" % name))
    for name in sorted(base.required):
        if name in STARTER_ALWAYS:
            continue
        if name not in fields or fields[name] is None:
            out.append(Finding("missing-required", rel, 1,
                               "поле %s читает вид" % name))
    for name, allowed in sorted(vocabulary.items()):
        if name in fields and fields[name] is not None and fields[name] not in allowed:
            out.append(Finding("value-outside-vocabulary", rel, 1,
                               "%s=%r вне словаря %s" % (name, fields[name], allowed)))
    return out


def scan(root, today=None):
    root = Path(root)
    findings = []
    for base_path in sorted(root.rglob("views.base")):
        collection = base_path.parent
        base = parse_base(base_path.read_text(encoding="utf-8"))

        vocabulary = {}
        readme = collection / "README.md"
        if readme.exists():
            try:
                declaration = parse_frontmatter(readme.read_text(encoding="utf-8"))
            except FrontmatterError:
                declaration = {}
            values = declaration.get("values") or {}
            if isinstance(values, dict):
                vocabulary = {k: v for k, v in values.items() if isinstance(v, list)}

        for folder in base.folders:
            records_dir = root / folder
            if not records_dir.exists():
                continue
            for record in sorted(records_dir.rglob("*.md")):
                rel = record.relative_to(root).as_posix()
                try:
                    fields = parse_frontmatter(record.read_text(encoding="utf-8"))
                except FrontmatterError as error:
                    findings.append(Finding("unparseable", rel, error.line, str(error)))
                    continue
                findings.extend(check_record(rel, fields, base, vocabulary))
    return Report(findings)


def main(argv=None):
    parser = argparse.ArgumentParser(description="frontmatter gate")
    parser.add_argument("root")
    parser.add_argument("--today", default=None)
    args = parser.parse_args(argv)
    report = scan(args.root, today=args.today)
    rendered = report.render()
    if rendered:
        print(rendered)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_frontmatter -v`
Expected: PASS (6 tests)

- [x] **Step 5: Коммит**

```bash
git add scripts/check_frontmatter.py tests/test_check_frontmatter.py
git commit -m "wave1: гейт frontmatter, контракт из видов"
```

---

### Task 13: Точный список находок и детерминизм отчёта

Критерий выхода волны: не «гейт что-то нашёл», а какие именно находки и сколько; плюс побайтовая одинаковость отчёта независимо от места чекаута.

**Files:**
- Create: `tests/test_fixtures.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_fixtures.py`:

```python
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_frontmatter, check_links

ROOT = Path(__file__).resolve().parent.parent
BROKEN = ROOT / "fixtures" / "broken"
GREEN = ROOT / "fixtures" / "green"


class TestExactFindings(unittest.TestCase):
    def test_link_gate_finds_exactly_this(self):
        self.assertEqual(
            check_links.scan(BROKEN).counts(),
            {
                "unresolved": 3,
                "md-link-to-file": 1,
                "link-to-transient": 1,
                "escapes-root": 2,
                "ambiguous": 1,
                "dead-allow": 2,
                "orphan": 1,
            },
        )

    def test_frontmatter_gate_finds_exactly_this(self):
        self.assertEqual(
            check_frontmatter.scan(BROKEN).counts(),
            {"missing-required": 3, "value-outside-vocabulary": 1, "unparseable": 1},
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
```

- [x] **Step 2: Прогнать и увидеть настоящие числа**

Run: `python3 -m unittest tests.test_fixtures -v`
Expected: FAIL с расхождением счётчиков.

**Здесь есть развилка, и она важна.** Расхождение значит одно из двух: гейт ловит не то, или фикстура содержит не то, что задумано. Разбираться обязательно по существу — открыть фикстуру и убедиться глазами, какие находки в ней действительно должны быть. **Подгонять числа под то, что выдал гейт, запрещено**: тогда тест перестаёт быть проверкой и становится снимком поведения, включая ошибочного.

- [x] **Step 3: Починить настоящую причину**

Правится либо гейт, либо фикстура — в зависимости от того, что оказалось неверным. Ожидаемые числа выведены из состава фикстуры Task 7:

| класс | откуда |
|---|---|
| `unresolved` 3 | `[[несуществующая заметка]]`, `scripts/move.py` в CLAUDE.md, `scripts/rename.py` в rule-файле |
| `md-link-to-file` 1 | `[профиль](../../core/me.md)` |
| `link-to-transient` 1 | `[[tmp/plan]]` из `areas` |
| `escapes-root` 2 | `` `/Users/artem/notes.md` `` и `[[../../../soseddniy-repo/file]]` |
| `ambiguous` 1 | `[[dup]]` при двух `dup.md` |
| `dead-allow` 2 | строка без причины и строка, ничего не исключающая |
| `orphan` 1 | транскрипт, на который никто не сослался |

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_fixtures -v`
Expected: PASS (6 tests)

- [x] **Step 5: Коммит**

```bash
git add tests/test_fixtures.py
git commit -m "wave1: точный список находок и детерминизм отчёта"
```

---

### Task 14: Проверка пакета

**Files:**
- Create: `scripts/check_package.py`
- Create: `tests/test_check_package.py`

- [x] **Step 1: Написать падающий тест**

`tests/test_check_package.py`:

```python
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_package import check

ROOT = Path(__file__).resolve().parent.parent


def _minimal_package(root):
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "x", "version": "0.1.0"}), encoding="utf-8")
    (root / "hooks").mkdir()
    (root / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [{"matcher": "*", "hooks": []}]}}),
        encoding="utf-8")
    skill = root / "skills" / "drain-inbox"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: drain-inbox\ndescription: Разбирает inbox\n---\n", encoding="utf-8")
    (skill / "eval.txt").write_text("разбери инбокс\ndrain the inbox\n", encoding="utf-8")
    return root


class TestPackageCheck(unittest.TestCase):
    def test_minimal_package_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            self.assertEqual(check(root).counts(), {})

    def test_unknown_hook_event_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"OnFullMoon": [{"matcher": "*", "hooks": []}]}}),
                encoding="utf-8")
            self.assertIn("unknown-hook-event", check(root).counts())

    def test_absolute_path_anywhere_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: drain-inbox\ndescription: x\n---\nЗовёт /Users/artem/x.py\n",
                encoding="utf-8")
            self.assertIn("absolute-path", check(root).counts())

    def test_skill_without_description_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: drain-inbox\n---\n", encoding="utf-8")
            self.assertIn("skill-without-description", check(root).counts())

    def test_skill_without_trigger_eval_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "eval.txt").unlink()
            self.assertIn("skill-without-eval", check(root).counts())

    def test_relative_script_call_in_a_skill_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: drain-inbox\ndescription: x\n---\n"
                "Запусти `python3 scripts/drain.py`\n", encoding="utf-8")
            self.assertIn("relative-path-in-skill", check(root).counts())

    def test_plugin_root_variable_is_the_allowed_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: drain-inbox\ndescription: x\n---\n"
                'Запусти `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/drain.py"`\n',
                encoding="utf-8")
            self.assertNotIn("relative-path-in-skill", check(root).counts())

    def test_destructive_example_in_adopt_instructions_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            adopt = root / "skills" / "adopt-context-repo"
            adopt.mkdir(parents=True)
            (adopt / "SKILL.md").write_text(
                "---\nname: adopt-context-repo\ndescription: x\n---\n"
                "Переложи так: mv journal areas/journal\n", encoding="utf-8")
            (adopt / "eval.txt").write_text("прими репозиторий\nadopt this repo\n",
                                            encoding="utf-8")
            self.assertIn("destructive-example", check(root).counts())

    def test_skill_name_must_match_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "skills" / "drain-inbox" / "SKILL.md").write_text(
                "---\nname: другое-имя\ndescription: x\n---\n", encoding="utf-8")
            self.assertIn("skill-name-mismatch", check(root).counts())


class TestThisPackage(unittest.TestCase):
    def test_our_own_package_is_green(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_package.py"), str(ROOT)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_package -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.check_package'`

- [x] **Step 3: Реализация**

`scripts/check_package.py`:

```python
#!/usr/bin/env python3
"""Проверка пакета перед выпуском. Запускается руками, CI нет.

Самый дешёвый артефакт разбора: одна строка с неподдерживаемым типом хука
жила у изученного аналога три с половиной месяца.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.findings import Finding, Report
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter

HOOK_EVENTS = frozenset({
    "SessionStart", "PreToolUse", "PostToolUse", "Stop", "PreCompact",
    "UserPromptSubmit", "SubagentStop", "Notification", "SessionEnd",
})
HOOK_TYPES = frozenset({"command"})
MATCHERS = re.compile(r"^[A-Za-z*|_]+$")

# Абсолютный путь верен ровно на одной машине.
ABSOLUTE = re.compile(r"(?<![\w.])(?:/Users/|/home/|/opt/|/etc/|~/)")
# Вызов скрипта пакета из прозы скилла.
SCRIPT_CALL = re.compile(r"(?:python3?\s+|sh\s+|bash\s+|\./)\S*scripts/\S+")
# Разрушающий пример в инструкциях ADOPT.
DESTRUCTIVE = re.compile(r"(?<![\w-])(?:mv|rm)\s+[^\s`]")

SKIP_DIRS = {".git", "fixtures", "tests", "docs", ".baton", "__pycache__"}


def _iter_package_files(root):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in (".md", ".py", ".sh", ".json", ".base", ".txt") or path.name == "check":
            yield path


def check(root):
    root = Path(root)
    findings = []

    hooks_file = root / "hooks" / "hooks.json"
    if hooks_file.exists():
        data = json.loads(hooks_file.read_text(encoding="utf-8"))
        for event, entries in (data.get("hooks") or {}).items():
            if event not in HOOK_EVENTS:
                findings.append(Finding("unknown-hook-event", "hooks/hooks.json", 1, event))
            for entry in entries or []:
                matcher = entry.get("matcher", "*")
                if not MATCHERS.match(str(matcher)):
                    findings.append(Finding("unknown-matcher", "hooks/hooks.json", 1, str(matcher)))
                for hook in entry.get("hooks") or []:
                    if hook.get("type") not in HOOK_TYPES:
                        findings.append(Finding("unknown-hook-type", "hooks/hooks.json", 1,
                                                str(hook.get("type"))))

    skills_dir = root / "skills"
    if skills_dir.exists():
        for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            rel = skill.relative_to(root).as_posix()
            manifest = skill / "SKILL.md"
            if not manifest.exists():
                findings.append(Finding("skill-without-description", rel, 1, "нет SKILL.md"))
                continue
            try:
                fields = parse_frontmatter(manifest.read_text(encoding="utf-8"))
            except FrontmatterError as error:
                findings.append(Finding("unparseable", rel + "/SKILL.md", error.line, str(error)))
                continue
            if not fields.get("description"):
                findings.append(Finding("skill-without-description", rel, 1, "пустое описание"))
            if fields.get("name") != skill.name:
                findings.append(Finding("skill-name-mismatch", rel, 1,
                                        "%r != %r" % (fields.get("name"), skill.name)))
            if not (skill / "eval.txt").exists():
                findings.append(Finding("skill-without-eval", rel, 1,
                                        "нет eval.txt: срабатывание не проверяется"))

    for path in _iter_package_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.split("\n"), start=1):
            if ABSOLUTE.search(line):
                findings.append(Finding("absolute-path", rel, lineno, line.strip()[:80]))
            # Восемь скиллов у изученного аналога звали скрипт относительным
            # путём: рабочим каталогом оказался репозиторий пользователя,
            # и вся заявленная функциональность молча не работала.
            if rel.startswith("skills/") and SCRIPT_CALL.search(line) \
                    and "${CLAUDE_PLUGIN_ROOT}" not in line:
                findings.append(Finding("relative-path-in-skill", rel, lineno,
                                        line.strip()[:80]))
            # ADOPT мутирует чужое дерево; пример mv или rm в его инструкциях
            # рано или поздно исполнят буквально.
            if rel.startswith("skills/adopt-") and DESTRUCTIVE.search(line):
                findings.append(Finding("destructive-example", rel, lineno,
                                        line.strip()[:80]))

    return Report(findings)


def main(argv=None):
    parser = argparse.ArgumentParser(description="package check")
    parser.add_argument("root")
    args = parser.parse_args(argv)
    report = check(args.root)
    rendered = report.render()
    if rendered:
        print(rendered)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
```

Дописать классы в `scripts/findings.py` (`_SEVERITY` и новый кортеж):

```python
PACKAGE_CLASSES = (
    "unknown-hook-event",
    "unknown-hook-type",
    "unknown-matcher",
    "absolute-path",
    "relative-path-in-skill",
    "destructive-example",
    "gate-not-read-only",
    "tests-touched-product",
    "skill-without-description",
    "skill-without-eval",
    "skill-name-mismatch",
)
```

и по строке `"<класс>": "error",` для каждого в `_SEVERITY`.

Два последних класса доказываются не разбором текста, а прогоном. Дописать
в `scripts/check_package.py`:

```python
import hashlib
import subprocess


def _tree_hash(root):
    """Хеш дерева: имя, размер и содержимое каждого файла, кроме служебного."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith((".git/", "__pycache__/")) or "/__pycache__/" in rel:
            continue
        digest.update(rel.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def check_read_only(root, gate, fixture):
    """Гейт обязан доказать read-only хешем дерева до и после."""
    before = _tree_hash(fixture)
    subprocess.run([sys.executable, str(root / "scripts" / gate), str(fixture)],
                   capture_output=True, text=True)
    after = _tree_hash(fixture)
    if before != after:
        return [Finding("gate-not-read-only", "scripts/" + gate, 1,
                        "дерево фикстуры изменилось после прогона")]
    return []
```

и позвать для обоих гейтов на битой фикстуре, если она есть в дереве.
Проверка «тесты не создали и не изменили ни одного файла продукта» —
тот же приём вокруг `python3 -m unittest discover`, хеш берётся по `scripts/`
и `.claude-plugin/`; расхождение даёт `tests-touched-product`.

- [x] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_package -v`
Expected: PASS (10 tests)

- [x] **Step 5: Коммит**

```bash
git add scripts/check_package.py scripts/findings.py tests/test_check_package.py
git commit -m "wave1: проверка пакета — хуки, абсолютные пути, скиллы и их evals"
```

---

### Task 15: «Нет проверки — нет гейта» как исполняемое правило

Правило секции 16 само обязано быть проверкой, иначе оно дисциплина.

**Files:**
- Create: `tests/test_gate_coverage.py`
- Create: `docs/gate-coverage.md`

- [x] **Step 1: Написать падающий тест**

`tests/test_gate_coverage.py`:

```python
import unittest
from pathlib import Path

from scripts.findings import FRONTMATTER_CLASSES, LINK_CLASSES, PACKAGE_CLASSES

ROOT = Path(__file__).resolve().parent.parent
COVERAGE = ROOT / "docs" / "gate-coverage.md"


class TestEveryClassIsProven(unittest.TestCase):
    """У каждого класса либо фикстура, либо записанная причина её отсутствия.

    Пустым оставить нельзя — это и есть механизм под «эффективность,
    а не маскарад»: нельзя молча сделать вид, что покрыто.
    """

    def test_coverage_table_lists_every_class(self):
        table = COVERAGE.read_text(encoding="utf-8")
        for cls in LINK_CLASSES + FRONTMATTER_CLASSES + PACKAGE_CLASSES:
            self.assertIn("`%s`" % cls, table, "класс %s не объяснён" % cls)

    def test_no_empty_justifications(self):
        for line in COVERAGE.read_text(encoding="utf-8").split("\n"):
            if not line.startswith("| `"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            self.assertTrue(all(cells), "пустая клетка в строке: %s" % line)
```

- [x] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_gate_coverage -v`
Expected: FAIL — `FileNotFoundError: docs/gate-coverage.md`

- [x] **Step 3: Написать таблицу покрытия**

`docs/gate-coverage.md`:

```markdown
# Покрытие классов находок

Правило секции 16: у каждого гейта либо исполняемая проверка на фикстуре,
либо обязательное поле с объяснением, почему её нет. Пустым оставить нельзя.
Таблицу держит `tests/test_gate_coverage.py`.

| класс | чем доказан |
|---|---|
| `unresolved` | битая фикстура, 4 находки, `tests/test_fixtures.py` |
| `md-link-to-file` | битая фикстура, 1 находка |
| `link-to-transient` | битая фикстура, 1 находка |
| `escapes-root` | битая фикстура, 2 находки: абсолютный путь и `..` выше корня |
| `dead-allow` | битая фикстура, 2 находки: строка без причины и мёртвая строка |
| `ambiguous` | битая фикстура, 1 находка при двух `dup.md` |
| `orphan` | битая фикстура, 1 находка в `sources` |
| `missing-required` | битая фикстура, запись без `status` при `groupBy: status` |
| `value-outside-vocabulary` | битая фикстура, `status: активно` вне словаря |
| `unparseable` | битая фикстура, блочный скаляр в поле с потребителем |
| `unknown-hook-event` | `tests/test_check_package.py`, временный пакет с `OnFullMoon` |
| `unknown-hook-type` | `tests/test_check_package.py`, тип вне закрытого списка |
| `unknown-matcher` | `tests/test_check_package.py`, матчер вне закрытого множества |
| `absolute-path` | `tests/test_check_package.py`, `/Users/` в прозе скилла |
| `relative-path-in-skill` | `tests/test_check_package.py`, вызов `scripts/*` без `${CLAUDE_PLUGIN_ROOT}` |
| `destructive-example` | `tests/test_check_package.py`, пример `mv` в инструкциях ADOPT |
| `gate-not-read-only` | `check_read_only`: хеш дерева фикстуры до и после прогона гейта |
| `tests-touched-product` | тот же приём вокруг прогона тестов, хеш по `scripts/` и `.claude-plugin/` |
| `skill-without-description` | `tests/test_check_package.py`, SKILL.md без описания |
| `skill-without-eval` | `tests/test_check_package.py`, скилл без `eval.txt` |
| `skill-name-mismatch` | `tests/test_check_package.py`, имя не совпало с папкой |
```

- [x] **Step 4: Прогнать всё разом**

Run: `./check`
Expected: все тесты PASS, проверка пакета молчит, код возврата 0

- [x] **Step 5: Коммит**

```bash
git add docs/gate-coverage.md tests/test_gate_coverage.py
git commit -m "wave1: покрытие классов доказано таблицей с исполняемой проверкой"
```

---

## Задачи 16–23: дыры, найденные состязательной проверкой

Задачи 1–15 сделали `./check` зелёным. Состязательная проверка сажала мутации
в копию дерева и смотрела, покраснеет ли набор: критерии 1, 3, 4 и 5
опровергнуты — там, где посаженное нарушение не роняет тесты, критерий не
выполнен, а зелёный цвет означает лишь, что проверка в этом месте слепа.

Каждая задача ниже начинается с теста, который **сегодня проходит зелёным на
сломанном коде** — это и есть доказательство дыры.

**Порядок исполнения.** Технически задачи независимы; жёстких связей две — 22
после 21 (обе правят один ожидаемый список), и 17 раньше 20 (таблица покрытия
ссылается на тест, который заводит 17). Рекомендуемый порядок:

| # | почему здесь |
|---|---|
| 16 | первой: дыра сработает в волне 2, которая производит `hooks/` |
| 17, 18, 19 | одним заходом — все три правят `check_package.py` |
| 20 | после 17: ссылается на `test_matcher_typo_is_caught` |
| 21 → 22 | только в этом порядке |
| 23 | последней, ни от чего не зависит |

**Три решения ждут слова автора.** Приняты агентом, обоснованы внутри задач,
обратимы — но это выбор, а не умолчание. До ответа задачи исполняются как
написаны.

| задача | решение | альтернатива, если автор не согласен |
|---|---|---|
| 17 | закрытое множество матчеров — 11 имён инструментов, выведены агентом; в спеке списка нет | взять список из документации Claude Code целиком либо свести к тем, что реально использует волна 2 |
| 18 | «any absolute path anywhere» прочитано как «путь от настоящего корня ФС»: закрытый список префиксов плюс Windows и UNC | буквальное чтение — любой токен вида `/сегмент/`; даёт ложные срабатывания на маршрутах API, из-за которых периметр уже откатывали |
| 23 | `--today` не снят, а сделан наблюдаемым: снятие механизма из спеки — эскалация по `CLAUDE.md` | снять флаг до волны, где появятся правила, зависящие от даты — но это правка спеки, а не кода |

---

### Task 16: Копия модуля зон ловится тестом (критерий 5)

Дыра: `if path.name == "zones.py": continue` пропускает файл с таким именем
**где угодно**. Побайтовая копия `scripts/zones.py` в `hooks/zones.py` набор не
роняет — а копирование файла и есть самый вероятный способ завести второе
определение. Волны 2 и 3 производят ровно `hooks/` и `scaffold/`.

**Files:**
- Modify: `tests/test_zones.py:29-61`

- [ ] **Step 1: Написать падающий тест**

Заменить класс `TestSingleDefinition` целиком на модульную функцию плюс два
теста. Пропуск идёт по относительному пути, а не по имени файла:

```python
_NOT_PACKAGE = {".git", "__pycache__", "tests", "fixtures", "docs"}


def _offenders(root):
    """Файлы пакета, держащие свою копию таблицы зон.

    Пропускается ровно канонический `scripts/zones.py`, по относительному
    пути. Пропуск по имени файла делал невидимой любую копию модуля —
    единственный способ завести второе определение, который проверка
    исключала по построению.
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
```

Дописать импорт в шапку файла:

```python
import tempfile
```

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_zones -v`
Expected: `test_a_copy_of_zones_py_elsewhere_is_an_offender` FAIL — на старом
коде `_offenders` ещё не существует, тест падает с `NameError`. Это ожидаемо:
шаг 1 несёт и тест, и целевую форму кода, поэтому сначала внести **только**
два теста, оставив старый метод, убедиться, что новый падает, и лишь затем
внести `_offenders`.

- [ ] **Step 3: Внести `_offenders` и удалить старый метод**

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_zones -v`
Expected: оба теста PASS

- [ ] **Step 5: Коммит**

```bash
git add tests/test_zones.py
git commit -m "wave1: тест единственного определения зон ловит копию файла"
```

---

### Task 17: Матчеры и типы хуков — закрытое множество (критерий 3)

Дыра: `MATCHERS = re.compile(r"^[A-Za-z*|_]+$")` проверяет **форму**, а не
принадлежность списку, поэтому опечатка `Bahs` проходит зелёной. Спека, секция
21: «матчеры — из закрытого множества». Опечатка в матчере и есть та поломка,
ради которой проверка заводилась: у изученного аналога одна такая строка жила
три с половиной месяца.

**Files:**
- Modify: `scripts/check_package.py:28`, `scripts/check_package.py:94`
- Test: `tests/test_check_package.py`

- [ ] **Step 1: Написать падающий тест**

Дописать в `TestPackageCheck`:

```python
    def test_matcher_typo_is_caught(self):
        """Критерий 3: матчер вне закрытого множества обязан валить проверку.

        `Bahs` — опечатка в `Bash`. Проверкой формы она проходила зелёной.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"PreToolUse": [
                    {"matcher": "Bahs", "hooks": []}
                ]}}), encoding="utf-8")
            self.assertIn("unknown-matcher", check(root).counts())

    def test_known_matcher_forms_pass(self):
        for matcher in ("*", "Bash", "Edit|Write"):
            with self.subTest(matcher=matcher), tempfile.TemporaryDirectory() as tmp:
                root = _minimal_package(Path(tmp))
                (root / "hooks" / "hooks.json").write_text(
                    json.dumps({"hooks": {"PreToolUse": [
                        {"matcher": matcher, "hooks": []}
                    ]}}), encoding="utf-8")
                self.assertNotIn("unknown-matcher", check(root).counts())

    def test_alternation_with_one_bad_member_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {"PreToolUse": [
                    {"matcher": "Edit|Wrote", "hooks": []}
                ]}}), encoding="utf-8")
            self.assertIn("unknown-matcher", check(root).counts())
```

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_package -v`
Expected: `test_matcher_typo_is_caught` и
`test_alternation_with_one_bad_member_is_caught` FAIL — `Bahs` и `Edit|Wrote`
проходят форму `^[A-Za-z*|_]+$`

- [ ] **Step 3: Реализация**

Заменить строку 28 `scripts/check_package.py`:

```python
# Матчер хука — имя инструмента, `*` или альтернатива через `|`. Закрытое
# множество, а не форма: `^[A-Za-z*|_]+$` принимал любое слово, поэтому
# опечатка `Bahs` проходила зелёной — ровно та поломка, ради которой
# проверка и заводилась. Новый инструмент добавляется правкой этого списка;
# в этом и смысл закрытого множества.
TOOL_NAMES = frozenset({
    "Bash", "Edit", "Glob", "Grep", "NotebookEdit", "Read", "Task",
    "TodoWrite", "WebFetch", "WebSearch", "Write",
})


def matcher_is_known(matcher):
    matcher = str(matcher)
    if matcher == "*":
        return True
    parts = matcher.split("|")
    return all(part in TOOL_NAMES for part in parts)
```

Заменить проверку в `check()` (строка 94):

```python
                    if not matcher_is_known(matcher):
```

- [ ] **Step 4: Прогнать — должно пройти**

Run: `./check`
Expected: все тесты PASS, проверка пакета молчит, код возврата 0

- [ ] **Step 5: Коммит**

```bash
git add scripts/check_package.py tests/test_check_package.py
git commit -m "wave1: матчеры из закрытого множества, а не по форме регулярки"
```

---

### Task 18: Абсолютный путь — все формы, не пять префиксов (критерий 3)

Дыра: `_ABSOLUTE_PREFIXES` знает пять префиксов, поэтому `/tmp/`, `/var/`,
`/usr/local/`, `/Volumes/`, `C:\` и UNC проходят. Критерий говорит «any
absolute path **anywhere** in the package».

Читается это как «путь, начинающийся с настоящего корня файловой системы», а не
«любой токен со слэшем»: широкая форма даёт ложные срабатывания на маршрутах
API и слэш-командах — та самая поломка, из-за которой периметр уже откатывали
(DEC-0003, теперь в `CLAUDE.md`).

**Files:**
- Modify: `scripts/check_package.py:34-37`
- Test: `tests/test_check_package.py`

- [ ] **Step 1: Написать падающий тест**

```python
    def test_every_absolute_form_is_caught(self):
        """Критерий 3: пять префиксов оставляли зелёными шесть форм."""
        forms = [
            "/Users/artem/x.py", "/home/artem/x.py", "/tmp/scratch/x.py",
            "/var/log/x.txt", "/usr/local/bin/tool", "/Volumes/disk/x.md",
            "/private/tmp/x.py", "~/notes/x.md", "C:\\Users\\artem\\x.py",
            "D:/data/x.py", "\\\\server\\share\\x.py",
        ]
        for form in forms:
            with self.subTest(form=form):
                self.assertIsNotNone(
                    check_package.ABSOLUTE.search("Зовёт %s отсюда" % form), form)

    def test_relative_and_route_like_tokens_are_not_absolute(self):
        """Ложные срабатывания, ради которых периметр уже откатывали."""
        for token in ("scripts/x.py", "../core/me.md", "/backlinks/:path",
                      "/baton:auto 1", "http://example.com/x"):
            with self.subTest(token=token):
                self.assertIsNone(check_package.ABSOLUTE.search(token), token)
```

Дописать импорт в шапку `tests/test_check_package.py`:

```python
from scripts import check_package
```

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_package -v`
Expected: `test_every_absolute_form_is_caught` FAIL на первой же форме `/tmp/`

- [ ] **Step 3: Реализация**

Заменить строки 34–37 `scripts/check_package.py`:

```python
_ABSOLUTE_PREFIXES = (
    "/" + "Users/", "/" + "home/", "/" + "root/", "/" + "opt/", "/" + "etc/",
    "/" + "tmp/", "/" + "var/", "/" + "usr/", "/" + "srv/", "/" + "mnt/",
    "/" + "media/", "/" + "private/", "/" + "Volumes/", "/" + "Applications/",
    "/" + "Library/", "/" + "System/", "~" + "/",
)
ABSOLUTE = re.compile(
    "(?<![\\w.])(?:%s)" % "|".join(re.escape(p) for p in _ABSOLUTE_PREFIXES)
    # C:\ и C:/ — буква диска. Однобуквенность и отсутствие слова слева
    # разводят её с `http://`, где перед двоеточием стоит `p`.
    + r"|(?<![\w.])[A-Za-z]:[\\/]"
    # UNC \\сервер\ресурс
    + r"|(?<![\w.])\\\\[A-Za-z0-9._-]+\\"
)
```

- [ ] **Step 4: Прогнать — должно пройти**

Run: `./check`
Expected: все тесты PASS, проверка пакета молчит, код возврата 0

- [ ] **Step 5: Коммит**

```bash
git add scripts/check_package.py tests/test_check_package.py
git commit -m "wave1: абсолютный путь — все формы корня, включая Windows и UNC"
```

---

### Task 19: Периметр проверки пакета — всё, что читается текстом (критерий 3)

Две дыры сразу. Первая: `SKIP_DIRS` исключает **все восемь имён зон**, поэтому
любой каталог пакета, чьё имя совпало с зоной, уходит из скана целиком. Вторая:
фильтр по расширению не читает файлы без расширения, `.yaml`, `.toml` и
`Makefile` — ровно те места, где абсолютный путь и живёт.

Исключать нужно ровно два зональных каталога, и по названной причине: этот
репозиторий удваивается под контекст-репозиторий собственной разработки, и
абсолютный путь в чужой цитате внутри `sources/` — не находка проверки пакета.

**Files:**
- Modify: `scripts/check_package.py:49`, `scripts/check_package.py:59-72`
- Test: `tests/test_check_package.py`

- [ ] **Step 1: Написать падающий тест**

```python
    def test_extensionless_and_yaml_files_are_scanned(self):
        """Критерий 3: фильтр по расширению уводил из-под скана целые форматы."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "Makefile").write_text(
                "run:\n\tpython3 /Users/artem/x.py\n", encoding="utf-8")
            self.assertIn("absolute-path", check(root).counts())

    def test_a_package_dir_named_like_a_zone_is_still_scanned(self):
        """Восемь имён зон в SKIP_DIRS снимали со скана целые поддеревья."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            core = root / "core"
            core.mkdir()
            (core / "notes.md").write_text("Смотри /Users/artem/x.md\n", encoding="utf-8")
            self.assertIn("absolute-path", check(root).counts())

    def test_binary_files_do_not_break_the_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _minimal_package(Path(tmp))
            (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
            self.assertEqual(check(root).counts(), {})
```

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_package -v`
Expected: `test_extensionless_and_yaml_files_are_scanned` и
`test_a_package_dir_named_like_a_zone_is_still_scanned` FAIL

- [ ] **Step 3: Реализация**

Заменить строку 49 и функцию `_iter_package_files`:

```python
# Каталоги, не входящие в пакет (dev-инструменты секции 21). `inbox/` и
# `sources/` — материалы собственной разработки: этот репозиторий удваивается
# под контекст-репозиторий своей же разработки, и абсолютный путь в чужой
# цитате внутри них не находка проверки пакета. Остальные шесть имён зон
# отсюда убраны: раньше исключались все восемь, и любой каталог пакета, чьё
# имя совпало с зоной, уходил из скана целиком.
SKIP_DIRS = {".git", ".claude", "fixtures", "tests", "docs", "__pycache__",
             "inbox", "sources"}


def _iter_package_files(root):
    """Все файлы пакета, которые читаются как текст.

    Формат определяется тем, декодируется ли файл в UTF-8, а не расширением:
    фильтр по списку расширений уводил из-под проверки файлы без расширения,
    `.yaml`, `.toml` и `Makefile`. Бинарные отсеиваются на чтении, в `check()`.

    Проверяется только первый сегмент, как в `zones.zone_of()`: проверка по
    любому сегменту на любой глубине снимала со скана `skills/inbox/` — скилл,
    чьё имя совпало с зоной.
    """
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.relative_to(root).parts[0] in SKIP_DIRS:
            continue
        yield path
```

Импорт `zones` в `check_package.py` после этого остаётся нужен только если его
использует что-то ещё — проверить `grep -n "zones\." scripts/check_package.py`
и удалить строку `from scripts import zones`, если других вхождений нет.

- [ ] **Step 4: Прогнать — должно пройти**

Run: `./check`
Expected: все тесты PASS, проверка пакета молчит, код возврата 0

Если проверка пакета покраснела на собственном репозитории — прочитать
находки. Это не повод расширять `SKIP_DIRS`: расширение периметра обратно
уже откатывали однажды (`CLAUDE.md`, «не переоткрывать»).

- [ ] **Step 5: Коммит**

```bash
git add scripts/check_package.py tests/test_check_package.py
git commit -m "wave1: периметр проверки пакета — все текстовые файлы, зоны только две"
```

---

### Task 20: Таблица покрытия ссылается на существующий тест (критерий 4)

Критерий держит только половину: пустая клетка валит набор, а клетка,
называющая несуществующий тест, проходит — и удаление теста при живой строке
таблицы проходит тоже. Таблица не умеет отличить настоящий тест от выдуманного
имени.

Лечится формой: третий столбец несёт машинно-проверяемую ссылку
`` `tests/файл.py::Класс::тест` `` либо явное `нет проверки: причина`.

**Files:**
- Modify: `tests/test_gate_coverage.py` (целиком), `docs/gate-coverage.md`
  (таблица)

- [ ] **Step 1: Написать падающий тест**

Заменить `tests/test_gate_coverage.py` целиком:

```python
import re
import unittest
from pathlib import Path

from scripts.findings import FRONTMATTER_CLASSES, LINK_CLASSES, PACKAGE_CLASSES

ROOT = Path(__file__).resolve().parent.parent
COVERAGE = ROOT / "docs" / "gate-coverage.md"

CITATION = re.compile(r"`(tests/[A-Za-z0-9_./]+\.py)((?:::[A-Za-z0-9_]+)+)`")
NO_TEST = "нет проверки:"


def _rows(text):
    for line in text.split("\n"):
        if line.startswith("| `"):
            yield line, [c.strip() for c in line.strip("|").split("|")]


def _problems(text, root):
    """Строки таблицы, которые ничего не доказывают.

    Три формы негодности: не три столбца, пустая клетка, ссылка на тест,
    которого нет. Последняя — та, из-за которой критерий 4 держался
    наполовину: выдуманное имя теста и удаление настоящего проходили зелёными.
    """
    out = []
    for line, cells in _rows(text):
        if len(cells) != 3 or not all(cells):
            out.append("не три непустых столбца: %s" % line)
            continue
        citation = cells[2]
        if citation.startswith(NO_TEST):
            if not citation[len(NO_TEST):].strip():
                out.append("пустая причина отсутствия проверки: %s" % line)
            continue
        match = CITATION.fullmatch(citation)
        if match is None:
            out.append("ссылка не в форме `tests/файл.py::Класс::тест`: %s" % line)
            continue
        path = Path(root) / match.group(1)
        if not path.exists():
            out.append("нет файла %s: %s" % (match.group(1), line))
            continue
        source = path.read_text(encoding="utf-8")
        for symbol in [s for s in match.group(2).split("::") if s]:
            if symbol not in source:
                out.append("в %s нет %s: %s" % (match.group(1), symbol, line))
    return out


class TestEveryClassIsProven(unittest.TestCase):
    """У каждого класса либо исполняемая проверка, либо записанная причина.

    Пустым оставить нельзя — это и есть механизм под «эффективность,
    а не маскарад»: нельзя молча сделать вид, что покрыто.
    """

    def test_coverage_table_lists_every_class(self):
        table = COVERAGE.read_text(encoding="utf-8")
        for cls in LINK_CLASSES + FRONTMATTER_CLASSES + PACKAGE_CLASSES:
            self.assertIn("`%s`" % cls, table, "класс %s не объяснён" % cls)

    def test_the_real_table_is_sound(self):
        self.assertEqual(_problems(COVERAGE.read_text(encoding="utf-8"), ROOT), [])


class TestTheTableCannotLie(unittest.TestCase):
    """Регрессия на критерий 4: таблица обязана отличать тест от имени."""

    _GOOD = ("| `orphan` | битая фикстура, 1 находка | "
             "`tests/test_fixtures.py::TestExactFindings::"
             "test_every_link_finding_sits_on_its_own_specimen` |")

    def test_a_sound_row_has_no_problems(self):
        self.assertEqual(_problems(self._GOOD, ROOT), [])

    def test_a_fabricated_test_name_is_caught(self):
        row = self._GOOD.replace("test_every_link_finding_sits_on_its_own_specimen",
                                 "test_this_never_existed")
        self.assertEqual(len(_problems(row, ROOT)), 1)

    def test_a_missing_test_file_is_caught(self):
        row = self._GOOD.replace("test_fixtures.py", "test_deleted.py")
        self.assertEqual(len(_problems(row, ROOT)), 1)

    def test_prose_instead_of_a_citation_is_caught(self):
        row = "| `orphan` | битая фикстура, 1 находка | покрыто тестами |"
        self.assertEqual(len(_problems(row, ROOT)), 1)

    def test_omitted_and_empty_cells_are_caught(self):
        self.assertEqual(len(_problems("| `orphan` |", ROOT)), 1)
        self.assertEqual(len(_problems("| `orphan` |  |  |", ROOT)), 1)

    def test_an_empty_reason_for_having_no_test_is_caught(self):
        row = "| `orphan` | нечем | нет проверки:  |"
        self.assertEqual(len(_problems(row, ROOT)), 1)

    def test_a_named_reason_for_having_no_test_passes(self):
        row = "| `orphan` | нечем | нет проверки: класс появится в волне 4 |"
        self.assertEqual(_problems(row, ROOT), [])
```

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_gate_coverage -v`
Expected: `test_the_real_table_is_sound` FAIL — таблица сейчас о двух столбцах

- [ ] **Step 3: Переписать таблицу**

Заменить таблицу в `docs/gate-coverage.md` на три столбца:

```markdown
| класс | чем доказан | тест |
|---|---|---|
| `unresolved` | битая фикстура, 4 находки | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `md-link-to-file` | битая фикстура, 1 находка | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `link-to-transient` | битая фикстура, 1 находка | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `escapes-root` | битая фикстура, 2 находки: абсолютный путь и `..` выше корня | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `dead-allow` | битая фикстура, 2 находки: строка без причины и мёртвая строка | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `ambiguous` | битая фикстура, 1 находка при двух `dup.md` | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `orphan` | битая фикстура, 1 находка в `sources` | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `missing-required` | битая фикстура, запись без `status` при `groupBy: status` | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `value-outside-vocabulary` | битая фикстура, `status: активно` вне словаря | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `unparseable` | битая фикстура, блочный скаляр в поле с потребителем | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `unknown-hook-event` | временный пакет с `OnFullMoon` | `tests/test_check_package.py::TestPackageCheck::test_unknown_hook_event_fails` |
| `unknown-hook-type` | тип вне закрытого списка | `tests/test_check_package.py::TestPackageCheck::test_unknown_hook_type_fails` |
| `unknown-matcher` | матчер вне закрытого множества, включая опечатку `Bahs` | `tests/test_check_package.py::TestPackageCheck::test_matcher_typo_is_caught` |
| `absolute-path` | одиннадцать форм абсолютного пути, включая Windows и UNC | `tests/test_check_package.py::TestPackageCheck::test_every_absolute_form_is_caught` |
| `relative-path-in-skill` | вызов `scripts/*` без `${CLAUDE_PLUGIN_ROOT}` | `tests/test_check_package.py::TestPackageCheck::test_relative_script_call_in_a_skill_fails` |
| `destructive-example` | пример `mv` в инструкциях ADOPT | `tests/test_check_package.py::TestPackageCheck::test_destructive_example_in_adopt_instructions_fails` |
| `gate-not-read-only` | хеш дерева фикстуры до и после прогона гейта | `tests/test_check_package.py::TestGateNotReadOnlyMechanism::test_mutating_gate_is_caught` |
| `tests-touched-product` | тот же приём вокруг прогона тестов | `tests/test_check_package.py::TestTestsTouchedProductMechanism::test_test_run_that_writes_to_scripts_is_caught` |
| `skill-without-description` | SKILL.md без описания | `tests/test_check_package.py::TestPackageCheck::test_skill_without_description_fails` |
| `skill-without-eval` | скилл без `eval.txt` | `tests/test_check_package.py::TestPackageCheck::test_skill_without_trigger_eval_fails` |
| `skill-name-mismatch` | имя не совпало с папкой | `tests/test_check_package.py::TestPackageCheck::test_skill_name_must_match_directory` |
```

- [ ] **Step 4: Прогнать — должно пройти**

Run: `./check`
Expected: все тесты PASS, проверка пакета молчит, код возврата 0

- [ ] **Step 5: Коммит**

```bash
git add docs/gate-coverage.md tests/test_gate_coverage.py
git commit -m "wave1: таблица покрытия ссылается на существующий тест, а не на имя"
```

---

### Task 21: Точный список сравнивает деталь находки (критерий 1)

Дыра: `places()` выбрасывает `detail`, поэтому находки с одинаковыми (путь,
строка, класс) взаимозаменяемы. Показательный случай — `dead-allow`: строка
аллоулиста без причины подпадает и под правило «нет причины», и под правило
«ничего не исключает». Удалить первое правило — набор не покраснеет, потому что
второе даст находку в том же месте того же класса. Различает их только текст.

**Files:**
- Modify: `tests/test_fixtures.py:60-63`, `tests/test_fixtures.py:81-117`

- [ ] **Step 1: Написать падающий тест**

Заменить `places()` и оба списка. Значения деталей — настоящие, снятые с гейта:

```python
def places(report):
    """Находки как (путь, строка, класс, деталь) в порядке отчёта.

    Деталь входит в ключ намеренно: без неё находки с одинаковыми путём,
    строкой и классом взаимозаменяемы, и подмена одного правила другим
    набор не роняет.
    """
    return [(f.path, f.line, f.cls, f.detail)
            for f in sorted(report.findings, key=Finding.key)]
```

```python
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
                ("areas/hiring/bare.md", 4, "ambiguous",
                 "[[dup]] → areas/hiring/dup.md, core/dup.md"),
                ("areas/hiring/escapes.md", 4, "escapes-root",
                 "[[../../../soseddniy-repo/file]]"),
                ("areas/hiring/md-link.md", 4, "md-link-to-file",
                 "[профиль](../../core/me.md)"),
                ("areas/hiring/note.md", 4, "unresolved", "[[несуществующая заметка]]"),
                ("areas/hiring/transient.md", 4, "link-to-transient", "[[tmp/plan]]"),
                ("sources/transcripts/items/2026-07-14-call.md", 1, "orphan",
                 "на файл никто не сослался"),
            ],
        )
```

```python
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
```

- [ ] **Step 2: Проверить, что дыра закрылась**

Тест обязан покраснеть на посаженной мутации, а не только пройти на целом
коде. Проверка — во временной копии, рабочее дерево не трогать:

```bash
python3 - <<'PY'
import re, shutil, subprocess, sys, tempfile
from pathlib import Path
root = Path(".").resolve()
with tempfile.TemporaryDirectory() as tmp:
    copy = Path(tmp) / "repo"
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    gate = copy / "scripts" / "check_links.py"
    text = gate.read_text(encoding="utf-8")
    mutated = text.replace("строка без причины: ", "правило ничего не исключает, удалите: ")
    assert mutated != text, "мутация не применилась — проверь строку в check_links.py"
    gate.write_text(mutated, encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "unittest",
                             "tests.test_fixtures", "-q"],
                            cwd=copy, capture_output=True, text=True)
    print("код возврата:", result.returncode)
    sys.exit(0 if result.returncode != 0 else 1)
PY
```

Expected: код возврата 1 у `unittest` (то есть набор покраснел), скрипт выходит
с 0. До правки `places()` набор оставался зелёным — это и была дыра.

- [ ] **Step 3: Прогнать на целом коде**

Run: `./check`
Expected: все тесты PASS, код возврата 0

- [ ] **Step 4: Коммит**

```bash
git add tests/test_fixtures.py
git commit -m "wave1: точный список сравнивает деталь, а не только место и класс"
```

---

### Task 22: Образец, отличающий резолв по пути от резолва по basename (критерий 1)

Дыра: подмена `ambiguous` на совпадение basename — прямо запрещённая спекой,
строка 1613, «ссылка реально резолвится в два и более кандидата, не сам факт
совпадения имён» — набор не роняет. Разводит эти два поведения образец, которого
в фикстуре нет: ссылка **с путём**, чей basename существует в другом месте.
Правило резолва спеки: есть `/` — только полный путь от корня, без отката
на basename.

**Files:**
- Create: `fixtures/broken/areas/hiring/pathlink.md`
- Modify: `tests/test_fixtures.py` (счётчик и список из Task 21, шапка-таблица)

- [ ] **Step 1: Положить образец**

```bash
cat > fixtures/broken/areas/hiring/pathlink.md <<'MD'
# Ссылка полным путём

Резолв по пути, без отката на basename: `projects/dup.md` не существует,
хотя `dup.md` есть в двух других местах.

Смотри [[projects/dup]].
MD
```

- [ ] **Step 2: Дописать падающий тест**

В `test_link_gate_finds_exactly_this` поднять `unresolved` с 4 до 5. В
`test_every_link_finding_sits_on_its_own_specimen` добавить строку — она
встаёт между `areas/hiring/note.md` и `areas/hiring/transient.md` по
сортировке ключа:

```python
                ("areas/hiring/pathlink.md", 6, "unresolved", "[[projects/dup]]"),
```

Дописать в таблицу образцов в докстринге файла:

```
| `unresolved` 5 | ...прежние четыре; `[[projects/dup]]` в `areas/hiring/pathlink.md` — путь не существует, откат на basename запрещён |
```

- [ ] **Step 3: Прогнать и сверить номер строки**

Run: `python3 -m unittest tests.test_fixtures -v`
Expected: FAIL с diff, показывающим настоящий номер строки находки. Если он
не 6 — поправить ожидание в тесте под фактическую строку файла, а не двигать
образец.

- [ ] **Step 4: Проверить, что дыра закрылась**

```bash
python3 - <<'PY'
import shutil, subprocess, sys, tempfile
from pathlib import Path
root = Path(".").resolve()
with tempfile.TemporaryDirectory() as tmp:
    copy = Path(tmp) / "repo"
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    result = subprocess.run([sys.executable, "-c",
        "import sys; sys.path.insert(0,'.');"
        "from scripts import check_links;"
        "print(check_links.scan('fixtures/broken').counts())"],
        cwd=copy, capture_output=True, text=True)
    print(result.stdout, result.stderr)
PY
```

Expected: `unresolved` равен 5. Резолв по basename дал бы 4 и лишний
`ambiguous` — то есть другой счёт, и тест бы покраснел.

- [ ] **Step 5: Прогнать целиком**

Run: `./check`
Expected: все тесты PASS, код возврата 0

- [ ] **Step 6: Коммит**

```bash
git add fixtures/broken/areas/hiring/pathlink.md tests/test_fixtures.py
git commit -m "wave1: образец разводит резолв по пути и откат на basename"
```

---

### Task 23: `--today` перестаёт быть молчаливой заглушкой (критерий 2)

Критерий 2 выполнен — отчёты побайтово детерминированы, — но с оговоркой:
`--today` разбирается и передаётся в `scan()`, где нигде не читается. Сегодня
это безвредно только потому, что в волне 1 нет правил, зависящих от даты.
Параметр, который принимают и молча игнорируют, — ровно то, что запрещает
незыблемое №4.

Механизм из спеки не снимается (это была бы эскалация автору). Вместо этого
он становится наблюдаемым, а настоящая гарантия детерминизма — часов в
`scripts/` нет — выражается исполняемой проверкой.

**Files:**
- Modify: `scripts/check_links.py:214`, `scripts/check_frontmatter.py:41`
- Test: `tests/test_fixtures.py`

- [ ] **Step 1: Написать падающий тест**

Дописать в `TestDeterminism`:

```python
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
```

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_fixtures -v`
Expected: `test_today_is_carried_on_the_report` FAIL — у `Report` нет
атрибута `today`

- [ ] **Step 3: Реализация**

В `scripts/findings.py` — `Report` принимает дату и держит её:

```python
class Report:
    def __init__(self, findings, today=None):
        self.findings = list(findings)
        # Дата прогона, если её передали. Правил, зависящих от даты, в волне 1
        # нет; параметр несётся явно, чтобы принятое значение было наблюдаемо,
        # а не проглочено молча (незыблемое №4).
        self.today = today
```

В `scripts/check_links.py`, конец `scan()` — заменить возврат отчёта на
`return Report(findings, today=today)`. То же в `scripts/check_frontmatter.py`.

- [ ] **Step 4: Прогнать — должно пройти**

Run: `./check`
Expected: все тесты PASS, проверка пакета молчит, код возврата 0

- [ ] **Step 5: Коммит**

```bash
git add scripts/findings.py scripts/check_links.py scripts/check_frontmatter.py tests/test_fixtures.py
git commit -m "wave1: --today наблюдаем, отсутствие часов в гейтах доказано тестом"
```

---

## Закрытие волны

Критерии выхода (`docs/roadmap.md`, «Волна 1») проверяются так:

| критерий | чем | закрыт задачей |
|---|---|---|
| точный список находок по классу, числу и **детали** | `tests/test_fixtures.py::TestExactFindings` | 21, 22 |
| побайтовая одинаковость независимо от места чекаута | `TestDeterminism::test_report_is_identical_from_another_checkout_location` | — |
| дата явным параметром, часов в гейтах нет | `TestDeterminism::test_no_module_in_scripts_reads_the_clock` | 23 |
| проверка пакета валит на закрытых списках, абсолютных путях, скиллах без описания и eval | `tests/test_check_package.py` | 17, 18, 19 |
| у каждого гейта проверка или записанная причина, и причина проверяема | `tests/test_gate_coverage.py` | 20 |
| зоны определены ровно один раз, включая копию файла | `tests/test_zones.py::TestSingleDefinition` | 16 |

Волна закрывается не зелёным `./check`, а зелёным `./check` **плюс** проверкой,
что посаженное нарушение его роняет. Шаги «проверить, что дыра закрылась» в
задачах 21 и 22 — образец такой проверки; повторить её для остальных задач
перед закрытием. Дальше — `superpowers:requesting-code-review`, затем
`superpowers:finishing-a-development-branch`, затем волны 2 и 3 (они
параллельны) по `docs/roadmap.md`.

**Что волна 1 отдаёт волнам 2 и 3:** `scripts/zones.py` — восемь зон, префиксы, права записи, `DENY_PATTERNS`; `scripts/findings.py` — имена классов, `EXIT_OK`, `EXIT_VIOLATION`, `EXIT_TOOL_FAILED`; `scripts/paths.py` — признак пути и `escapes_root`; CLI обоих гейтов: `python3 scripts/check_links.py <корень> [--today ГГГГ-ММ-ДД]`, код 2 при нарушении.
