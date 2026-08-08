"""Разбор frontmatter без зависимостей.

Принимает подмножество YAML, которое реально пишет Obsidian Properties:
скаляры, кавычки, flow-списки, блочные списки, одну вложенную мапу.
Всё, чего не понимает, — исключение с номером строки. Молчаливого
сброса состояния нет: угадавший парсер хуже отсутствующего.
"""

import re

_DELIM = "---"
_KEY = re.compile(r"^(?P<indent>[ ]*)(?P<key>[^:#\s][^:]*):(?P<rest>.*)$")
_ITEM = re.compile(r"^(?P<indent>[ ]*)-\s+(?P<value>.*)$")


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
    pending_key = None      # ключ, ждущий блочного списка или вложенной мапы
    pending_indent = 0

    for offset, line in enumerate(body):
        lineno = offset + 2  # +1 за разделитель, +1 за счёт с единицы
        if "\t" in line:
            raise FrontmatterError("табуляция в отступе", lineno)
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue

        item = _ITEM.match(line)
        if item:
            if pending_key is None:
                raise FrontmatterError("элемент списка без ключа", lineno)
            target = out[pending_key]
            if not isinstance(target, list):
                raise FrontmatterError("элемент списка после скаляра", lineno)
            target.append(_scalar(item.group("value"), lineno))
            continue

        match = _KEY.match(line)
        if not match:
            raise FrontmatterError("строка не разобрана", lineno)

        indent = len(match.group("indent"))
        key = match.group("key").strip()
        rest = match.group("rest")

        if indent > pending_indent and pending_key is not None:
            holder = out[pending_key]
            if not isinstance(holder, dict):
                if holder in (None, []):
                    holder = {}
                    out[pending_key] = holder
                else:
                    raise FrontmatterError("вложенная мапа после скаляра", lineno)
            holder[key] = _scalar(rest, lineno)
            continue

        value = _scalar(rest, lineno)
        out[key] = value
        if value is None:
            out[key] = []          # может стать списком или мапой
            pending_key = key
            pending_indent = indent
        else:
            pending_key = None
            pending_indent = indent

    # Ключи, за которыми так ничего и не пришло, — пустые, а не пустые списки.
    for key, value in list(out.items()):
        if value == []:
            out[key] = None
    return out
