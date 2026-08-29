#!/usr/bin/env python3
"""Единственное удаление, которое MAINTAIN делает сам.

Пустая коллекция не может содержать содержимого по определению, поэтому
удаление не пересекает линию ответственности. Порог включающий: `>= 30` дней,
и живёт он у слоя спроса — здесь его нет, чтобы второе определение не
разошлось с первым молча.

Порог нужен не показу, а **действию**: у показа цены ошибки нет, у удаления
есть. Поэтому §19 вправе назвать 30 дней, а §27 вправе отказать в пороге —
они говорят о разных вещах.

Обе даты приходят извне процесса. `--today` обязателен: у гейта отсутствие
даты меняет текст отчёта, здесь — удаляет папку. Умолчание из системных часов
вернуло бы в мутирующий режим ту самую зависимость, которую волна 1
выкорчёвывала дважды.

Само удаление — `drop` волны 4, второго скрипта не заводится: содержимое
остаётся в истории, и порог охраняет обратимый ход, а не невозвратный.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import drop
from scripts.findings import EXIT_OK
from scripts.maintain import demand

# Имя факта, а не его копия: литерал живёт в закрытом множестве `drop`, и
# переписанный здесь заново он отказывал бы в удалении молча и навсегда.
REASON = drop.EMPTY_COLLECTION


def _days_text(value):
    """Число дней либо токен вместо него. Токен печатается вместо числа, а
    не рядом с ним: поставленный рядом, он читался бы как измерение."""
    return "дней %d" % value if isinstance(value, int) else value


def run(root, today):
    """(удалённые пути, отчёт).

    Отчёт называет **обе** стороны порога: пустую коллекцию, оставленную на
    месте, и удалённую. Показ, молчащий про оставленную, не отличить от
    порога, который её не заметил.
    """
    root = Path(root)
    removed = []
    lines = ["# порог %d дней, today=%s" % (demand.THRESHOLD_DAYS, today)]
    for collection in demand.collections(root):
        if demand.records(root, collection):
            continue
        days = demand.age(root, collection, today)
        lines.append("коллекция %s: пуста, %s" % (collection, _days_text(days)))
        if not isinstance(days, int) or days < demand.THRESHOLD_DAYS:
            continue
        # Порог проверен дважды, и это не дублирование: здесь он решает, стоит
        # ли звать удаление, а внутри `drop` — авторизует его. Вторая проверка
        # не верит первой, в этом её смысл.
        report, code = drop.run_authorised(root, collection, REASON, today)
        if code == EXIT_OK:
            removed.append(collection)
            lines.append("удалена: %s, %s" % (collection, _days_text(days)))
        else:
            lines.append(report.strip())
    return sorted(removed), "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="remove empty collections past the threshold")
    parser.add_argument("root")
    parser.add_argument("--today", required=True,
                        help="обязателен: здесь дата удаляет папку, а не меняет текст")
    args = parser.parse_args(argv)
    _, report = run(args.root, args.today)
    sys.stdout.write(report)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
