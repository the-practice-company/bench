"""Статический разбор views.base.

Извлекает: пути фильтров, свойства с уровнем требования, имена формул.
Ничего не вычисляет — секция «Общее для гейтов»: гейту нужен сканер.
"""

import re

_INFOLDER = re.compile(r'file\.inFolder\(\s*["\']([^"\']+)["\']\s*\)')
# file.hasProperty("X") называет свойство X явно — это не литеральное
# значение и не поле "hasProperty", а обращение к полю по имени.
_HASPROPERTY = re.compile(r'\.hasProperty\(\s*["\']([^"\']+)["\']\s*\)')
# note["X"] / file["X"] — доступ к свойству по индексу, тоже явное имя.
_BRACKET = re.compile(r'(?:note|file)\[\s*["\']([^"\']+)["\']\s*\]')
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DQUOTED = re.compile(r'"[^"]*"')
# Одинарные кавычки в DQL — то же самое литеральное значение сравнения,
# но только рядом с оператором: одинарными кавычками в этом файле также
# оборачивают YAML-значение целиком (см. SAMPLE в тестах), и слепая
# вырезка испортила бы такие строки.
_SQUOTED_LITERAL = re.compile(r"(?:!=|==)\s*'[^']*'")

# Где упомянуто поле — таково требование к нему (секция 14).
_REQUIRED_KEYS = ("filters", "sort", "groupBy")
_KNOWN_KEYS = ("order", "columnSize")

_STOPWORDS = {
    "and", "or", "not", "file", "note", "inFolder", "hasProperty",
    "table", "cards", "list",
    "name", "true", "false", "null", "now", "date", "if", "then", "else",
}


class Base:
    def __init__(self, folders, required, known, formulas):
        self.folders = folders
        self.required = required
        self.known = known
        self.formulas = formulas


def _identifiers(chunk):
    # Путь папки (inFolder) — литеральное значение, уже собрано отдельно
    # (folders) и несущественно для сканера полей.
    chunk = _INFOLDER.sub(" ", chunk)

    # hasProperty(...) и обращение по индексу называют свойство явно —
    # имя нужно забрать до того, как остальные кавычки будут вырезаны
    # как литералы.
    props = set()

    def _take(match):
        props.add(match.group(1))
        return " "

    chunk = _HASPROPERTY.sub(_take, chunk)
    chunk = _BRACKET.sub(_take, chunk)

    # Всё, что осталось в кавычках, — литеральные значения фильтров
    # (например, `status != "closed"`), а не имена свойств.
    chunk = _DQUOTED.sub(" ", chunk)
    chunk = _SQUOTED_LITERAL.sub(" ", chunk)

    idents = {m.group(0) for m in _IDENT.finditer(chunk)} - _STOPWORDS
    return idents | props


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
