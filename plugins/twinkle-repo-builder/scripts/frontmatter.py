"""Разбор frontmatter без зависимостей.

Принимает подмножество YAML, которое реально пишет Obsidian Properties:
скаляры, кавычки, flow-списки, блочные списки, одну вложенную мапу — и
блочный список внутри неё. Последнее сочетание докстрока обещала и раньше,
а разбор на нём падал: multi-value свойство под вложенным ключом панель
Properties пишет именно так, и `values:\\n  status:\\n    - open` — самая
частая форма объявления коллекции, а не экзотика.

Всё, чего не понимает, — исключение с номером строки. Молчаливого сброса
состояния нет: угадавший парсер хуже отсутствующего. Повторный ключ — тот же
сброс, только незаметный, и он тоже исключение: побеждала последняя строка,
первое значение исчезало без следа и до гейта не доезжало вовсе.
"""

import re

_DELIM = "---"
_KEY = re.compile(r"^(?P<indent>[ ]*)(?P<key>[^:#\s][^:]*):(?P<rest>.*)$")
_ITEM = re.compile(r"^(?P<indent>[ ]*)-\s+(?P<value>.*)$")

# Корневая мапа плюс одна вложенная — ровно то, что обещано выше. Глубже
# разбор не угадывает, а отказывается: формы, которой нет у Properties,
# в объявлении коллекции взяться неоткуда, а тихо разобранная третья
# ступень выглядела бы правдоподобно и означала бы что угодно.
_MAX_MAP_DEPTH = 2


class FrontmatterError(Exception):
    def __init__(self, message, line):
        super().__init__("%s (строка %d)" % (message, line))
        self.line = line


def _scalar(raw, lineno):
    raw = raw.strip()
    if raw == "":
        return None
    if raw[0] in "|>":
        raise FrontmatterError("блочный скаляр не поддерживается", lineno)
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if inner == "":
            return []
        return [_scalar(part, lineno) for part in inner.split(",")]
    return raw


def _map_depth(stack):
    return sum(1 for _, container in stack if isinstance(container, dict))


def parse(text):
    """dict полей. Пустой dict, если frontmatter нет вовсе."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != _DELIM:
        return {}

    body = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            body = lines[1:i]
            break
    if body is None:
        raise FrontmatterError("frontmatter не закрыт", 1)

    out = {}
    # Стек открытых контейнеров: (отступ их элементов, контейнер). Дно —
    # корневая мапа. Каждая строка сперва закрывает всё, что глубже её
    # отступа, и только потом кладёт значение: так уровень вложенности
    # закрывается явно, а не теряется где-то в середине разбора. Одной
    # пары «ждущий ключ + его отступ» на это не хватало — она помнила
    # ровно один уровень, и вложенный список закрывать было нечем.
    stack = [(0, out)]
    # Ключ, за которым ещё ничего не пришло: следующая строка и решает,
    # чем он окажется — списком, мапой или пустым полем.
    pending = None      # (отступ ключа, мапа-владелец, имя ключа)

    for offset, line in enumerate(body):
        lineno = offset + 2  # +1 за разделитель, +1 за счёт с единицы
        if "\t" in line:
            raise FrontmatterError("табуляция в отступе", lineno)
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue

        item = _ITEM.match(line)
        if item:
            indent = len(item.group("indent"))
            # Блочный список открывается и вровень с ключом, и с отступом:
            # обе формы законны в YAML, и обе встречаются в реальных файлах.
            if pending is not None and indent >= pending[0]:
                key_indent, owner, key = pending
                target = []
                owner[key] = target
                stack.append((indent, target))
                pending = None
            else:
                while len(stack) > 1 and stack[-1][0] > indent:
                    stack.pop()
                open_indent, target = stack[-1]
                if not isinstance(target, list):
                    raise FrontmatterError("элемент списка без ключа", lineno)
                if open_indent != indent:
                    raise FrontmatterError("неожиданный отступ", lineno)
            target.append(_scalar(item.group("value"), lineno))
            continue

        match = _KEY.match(line)
        if not match:
            raise FrontmatterError("строка не разобрана", lineno)

        indent = len(match.group("indent"))
        key = match.group("key").strip()
        rest = match.group("rest")

        if pending is not None and indent > pending[0]:
            key_indent, owner, pending_key = pending
            if _map_depth(stack) >= _MAX_MAP_DEPTH:
                raise FrontmatterError("мапа глубже одной вложенной "
                                       "не поддерживается", lineno)
            target = {}
            owner[pending_key] = target
            stack.append((indent, target))
            pending = None
        else:
            # Список закрывается ключом своего же отступа: `- a` на второй
            # колонке принадлежит ключу с первой, а `other:` на второй — уже
            # мапе-владельцу. Мапа при равном отступе, наоборот, остаётся
            # открытой: это её собственный следующий ключ.
            while len(stack) > 1 and (
                    stack[-1][0] > indent
                    or (isinstance(stack[-1][1], list) and stack[-1][0] >= indent)):
                stack.pop()
            open_indent, target = stack[-1]
            if not isinstance(target, dict):
                raise FrontmatterError("ключ на месте элемента списка", lineno)
            if len(stack) == 1 and not out:
                # Первый ключ задаёт отступ корневой мапы: блок, сдвинутый
                # целиком, — законный YAML и разбирался здесь всегда.
                # Отказ от него был бы не строгостью, а регрессией.
                stack[0] = (indent, out)
                open_indent = indent
            if open_indent != indent:
                raise FrontmatterError("неожиданный отступ", lineno)
            pending = None

        if key in target:
            raise FrontmatterError("повторный ключ: %s" % key, lineno)

        value = _scalar(rest, lineno)
        target[key] = value
        if value is None:
            pending = (indent, target, key)

    return out
