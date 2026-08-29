#!/usr/bin/env python3
"""Единственная точка логики хуков.

Одна таблица зон, один разбор stdin, одна точка отказа. У изученного аналога
три разошедшиеся таблицы зон и две копии парсера JSON, одна из которых не
исполняется никогда, потому что установлен `jq`.

Коды: 2 — нарушение, 0 — всё остальное, включая «не смог», у которого всегда
есть видимая строка причины (секция 15 спеки).
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooks import boundary
from scripts import zones
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


# Имена полей `tool_input` для Write/Edit/NotebookEdit документация не
# называет. Список кандидатов закрытый и проверяемый: не совпало ни одно —
# хук говорит об этом вслух и не решает. Угадывать молча запрещено
# (незыблемое №4), блокировать по неразобранному вводу — тоже: это блок по
# собственной слепоте, а не по нарушению.
_PATH_FIELDS = ("file_path", "path", "notebook_path", "filePath")


def tool_path(payload):
    """Путь, по которому инструмент собирается писать, или None.

    Не документировано не только имя поля, но и форма самого `tool_input`,
    поэтому не-отображение здесь не обвал, а тот же ответ «не нашёл»:
    сообщать про вход должна строка про вход, а не трассировка про строку
    этого файла.
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    for field in _PATH_FIELDS:
        value = tool_input.get(field)
        if isinstance(value, str) and value:
            return value
    return None


def _base_of(payload):
    """Каталог, в котором работает агент: `cwd` события, запасной — окружение.

    Рабочий каталог самого процесса хука не документирован, поэтому
    `os.getcwd()` здесь не зовётся никогда — ни прямо, ни через нормализацию
    относительного пути. У изученного аналога восемь скиллов звали скрипт
    относительным путём, рабочим каталогом оказался репозиторий пользователя,
    и вся заявленная функциональность молча не работала.
    """
    return payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")


def _absolute(target, base):
    """Путь инструмента, приведённый к абсолютному от `cwd` события.

    Относительный путь осмыслен только относительно каталога агента. Отдать
    его нормализации как есть — вернуть рабочий каталог процесса через чёрный
    ход: законная запись объявлялась бы выходом за границу, а выход за границу
    получал бы отказ с неверной причиной.

    Тильда раскрывается раньше склейки, и это не украшение. Склеенная
    с корнем, она читается как каталог с именем в один символ внутри
    репозитория, то есть путь внутри границы, — а инструмент, раскрывающий
    тильду, пишет в домашний каталог. Дыра в незыблемом №6 ценой одного
    символа, и притом молчаливая.
    """
    target = os.path.expanduser(target)
    return target if os.path.isabs(target) else os.path.join(base, target)


def on_pre_tool_use(payload):
    """Запись инструментом: блок за границей и на правке источника, иначе — слово.

    Три исхода различаются не строгостью, а тем, чью территорию затрагивают:
    граница репозитория и неизменяемость источника — поломки, и на них код 2;
    переписывание долгоживущей записи — содержимое, а содержимое принадлежит
    автору (линия ответственности), поэтому предупреждение и код 0.
    """
    base = _base_of(payload)
    root = boundary.find_root(base) if base else None
    if root is None:
        print("гейт не выполнился: корень репозитория не найден "
              "(маркер %s не найден вверх от %s)" % (boundary.MARKER, base),
              file=sys.stderr)
        return EXIT_OK

    target = tool_path(payload)
    if target is None:
        received = payload.get("tool_input")
        # В строке — то, что пришло на самом деле: список кандидатов закрыт,
        # и пополняют его по увиденному полю, а не по догадке.
        print("гейт не выполнился: путь не разобран в tool_input, получено %r"
              % (sorted(received) if isinstance(received, dict) else received,),
              file=sys.stderr)
        return EXIT_OK

    target = _absolute(target, base)
    if boundary.outside(target, root):
        print("граница рабочего каталога: %s лежит вне корня %s. Плагин "
              "не пишет наружу никогда" % (target, root), file=sys.stderr)
        return EXIT_VIOLATION

    zone = zones.zone_of(os.path.relpath(os.path.realpath(target), str(root)))
    exists = Path(target).exists()
    if zone is None or zone in zones.READ_ONLY or not exists:
        # Три разные причины молчать, и ни одна из них не «на всякий случай».
        # Вне зон живут файлы, о которых таблица секции 15 не говорит ничего,
        # а правила без выраженной проверки у нас не существует. Чужой
        # git-сабмодуль закрыт раньше и статически, через `permissions.deny`
        # целевого репозитория: динамика поверх статики — второй источник
        # истины, который с первым разойдётся. Новый файл не переписывает
        # ничего и потому законен во всех восьми зонах.
        return EXIT_OK

    if zone == "sources":
        # Не конвенция, а поломка, и потому реакция та же, что у поломки:
        # поправленный задним числом источник делает недоказуемым каждый
        # вывод, который на него ссылается (секция 7).
        print("зона sources неизменяема: правка существующего задним числом "
              "делает недоказуемым каждый вывод, который на него ссылается. "
              "Добавить новый файл можно, переписать существующий — нет",
              file=sys.stderr)
        return EXIT_VIOLATION

    if zone in zones.ADD_ONLY:
        print("зона %s только для добавления: правка существующей записи — "
              "предупреждение, у автора может быть причина" % zone,
              file=sys.stderr)
    elif zone in zones.LONG_LIVED:
        print("зона %s — долгоживущий слой: переписывание существующего "
              "отравит всё, что на нём стоит. Решает автор" % zone,
              file=sys.stderr)
    return EXIT_OK


# Обработчики регистрируются задачами волны. Пустая таблица — не заглушка:
# каждое незарегистрированное событие называет себя вслух строкой выше.
HANDLERS = {
    "PreToolUse": on_pre_tool_use,
}


if __name__ == "__main__":
    sys.exit(main())
