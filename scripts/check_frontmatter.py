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
