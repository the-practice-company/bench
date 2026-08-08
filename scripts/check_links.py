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
