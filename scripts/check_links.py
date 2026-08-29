#!/usr/bin/env python3
"""Гейт ссылок.

Классы: unresolved, md-link-to-file, link-to-transient, escapes-root,
dead-allow, ambiguous, orphan. Секция 13 спеки.
"""

import argparse
import re
import sys
import unicodedata
from fnmatch import fnmatchcase
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import paths as pathlib_rules
from scripts import zones
from scripts.findings import Finding, Report
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter

_FENCE = re.compile(r"```.*?```", re.S)
# Ограничитель inline-кода — прогон из N backtick'ов, закрывает его такой же
# прогон: ``двойным`` оборачивают текст, в котором backtick и встречается.
# Форма «backtick, не-backtick, backtick» знала только N=1, и на ``пути``
# расходились оба прохода: backtick-цикл видел две пустые вставки и терял
# токен целиком, а wikilink-цикл переставал считать содержимое кодом
# и читал пример как живую ссылку.
_INLINE = re.compile(r"(?<!`)(`+)([^\n]*?)\1(?!`)")
_WIKILINK = re.compile(r"!?\[\[([^\]\n]+)\]\]")
_MDLINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")
# Ссылка-сноска: `[метка]: цель "заголовок"`. Даёт ту же цель, что инлайновая
# форма, но `](` в ней нет, поэтому мимо `_MDLINK` проходили сразу два класса,
# `escapes-root` и `md-link-to-file`. Определение занимает строку целиком:
# в цели нет пробелов, после неё допустим только заголовок в кавычках. Иначе
# ссылкой считалась бы проза вида `[1]: см. ниже, в разделе про зоны`.
# `[^метка]:` — примечание Obsidian, а не ссылка: его текст цели не называет
# вовсе, и однословное примечание иначе становилось бы `md-link-to-file`.
_MDREF = re.compile(
    r"^ {0,3}\[(?!\^)([^\]\n]+)\]:[ \t]*(<[^>\n]*>|\S+)"
    r"(?:[ \t]+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^)\n]*\)))?[ \t]*$")

SCANNED_FOR_TOKENS = ("CLAUDE.md", "README.md", "SKILL.md")
RULES_PREFIX = ".claude/rules/"

ALLOWLIST_NAME = ".link-allow"

# Закрытый словарь архетипов спеки английский: journal / pipeline / registry
# (секции 9 и 28). Пока здесь стояло русское слово, периметр сирот у любой
# коллекции, созданной рецептом, был пуст — класс `orphan` на живом выводе
# не мог сработать ни разу.
REGISTRY_ARCHETYPE = "registry"


def _read(path):
    """Текст файла; недекодируемый байт заменяется, а не уносит файл из гейта.

    Тот же фикс и по той же причине, что в `check_package._iter_package_files`
    («один недекодируемый байт уводил файл из-под гейта целиком»): 16
    unresolved замера приехали из Notion-экспорта, и случайный байт в одном
    из таких файлов — не экзотика. Здесь было хуже тихого пропуска: чтение
    роняло весь прогон, автор не получал отчёта вовсе, а код возврата
    оказывался 1 — контракт `findings.py` такого кода не знает (2 или 0).
    """
    return path.read_text(encoding="utf-8", errors="replace")


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


class Link:
    __slots__ = ("target", "line", "raw", "kind")

    def __init__(self, target, line, raw, kind):
        self.target = target
        self.line = line
        self.raw = raw
        self.kind = kind


def _blank_fences(text):
    """Вырезает только ```-блоки, сохраняя переводы строк и inline-код внутри строк.

    Отдельно от _blank_code: backtick-сканирование ниже само читает inline-код
    (это его источник токенов), ему нужно только не видеть fenced-примеры.
    """
    def keep_newlines(match):
        return re.sub(r"[^\n]", " ", match.group(0))
    return _FENCE.sub(keep_newlines, text)


def _blank_code(text):
    """Вырезает код, сохраняя переводы строк, чтобы номера не поехали."""
    def keep_newlines(match):
        return re.sub(r"[^\n]", " ", match.group(0))
    return _INLINE.sub(keep_newlines, _blank_fences(text))


def extract_links(text):
    clean = _blank_code(text)
    out = []
    for lineno, line in enumerate(clean.split("\n"), start=1):
        for match in _WIKILINK.finditer(line):
            target = match.group(1).split("|")[0].split("#")[0].split("^")[0].strip()
            out.append(Link(target, lineno, match.group(0), "wikilink"))
        for match in _MDLINK.finditer(line):
            out.append(Link(match.group(1).strip(), lineno, match.group(0), "mdlink"))
        # Определение ссылки-сноски судится как markdown-ссылка: цель у них
        # одна и та же, а `[метка]` в тексте — только указатель на эту строку.
        # В отчёт идёт строка целиком: `[out]` без цели автору ничего не
        # говорит, чинить нужно именно здесь.
        match = _MDREF.match(line)
        if match:
            target = match.group(2).strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1].strip()
            out.append(Link(target, lineno, line.strip(), "mdlink"))
    return out


def _index(root, ignored):
    """basename без расширения -> список относительных путей.

    Для файла в корне репозитория basename и относительный путь без
    расширения — одна и та же строка (`README` == `README`): нельзя
    регистрировать её дважды под одним ключом, иначе один файл выглядит
    как два кандидата и bare-ссылка на него ложно помечается ambiguous.

    Тот же периметр (`_ignored`/`_in_perimeter`), что у обоих главных
    циклов: иначе файл из архива или .gitignore-поддерева становится
    резолвящейся целью, хотя гейт его нигде больше не читает.
    """
    index = {}
    for path in root.rglob("*.md"):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        stem = unicodedata.normalize("NFC", path.stem)
        rel_stem = unicodedata.normalize("NFC", rel[:-3])
        for key in {stem, rel_stem}:
            bucket = index.setdefault(key, [])
            if rel not in bucket:
                bucket.append(rel)
    return index


def _orphan_perimeter(root, ignored):
    """Пути, где отсутствие входящей ссылки означает что-то определённое.

    Тот же периметр, что у главных циклов: без него поддерево, которое
    гейт нигде не читает ради ссылок (архив, .gitignore), всё равно
    проверяется на сирот — и оказывается сиротским по построению, потому
    что связывающие его ссылки никто не сканирует.
    """
    perimeter = set()
    for path in root.rglob("*.md"):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        if zones.zone_of(rel) == "sources" and "/items/" in rel:
            perimeter.add(rel)
    for readme in root.rglob("README.md"):
        rel_readme = readme.relative_to(root).as_posix()
        if not _in_perimeter(rel_readme, ignored):
            continue
        try:
            fields = parse_frontmatter(_read(readme))
        except FrontmatterError:
            continue
        if fields.get("archetype") != REGISTRY_ARCHETYPE:
            continue
        items = readme.parent / "items"
        for path in items.rglob("*.md") if items.exists() else []:
            rel_item = path.relative_to(root).as_posix()
            if not _in_perimeter(rel_item, ignored):
                continue
            perimeter.add(rel_item)
    return perimeter


def classify_mdlink(target):
    """None, если markdown-ссылка допустима; иначе класс находки."""
    target = target.strip()
    if pathlib_rules.is_url(target) or target.startswith("#"):
        return None
    return "md-link-to-file"


def _transient_violation(source_rel, target):
    """Ссылка из долгоживущей зоны в исчезающую — отложенная поломка.

    `target` — путь цели, а не текст ссылки: у `[[scratch]]` зоны в тексте
    нет вовсе. Вызывается после резолва, по каждому кандидату.
    """
    source_zone = zones.zone_of(source_rel)
    target_zone = zones.zone_of(target)
    if source_zone in zones.LONG_LIVED and target_zone in zones.TRANSIENT:
        return True
    return False


class Ignored(tuple):
    """Префиксы `.gitignore` плюс его же отрицания (`!`).

    Кортеж, потому что `str.startswith` принимает именно кортеж, и оба гейта
    на этом стоят: `check_package` импортирует отсюда и `_ignored`,
    и `_in_perimeter`. Отрицания едут рядом, а не вторым возвращаемым
    значением, — иначе их пришлось бы протаскивать через чужую сигнатуру
    и периметры двух гейтов снова разошлись бы.
    """

    negated = ()

    def __new__(cls, prefixes, negated=()):
        self = super().__new__(cls, tuple(sorted(prefixes)))
        self.negated = tuple(negated)
        return self


def _ignored(root):
    """Префиксы, в которые гейт не заходит: .gitignore плюс archive/.

    `!`-строка возвращает путь в дерево, и периметр обязан её применять:
    выброшенная, она делала игнорируемое множество строго шире того, что
    репозиторий игнорирует на самом деле, — ровно наоборот тому, что здесь
    написано. Одно отличие от git осознанное: git отказывается возвращать
    файл из исключённого каталога, здесь отрицание сильнее каталога.
    Сдвиг в сторону «прочитать лишний файл»: лишнее гейт назовёт вслух,
    а непрочитанное молчит.
    """
    prefixes = {".git/", "archive/"}
    negated = []
    ignore = root / ".gitignore"
    if ignore.exists():
        for line in _read(ignore).split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("!"):
                negated.append(line[1:].lstrip("/"))
            else:
                prefixes.add(line.rstrip("/") + "/")
    return Ignored(prefixes, negated)


def _in_perimeter(rel, ignored):
    """Читает ли гейт этот путь. Отрицание `.gitignore` сильнее префикса.

    `getattr`, а не атрибут напрямую: сюда приходит и голый кортеж —
    из `check_package`, и из мутации «периметр снова слеп к .gitignore».
    """
    for pattern in getattr(ignored, "negated", ()):
        if fnmatchcase(rel, pattern) or rel.startswith(pattern.rstrip("/") + "/"):
            return True
    return not rel.startswith(tuple(ignored))


def _scanned_for_tokens(rel, name):
    """Периметр backtick-сканирования: четыре строки таблицы, и ни строкой больше."""
    return name in SCANNED_FOR_TOKENS or rel.startswith(RULES_PREFIX)


def _exists_exactly(root, token):
    """Есть ли такой путь — с точностью до регистра и формы Unicode.

    `(root / token).exists()` спрашивает файловую систему, а она на macOS
    отвечает «да» на `Scripts/Check_Links.py`, на Linux — «нет»: один
    репозиторий давал два разных вердикта. Резолв wikilink регистр при этом
    различал всегда (поиск по словарю), то есть две половины одного гейта
    расходились между собой. Критерий 2 — про отчёт, не зависящий от места
    клона; платформа — тот же довод одной ступенью выше.

    Сравнение посегментное, по именам из каталога. NFC с обеих сторон:
    macOS отдаёт имена в NFD, текст файла почти всегда в NFC, и без
    приведения та же строка разъезжается на ровном месте.
    """
    rel = pathlib_rules.normalise(token).rstrip("/")
    if not rel or rel == ".":
        return True
    current = root
    for part in rel.split("/"):
        part = unicodedata.normalize("NFC", part)
        try:
            names = {unicodedata.normalize("NFC", child.name)
                     for child in current.iterdir()}
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return True


def _classify_token(token, root, allowed):
    """Судьба токена-пути: класс находки или None. Единственное определение.

    Сюда ходят оба места, где гейт судит токен, — backtick-цикл и
    `.claude/settings*.json`. Второй копии этой лестницы в пакете быть
    не должно: три разошедшиеся копии одной таблицы уже стоили этому
    репозиторию критерия выхода (`tests/test_zones.py::TestSingleDefinition`),
    а здесь разойтись особенно легко — обе копии выглядят одинаково
    безобидно и обе решают, выпустить ли ссылку за корень.

    Порядок ступеней и есть правило (секция 13):

    1. Выход за корень судится первым и не зависит от того, шаблон перед
       нами или конкретный путь. Глоб по чужому домашнему каталогу —
       находка `escapes-root` ровно так же, как конкретный файл в нём:
       шаблон снимает вопрос «есть ли такой файл», но не даёт права выйти
       из репозитория. Образец лежит в битой фикстуре, а не здесь: строка
       с таким токеном в самом пакете — находка `absolute-path`
       (проверка пакета поймала её на первом же прогоне).
    2. Шаблон дальше не проверяется. `**/knowledge/**` называет множество,
       и спрашивать о существовании множества — ошибка категории. Без этой
       ступени каркас, предписанный секциями 4 и 9, не проходил гейт,
       предписанный секцией 13, — блокер, на который упёрлась волна 3.
    3. Конкретный путь проверяется как прежде — но существование спрашивается
       у дерева, а не у файловой системы (`_exists_exactly`): иначе вердикт
       зависел от регистрочувствительности тома. Ослабления нет:
       `areas/hiring/items/` метасимволов не содержит и остаётся находкой.
    """
    if pathlib_rules.escapes_root(token, base=""):
        return "escapes-root"
    if pathlib_rules.is_pattern(token):
        return None
    if not _exists_exactly(root, token) and not allowed(token):
        return "unresolved"
    return None


def _settings_paths(root, ignored, allowed):
    """Токены `.claude/settings*.json`, с разворачиванием правил разрешений.

    В отчёт идёт токен как он записан в файле, а судится развёрнутый:
    иначе `Edit(X)` и `Write(X)` на одной строке дают две неразличимые
    находки, и автор не понимает, какое из двух правил чинить.
    """
    out = []
    for path in sorted(root.glob(".claude/settings*.json")):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        text = _read(path)
        for lineno, line in enumerate(text.split("\n"), start=1):
            for raw in re.findall(r'"([^"]+)"', line):
                token = pathlib_rules.unwrap_tool(raw)
                if not pathlib_rules.is_path_token(token):
                    continue
                cls = _classify_token(token, root, allowed)
                if cls:
                    out.append(Finding(cls, rel, lineno, raw))
    return out


def scan(root, today=None):
    root = Path(root)
    ignored = _ignored(root)
    index = _index(root, ignored)
    findings = []
    referenced = set()

    allow_path = root / ALLOWLIST_NAME
    allow = parse_allowlist(_read(allow_path)) if allow_path.exists() else []

    def allowed(target):
        """Гасит ли аллоулист эту цель.

        Совпадение — с целью целиком, глоб-метасимволы работают
        (`черновики/*`). Голая подстрока запрещена: запись `a` гасила
        `unresolved` по всему репозиторию и при этом считалась
        использованной, поэтому `dead-allow` о ней молчал — исключение
        ослабляло гейт везде, выглядя живым. Весь аргумент спеки за
        `dead-allow` в том, что уцелевшее исключение тихо ослабляет
        проверку; подстрочное совпадение делало это ослабление ещё
        и ненаблюдаемым. «Строка на паттерн» читается как шаблон,
        а не как обрывок пути.
        """
        target = unicodedata.normalize("NFC", target)
        for entry in allow:
            if entry.pattern and fnmatchcase(
                    target, unicodedata.normalize("NFC", entry.pattern)):
                entry.used = True
                return True
        return False

    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        text = _read(path)
        for link in extract_links(text):
            target = unicodedata.normalize("NFC", link.target)

            if pathlib_rules.escapes_root(target, base=rel):
                findings.append(Finding("escapes-root", rel, link.line, link.raw))
                continue

            if link.kind == "mdlink":
                cls = classify_mdlink(target)
                if cls:
                    findings.append(Finding(cls, rel, link.line, link.raw))
                continue

            candidates = index.get(target, [])
            for candidate in candidates:
                referenced.add(candidate)          # относительный путь цели

            # `link-to-transient` — про цель ссылки, а не про её текст.
            # `[[scratch]]`, единственная форма, которую пишет Obsidian, зоны
            # в тексте не несёт вовсе, и проверка до резолва молчала ровно
            # там, где класс и нужен. Текст остаётся вторым источником для
            # случая, когда зону он называет, а файла нет: `[[tmp/ghost]]` —
            # по-прежнему отложенная поломка, а не ссылка в никуда.
            transient = [c for c in candidates if _transient_violation(rel, c)]
            if not candidates and _transient_violation(rel, target):
                transient = [target]
            if transient:
                detail = link.raw
                if candidates:
                    detail = "%s → %s" % (link.raw, ", ".join(sorted(transient)))
                findings.append(Finding("link-to-transient", rel, link.line, detail))

            # Неоднозначность и исчезающая цель — два разных факта об одной
            # ссылке, и чинятся они по-разному: первая — полным путём, вторая
            # — отказом ссылаться в `tmp/`. Поэтому сообщаются оба. Погасить
            # ошибку предупреждением нельзя: `ambiguous` гейт не роняет,
            # и ссылка, которая по построению протухнет, ушла бы зелёной.
            if len(candidates) > 1:
                findings.append(Finding("ambiguous", rel, link.line,
                                        "%s → %s" % (link.raw, ", ".join(sorted(candidates)))))
            elif not candidates and not transient and not allowed(target):
                findings.append(Finding("unresolved", rel, link.line, link.raw))

    # Backtick-токены: пути и команды вперемешку, признак — is_path_token.
    # Периметр — ровно четыре строки таблицы «Что проверяется»: CLAUDE.md,
    # README.md, SKILL.md и .claude/rules/*.md. Ни одного класса за него
    # не выносится, включая escapes-root: расширение сканирования ради
    # ожидаемого счёта — нарушение спеки (DEC-0003), образец переезжает
    # в периметр, а не периметр к образцу. Wikilink и markdown-ссылка
    # разбираются выше, в любом .md, — это первые две строки той же таблицы.
    # Fenced-блоки вырезаются тем же способом, что и в extract_links: пример
    # внутри ``` — документация, а не живой токен (секция 13, «Перед разбором
    # вырезаются блоки кода и inline-код»); inline backtick-код здесь не
    # вырезается — это и есть источник токенов этого прохода.
    # Судьбу отобранного токена решает _classify_token — то же самое место,
    # что и для settings*.json: правило про глоб и границу корня одно на оба
    # цикла, второй копии быть не должно.
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        if not _scanned_for_tokens(rel, path.name):
            continue
        text = _blank_fences(_read(path))
        for lineno, line in enumerate(text.split("\n"), start=1):
            for match in _INLINE.finditer(line):
                token = match.group(2).strip()
                if not pathlib_rules.is_path_token(token):
                    continue
                cls = _classify_token(token, root, allowed)
                if cls:
                    findings.append(Finding(cls, rel, lineno, "`%s`" % token))

    findings.extend(_settings_paths(root, ignored, allowed))

    # Мёртвые записи аллоулиста оцениваются последними: только к этому
    # моменту все места, поднимающие unresolved (wikilink-цикл, backtick-
    # цикл, settings.json), уже прогнали через него свои цели и пометили
    # использованные записи — иначе запись, разрешающая находку из более
    # позднего прохода, выглядит неиспользованной и гейт противоречит сам
    # себе: одновременно unresolved и «удалите правило, которое это гасит».
    for entry in allow:
        if entry.reason is None:
            findings.append(Finding("dead-allow", ALLOWLIST_NAME, entry.line,
                                    "строка без причины: %s" % entry.pattern))
        elif not entry.used:
            findings.append(Finding("dead-allow", ALLOWLIST_NAME, entry.line,
                                    "правило ничего не исключает, удалите: %s" % entry.pattern))

    for rel in sorted(_orphan_perimeter(root, ignored)):
        if rel not in referenced:
            findings.append(Finding("orphan", rel, 1, "на файл никто не сослался"))

    return Report(findings, today=today)


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
