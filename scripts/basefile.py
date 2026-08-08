"""Статический разбор views.base.

Извлекает: пути фильтров, свойства с уровнем требования, имена формул.
Ничего не вычисляет — секция «Общее для гейтов»: гейту нужен сканер.
"""

import re

_INFOLDER = re.compile(r'file\.inFolder\(\s*["\']([^"\']+)["\']\s*\)')
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DQUOTED = re.compile(r'"[^"]*"')

# Где упомянуто поле — таково требование к нему (секция 14).
_REQUIRED_KEYS = ("filters", "sort", "groupBy")
_KNOWN_KEYS = ("order", "columnSize")

_STOPWORDS = {
    "and", "or", "not", "file", "inFolder", "table", "cards", "list",
    "name", "true", "false", "null", "now", "date", "if", "then", "else",
}


class Base:
    def __init__(self, folders, required, known, formulas):
        self.folders = folders
        self.required = required
        self.known = known
        self.formulas = formulas


def _identifiers(chunk):
    # Пути папок (inFolder) и содержимое двойных кавычек — литеральные
    # значения фильтров, а не имена свойств. Уже собраны отдельно (folders)
    # или несущественны для сканера.
    chunk = _INFOLDER.sub(" ", chunk)
    chunk = _DQUOTED.sub(" ", chunk)
    return {m.group(0) for m in _IDENT.finditer(chunk)} - _STOPWORDS


def _section(text, key):
    """Грубая нарезка по ключу верхнего или вложенного уровня.

    Секция кончается на первой строке с отступом не больше, чем у ключа.
    """
    out = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(key + ":"):
            continue
        indent = len(line) - len(line.lstrip(" -"))
        out.append(stripped[len(key) + 1:])
        for follower in lines[i + 1:]:
            if follower.strip() == "":
                continue
            follower_indent = len(follower) - len(follower.lstrip(" -"))
            if follower_indent <= indent:
                break
            out.append(follower)
    return "\n".join(out)


def parse_base(text):
    folders = _INFOLDER.findall(text)

    formula_block = _section(text, "formulas")
    formulas = set()
    formula_fields = {}
    for line in formula_block.split("\n"):
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        name, expression = stripped.split(":", 1)
        name = name.strip().strip("-").strip()
        if not name:
            continue
        formulas.add(name)
        formula_fields[name] = _identifiers(expression)

    required = set()
    known = set()
    for key in _REQUIRED_KEYS:
        required |= _identifiers(_section(text, key))
    for key in _KNOWN_KEYS:
        known |= _identifiers(_section(text, key))

    # Формула — не поле записи. Её имя вычитается, а поля из её выражения
    # наследуют уровень требования того места, где формула употреблена.
    for name in formulas:
        if name in required:
            required.discard(name)
            required |= formula_fields.get(name, set())
        if name in known:
            known.discard(name)
            known |= formula_fields.get(name, set())

    known -= required
    return Base(folders, required, known, formulas)
