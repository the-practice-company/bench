#!/usr/bin/env python3
"""`revert`: названные пути возвращаются в состояние `HEAD`.

Секция 18 предписывает выкладку из индекса. Проверено на живом git: после
переезда индекса со старым путём нет, команда падает на pathspec, а новый
путь выкладывается из индекса, то есть не меняется ничем. Механизм, на
котором держится безопасность процедуры, отката не даёт.

Здесь `revert` снимает названные пути из индекса, выкладывает из `HEAD` то,
что в `HEAD` есть, и удаляет то, чего в `HEAD` нет, а в дереве появилось.
Плана не требует: аварийный выход, заблокированный ровно тогда, когда он
нужен, бесполезен. Его ограничивают два других условия — пути внутри корня
и существующий `HEAD`.

**Чего подметание не удаляет.** Список берётся у `git ls-files --others
--exclude-standard`, а не обходом файловой системы. Обход снёс бы
необратимо две вещи: содержимое вложенного чужого репозитория (оно
исключено, а значит «не в HEAD») и всё игнорируемое `.gitignore`-ом. Коммит
«как было» делает `git add -A`, поэтому всё неигнорируемое отслежено, и
подметание берёт ровно то, что создал ход.

Список берётся **один раз на все пути**, а не по пути за раз. Иначе `revert`
зависит от порядка аргументов: подметённый `.gitignore` перестаёт скрывать
своё, и на следующем пути удаляется то, что минуту назад было защищено.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION, Finding, Report


def _restore(root, path):
    """Снять путь из индекса и выложить из `HEAD` то, что в `HEAD` есть."""
    tree.git(root, "reset", "-q", "HEAD", "--", path)
    if tree.git_zlines(root, "ls-tree", "-r", "--name-only", "-z",
                       "HEAD", "--", path):
        tree.git(root, "checkout", "HEAD", "--", path)


def _sweep(root, paths):
    """Удалить созданное ходом. Возвращает находки про то, что не удалено.

    Не обычный файл здесь ровно один наблюдённый: неисключённый вложенный
    репозиторий приезжает из `ls-files --others` каталогом — `vendor/`, одной
    записью. Удалить его как файл — упасть посреди отката; удалить
    рекурсивно — снести чужой репозиторий, чего не откатывает уже ничто.
    Поэтому он называется и остаётся.
    """
    findings = []
    for rel in tree.git_zlines(root, "ls-files", "--others",
                               "--exclude-standard", "-z", "--", *paths):
        target = root / rel
        if target.is_file() and not target.is_symlink():
            target.unlink()
            continue
        if target.is_dir() and (target / ".git").exists():
            findings.append(Finding("foreign-repo", rel.rstrip("/"), 1,
                                    "папка с `.git` внутри: подметанием не "
                                    "удаляется, осталась в дереве"))
            continue
        findings.append(Finding("foreign-repo", rel.rstrip("/"), 1,
                                "не обычный файл: подметанием не удаляется, "
                                "осталась в дереве"))
    return findings


def _emptied(root, paths):
    """Каталоги, из которых откат вынул последний файл.

    Git пустых каталогов не знает и вернуть их не может — это названный
    остаток, а не поломка. Отчёт называет их поимённо: замолчать здесь
    значило бы отдать автору дерево, отличающееся от исходного тем, о чём
    ему не сказали.
    """
    out = set()
    for path in paths:
        base = root / path
        if not base.is_dir():
            continue
        for entry in base.rglob("*"):
            if entry.is_dir() and not entry.is_symlink() and not any(entry.iterdir()):
                out.add(entry.relative_to(root).as_posix())
        if not any(base.iterdir()):
            out.add(Path(path).as_posix())
    return sorted(out)


def run(root, paths):
    root = Path(root)
    outside = [p for p in paths if not tree.inside(root, p)]
    if outside:
        return ("отказ: путь вне корня: %s\n" % ", ".join(sorted(outside)),
                EXIT_VIOLATION)
    if tree.head(root) is None:
        return "отказ: нет коммита, возвращать не к чему\n", EXIT_VIOLATION

    for path in paths:
        _restore(root, path)
    findings = _sweep(root, paths)

    lines = [line for line in (Report(findings).render(),) if line]
    lines.extend("опустевший каталог остался: %s" % name
                 for name in _emptied(root, paths))
    lines.append("возвращено в HEAD: %s" % ", ".join(sorted(paths)))
    return "\n".join(lines) + "\n", EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="return paths to HEAD")
    parser.add_argument("root")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)
    report, code = run(args.root, args.paths)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
