#!/usr/bin/env python3
"""Единственная точка логики хуков.

Одна таблица зон, один разбор stdin, одна точка отказа. У изученного аналога
три разошедшиеся таблицы зон и две копии парсера JSON, одна из которых не
исполняется никогда, потому что установлен `jq`.

Наружу — коды рукопожатия, а не 0 и 2: их переводит шим (см. ниже). Секция 15
спеки требует, чтобы 2 означал нарушение и только его, а «не смог» всегда имел
видимую строку причины.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooks import bashscan, boundary, summary, turnfiles
from scripts import check_frontmatter, check_links, zones
from scripts.findings import EXIT_OK, EXIT_VIOLATION

# Коды рукопожатия с шимом. Их единственная работа — доказать, что hook.py
# действительно отработал: наружу они не выходят, шим переводит первый в 0,
# второй в 2, а всё остальное — в «не смог» с видимой строкой.
#
# Пока шим пропускал 0 и 2 как есть, доказательства не было ни у одного из
# двух исходов. `python3` в дикой природе бывает обёрткой venv или pyenv, и
# её собственная двойка приезжала в Claude Code блокировкой записи без единой
# строки причины — ровно та поломка, ради которой шим и заведён. С другой
# стороны, ноль возвращает и любая посторонняя команда, оказавшаяся на месте
# python, — скажем, echo: гейт молча разрешал всё.
#
# Числа выбраны так, чтобы их не вернул никто другой: 0, 1 и 2 у python свои,
# 120 — его же сбой сброса буферов, 64–78 заняты `sysexits.h`, 126 и 127
# печатает оболочка, 128+N — сигналы.
EXIT_CHECKED_OK = 91
EXIT_CHECKED_VIOLATION = 92

_HANDSHAKE = {EXIT_OK: EXIT_CHECKED_OK, EXIT_VIOLATION: EXIT_CHECKED_VIOLATION}

# Поля нагрузки, которые читаются как строки. Проверяются здесь, а не по месту
# чтения: `cwd` числом доезжает до `Path()` и роняет хук `TypeError`'ом про
# аргумент конструктора — то есть в транскрипт уходит трассировка про строку
# этого файла вместо строки про то, что случилось со входом.
_STRING_FIELDS = ("cwd", "session_id")


def read_event(stream):
    """Полезная нагрузка из stdin. Непонятный вход — не нарушение.

    Ловится не только `JSONDecodeError`: разобранный JSON бывает массивом,
    строкой и `null`, и каждый из них раньше давал `AttributeError` на первом
    же `.get`. Обработан был тот случай, который придумали, а не тот, который
    приезжает.
    """
    raw = stream.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as error:
        raise ValueError("вход не разобран: %s" % error)
    if not isinstance(payload, dict):
        raise ValueError("вход не объект, а %s" % type(payload).__name__)
    for field in _STRING_FIELDS:
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError("поле %s пришло как %s, а ожидается строка"
                             % (field, type(value).__name__))
    return payload


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


def _root_of(payload):
    """Корень репозитория или None, с напечатанной причиной.

    Причина одна на все события, и разъезжаться ей нельзя: её текст
    утверждается тестами трёх веток дословно, а три копии одного сообщения
    однажды разойдутся. Молча выйти отсюда не имеет права ни одна ветка
    (незыблемое №4).
    """
    base = _base_of(payload)
    root = boundary.find_root(base) if base else None
    if root is None:
        print("гейт не выполнился: корень репозитория не найден (вверх от %s "
              "нет каталога, где маркер %s лежит рядом с .git)"
              % (base, boundary.MARKER), file=sys.stderr)
    return root


def _canonical_first(root, rel):
    """Первый сегмент пути в том написании, в котором он лежит на диске.

    Зона выводится из первого сегмента, и регистр этот вывод ломал молча:
    `realpath` на macOS регистр не приводит, поэтому `SOURCES/x.md` — тот же
    inode, что `sources/x.md`, но зоной не считался, и обработчик уходил
    в ветку «вне зон», где не говорят ничего. Тем же движением портился
    список файлов хода: git индексирует `sources/x.md`, а записано было
    `SOURCES/x.md`, и `Stop` счёл бы правку агента чужой.

    Написание не сравнивается без учёта регистра и не приводится к нижнему:
    и то и другое было бы неверно на файловой системе, регистр различающей,
    где `SOURCES/` — действительно другой каталог. Признаётся совпадением
    только один и тот же inode (`samefile`), и это не эвристика, а
    доказательство: на такой системе несуществующего `SOURCES/` попросту нет,
    `samefile` падает `OSError`, и путь остаётся как пришёл.

    Один `listdir` корня и только для первого сегмента: зоны живут в корне
    и нигде больше.
    """
    parts = rel.split("/")
    head = parts[0]
    if not head or head in (".", ".."):
        return rel
    try:
        entries = os.listdir(str(root))
    except OSError:
        return rel
    if head in entries:
        return rel
    lowered = head.lower()
    for entry in entries:
        if entry.lower() != lowered:
            continue
        try:
            if not (Path(root) / entry).samefile(Path(root) / head):
                continue
        except OSError:
            continue
        return "/".join([entry] + parts[1:])
    return rel


def _relative(root, target):
    """Путь записи относительно корня, в написании файловой системы.

    Одна форма на обе ветки записи, и разъезжаться ей нельзя: по ней и
    считается зона, и сравниваются находки гейтов (`Finding.path` собран
    ровно так же), и пишется список файлов хода. Разное написание в этих
    трёх местах даёт три разных ответа на один вопрос.
    """
    rel = Path(os.path.realpath(str(target))).relative_to(
        os.path.realpath(str(root))).as_posix()
    return _canonical_first(root, rel)


def _resolved_target(payload):
    """Корень репозитория и абсолютный путь записи, либо `(None, None)`.

    Прелюдия у обеих веток записи — `PreToolUse` и `PostToolUse` — одна, и
    разъезжаться ей нельзя: обе причины «не смог» утверждаются тестами обеих
    веток дословно.
    """
    base = _base_of(payload)
    root = _root_of(payload)
    if root is None:
        return None, None

    target = tool_path(payload)
    if target is None:
        received = payload.get("tool_input")
        # В строке — то, что пришло на самом деле: список кандидатов закрыт,
        # и пополняют его по увиденному полю, а не по догадке.
        print("гейт не выполнился: путь не разобран в tool_input, получено %r"
              % (sorted(received) if isinstance(received, dict) else received,),
              file=sys.stderr)
        return None, None

    return root, _absolute(target, base)


def on_pre_tool_use(payload):
    """Запись инструментом: блок за границей и на правке источника, иначе — слово.

    Три исхода различаются не строгостью, а тем, чью территорию затрагивают:
    граница репозитория и неизменяемость источника — поломки, и на них код 2;
    переписывание долгоживущей записи — содержимое, а содержимое принадлежит
    автору (линия ответственности), поэтому предупреждение и код 0.

    Остаточный риск назван в том же регистре, что `bashscan.UNCATCHABLE`,
    и по той же причине: неназванная дыра превращает бэкстоп в притворную
    песочницу. Зона выводится из пути, а к одному inode ведут два имени —
    `realpath` разворачивает символические ссылки и не видит жёстких. Отсюда:
    жёсткая ссылка из `sources` в `core` даёт обычное `core`-предупреждение
    там, где пишется inode источника. Механизма против этого нет намеренно:
    искать второе имя inode — обход дерева на каждой записи, а случай ни разу
    не наблюдался.
    """
    root, target = _resolved_target(payload)
    if root is None:
        return EXIT_OK

    if boundary.outside(target, root):
        print("граница рабочего каталога: %s лежит вне корня %s. Плагин "
              "не пишет наружу никогда" % (target, root), file=sys.stderr)
        return EXIT_VIOLATION

    zone = zones.zone_of(_relative(root, target))
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


def _gate_findings(root, wanted):
    """Находки обоих гейтов по названным файлам и список не сработавших гейтов.

    Гейты зовутся модулями, а не подпроцессом: три процесса на запись файла
    против одного импорта, и второй разбор JSON. Индекс ссылок всё равно
    строится по всему дереву — фильтр стоит **после** разбора, а не вместо
    него: иначе `unresolved` неотличим от «цель есть, но её не просканировали».

    Сравнение идёт с `Finding.path`, и пути в `wanted` собраны ровно так же,
    как их собирают гейты: `relative_to(root).as_posix()`. Любая другая форма
    пути молча не совпала бы ни с одной находкой, и гейт выглядел бы
    работающим.

    Упавший гейт называет себя и не уносит с собой второй, но и не исчезает
    из ответа: `SessionStart` коммитит по итогу прогона, и коммит на власти
    прогона, который не состоялся, — подпись под непроверенным.

    Поломка наблюдённая, не гипотеза: `check_links.scan` обходит `*.md` и
    читает каждое совпадение как файл, а каталог с таким именем — одно
    движение мыши в Obsidian — даёт `IsADirectoryError`. Один такой каталог
    где угодно в дереве иначе гасил бы `PostToolUse` на каждой записи, а
    причиной в stderr значился бы код возврата hook.py. Прежним образцом
    здесь был файл в cp1251; ронять гейт он перестал в `cc3c7ea`, ветка
    осталась.
    """
    out, failed = [], []
    for gate in (check_links, check_frontmatter):
        name = gate.__name__.rsplit(".", 1)[-1]
        try:
            report = gate.scan(root)
        except Exception as error:
            print("гейт не выполнился: %s упал на %s — %s"
                  % (name, type(error).__name__, error), file=sys.stderr)
            failed.append(name)
            continue
        out.extend(f for f in report.findings if f.path in wanted)
    return out, failed


def on_post_tool_use(payload):
    """Запись состоялась: отчёт по записанному файлу и строка в список хода.

    Возвращает 0 всегда. `PostToolUse` сообщает, а не запрещает: файл уже на
    диске, и код 2 после факта — театр, а не гейт. Красный ход останавливает
    `Stop`, и это его работа.

    Цена фильтра по записанному файлу названа, а не забыта: файл, *вызвавший*
    находку, — ровно тот, который фильтр и выбрасывает. Новый `areas/dup.md`
    делает существующий `[[dup]]` в `core/me.md` неоднозначным, и об этом
    здесь не будет сказано ни слова. Фильтр всё равно остаётся: отчёт по
    всему дереву на каждой записи — это отчёт, который перестают читать,
    а красный ход всё равно не уйдёт мимо `Stop`.
    """
    root, target = _resolved_target(payload)
    if root is None:
        return EXIT_OK

    if boundary.outside(target, root):
        # Судить не о чем — гейты сканируют репозиторий, а файл лежит не в нём.
        # Но и в список хода такой путь не попадёт: `Stop` заряжает по этому
        # списку `git add`, и наружный путь в нём — заряженное нарушение
        # незыблемого №6. Запретить запись — работа `PreToolUse`, не эта.
        print("файл %s лежит вне корня %s: гейты по нему не считаются и в "
              "список файлов хода он не пишется" % (target, root),
              file=sys.stderr)
        return EXIT_OK

    rel = _relative(root, target)

    if not turnfiles.record(root, payload.get("session_id") or "", rel):
        print("гейт не выполнился: список файлов хода не записан (каталог "
              ".git не открывается в %s). Stop сочтёт правки этого хода "
              "чужими и ограничится сообщением" % root, file=sys.stderr)

    findings, _ = _gate_findings(root, {rel})
    if findings:
        print("\n".join(f.render() for f in findings), file=sys.stderr)
    return EXIT_OK


def on_session_start(payload):
    """Сводка в контекст и чекпоинт чужой работы, если она зелёная.

    Незакоммиченное на старте по определению чужое: сессия только что
    началась, агент ещё ничего не писал, — значит, там человек в Obsidian
    или соседний агент. Зелёное сохраняется чекпоинтом, чтобы эта работа
    не потерялась; красное показывается и не коммитится: плагин не
    подписывается под тем, чего не чинил.

    Печатается всё в stdout, а не в stderr: только у `SessionStart` и двух
    соседей по промпту stdout попадает в контекст сессии, а адресат этих
    строк — агент. В stderr уходит одно — «гейт не выполнился»: общий канал
    отказа у всех хуков. Невосстановимое при этом названо и в сводке словом,
    чтобы молчание git не читалось как чистое дерево (незыблемое №4).

    Код всегда 0. Нарушения здесь нет по построению: никто ещё ничего не
    сделал, судить не о чем.
    """
    root = _root_of(payload)
    if root is None:
        return EXIT_OK

    state = summary.collect(root)
    print(summary.render(state))
    for problem in state.problems:
        print("гейт не выполнился: %s" % problem, file=sys.stderr)

    if not state.dirty:
        # Ни `None`, ни пустой список поводом для коммита не являются, и
        # причины у них разные: в первом случае неизвестно что коммитить,
        # во втором нечего.
        return EXIT_OK

    if state.git_root is not None and Path(state.git_root) != Path(root):
        # `--porcelain` печатает пути от корня git, а гейты — от корня рецепта.
        # Разошлись корни — разошлись и списки, на целую приставку пути: ни
        # одна находка не найдёт своего файла, и красное уедет в чекпоинт
        # молча. Отказ вслух лучше правки, посчитанной на разъехавшихся путях.
        print("чекпоинт не сделан: корень рецепта %s не совпадает с корнем "
              "git %s, и пути в них разной длины" % (root, state.git_root))
        return EXIT_OK

    if state.unmerged:
        # `git add` по конфликтному файлу помечает конфликт разрешённым.
        # Плагин выдал бы за решение то, чего не решал, — и закоммитил текст
        # вместе с маркерами `<<<<<<<`. Гейты этого не ловят: маркер конфликта
        # не ссылка и не frontmatter.
        print("чекпоинт не сделан: в дереве незавершённое слияние. Развести "
              "чужой конфликт плагин не имеет права")
        return EXIT_OK

    findings, failed = _gate_findings(root, set(state.dirty))
    if failed:
        print("чекпоинт не сделан: не отработал %s, и зелени никто не видел"
              % ", ".join(failed))
        return EXIT_OK

    red = summary.errors(findings)
    if red:
        print("незакоммиченное не прошло гейты, чекпоинт не сделан:")
        print("\n".join(f.render() for f in sorted(red, key=lambda f: f.key())))
        return EXIT_OK

    staged, skipped = summary.committable(root, state.dirty)
    for rel in skipped:
        print("чекпоинт не берёт %s: это каталог, а сдвиг указателя сабмодуля "
              "коммитит его владелец, не плагин" % rel)
    try:
        summary.checkpoint(root, staged)
    except summary.GitSilent as error:
        print("гейт не выполнился: чекпоинт не записан: %s" % error,
              file=sys.stderr)
    return EXIT_OK


def bash_command(payload):
    """Строка команды из `tool_input`, или None.

    Отдельная функция, а не поле в `_PATH_FIELDS`: у Bash имя поля известно
    и одно, и путать «не нашли путь среди четырёх кандидатов» с «пришла
    не команда» нельзя — это разные причины и разные строки.
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    return command if isinstance(command, str) and command else None


def on_pre_tool_use_bash(payload):
    """Команда в терминале: блок на перемещении, удалении и записи мимо гейтов.

    Отдельное событие, а не ветка внутри `on_pre_tool_use`: матчеры в
    `hooks.json` разные, и различать их по `tool_name` значило бы завести
    второй источник истины о том, какой инструмент приехал.

    Корень репозитория здесь не ищется и не нужен: сканер судит по первому
    сегменту пути, о чём честно сказано в `bashscan.UNCATCHABLE` («запись по
    абсолютному пути»). Спрашивать корень ради ответа, который от него не
    зависит, — лишняя причина отказа на пустом месте.

    Неразобранный ввод — код 0 и видимая строка, никогда не блок: блокировать
    по собственной слепоте значит запретить работу за то, чего не прочитал
    (незыблемое №4).
    """
    command = bash_command(payload)
    if command is None:
        received = payload.get("tool_input")
        print("гейт не выполнился: команда не разобрана в tool_input, "
              "получено %r"
              % (sorted(received) if isinstance(received, dict) else received,),
              file=sys.stderr)
        return EXIT_OK

    verdict = bashscan.judge(command)
    if verdict.blocked:
        print(verdict.reason, file=sys.stderr)
        return EXIT_VIOLATION
    return EXIT_OK


# Обработчики регистрируются задачами волны. Пустая таблица — не заглушка:
# каждое незарегистрированное событие называет себя вслух строкой выше.
#
# `PreToolUseBash` — не событие ядра, а второй маршрут того же `PreToolUse`:
# имя приезжает аргументом из `hooks.json`, где матчер `Bash` отделён от
# матчера записи. Пока этой строки не было, весь сканер команд был мёртвым
# кодом при 62 зелёных тестах: голый `mv` проходил, а в stderr значилось, что
# событие не обслуживается.
HANDLERS = {
    "SessionStart": on_session_start,
    "PreToolUse": on_pre_tool_use,
    "PreToolUseBash": on_pre_tool_use_bash,
    "PostToolUse": on_post_tool_use,
}


if __name__ == "__main__":
    # Наружу уходит код рукопожатия, а не результат сам по себе. Код, которого
    # нет в таблице, не переводится: пусть шим назовёт его вслух, чем он
    # притворится одним из двух знакомых исходов.
    _code = main()
    sys.exit(_HANDSHAKE.get(_code, _code))
