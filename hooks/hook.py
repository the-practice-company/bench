#!/usr/bin/env python3
"""Единственная точка логики хуков.

Одна таблица зон, один разбор stdin, одна точка отказа. У изученного аналога
три разошедшиеся таблицы зон и две копии парсера JSON, одна из которых не
исполняется никогда, потому что установлен `jq`.

Коды: 2 — нарушение, 0 — всё остальное, включая «не смог», у которого всегда
есть видимая строка причины (секция 15 спеки).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.findings import EXIT_OK, EXIT_VIOLATION


def read_event(stream):
    """Событие и полезная нагрузка из stdin. Битый JSON — не нарушение."""
    raw = stream.read()
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as error:
        raise ValueError("вход не разобран: %s" % error)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    event = argv[0] if argv else ""
    try:
        payload = read_event(sys.stdin)
    except ValueError as error:
        print("гейт не выполнился: %s" % error, file=sys.stderr)
        return EXIT_OK

    handler = HANDLERS.get(event)
    if handler is None:
        # Событие, которого диспетчер не знает, — не разрешение и не запрет,
        # а неспособность проверить. Молча вернуть 0 нельзя (незыблемое №4):
        # опечатка в hooks.json выглядела бы работающим хуком.
        print("гейт не выполнился: событие %s не обслуживается" % event,
              file=sys.stderr)
        return EXIT_OK
    return handler(payload)


# Обработчики регистрируются задачами волны. Пустая таблица — не заглушка:
# каждое незарегистрированное событие называет себя вслух строкой выше.
HANDLERS = {}


if __name__ == "__main__":
    sys.exit(main())
