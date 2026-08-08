# Волна 1: гейты и проверка пакета — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать два гейта (ссылки и frontmatter), проверку пакета и общий слой определений, на которых стоят волны 2 и 3, — так, чтобы каждая находка была доказана фикстурой с точным списком.

**Architecture:** Пакет плагина Claude Code. Ядро — четыре библиотечных модуля (`zones`, `frontmatter`, `paths`, `findings`), поверх них три исполняемых скрипта-гейта, каждый со своим CLI и кодом возврата. Никакого движка: всё статический разбор текста. Определения зон, имена классов находок, `permissions.deny` и коды возврата живут ровно в одном месте — волны 2 и 3 их импортируют и не копируют.

**Tech Stack:** Python 3 stdlib (`unittest`, `pathlib`, `re`, `unicodedata`, `argparse`, `json`), git, POSIX shell. Ноль внешних зависимостей — это незыблемое №5.

**Спека:** `docs/superpowers/specs/2026-08-08-context-repo-plugin-design.md`, секции 1, 2, 13, 14, 16 и «Общее для гейтов».
**Конституция:** `docs/baton/constitution.md`, критерии выхода волны 1.

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
| `check` | `verify_cmd` конституции: тесты + проверка пакета одной командой |
| `fixtures/broken/` | битая фикстура: все классы обоих гейтов сразу |
| `fixtures/green/` | зелёный образец: гейты обязаны молчать |
| `tests/test_*.py` | утверждают точный список находок, не «что-то нашлось» |

Границы намеренные: `zones` ничего не импортирует и потому не может зациклиться с гейтами; `findings` не знает про файловую систему; гейты не знают друг о друге. Волна 2 (хуки) импортирует `zones`, `paths`, `findings` и зовёт гейты как подпроцессы — то есть её отказ не может изменить их поведение.

---

### Task 1: Скелет пакета и `./check`

Ходячий скелет: `verify_cmd` из конституции обязан работать с первого коммита, иначе гейт baton нечем проверить.

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `check`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `scripts/__init__.py`

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_smoke -v`
Expected: FAIL — `FileNotFoundError: .claude-plugin/plugin.json`

- [ ] **Step 3: Минимальная реализация**

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

- [ ] **Step 4: Сделать исполняемым и прогнать**

Run: `chmod +x check && python3 -m unittest tests.test_smoke -v`
Expected: PASS (1 test)

`./check` на этом шаге ещё падает: `check_package.py` не существует. Так и задумано — Task 14 его закрывает. До тех пор `verify_cmd` красный, и это честно.

- [ ] **Step 5: Коммит**

```bash
git add .claude-plugin/plugin.json check scripts/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "wave1: манифест пакета и точка входа verify_cmd"
```

---

### Task 2: Модуль зон — единственное определение

**Files:**
- Create: `scripts/zones.py`
- Create: `tests/test_zones.py`

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_zones -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.zones'`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_zones -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Коммит**

```bash
git add scripts/zones.py tests/test_zones.py
git commit -m "wave1: модуль зон, единственное определение с тестом на копии"
```

---

### Task 3: Классы находок и детерминированный отчёт

**Files:**
- Create: `scripts/findings.py`
- Create: `tests/test_findings.py`

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_findings -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.findings'`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_findings -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Коммит**

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

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_frontmatter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.frontmatter'`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_frontmatter -v`
Expected: PASS (12 tests)

Если `test_empty_value_is_none_not_empty_string` или `test_block_list` падают — дело в финальной нормализации пустых списков: список, в который что-то положили, пустым не остаётся, а ключ без продолжения обязан стать `None`. Правь только этот блок.

- [ ] **Step 5: Коммит**

```bash
git add scripts/frontmatter.py tests/test_frontmatter.py
git commit -m "wave1: парсер frontmatter из stdlib, громкий отказ вместо угадывания"
```

---

### Task 5: Пути — признак и граница корня

**Files:**
- Create: `scripts/paths.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_paths -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.paths'`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_paths -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Коммит**

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

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_basefile -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.basefile'`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_basefile -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Коммит**

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

- [ ] **Step 1: Собрать битую фикстуру**

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

- [ ] **Step 2: Собрать зелёный образец**

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

- [ ] **Step 3: Проверить, что дерево на месте**

Run: `find fixtures -type f | sort | wc -l`
Expected: `22`

- [ ] **Step 4: Коммит**

```bash
git add fixtures
git commit -m "wave1: битая фикстура на все классы и зелёный образец"
```

---

### Task 8: Гейт ссылок — извлечение и `unresolved`

**Files:**
- Create: `scripts/check_links.py`
- Create: `tests/test_check_links.py`

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.check_links'`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Коммит**

```bash
git add scripts/check_links.py tests/test_check_links.py
git commit -m "wave1: гейт ссылок, извлечение и класс unresolved"
```

---

### Task 9: Гейт ссылок — `md-link-to-file`, `link-to-transient`, `escapes-root`

**Files:**
- Modify: `scripts/check_links.py`
- Modify: `tests/test_check_links.py`

- [ ] **Step 1: Дописать падающие тесты**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_links.TestForbiddenShapes -v`
Expected: FAIL — `AssertionError: None != 1`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Дописать периметр и `settings*.json`**

Спека называет два места, которых в коде выше нет.

**Периметр задаёт `.gitignore`**, плюс отдельно исключается `archive/`, если он
есть в принимаемом репозитории: все 16 битых ссылок в замере сидели там, это
Notion-экспорт с percent-encoding, и без исключения первый прогон ADOPT даёт
стену шума. Добавить в `scripts/check_links.py`:

```python
def _ignored(root):
    """Префиксы, в которые гейт не заходит: .gitignore плюс archive/."""
    prefixes = {".git/", "archive/", ".baton/"}
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

- [ ] **Step 5: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: PASS (12 tests)

- [ ] **Step 6: Коммит**

```bash
git add scripts/check_links.py tests/test_check_links.py
git commit -m "wave1: md-link-to-file, link-to-transient, escapes-root, периметр и settings.json"
```

---

### Task 10: Гейт ссылок — `ambiguous`, аллоулист и `dead-allow`

**Files:**
- Modify: `scripts/check_links.py`
- Modify: `tests/test_check_links.py`

- [ ] **Step 1: Дописать падающие тесты**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_links.TestAllowlist -v`
Expected: FAIL — `ImportError: cannot import name 'parse_allowlist'`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Коммит**

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

- [ ] **Step 1: Дописать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_links.TestOrphan -v`
Expected: FAIL — `AssertionError: None != 1`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_links -v`
Expected: PASS (17 tests)

- [ ] **Step 5: Коммит**

```bash
git add scripts/check_links.py tests/test_check_links.py
git commit -m "wave1: orphan по объявлению, а не обобщением"
```

---

### Task 12: Гейт frontmatter

**Files:**
- Create: `scripts/check_frontmatter.py`
- Create: `tests/test_check_frontmatter.py`

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_frontmatter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.check_frontmatter'`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_frontmatter -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Коммит**

```bash
git add scripts/check_frontmatter.py tests/test_check_frontmatter.py
git commit -m "wave1: гейт frontmatter, контракт из видов"
```

---

### Task 13: Точный список находок и детерминизм отчёта

Критерий выхода волны: не «гейт что-то нашёл», а какие именно находки и сколько; плюс побайтовая одинаковость отчёта независимо от места чекаута.

**Files:**
- Create: `tests/test_fixtures.py`

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и увидеть настоящие числа**

Run: `python3 -m unittest tests.test_fixtures -v`
Expected: FAIL с расхождением счётчиков.

**Здесь есть развилка, и она важна.** Расхождение значит одно из двух: гейт ловит не то, или фикстура содержит не то, что задумано. Разбираться обязательно по существу — открыть фикстуру и убедиться глазами, какие находки в ней действительно должны быть. **Подгонять числа под то, что выдал гейт, запрещено**: тогда тест перестаёт быть проверкой и становится снимком поведения, включая ошибочного.

- [ ] **Step 3: Починить настоящую причину**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_fixtures -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Коммит**

```bash
git add tests/test_fixtures.py
git commit -m "wave1: точный список находок и детерминизм отчёта"
```

---

### Task 14: Проверка пакета

**Files:**
- Create: `scripts/check_package.py`
- Create: `tests/test_check_package.py`

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_check_package -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.check_package'`

- [ ] **Step 3: Реализация**

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

- [ ] **Step 4: Прогнать — должно пройти**

Run: `python3 -m unittest tests.test_check_package -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Коммит**

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

- [ ] **Step 1: Написать падающий тест**

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

- [ ] **Step 2: Прогнать и убедиться, что падает**

Run: `python3 -m unittest tests.test_gate_coverage -v`
Expected: FAIL — `FileNotFoundError: docs/gate-coverage.md`

- [ ] **Step 3: Написать таблицу покрытия**

`docs/gate-coverage.md`:

```markdown
# Покрытие классов находок

Правило секции 16: у каждого гейта либо исполняемая проверка на фикстуре,
либо обязательное поле с объяснением, почему её нет. Пустым оставить нельзя.
Таблицу держит `tests/test_gate_coverage.py`.

| класс | чем доказан |
|---|---|
| `unresolved` | битая фикстура, 3 находки, `tests/test_fixtures.py` |
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

- [ ] **Step 4: Прогнать всё разом**

Run: `./check`
Expected: все тесты PASS, проверка пакета молчит, код возврата 0

- [ ] **Step 5: Коммит**

```bash
git add docs/gate-coverage.md tests/test_gate_coverage.py
git commit -m "wave1: покрытие классов доказано таблицей с исполняемой проверкой"
```

---

## Закрытие волны

Критерии выхода из конституции проверяются так:

| критерий | чем |
|---|---|
| точный список находок по классу и числу | `tests/test_fixtures.py::TestExactFindings` |
| побайтовая одинаковость независимо от места чекаута | `TestDeterminism::test_report_is_identical_from_another_checkout_location` |
| дата явным параметром | флаг `--today` у обоих гейтов |
| проверка пакета валит на закрытых списках, абсолютных путях, скиллах без описания и eval | `tests/test_check_package.py` |
| у каждого гейта проверка или записанная причина | `tests/test_gate_coverage.py` |
| зоны определены ровно один раз | `tests/test_zones.py::TestSingleDefinition` |

После зелёного `./check` — обновить `docs/baton/state.md` через `baton-write`: волна 1 в `done`, `closed_at_sha` из `git rev-parse HEAD`, волны 2 и 3 в `todo` и разблокированы.

**Что волна 1 отдаёт волнам 2 и 3** (контракт из конституции): `scripts/zones.py` — восемь зон, префиксы, права записи, `DENY_PATTERNS`; `scripts/findings.py` — имена классов, `EXIT_OK`, `EXIT_VIOLATION`, `EXIT_TOOL_FAILED`; `scripts/paths.py` — признак пути и `escapes_root`; CLI обоих гейтов: `python3 scripts/check_links.py <корень> [--today ГГГГ-ММ-ДД]`, код 2 при нарушении.
