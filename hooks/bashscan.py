#!/usr/bin/env python3
"""Сканер команды Bash: что блокируем в терминале и что честно не ловим.

Две поломки, ради которых он существует (секция 4 спеки волны 2):

1. Перемещение мимо цепочки `find-refs → rewrite-refs → move` ломает все
   входящие ссылки на файл разом: они остаются на старом пути и никуда
   не ведут. Это поломка, а не вопрос вкуса, поэтому голое `mv` блокируется.
2. Прямая запись в дерево контента минует `PostToolUse`: гейты по файлу
   не отработают, и в списке файлов хода его не будет, поэтому `Stop` сочтёт
   поломку чужой и не заблокирует ход.

Разбор посимвольный: `echo 'mv a b'` — не перемещение. Пути сравниваются
по сегменту, а не по префиксу строки, иначе гейт краснеет на невинных именах,
и его учатся обходить.

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

# Закрытое множество форм перемещения. Матчеры ниже читают отсюда и своих
# копий не держат: правка этой строки меняет поведение.
BLOCKED = ("mv", "git mv")

_MOVE_COMMANDS = frozenset(form for form in BLOCKED if " " not in form)
_GIT_SUBCOMMANDS = frozenset(form.split(" ", 1)[1] for form in BLOCKED
                             if form.startswith("git "))

# Явный список неперехватываемого — часть поставки, а не оговорка. Каждая
# строка проверена тестом `TestUncatchableIsHonest`: запись «не ловим»,
# которую на самом деле ловим, вводит в заблуждение так же, как молчаливая
# заглушка.
UNCATCHABLE = (
    "удаление и перемещение через python-скрипт, запущенный из Bash",
    "перемещение во временный каталог вне репозитория не командой mv: "
    "cp с последующим rm, редактор, файловый менеджер",
    "eval со строкой, собранной во время исполнения",
    "перемещение внутри строки, отданной в bash -c или sh -c, и внутри тела "
    "here-doc, отданного оболочке: и то и другое гасится как данные",
    "имя команды в кавычках: гасится тем же правилом, которое спасает "
    "безобидное echo с перемещением внутри строки",
    "имя команды, приехавшее из переменной: раскрытие происходит в оболочке, "
    "сканеру видно только имя переменной",
    "значение опции обёртки, прочитанное как имя команды: sudo -u имя mv",
    "перемещение подкомандой мультикоманд-бинарника: busybox mv",
    "перемещение чужой командой с тем же действием: rsync "
    "--remove-source-files",
    "удаление: rm ломает входящие ссылки ровно так же, как перемещение, "
    "но спека закрывает перемещение и запись, а не удаление",
    "запись в дерево контента командой, а не перенаправлением: cp, tee, sed -i",
    "запись по абсолютному пути: сканер судит по первому сегменту пути "
    "и корня репозитория не знает",
    "перемещение через find -exec и через функцию оболочки, чьё имя не mv",
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
    """Команда без того, что командой не является: тел here-doc и кавычек."""
    return _strip_quoted(_strip_heredocs(text))


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
    for index, token in enumerate(tokens):
        if _ASSIGNMENT.match(token):
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


def _written_into_content(line):
    """Цель перенаправления, попадающая в долгоживущую зону, или None.

    Долгоживущие — те, на которые ссылаются: незамеченная правка там роняет
    чужие ссылки. Транзитные не сторожатся: их содержимое исчезает
    по построению, ссылок на него нет.
    """
    for target in _REDIRECT.findall(_clean(line)):
        if touches_zone(target, zones.LONG_LIVED):
            return target
    return None


def judge(line):
    """Блокировать ли команду. В причине — имя правильного пути."""
    for segment in _segments(line):
        tokens = segment.split()
        if "--help" in tokens:
            # Справка ничего не двигает, а ложный блок на безобидной команде
            # учит обходить гейт целиком.
            continue
        name, rest = _head(tokens)
        if name is None:
            continue
        if _basename(name) in _MOVE_COMMANDS:
            return Verdict(True, _MOVE_REASON)
        if _basename(name) == "git" and _git_subcommand(rest) in _GIT_SUBCOMMANDS:
            return Verdict(True, _MOVE_REASON)
    target = _written_into_content(line)
    if target is not None:
        return Verdict(True, _WRITE_REASON % target)
    return Verdict(False)
