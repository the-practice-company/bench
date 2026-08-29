#!/usr/bin/env python3
"""`drop`: содержимое остаётся в истории, папки в дереве не остаётся.

Седьмой скрипт сверх шести из §18: `move` умеет только переносить, `revert`
только откатывать, а убрать папку, оставив её в истории, нечем. Альтернативы
отвергнуты: расселять архив по зонам противоречит §1 (он уезжает целиком),
оставить папку прямо запрещено §1 и §18.

Этой командой мирятся §13 и §18. Исключение `archive/` из периметра гейта
**не трогается**: инвентарь архив видит, план обязан нести о нём строку,
цель строки — `git-history`. Пока папка есть, гейт её не читает; после
согласованной строки папки нет, и бессрочным исключение быть перестаёт, не
будучи снятым.

Предусловие: путь присутствует в `HEAD`. Удалить нескоммиченное значило бы
удалить безвозвратно — то самое, против чего заведён коммит «как было».
Флага `-f` у `git rm` здесь нет по той же причине: путь с несохранёнными
правками git не удаляет, и уговаривать его незачем.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import plan as adopt_plan
from scripts.adopt import tree
from scripts.adopt.move import agreed_line
from scripts.findings import EXIT_OK, EXIT_VIOLATION


def run(root, source, plan_path):
    root = Path(root)
    # Цель не спрашивается у автора: `drop` исполняет ровно `git-history`,
    # и строка ищется по источнику. Ожидаемое действие сверяет `agreed_line`.
    line, reason = agreed_line(root, source, None, plan_path, "drop")
    if line is None:
        return reason + "\n", EXIT_VIOLATION
    # Граница — раньше состояния. Состояние удаления читает существование
    # источника, и путь вне корня, которого там нет, оно назовёт исполненным:
    # отказ по незыблемому №6 уехал бы в бодрое «уже исполнено».
    if not tree.inside(root, source):
        return "отказ: путь вне корня: %s\n" % source, EXIT_VIOLATION
    if adopt_plan.state(root, line) == "done":
        return "уже исполнено: `%s` -> `%s`\n" % (source, line.target), EXIT_OK
    if tree.head(root) is None:
        return "отказ: нет коммита, удалять безвозвратно нельзя\n", EXIT_VIOLATION
    if not tree.git_zlines(root, "ls-tree", "-r", "--name-only", "-z",
                           "HEAD", "--", source):
        return ("отказ: пути нет в коммите, удаление было бы безвозвратным: %s\n"
                % source), EXIT_VIOLATION
    removed = tree.git(root, "rm", "-r", "-q", "--", source)
    if removed.returncode != 0:
        return ("отказ: удаление не прошло: %s\n"
                % (removed.stderr.strip() or removed.stdout.strip()
                   or "git промолчал")), EXIT_VIOLATION
    return "убрано из дерева, осталось в истории: %s\n" % source, EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="drop a path into git history")
    parser.add_argument("root")
    parser.add_argument("source")
    parser.add_argument("--plan", required=True,
                        help="план усыновления: без него мутация не идёт")
    args = parser.parse_args(argv)
    report, code = run(args.root, args.source, args.plan)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
