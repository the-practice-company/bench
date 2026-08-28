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
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter

_FENCE = re.compile(r"```.*?```", re.S)
_INLINE = re.compile(r"`[^`\n]*`")
_WIKILINK = re.compile(r"!?\[\[([^\]\n]+)\]\]")
_MDLINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")

SCANNED_FOR_TOKENS = ("CLAUDE.md", "README.md", "SKILL.md")
RULES_PREFIX = ".claude/rules/"

ALLOWLIST_NAME = ".link-allow"

REGISTRY_ARCHETYPE = "реестр"


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
            fields = parse_frontmatter(readme.read_text(encoding="utf-8"))
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
    """Ссылка из долгоживущей зоны в исчезающую — отложенная поломка."""
    source_zone = zones.zone_of(source_rel)
    target_zone = zones.zone_of(target)
    if source_zone in zones.LONG_LIVED and target_zone in zones.TRANSIENT:
        return True
    return False


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


def _scanned_for_tokens(rel, name):
    """Периметр backtick-сканирования: четыре строки таблицы, и ни строкой больше."""
    return name in SCANNED_FOR_TOKENS or rel.startswith(RULES_PREFIX)


def _settings_paths(root, ignored, allowed):
    out = []
    for path in sorted(root.glob(".claude/settings*.json")):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.split("\n"), start=1):
            for token in re.findall(r'"([^"]+)"', line):
                if not pathlib_rules.is_path_token(token):
                    continue
                if pathlib_rules.escapes_root(token, base=""):
                    out.append(Finding("escapes-root", rel, lineno, token))
                elif not (root / token).exists() and not allowed(token):
                    out.append(Finding("unresolved", rel, lineno, token))
    return out


def scan(root, today=None):
    root = Path(root)
    ignored = _ignored(root)
    index = _index(root, ignored)
    findings = []
    referenced = set()

    allow_path = root / ALLOWLIST_NAME
    allow = parse_allowlist(allow_path.read_text(encoding="utf-8")) if allow_path.exists() else []

    def allowed(target):
        for entry in allow:
            if entry.pattern and entry.pattern in target:
                entry.used = True
                return True
        return False

    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        text = path.read_text(encoding="utf-8")
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

            if _transient_violation(rel, target):
                findings.append(Finding("link-to-transient", rel, link.line, link.raw))
                continue

            candidates = index.get(target, [])
            for candidate in candidates:
                referenced.add(candidate)          # относительный путь цели
            if len(candidates) > 1:
                findings.append(Finding("ambiguous", rel, link.line,
                                        "%s → %s" % (link.raw, ", ".join(sorted(candidates)))))
            elif not candidates and not allowed(target):
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
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        if not _scanned_for_tokens(rel, path.name):
            continue
        text = _blank_fences(path.read_text(encoding="utf-8"))
        for lineno, line in enumerate(text.split("\n"), start=1):
            for token in _INLINE.findall(line):
                token = token.strip("`").strip()
                if not pathlib_rules.is_path_token(token):
                    continue
                if pathlib_rules.escapes_root(token, base=""):
                    findings.append(Finding("escapes-root", rel, lineno, "`%s`" % token))
                    continue
                if not (root / token).exists() and not allowed(token):
                    findings.append(Finding("unresolved", rel, lineno, "`%s`" % token))

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
