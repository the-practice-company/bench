#!/usr/bin/env python3
"""`read-plan`: единственный источник списка «что исполнять».

Печатает только строки согласованные, без `?`, в состоянии «не исполнено».
Не исполняет ничего сам: это половина механизма, держащего инвариант волны,
и она предотвращает, но верит вызывающему. Вторая половина — `check-plan`,
которая ловит уход с плана, кем бы он ни был сделан.

План с находками не исполняется вовсе: строки не печатаются, печатается
отчёт, код возврата — 2.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import plan as adopt_plan
from scripts.findings import EXIT_OK, EXIT_VIOLATION, Report


def render(root, path):
    """(текст, код возврата). Ни то ни другое не печатается здесь."""
    lines, found = adopt_plan.load(root, path)
    report = Report(found)
    if report.exit_code() != EXIT_OK:
        return report.render(), EXIT_VIOLATION
    out = []
    for line in lines:
        what = adopt_plan.action(line)
        if what is None or not line.agreed:
            continue
        if adopt_plan.state(root, line) != "pending":
            continue
        out.append("\t".join([line.stage or "-", what, line.source, line.target]))
    return "\n".join(out) + ("\n" if out else ""), EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="what the plan agrees to execute")
    parser.add_argument("root")
    parser.add_argument("plan")
    args = parser.parse_args(argv)
    text, code = render(args.root, args.plan)
    if text:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
