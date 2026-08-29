"""Каркас рецепта: инвентарь, содержание артефактов, оба гейта.

Чистая фикстура секции 16 — это сам `scaffold/`, а не копия в `fixtures/`:
проверять надо тот объект, который уезжает пользователю. Красное здесь
означает дефект пакета, а не дефект инстанса.
"""

import json
import re
import unittest
from pathlib import Path

from scripts import paths, zones
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

_CYRILLIC = re.compile(r"[Ѐ-ӿ]")


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

    def test_every_zone_readme_is_english(self):
        """Секция 25: форму везёт плагин, значит форма английская.

        Проверка, а не намерение: этот репозиторий пишет по-русски всё, кроме
        каркаса, и соседний файл на расстоянии одной вкладки — русский. Без
        исполняемого признака правило держится только вниманием того, кто
        пишет следующий README (незыблемое №2).
        """
        offenders = []
        for zone in zones.ZONES:
            for lineno, line in enumerate(zone_readme(zone).split("\n"), start=1):
                if _CYRILLIC.search(line):
                    offenders.append((zone, lineno))
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


# Права записи в карте — единственное исключение из теста «какая проверка
# упадёт» (секция 9). Их держит PreToolUse, но агент обязан знать до попытки,
# иначе тратит ход на exit 2. Одно слово в колонке, не правило.
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

# Три раздела скелета секции 9 — весь его состав. «Указатели» из него удалены
# вместе с появлением path-scoped rules: раздел был суррогатом доставки,
# и возвращать его нельзя.
CLAUDE_SECTIONS = ("## Zone map", "## Placement rule",
                   "## What cannot be derived and cannot be linted")

MEMBERSHIP_TEST = ("Before writing one here, ask which check would fail if "
                   "someone broke it. If a gate or an artefact could hold it, "
                   "it goes there instead.")

LANGUAGE_LINE = ("This file is English by convention. The conversation and "
                 "the content of the repository are in the author's language.")

ZONE_ROW = re.compile(r"^\| (\w+)/ +\| ([^|]+?) +\| ([^|]+?) +\|$", re.M)


class TestGeneratedClaudeMd(unittest.TestCase):
    """Скелет секции 9: карта, правило размещения, домен не заполнен."""

    def setUp(self):
        self.text = (SCAFFOLD / "CLAUDE.md").read_text(encoding="utf-8")

    def test_the_zone_map_names_the_eight_zones_in_order(self):
        self.assertEqual([row[0] for row in ZONE_ROW.findall(self.text)],
                         list(zones.ZONES))

    def test_every_zone_row_carries_its_write_rule(self):
        self.assertEqual({row[0]: row[2] for row in ZONE_ROW.findall(self.text)},
                         WRITE_RULE)

    def test_the_placement_rule_asks_the_pipeline_question_first(self):
        """Секция 1: два вопроса задаются по порядку, статус перебивает тему.

        Утверждается точный список пар «номер — ось», а не наличие слов:
        перестановка двух строк местами меняет правило на обратное и обязана
        краснеть.
        """
        steps = re.findall(r"^(\d)\. .+ → an? (\w+) zone$", self.text, re.M)
        self.assertEqual(steps, [("1", "pipeline"), ("2", "semantic")])

    def test_it_lists_no_files(self):
        """Критерий 4 волны: карта зон и правило размещения — да, файлы — нет.

        Признак механический: токен с закрытым расширением. Перечисление
        файлов начинается именно с него, в backtick'ах или без — backtick
        в класс символов не входит, поэтому обе формы ловятся одним проходом.
        Список от руки гниёт, а на вопрос «что здесь лежит» лучше отвечает
        обход дерева.
        """
        offenders = [token for token in re.findall(r"[\w./-]+", self.text)
                     if token.endswith(paths.PATH_EXTENSIONS)]
        self.assertEqual(offenders, [])

    def test_the_domain_line_is_an_explicit_placeholder(self):
        """Незыблемое №4: невосстановимое помечается, а не подставляется молча.

        Домен в коммите 1 неизвестен, и строка об этом говорит вслух — сразу
        под заголовком, на месте описания домена из скелета. CREATE заменяет
        её ответом автора в коммите 2; в headless без брифа она остаётся,
        а вопрос уезжает в открытые нити.
        """
        lines = self.text.split("\n")
        self.assertEqual([i for i, line in enumerate(lines)
                          if line.startswith(DOMAIN_PLACEHOLDER)], [2])

    def test_it_says_which_language_it_is_in(self):
        """Секция 25: без этой строки агент в русскоязычном репозитории
        подстраивается под инструкции и начинает отвечать по-английски."""
        self.assertEqual(" ".join(self.text.split()).count(LANGUAGE_LINE), 1)

    def test_the_sections_are_these_three_and_pointers_is_gone(self):
        """Точный список разделов, а не отсутствие одного.

        «Указатели» ушли не потому, что раздел плох, а потому что доставку
        политики зоны взял на себя path-scoped rule. Утверждение о составе
        держит и это, и любой другой самовольно доросший раздел.
        """
        self.assertEqual(re.findall(r"^## .+$", self.text, re.M),
                         list(CLAUDE_SECTIONS))

    def test_it_asks_whether_a_gate_could_hold_the_rule(self):
        """Тест на добавление из секции 9 — единственное, что держит жанр.

        Без него раздел «чего нельзя вывести» собирает пересказ гейтов: файл
        превращается из пола в планку, и происходит это по одному правилу
        за раз, незаметно.
        """
        self.assertEqual(" ".join(self.text.split()).count(MEMBERSHIP_TEST), 1)

    def test_it_is_english(self):
        """Секция 25: форму везёт плагин, значит форма английская.

        Тот же исполняемый признак, что у README зон: этот репозиторий пишет
        по-русски всё, кроме каркаса, и без проверки правило держится только
        вниманием того, кто правит файл следующим (незыблемое №2).
        """
        self.assertEqual([lineno for lineno, line
                          in enumerate(self.text.split("\n"), start=1)
                          if _CYRILLIC.search(line)], [])


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
        self.assertEqual(actual,
                         {name: [glob] for name, glob in CROSS_CUTTING.items()})

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

    def test_every_clause_of_a_closing_names_a_mechanism(self):
        """`any` по всему закрытию — дыра, а не строгость.

        Закрытие перечисляет механизмы через `;`. Пока судится закрытие
        целиком, фраза из трёх частей проходит, назови она два выдуманных
        механизма и один настоящий: проверено на строке `frontmatter gate —
        real; vibes gate — invented.`, которую соседний тест признаёт
        законной. Закрытым список становится, только когда судится каждая
        часть.

        Чего эта проверка не ловит и не может поймать: **что именно**
        механизм делает. `link gate — the folder the filter names` из плана
        состояла из известного имени и неправды во всём остальном — ни один
        гейт не читает `.base`, а `check_frontmatter` на несуществующей
        папке молча делает `continue`. Такое ловится чтением кода гейта,
        им и было поймано.
        """
        wrong = []
        for path in rule_files():
            text = path.read_text(encoding="utf-8")
            index = text.rfind(HELD)
            if index < 0:
                continue
            for clause in text[index + len(HELD):].split(";"):
                if not clause.strip():
                    continue
                if not any(name in clause for name in KNOWN_MECHANISMS):
                    wrong.append((path.name, " ".join(clause.split())[:50]))
        self.assertEqual(wrong, [])

    def test_both_closing_forms_are_actually_used(self):
        """Форма «не гейтится» существует не на бумаге. Конвенция ровно одна.

        План называл конвенциями две — разбор inbox и жанр README, — но
        спека подтверждает только вторую: «Гейта под это нет… само
        перечисление это конвенция, и держит её path-scoped rule
        `readme.md`». Про inbox та же спека говорит обратное в таблице
        секции 15: «правка существующего в `inbox`, `decisions` —
        предупреждение», и `hooks/hook.py` печатает его той же веткой
        `ADD_ONLY`, а Stop-хук каждый ход печатает возраст старшего
        элемента. Назвать inbox негейтящимся значило бы противоречить
        двум файлам из тех же одиннадцати, где ровно то же предупреждение
        write hook названо гейтом (`core`, `areas`).

        Одного пользователя форме довольно: мёртвой она станет на нуле,
        а не на единице.
        """
        ungated = [p.name for p in rule_files()
                   if NOT_GATED in p.read_text(encoding="utf-8")]
        self.assertEqual(ungated, ["readme.md"])

    def test_no_rule_reproduces_a_collection_vocabulary(self):
        offenders = []
        for path in rule_files():
            words = set(re.findall(r"[a-z]+",
                                   path.read_text(encoding="utf-8").lower()))
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

    def test_every_rule_is_english(self):
        """Секция 25, третий раз тем же признаком.

        У README зон и у CLAUDE.md эта проверка есть, у одиннадцати правил
        её в плане не было — а они как раз тот артефакт, который пишется
        по одному файлу за раз и в котором сорваться на русский легче
        всего. Правило без исполняемой проверки не существует (незыблемое
        №2), и здесь это ровно тот случай.
        """
        offenders = []
        for path in rule_files():
            for lineno, line in enumerate(
                    path.read_text(encoding="utf-8").split("\n"), start=1):
                if _CYRILLIC.search(line):
                    offenders.append((path.name, lineno))
        self.assertEqual(offenders, [])


# Четыре мелких артефакта каркаса. Пути, а не имена: фрагмент настроек лежит
# под `.claude/`, и остальные три — в корне.
FRAGMENT = SCAFFOLD / ".claude" / "settings-fragment.json"
MARKER = SCAFFOLD / ".twinkle-repo-builder"
GITIGNORE = SCAFFOLD / ".gitignore"
OPEN_THREADS = SCAFFOLD / "OPEN-THREADS.md"

GITIGNORE_LINES = (
    ".obsidian/workspace*.json",
    ".trash/",
    ".DS_Store",
    "node_modules/",
    "__pycache__/",
)

# Словарь размера: любое из этих слов в `.gitignore` — обещание порога,
# которого до волны 5 нет ни в одном коде.
_SIZE_WORDS = re.compile(
    r"(?<![\w-])(?:size|threshold|limit|bytes?|megabytes?|[kmg]i?b)(?![\w-])",
    re.I)


class TestSettingsFragment(unittest.TestCase):
    def test_the_fragment_is_composed_from_the_single_definition(self):
        """Обёртки собираются из zones.DENY_PATTERNS, а не пишутся заново.

        Глубина глоба — отсуженное решение: `knowledge/**` был шире своей
        причины и блокировал CREATE, которому надо положить в зону README.
        Разошедшиеся копии такого решения молчаливы.

        Составленное ожидание сходится с составленным файлом и на пустоте:
        `READ_ONLY` не закреплён литералом нигде в наборе, и опустевший
        источник дал бы два пустых списка и зелёный тест на пустом запрете.
        Непустота утверждается отдельно — она и есть содержание правила.
        """
        excludes = ["**/%s/**" % zone for zone in sorted(zones.READ_ONLY)]
        deny = ["%s(./%s)" % (tool, pattern)
                for tool in ("Edit", "Write")
                for pattern in zones.DENY_PATTERNS]
        self.assertEqual([bool(excludes), bool(deny)], [True, True])
        fragment = json.loads(FRAGMENT.read_text(encoding="utf-8"))
        self.assertEqual(
            fragment,
            {
                "claudeMdExcludes": excludes,
                "permissions": {"deny": deny},
            },
        )

    def test_the_fragment_is_not_named_settings_json(self):
        """Копия поверх `settings.json` затёрла бы `enabledPlugins`, которым
        включён сам плагин: он выключил бы себя первым же действием."""
        self.assertFalse((SCAFFOLD / ".claude" / "settings.json").exists())


class TestRecipeMarker(unittest.TestCase):
    def test_the_marker_carries_the_version_and_nothing_else(self):
        """Секция 22: в конфиге только то, чего не вывести из дерева.
        Осталось одно поле, и это признак работающего правила."""
        manifest = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marker = json.loads(MARKER.read_text(encoding="utf-8"))
        self.assertEqual(marker, {"version": manifest["version"]})


class TestGitignore(unittest.TestCase):
    def test_it_carries_exactly_these_lines(self):
        lines = [line.strip() for line
                 in GITIGNORE.read_text(encoding="utf-8").split("\n")
                 if line.strip() and not line.strip().startswith("#")]
        self.assertEqual(lines, list(GITIGNORE_LINES))

    def test_it_states_no_size_threshold(self):
        """Порог в байтах здесь выразить нечем; механизм переезжает в MAINTAIN
        и до тех пор не притворяется существующим.

        Судится проза: строки шаблонов закреплены поимённо соседним тестом,
        и обещание может спрятаться только в комментарии. Признак — словарь
        размера целыми словами и без учёта регистра. План искал подстроки
        `MB` и `size`, то есть пропускал и `10 mb`, и `Size limit` с
        заглавной — тот же промах, что закрытое множество матчеров ловило
        в проверке пакета.
        """
        found = _SIZE_WORDS.findall(GITIGNORE.read_text(encoding="utf-8"))
        self.assertEqual(found, [])


class TestOpenThreads(unittest.TestCase):
    def test_it_ships_as_a_form_without_invented_content(self):
        """Пустой список — не выдуманное содержимое, а форма, как README зоны."""
        text = OPEN_THREADS.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Open threads"))
        bullets = [line for line in text.split("\n") if line.startswith("- ")]
        self.assertEqual(bullets, [])

    def test_it_lives_in_the_root_and_not_in_a_zone(self):
        """Это состояние работы над доменом, а не содержимое домена; `tmp`
        вдобавок исчезающая зона, и ссылка на неё — класс находки."""
        strays = sorted(p.relative_to(SCAFFOLD).as_posix()
                        for p in SCAFFOLD.rglob("OPEN-THREADS.md"))
        self.assertEqual(strays, ["OPEN-THREADS.md"])


# Четыре артефакта этой задачи, путями от корня каркаса.
SMALL_ARTEFACTS = (".gitignore", ".twinkle-repo-builder", "OPEN-THREADS.md",
                   ".claude/settings-fragment.json")


class TestSmallArtefactsAreEnglish(unittest.TestCase):
    def test_none_of_them_carries_russian(self):
        """Секция 25, четвёртый раз тем же признаком.

        У README зон, у CLAUDE.md и у одиннадцати правил проверка языка
        есть, у четырёх мелких артефактов в плане её не было. Прозу везут
        двое из них — комментарии `.gitignore` и текст `OPEN-THREADS.md`, —
        и это ровно те файлы, которые правятся между делом. Остальные два
        стоят здесь потому, что список артефактов задачи должен быть один,
        а не «те, в которых проза сегодня есть».
        """
        offenders = []
        for name in SMALL_ARTEFACTS:
            text = (SCAFFOLD / name).read_text(encoding="utf-8")
            for lineno, line in enumerate(text.split("\n"), start=1):
                if _CYRILLIC.search(line):
                    offenders.append((name, lineno))
        self.assertEqual(offenders, [])
