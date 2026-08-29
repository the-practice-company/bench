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

**Форм авторизации две, и обе — проверка, а не доверие вызывающему.**
Согласованная строка плана (ADOPT) и проверенный факт (MAINTAIN, волна 5).
Вторая заведена ради единственного удаления, которое MAINTAIN делает сам:
пустая коллекция за порогом. Содержимого в ней нет по определению, поэтому
удаление не пересекает линию ответственности, — но факт этот `drop`
устанавливает сам, а не принимает флагом.

Отсюда импорт из `scripts/maintain/`: список коллекций, список записей,
возраст из git и порог принадлежат слою спроса целиком, и копия любого из
них разошлась бы с оригиналом молча.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import plan as adopt_plan
from scripts.adopt import tree
from scripts.adopt.move import agreed_line
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from scripts.maintain import demand

# Имя единственного сегодняшнего факта. Строка — имя, а не разрешение:
# разрешает проверка, стоящая рядом с ней в таблице.
EMPTY_COLLECTION = "пустая коллекция за порогом"

# Закрытое множество причин. Открытое означало бы, что удалять можно по
# любому поводу, лишь бы он был назван словами.
AUTHORISED = {
    EMPTY_COLLECTION: demand.empty_past_threshold,
}


def _remove(root, source):
    """Общий хвост обеих форм: коммит, присутствие в нём, `git rm`.

    Хвост общий не для краткости: предусловие «путь лежит в `HEAD`» — это и
    есть обратимость удаления, и вторая его копия однажды отстала бы от
    первой, оставив одну из форм удалять безвозвратно.
    """
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


def run_authorised(root, source, reason, today):
    """Удаление, авторизованное проверенным фактом, а не строкой плана.

    Причина приезжает строкой, но строка — только имя факта: сам факт
    проверяется здесь заново. Приняв его флагом, `drop` удалял бы по слову
    вызывающего, и вся тяжесть решения переехала бы в вызывающего, где её
    никто не проверяет.

    `today` — данные хода, а не разрешение: дата обязательна у всего
    MAINTAIN, потому что взятая из системных часов она вернула бы в
    мутирующий режим ту самую зависимость, которую волна 1 выкорчёвывала
    дважды.
    """
    root = Path(root)
    verify = AUTHORISED.get(reason)
    if verify is None:
        return ("отказ: причина не из закрытого множества: %s\n"
                % reason), EXIT_VIOLATION
    # Граница — раньше факта. Снаружи корня факт считался бы по чужому
    # дереву, то есть плагин туда бы уже дотянулся (незыблемое №6).
    if not tree.inside(root, source):
        return "отказ: путь вне корня: %s\n" % source, EXIT_VIOLATION
    if not verify(root, source, today):
        return ("отказ: факт не подтвердился, «%s» про %s не сказано\n"
                % (reason, source)), EXIT_VIOLATION
    return _remove(root, source)


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
    return _remove(root, source)


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
