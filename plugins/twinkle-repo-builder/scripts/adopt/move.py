#!/usr/bin/env python3
"""`move`: перенос по согласованной строке плана. Ссылки не трогает.

Третий слой инварианта волны. `read-plan` предотвращает и верит
вызывающему; `check-plan` ловит постфактум; здесь мутация просто
отказывается случиться по строке, которой в плане нет. План — обязательный
аргумент, и дверь мимо инварианта закрыта разбором аргументов, а не
дисциплиной вызывающего.

Ссылки — работа `rewrite-refs`, и слипшись с переносом, цепочка потеряла бы
повторную входимость: оборвавшись между ними, она доводится следующим
запуском, потому что состояние строки считается из дерева.

Перенос идёт **через git**, а не средствами файловой системы. Мутация мимо
индекса прошла бы молча и оказалась бы невозвратной: `revert` выкладывает из
`HEAD` и подметает по `ls-files --others`, а переехавшего мимо git нет ни
там, ни там.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import plan as adopt_plan
from scripts.adopt import tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION, Report


def agreed_line(root, source, target, plan_path, expected_action):
    """Строка плана, разрешающая эту операцию, либо причина отказа.

    Возвращает `(строка, причина)`; ровно одно из двух — не None.

    Ожидаемое действие подставляется в текст отказа, а не зашито словом
    «перенос»: ту же функцию зовёт `drop`, и отчёт, обвиняющий автора в
    несогласованном переезде там, где речь про удаление, говорит о
    происходящем неправду.

    `target=None` — цель берётся из плана, а не сверяется с ней. Так зовёт
    `drop`: цели он не принимает, она подразумевается одна. Сверка по паре
    отвечала бы «такой строки в плане нет» на строку, которая в плане есть
    и исполняется переносом, — то есть прятала бы от автора настоящую
    причину отказа за той, которой нет. Двух строк с одним источником сюда
    не доезжает: их называет находкой `overlapping-line`.
    """
    lines, found = adopt_plan.load(root, plan_path)
    report = Report(found)
    if report.exit_code() != EXIT_OK:
        return None, report.render() + "\nплан не разобран, мутация не идёт"
    for line in lines:
        if line.source != source:
            continue
        if target is not None and line.target != target:
            continue
        if not line.agreed:
            return None, ("строка не согласована: `%s` -> `%s`"
                          % (line.source, line.target))
        if adopt_plan.is_question(line.target):
            return None, "цель несёт знак вопроса: `%s`" % line.target
        what = adopt_plan.action(line)
        if what is None:
            return None, ("строка не исполняется ничем: `%s` -> `%s`"
                          % (line.source, line.target))
        if what != expected_action:
            return None, ("строка исполняется не как `%s`, а как `%s`: `%s` -> `%s`"
                          % (expected_action, what, line.source, line.target))
        return line, None
    if target is None:
        return None, "такой строки в плане нет: `%s`" % source
    return None, "такой строки в плане нет: `%s` -> `%s`" % (source, target)


def _mkdirs(path):
    """Создать каталог с предками. Возвращает созданное, самым глубоким вперёд.

    Список нужен ради отката: каталог под целью создаётся **до** `git mv`,
    иначе переносить некуда, — а оставшись после отказа, он становится
    `uncovered-path` в следующем же `read-plan`, то есть план объявляется
    неполным за то, чего автор не делал.
    """
    missing = []
    while not path.exists():
        missing.append(path)
        path = path.parent
    for created in reversed(missing):
        created.mkdir()
    return missing


def run(root, source, target, plan_path):
    root = Path(root)
    line, reason = agreed_line(root, source, target, plan_path, "move")
    if line is None:
        return reason + "\n", EXIT_VIOLATION
    for path in (source, target):
        if not tree.inside(root, path):
            return "отказ: путь вне корня: %s\n" % path, EXIT_VIOLATION

    # Состояние спрашивается ради одного ответа — «уже исполнено»: повторный
    # вход в цепочку краснеть не обязан. Столкновение и потеря сюда не
    # доходят вовсе, их называет находкой `plan.load`; вторая копия той
    # проверки была бы веткой, которую нечем покраснеть (незыблемое №3).
    if adopt_plan.state(root, line) == "done":
        return "уже исполнено: `%s` -> `%s`\n" % (source, target), EXIT_OK

    made = _mkdirs((root / target).parent)
    moved = tree.git(root, "mv", source, target)
    if moved.returncode != 0:
        for created in made:
            if not any(created.iterdir()):
                created.rmdir()
        return ("отказ: перенос не прошёл: %s\n"
                % (moved.stderr.strip() or moved.stdout.strip()
                   or "git промолчал")), EXIT_VIOLATION
    return "перенесено: `%s` -> `%s`\n" % (source, target), EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="move one agreed path")
    parser.add_argument("root")
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--plan", required=True,
                        help="план усыновления: без него мутация не идёт")
    args = parser.parse_args(argv)
    report, code = run(args.root, args.source, args.target, args.plan)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
