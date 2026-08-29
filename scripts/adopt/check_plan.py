#!/usr/bin/env python3
"""`check-plan`: вторая половина механизма инварианта волны.

`read-plan` предотвращает и верит вызывающему. Эта проверка сверяет, что
дерево не ушло с плана, — и ловит уход, кем бы он ни был сделан: скриптом,
скиллом или рукой автора.

Судятся только пути, **присутствовавшие** в коммите «как было». Создание под
инвариант не подпадает: оно обратимо удалением того, чего до ADOPT не было,
и без него нельзя написать даже план. Буквальное «всё, что изменилось с
коммита 0» сделало бы коммит каркаса — чисто аддитивный — сплошной находкой.

Отсюда и форма сравнения: множество путей коммита «как было» против списка
изменившихся. Она дословно повторяет формулировку инварианта, и разбирать
буквы статусов (`A`, `M`, `D`) ради того же ответа не нужно.

`--no-renames` держит здесь находку, а не аккуратность вывода. Проверено на
живом git: с определением переименования `--name-only` показывает **только**
новый путь, а его в коммите «как было» не было, — и правка, сделанная
переименованием мимо плана, ушла бы незамеченной. Без определения она
раскладывается на удаление и создание, и удалённая половина судится.

Файл, изменённый правкой ссылок, оправдан журналом `.git/adopt-touched`, а
не исключением в проверке.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import plan as adopt_plan
from scripts.adopt import tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION, Finding, Report


def _under(child, parent):
    return child == parent or child.startswith(parent + "/")


def run(root, plan_path):
    """(текст, код возврата). Ничего не печатает и ничего не меняет."""
    root = Path(root)
    base = tree.read_base(root)
    if base is None:
        return ("отказ: точки отката нет, сверять не с чем — "
                "запусти init-tree\n"), EXIT_VIOLATION

    lines, found = adopt_plan.load(root, plan_path)
    report = Report(found)
    if report.exit_code() != EXIT_OK:
        return report.render() + "\nплан не разобран, сверять не с чем\n", \
            EXIT_VIOLATION

    # Сам файл плана из-под суда выведен. Он лежит в коммите «как было» и
    # правится всю процедуру — ответы на вопросы дописываются в него, — так
    # что суд над инструментом согласия остановил бы усыновление на первом
    # же ответе. Ровно по этой причине `plan.coverage` вычитает его из дерева.
    plan_rel = adopt_plan._rel(root, plan_path)

    agreed = [line.source for line in lines
              if line.agreed and adopt_plan.action(line) is not None]
    justified = {rel for source, rel in tree.read_touched(root)
                 if any(_under(source, a) or _under(a, source) for a in agreed)}

    in_base = set(tree.git_zlines(root, "ls-tree", "-r", "--name-only",
                                  "-z", base))
    findings = []
    for rel in tree.git_zlines(root, "diff", "--no-renames", "--name-only",
                               "-z", base, "--", "."):
        if rel not in in_base:
            continue        # в коммите «как было» этого пути не было
        if rel == plan_rel:
            continue
        if any(_under(rel, source) for source in agreed):
            continue
        if rel in justified:
            continue
        findings.append(Finding("unagreed-change", rel, 1,
                                "путь изменился вне согласованной строки плана"))

    report = Report(findings)
    return report.render() + "\n", report.exit_code()


def main(argv=None):
    parser = argparse.ArgumentParser(description="did the tree leave the plan")
    parser.add_argument("root")
    parser.add_argument("plan")
    args = parser.parse_args(argv)
    text, code = run(args.root, args.plan)
    if text.strip():
        sys.stdout.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
