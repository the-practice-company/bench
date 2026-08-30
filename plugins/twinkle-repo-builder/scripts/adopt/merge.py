#!/usr/bin/env python3
"""`merge`: каркасная часть дописывается в чужой файл по строке плана.

`CLAUDE.md` и `.gitignore` в чужом дереве существуют до ADOPT, значит
подпадают под инвариант волны: изменить их без строки плана нельзя. Отсюда
зарезервированная цель `merge` — строка плана дешевле, чем исключение в
`check-plan`, и, в отличие от исключения, автор её видит и правит.

Байты дописывает `install_scaffold.merge`: копия каркаса в пакете одна, и
слияние обязано брать её же, иначе инстансы перестают быть одинаковыми. Здесь
— только согласие плана, граница корня, точка отката и состояние строки,
ровно тем же порядком, что у `move` и `drop`.

Закрытое множество сливаемого спрашивается **после** границы и **до**
состояния. После границы — потому что сосед вне корня в множество не входит
тоже, и отказ назвал бы автору не ту причину. До состояния — потому что
состояние читает файл, а каталог, попавший сюда строкой `merge`, читается
ошибкой, а не ответом.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import install_scaffold
from scripts.adopt import plan as adopt_plan
from scripts.adopt import tree
from scripts.adopt.move import agreed_line
from scripts.findings import EXIT_OK, EXIT_VIOLATION


def run(root, source, plan_path, scaffold=install_scaffold.SCAFFOLD):
    root = Path(root)
    # Цель не спрашивается у автора: `merge` исполняет ровно `merge`, и строка
    # ищется по источнику — как у `drop`.
    line, reason = agreed_line(root, source, None, plan_path, "merge")
    if line is None:
        return reason + "\n", EXIT_VIOLATION
    if not tree.inside(root, source):
        return "отказ: путь вне корня: %s\n" % source, EXIT_VIOLATION
    if source not in install_scaffold.MERGEABLE:
        return ("отказ: слиянию подлежат только %s\n"
                % ", ".join(install_scaffold.MERGEABLE)), EXIT_VIOLATION
    if adopt_plan.state(root, line) == "done":
        return "уже исполнено: `%s` -> `%s`\n" % (source, line.target), EXIT_OK
    # Тот же довод, что у `drop`: без коммита «как было» правка чужого файла
    # невозвратна, а ветка отказа от git сводит ADOPT к чтению. Молчаливое
    # «слито» здесь означало бы изменение, которое нечем отменить.
    if tree.head(root) is None:
        return "отказ: нет коммита, слияние было бы невозвратным\n", EXIT_VIOLATION
    install_scaffold.merge(root, source, scaffold)
    return "слито: `%s`\n" % source, EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="merge the scaffold into one agreed file")
    parser.add_argument("root")
    parser.add_argument("source")
    parser.add_argument("--plan", required=True,
                        help="план усыновления: без него мутация не идёт")
    parser.add_argument("--scaffold", default=str(install_scaffold.SCAFFOLD))
    args = parser.parse_args(argv)
    report, code = run(args.root, args.source, args.plan, args.scaffold)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
