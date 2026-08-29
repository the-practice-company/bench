#!/usr/bin/env python3
"""`init-tree`: дерево становится откатываемым, чужие репозитории — нетронутыми.

Коммит «как было» аддитивен: отменяется удалением каталога, который создал
сам ADOPT. Без него необратимо всё остальное, и именно на эту аддитивность
опирается секция 17, отправляя спорный случай в ADOPT.

Девятый скрипт волны, которого в таблице секции 18 нет. Заведён потому, что
неприкасаемость `foreign-repo` там объявлена держащейся «механизмом, а не
обещанием», а механизма не было ни одного: `git add -A` кладёт папку с `.git`
внутри в индекс gitlink'ом (`160000`) без записи в `.gitmodules`, коммит
«как было» несёт указатель на объект, которого в этом репозитории нет, клон
теряет содержимое целиком, а `revert` восстановить его не может по
построению. Отсюда исключение **до** коммита 0.

Ветка отказа (`--no-git`) — критерий 4: не создаётся ничего, не изменяется
ничего, отказ уезжает в шапку плана, а не в открытые нити (дописать в
существующий `OPEN-THREADS.md` было бы изменением файла).

Личность коммиттера не подставляется. Коммит «как было» — авторский, и
выдуманное имя в его истории осталось бы там навсегда; без личности git
отказывает, и отказ называется вслух (незыблемое №4).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import plan, tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION, Finding, Report

MARK = "# вложенные репозитории, исключены ADOPT"


def _write_exclude(root, nested):
    """Исключения пишутся блоком с маркером и переписываются целиком:
    дописывание давало бы дубли на каждом повторном запуске."""
    path = Path(root) / ".git" / "info" / "exclude"
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    skipping = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").split("\n"):
            if line.strip() == MARK:
                skipping = True
                continue
            if skipping and (not line.strip() or line.startswith("#")):
                skipping = False
            if not skipping:
                kept.append(line)
    block = ([MARK] + ["%s/" % name for name in nested]) if nested else []
    text = "\n".join([line for line in kept if line.strip()] + block)
    path.write_text(text + "\n" if text else "", encoding="utf-8")


def _rendered(findings, tail):
    """Отчёт находок и прозаический хвост, без пустых строк между ними."""
    parts = [part for part in (Report(findings).render(), tail) if part]
    return "\n".join(parts) + "\n"


def run(root, no_git=False):
    """(отчёт, код возврата). Ничего не печатает сам."""
    root = Path(root)
    if no_git:
        # Строка шапки называется дословно и берётся у `plan`: её ищет
        # повторный запуск, и разошедшиеся копии дали бы вечный переспрос
        # при на вид записанном отказе.
        return ("git не заведён по решению автора: дерево не тронуто, "
                "усыновление останавливается после плана; в шапку плана — "
                "«%s»\n" % plan.DECLINED), EXIT_OK

    nested = tree.nested_repositories(root)
    findings = [Finding("foreign-repo", name, 1,
                        "папка с `.git` внутри: не трогаем, вопрос о ней — "
                        "в открытые нити")
                for name in nested]

    if not (root / ".git").exists():
        init = tree.git(root, "init", "-q")
        if init.returncode != 0:
            return "git init не прошёл: %s\n" % init.stderr.strip(), EXIT_VIOLATION

    _write_exclude(root, nested)

    if tree.read_base(root) is not None:
        return _rendered(findings, "точка отката уже стоит, коммит «как было» "
                                   "не переделывается"), EXIT_OK

    tree.git(root, "add", "-A")
    commit = tree.git(root, "commit", "-q", "-m", "как было", "--allow-empty")
    sha = tree.head(root)
    # Отказ и «коммита нет» — одно условие, а не два подряд. Двумя они были,
    # и второе делало первое непроверяемым: мутация, снимавшая проверку кода
    # возврата, выживала, потому что её ловил следующий `if`. Причина берётся
    # у git целиком — «не сделан» без причины и есть тот молчащий отказ,
    # который здесь чинится (незыблемое №4).
    if commit.returncode != 0 or sha is None:
        return ("коммит «как было» не сделан: %s\n"
                % (commit.stderr.strip() or commit.stdout.strip()
                   or "HEAD не появился")), EXIT_VIOLATION
    tree.write_base(root, sha)

    return _rendered(findings, "точка отката: %s" % sha), EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="make the tree revertible")
    parser.add_argument("root")
    parser.add_argument("--no-git", action="store_true",
                        help="автор отказался заводить git: не трогать ничего")
    args = parser.parse_args(argv)
    report, code = run(args.root, no_git=args.no_git)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
