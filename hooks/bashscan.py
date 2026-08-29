#!/usr/bin/env python3
"""Сканер команды Bash: что блокируем в терминале и что честно не ловим.

Три поломки, ради которых он существует (секция 4 спеки волны 2):

1. Перемещение мимо цепочки `find-refs → rewrite-refs → move` ломает все
   входящие ссылки на файл разом: они остаются на старом пути и никуда
   не ведут. Это поломка, а не вопрос вкуса, поэтому голое `mv` блокируется.
2. Удаление ломает ровно то же самое: ссылки остаются на пути, которого
   больше нет. Отличие одно — блокируется по зоне, а не всегда: в зонах,
   чьё содержимое исчезает по построению, чистка и есть назначение.
3. Прямая запись в дерево контента минует `PostToolUse`: гейты по файлу
   не отработают, и в списке файлов хода его не будет, поэтому `Stop` сочтёт
   поломку чужой и не заблокирует ход.

Разбор посимвольный: `echo 'mv a b'` — не перемещение. Пути сравниваются
по сегменту, а не по префиксу строки, иначе гейт краснеет на невинных именах,
и его учатся обходить. Вердикт один на все зоны, а текст отказа свой у каждой:
совет взять инструмент записи в чужом сабмодуле был бы советом сделать
запрещённое.

**Это бэкстоп против случайности, а не песочница против намерения.** Читается
только текст команды; всё, что мимо, названо в `UNCATCHABLE` поимённо.
Записанный остаточный риск и отличает бэкстоп от притворной песочницы: без
списка пользователь считает, что защищён там, где не защищён.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import zones

# Закрытые множества форм. Матчеры ниже читают отсюда и своих копий
# не держат: правка этих строк меняет поведение.
BLOCKED = ("mv", "git mv")
# Удаление ломает входящие ссылки ровно так же, как перемещение: они остаются
# на пути, которого больше нет. Блокируется не всегда, а по зоне — см.
# `_delete_verdict`. `rmdir` сюда не входит: он сносит только пустой каталог,
# а на пустой каталог ссылаться нечему, то есть ломать нечего.
DELETES = ("rm", "git rm", "unlink")


def _forms(catalogue):
    """Простые имена и подкоманды git из списка форм."""
    return (frozenset(form for form in catalogue if " " not in form),
            frozenset(form.split(" ", 1)[1] for form in catalogue
                      if form.startswith("git ")))


_MOVE_COMMANDS, _GIT_MOVE = _forms(BLOCKED)
_DELETE_COMMANDS, _GIT_DELETE = _forms(DELETES)

# Сырьё. В приговоре не участвует: сторожится оно наравне с остальными
# нетранзитными зонами. Названо здесь только ради текста отказа — причина
# у него своя, а вердикт общий.
_IMMUTABLE_RAW = frozenset({"sources"})

# Путь, который уводит из каталога перехода: судить его по этому каталогу
# нельзя, потому что он не в нём.
_LEAVES_DIRECTORY = ("/", "..")

# Аргумент, который раскрывает оболочка: зоны из него не прочитать.
_UNREADABLE_ARG = re.compile(r"[$*?~]")

# Явный список неперехватываемого — часть поставки, а не оговорка. Каждая
# строка проверена тестом `TestUncatchableIsHonest`: запись «не ловим»,
# которую на самом деле ловим, вводит в заблуждение так же, как молчаливая
# заглушка.
UNCATCHABLE = (
    "удаление и перемещение через python-скрипт, запущенный из Bash",
    "перемещение наружу репозитория редактором или файловым менеджером",
    "удаление по пути, чью зону нечем прочитать: каталог перехода виден "
    "только у литерального cd — переход через переменную или подстановку "
    "раскрывает оболочка, и зоны из него не достать",
    "eval со строкой, собранной во время исполнения",
    "перемещение внутри строки, отданной в bash -c или sh -c, и внутри тела "
    "here-doc, отданного оболочке: и то и другое гасится как данные",
    "имя команды в кавычках: гасится тем же правилом, которое спасает "
    "безобидное echo с перемещением внутри строки",
    "имя команды, приехавшее из переменной: раскрытие происходит в оболочке, "
    "сканеру видно только имя переменной",
    "значение опции обёртки, прочитанное как имя команды: sudo -u имя mv",
    "перемещение подкомандой мультикоманд-бинарника: busybox mv. Таблица "
    "бинарник-подкоманда — машинерия ради случая, который на этой платформе "
    "ни разу не наблюдался",
    "перемещение чужой командой с тем же действием: rsync "
    "--remove-source-files",
    "запись в дерево контента командой, а не перенаправлением: cp, tee, sed -i",
    "запись по абсолютному пути: сканер судит по первому сегменту пути "
    "и корня репозитория не знает",
    "перемещение через функцию оболочки, чьё имя не mv",
)

# Порядок замены значим: `&&` и `||` обязаны уйти раньше `&` и `|`, иначе
# от них остаётся хвост и следующий сегмент начинается не с команды. Скобки
# здесь же — и подоболочка, и подстановка `$(...)`, и backtick открывают
# новый сегмент, а голова сегмента и есть команда.
_SEPARATORS = ("&&", "||", ";;", ";", "|&", "|", "&", "(", ")", "`", "\n")

# Слова, которые стоят перед командой, но командой не являются: обёртки и
# ключевые слова оболочки. Без них голова сегмента у цикла — `do`, а у
# `sudo mv` — `sudo`, и перемещение проходит незамеченным.
_TRANSPARENT = frozenset((
    "sudo", "command", "builtin", "exec", "eval", "env", "time", "timeout",
    "nice", "ionice", "stdbuf", "nohup", "xargs", "if", "then", "elif",
    "else", "while", "until", "do", "!", "{", "{}",
))

# `FOO=bar mv a b`: присваивание перед командой её не отменяет.
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Глобальные опции git, съедающие следующий токен. Без них подкомандой
# в `git -C dir mv a b` окажется имя каталога.
_GIT_VALUE_OPTIONS = frozenset(("-C", "-c", "--git-dir", "--work-tree",
                                "--namespace", "--exec-path"))

# Перенаправление вывода: с номером дескриптора (`2>`), удвоенное (`>>`)
# и с отменой noclobber (`>|`).
_REDIRECT = re.compile(r"\d*>>?\|?\s*([^\s>|;&()]+)")

# Перенаправление, стоящее перед командой, — не команда. Голый оператор
# съедает и следующий токен: это его цель, а не имя команды.
_AFTER_REDIRECT = re.compile(r"(?<=>)[&|]")
_REDIRECT_BARE = re.compile(r"^\d*(?:>>?|<)\|?$")
_REDIRECT_GLUED = re.compile(r"^\d*(?:>>?|<)\|?\S+$")

# `find … -exec mv {} …` — настоящее пакетное перемещение: одной командой
# рушатся все входящие ссылки разом, а не одна.
_EXEC_FLAGS = frozenset(("-exec", "-execdir", "-ok", "-okdir"))

# Начало here-doc ищется в два приёма. Сначала сам `<<` — но в строке, из
# которой уже вынуто содержимое кавычек, иначе сдвиг внутри текста (`echo
# "x << y"`) откроет here-doc, погасит хвост команды, и перемещение за ним
# пройдёт незамеченным. Потом ограничитель — но уже в исходной строке, потому
# что он сам бывает в кавычках: `<<'EOF'`.
_HEREDOC_OPEN = re.compile(r"<<-?")
_HEREDOC_LIMIT = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

# Приписка в каждом отказе. Спека требует, чтобы текст сам называл себя
# защитой от случайности: иначе отказ читается как песочница, и пользователь
# считает, что защищён там, где не защищён.
_BACKSTOP = ("Разбирается только текст команды: это защита от случайности, "
             "а не от намерения.")

# Правильный путь называется командными токенами, а не backtick-путём:
# у контекстного репозитория нет своего каталога скриптов, и backtick-путь
# в тексте отказа сам поднял бы unresolved в гейте ссылок.
_MOVE_REASON = (
    "перемещение мимо цепочки ломает все входящие ссылки на файл: они "
    "остаются на старом пути и никуда не ведут. Правильный путь — find-refs, "
    "затем rewrite-refs, затем move: сначала видно, кто ссылается, потом "
    "ссылки переписываются, и только потом файл двигается. " + _BACKSTOP)

_WRITE_REASON = (
    "запись в %s мимо инструментов редактирования идёт мимо гейтов: ссылки "
    "и обязательные поля никто не проверит, а в списке файлов хода файла "
    "не будет, и конец хода сочтёт поломку чужой. Правильный путь — "
    "инструмент Write или Edit, после них гейты отрабатывают сами. "
    + _BACKSTOP)

# Спека даёт на удаление в долгоживущей зоне подтверждение автора, а не
# скрипт. Назвать здесь несуществующий скрипт было бы тем же дефектом, что
# назвать существующий, делающий не то, что обещано в тексте.
_DELETE_REASON = (
    "удаление ломает все входящие ссылки на файл ровно так же, как "
    "перемещение: они остаются на пути, которого больше нет. На удаление "
    "того, что уже живёт в долгоживущей зоне, нужно подтверждение автора; "
    "find-refs до того показывает, кто ссылается, и во что это обойдётся. "
    + _BACKSTOP)

# Сырьё: правка и удаление — одна поломка, поэтому и текст один.
_RAW_REASON = (
    "сырьё неизменяемо по построению: поправленный или удалённый задним "
    "числом источник делает недоказуемым каждый вывод, который на него "
    "ссылается. Это поломка, а не нарушение конвенции. Правка и удаление "
    "здесь остаются операцией человека — хук блокирует агента, не автора. "
    + _BACKSTOP)

# Чужие сабмодули: совет «возьми инструмент записи» был бы советом сделать
# запрещённое, поэтому текст не называет ни его, ни подтверждение автора.
_READONLY_REASON = (
    "путь %s лежит в чужом git-сабмодуле: его содержимое ведётся в своём "
    "репозитории, а пути внутри сабмодулей закрыты статически в настройках. "
    "Ни писать, ни удалять здесь нечего — если файл нужен свой, ему место "
    "в другой зоне. " + _BACKSTOP)


class Verdict:
    __slots__ = ("blocked", "reason")

    def __init__(self, blocked, reason=""):
        self.blocked = blocked
        self.reason = reason


def _strip_quoted(text):
    """Содержимое кавычек заменяется пробелами: длина и позиции сохраняются.

    Экранированная кавычка строку не закрывает — иначе `echo "a\\" mv b"`
    читалось бы как перемещение.
    """
    out = []
    quote = None
    escaped = False
    for ch in text:
        if escaped:
            out.append(" " if quote else ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            out.append(" " if quote else ch)
            continue
        if quote:
            out.append(" ")
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            out.append(" ")
            continue
        out.append(ch)
    return "".join(out)


def _strip_heredocs(text):
    """Тела here-doc гасятся: это данные, а не команды.

    Строка `mv old.md new.md` внутри документа о том, как делать нельзя, —
    текст. Блокировать её значило бы запретить писать документацию про этот
    самый гейт, а ложный блок на безобидной команде учит обходить гейт.

    Тело гасится целиком, поэтому перемещение внутри here-doc, отданного
    оболочке, не ловится — названо в UNCATCHABLE. Перенаправление с первой
    строки при этом видно, и запись в дерево контента остаётся блоком.
    """
    out = []
    limit = None
    for line in text.split("\n"):
        if limit is not None:
            if line.strip() == limit:
                limit = None
            out.append("")
            continue
        out.append(line)
        opener = _HEREDOC_OPEN.search(_strip_quoted(line))
        if opener is None:
            continue
        # Позиции при гашении кавычек сохраняются, поэтому смещение из
        # очищенной строки годится для исходной.
        found = _HEREDOC_LIMIT.match(line, opener.start())
        if found:
            limit = found.group(2)
    return "\n".join(out)


def _clean(text):
    """Команда без того, что командой не является: тел here-doc и кавычек.

    Заодно гасятся `&` и `|` сразу за `>`: в `2>&1` это не фоновый запуск,
    а в `>|` не конвейер. Считать их разделителями нельзя — следующий
    сегмент начался бы с обломка, и команда за ним осталась бы неразобранной.
    """
    return _AFTER_REDIRECT.sub(" ", _strip_quoted(_strip_heredocs(text)))


def _segments(line):
    """Строка, разрезанная по разделителям, без содержимого кавычек."""
    clean = _clean(line)
    for separator in _SEPARATORS:
        clean = clean.replace(separator, "\n")
    return clean.split("\n")


def commands(line):
    """Первые слова всех сегментов команды, без содержимого кавычек."""
    out = []
    for segment in _segments(line):
        words = segment.split()
        if words:
            out.append(words[0])
    return out


def _basename(token):
    """Имя команды: вызов по полному пути, по имени и с обратной косой —
    одно и то же.

    Обратная косая перед именем — идиома обхода алиаса, а не другая команда;
    имени файла, начинающегося с неё, не бывает.
    """
    return token.rsplit("/", 1)[-1].lstrip("\\")


def _head(tokens):
    """Имя команды сегмента и её аргументы, сквозь обёртки и присваивания."""
    after_wrapper = False
    skip_next = False
    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if _ASSIGNMENT.match(token):
            continue
        if _REDIRECT_BARE.match(token):
            skip_next = True
            continue
        if _REDIRECT_GLUED.match(token):
            continue
        if _basename(token) in _TRANSPARENT:
            after_wrapper = True
            continue
        # Опции и числа сразу за обёрткой — её собственные аргументы, а не
        # команда: `timeout 5 mv`, `nice -n 5 mv`. Значение опции от опции
        # неотличимо, у каждой обёртки своя грамматика — `sudo -u имя mv`
        # так и остаётся непойманным, и это записано в UNCATCHABLE.
        if after_wrapper and (token.startswith("-") or token.isdigit()):
            continue
        return token, tokens[index + 1:]
    return None, []


def _git_subcommand(tokens):
    """Подкоманда git: опции пропускаются, значения при них — тоже."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _GIT_VALUE_OPTIONS:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return None


def _first_segment(token):
    """Первый сегмент пути: `journal/` совпадает, `journaling/` нет."""
    text = token.strip()
    while text.startswith("./"):
        text = text[2:]
    return text.rstrip("/").split("/")[0]


def touches_zone(line, zone_names):
    """Совпадение по сегменту пути, а не по префиксу строки.

    Префиксное сравнение краснеет на невинных путях, чьё имя начинается
    так же, — а гейт, который врёт, учатся обходить.
    """
    for token in _clean(line).split():
        if _first_segment(token) in zone_names:
            return True
    return False


def _is_guarded(zone):
    """Зона, где правка и удаление ломают чужие ссылки.

    Сторожится всё, что не транзитно. Транзитные зоны — ровно те, чьё
    содержимое исчезает по построению: ссылаться там не на что, а чистка
    и есть их назначение, так что блок был бы ложным.

    Предикат, а не список: зона, добавленная в таблицу завтра, начинает
    сторожиться сама собой. Список пришлось бы вспоминать — и один раз
    в нём уже забыли зону решений.
    """
    return zone in zones.ZONES and zone not in zones.TRANSIENT


def _zone_of_target(token, cwd_zone):
    """Зона пути, при нужде — по каталогу литерального `cd` перед ним.

    Путь, уводящий из этого каталога — абсолютный или через `..`, — по нему
    не судится: он не в нём.
    """
    zone = _first_segment(token)
    if zone in zones.ZONES:
        return zone
    if token.startswith(_LEAVES_DIRECTORY):
        return None
    return cwd_zone


def _written_into(text, cwd_zone):
    """Цель перенаправления, попадающая в сторожимую зону, и её зона."""
    for target in _REDIRECT.findall(_clean(text)):
        zone = _zone_of_target(target, cwd_zone)
        if _is_guarded(zone):
            return target, zone
    return None


def _cd_zone(rest):
    """Зона, в которую уводит литеральный `cd`, или None.

    Только литеральный аргумент: `cd` в переменную или в подстановку зоны
    не даёт. Догадываться нельзя — блок по угаданному каталогу и есть
    ложный блок, а он учит обходить гейт.
    """
    args = [token for token in rest if not token.startswith("-")]
    if len(args) != 1 or _UNREADABLE_ARG.search(args[0]):
        return None
    zone = _first_segment(args[0])
    return zone if zone in zones.ZONES else None


def _exec_commands(tokens):
    """Команды, запускаемые через `-exec` у find: имя стоит сразу за флагом.

    Зона берётся из аргументов самого find: цель такой команды — то, что он
    нашёл, а не токен `{}`, который классифицировать нечем.
    """
    out = []
    for index, token in enumerate(tokens):
        if token in _EXEC_FLAGS and index + 1 < len(tokens):
            out.append((tokens[index + 1], tokens[index + 2:], tokens))
    return out


def _zone_verdict(zone, token, in_zone_reason):
    """Отказ по зоне. Вердикт общий, текст — свой у каждой из трёх.

    Совет «возьми инструмент записи» в чужом сабмодуле и разговор о
    подтверждении автора в неизменяемом сырье были бы советами сделать
    запрещённое, поэтому текст выбирается зоной, а не одной строкой на всех.
    """
    if zone in zones.READ_ONLY:
        return Verdict(True, _READONLY_REASON % token)
    if zone in _IMMUTABLE_RAW:
        return Verdict(True, _RAW_REASON)
    return Verdict(True, in_zone_reason)


def _delete_verdict(pool, cwd_zone):
    """Приговор удалению: по зоне пути, а не по самой команде.

    Путь, чью зону прочитать нечем, блоком не наказывается: блокировать
    на непрочитанном пути — тот же ложный блок, только необъяснимый.
    """
    for token in pool:
        if token.startswith("-"):
            continue
        zone = _zone_of_target(token, cwd_zone)
        if _is_guarded(zone):
            return _zone_verdict(zone, token, _DELETE_REASON)
    return None


def _verdict_for(name, rest, pool, cwd_zone):
    """Приговор одной команде или None, если она не из закрытых множеств."""
    simple = _basename(name)
    if simple in _MOVE_COMMANDS:
        return Verdict(True, _MOVE_REASON)
    if simple in _DELETE_COMMANDS:
        return _delete_verdict(pool, cwd_zone)
    if simple == "git":
        subcommand = _git_subcommand(rest)
        if subcommand in _GIT_MOVE:
            return Verdict(True, _MOVE_REASON)
        if subcommand in _GIT_DELETE:
            return _delete_verdict(pool, cwd_zone)
    return None


def judge(line):
    """Блокировать ли команду. В причине — имя правильного пути."""
    cwd_zone = None
    for segment in _segments(line):
        tokens = segment.split()
        if "--help" in tokens:
            # Справка ничего не двигает, а ложный блок на безобидной команде
            # учит обходить гейт целиком.
            continue
        name, rest = _head(tokens)
        # Третий элемент — токены, среди которых ищется зона: у головы это
        # её собственные аргументы, у команды из `-exec` — весь вызов find.
        candidates = [] if name is None else [(name, rest, rest)]
        candidates.extend(_exec_commands(tokens))
        for candidate, candidate_rest, pool in candidates:
            verdict = _verdict_for(candidate, candidate_rest, pool, cwd_zone)
            if verdict is not None:
                return verdict
        written = _written_into(segment, cwd_zone)
        if written is not None:
            target, zone = written
            return _zone_verdict(zone, target, _WRITE_REASON % target)
        if name is not None and _basename(name) == "cd":
            # Неразобранный переход обнуляет каталог, а не сохраняет прежний:
            # после него неизвестно, где мы, и это честнее догадки.
            cwd_zone = _cd_zone(rest)
    return Verdict(False)
