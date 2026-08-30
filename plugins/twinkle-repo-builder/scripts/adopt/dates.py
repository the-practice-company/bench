#!/usr/bin/env python3
"""`created` усыновляемых записей. Невосстановимое помечается, не выдумывается.

§18 велит оставлять поле пустым, когда истории нет. Здесь пишется токен
`unknown`, и это расхождение обосновано в спеке волны: `check_frontmatter`
считает `created: ""` таким же `missing-required`, как отсутствующее, и дерево
после усыновления несёт N ошибок гейта, неотличимых от авторской небрежности.
Гейт, красный по построению, перестают читать — ровно то, чем §13 обосновывает
аллоулист.

Незыблемое №4 даёт две равные ветки — пометить синтетическим либо отправить в
отчёт; §18 выбрал вторую, не зная про первый гейт. Токен берёт первую и
сохраняет то, что §18 защищал: подставленная дата от настоящей неотличима, а
`unknown` датой не является и не станет ей никогда. Отчёт при этом остаётся,
`unrecoverable` ниже.

Названная цена: вид, сортирующий по `created`, такие записи упорядочить не
может.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import tree
from scripts.findings import Finding

UNKNOWN = "unknown"


def history_before(root, base):
    """Ревизия, где видна история **до** усыновления, либо None, если её нет.

    Точка отката разрешается явно, а не по пустому выводу `git log`. `base^`
    у корневого коммита git не разрешает: код 128 при пустом stdout, и
    `unknown` получился бы верным ответом по неотличимой причине — так же
    выглядел бы сломанный репозиторий, в котором история есть.

    `base` нет — усыновление ещё ничего не коммитило, и вся история в `HEAD`
    авторская.
    """
    if base is None:
        return "HEAD"
    proc = tree.git(root, "rev-parse", "--verify", "-q", "%s^" % base)
    return proc.stdout.strip() if proc.returncode == 0 else None


def created(root, rel):
    """ISO-дата первого коммита, затронувшего путь, либо токен `unknown`.

    Считается **до** первого перемещения, по исходному пути. Считать после
    переезда с `--follow` отвергнуто: определение переименования эвристично
    и на одинаковом содержимом переключается.

    Дата авторская (`%ad`), а не коммиттерская: `filter-branch` и перебазовка
    переписывают вторую в дату прогона — ту самую, против которой написан
    модуль, — и оставляют первую нетронутой.

    Путь уезжает в git с магией `:(literal)`. Измерено: без неё `журнал-*.md`
    — шаблон, а не путь, и он подбирает соседа постарше. Ответ тогда
    настоящая дата, но от другого файла.
    """
    root = Path(root)
    if tree.head(root) is None:
        return UNKNOWN                  # ни git, ни коммитов — истории нет
    revision = history_before(root, tree.read_base(root))
    if revision is None:
        return UNKNOWN
    proc = tree.git(root, "log", "--date=short", "--format=%ad",
                    revision, "--", ":(literal)%s" % rel)
    lines = [line for line in proc.stdout.split("\n") if line]
    return lines[-1] if lines else UNKNOWN


def unrecoverable(root, rels):
    """`created-unrecoverable` поимённо: имя грепается, одно число — нет."""
    return [Finding("created-unrecoverable", rel, 1,
                    "дата создания невосстановима: истории до усыновления нет")
            for rel in sorted(rels) if created(root, rel) == UNKNOWN]
