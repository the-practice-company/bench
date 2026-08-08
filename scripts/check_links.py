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


def _settings_paths(root, ignored):
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
                elif not (root / token).exists():
                    out.append(Finding("unresolved", rel, lineno, token))
    return out


def scan(root, today=None):
    root = Path(root)
    index = _index(root)
    findings = []
    ignored = _ignored(root)

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
            if not candidates:
                findings.append(Finding("unresolved", rel, link.line, link.raw))

    # Backtick-токены: пути и команды вперемешку, признак — is_path_token.
    # escapes-root проверяется в любом md-файле периметра — абсолютный или
    # выходящий за корень путь опасен независимо от того, где он упомянут.
    # unresolved (существование) проверяется только в файлах, на которые
    # реально ходят агент и хуки (SCANNED_FOR_TOKENS, .claude/rules/*.md) —
    # иначе гейт тонет в упоминаниях команд и путей в вольной прозе.
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        is_rule = rel.startswith(".claude/rules/")
        canonical = path.name in SCANNED_FOR_TOKENS or is_rule
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.split("\n"), start=1):
            for token in _INLINE.findall(line):
                token = token.strip("`").strip()
                if not pathlib_rules.is_path_token(token):
                    continue
                if pathlib_rules.escapes_root(token, base=""):
                    findings.append(Finding("escapes-root", rel, lineno, "`%s`" % token))
                    continue
                if canonical and not (root / token).exists():
                    findings.append(Finding("unresolved", rel, lineno, "`%s`" % token))

    findings.extend(_settings_paths(root, ignored))

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
