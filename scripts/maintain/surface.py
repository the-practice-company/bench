#!/usr/bin/env python3
"""Поверхность формы: единственное, что MAINTAIN вправе записать.

Статична и объявлена здесь литералом. Выведенная из того, что прогон
записал, она сделала бы `content_diff` тавтологией: проверка исключила бы
ровно то, что изменилось, и не покраснела бы никогда.

Всё, чего в перечислении нет, — содержимое: тело записи, значение
существующего поля, проза README, `.link-allow`, вложения.

**Зонового списка здесь нет, и это расхождение со спекой волны**, вынесенное
автору. Спека иллюстрирует правило фразой «любой файл в `core`, `sources`,
`knowledge`, `inbox`», а само правило строкой выше говорит другое: «всё,
чего в таблице нет, — содержимое». `views.base` в таблице есть — «любой
коллекции», — и коллекция в `core` существует (`core/people`, наблюдение 4
фикстуры). Зоновый запрет поверх перечисления заставил бы MAINTAIN читать
собственную законную починку вида как правку содержимого и откатывать себя
на каждом прогоне. Исключение над перечислением остаётся ровно одно — ниже,
и оно не про содержимое.

Здесь же живёт разбор гранулярности «секция»: и тот, кто чинит форм-секцию
`CLAUDE.md`, и тот, кто доказывает, что проза рядом уцелела, обязаны читать
одно определение секции. Два — разошлись бы, и расхождение выглядело бы как
законная починка, откатывающая себя на каждом прогоне.
"""

import re
import sys
from fnmatch import fnmatchcase
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import zones


class Entry:
    """Строка поверхности: путь и гранулярность правки."""

    __slots__ = ("pattern", "what", "why")

    def __init__(self, pattern, what, why):
        self.pattern = pattern
        self.what = what
        self.why = why


SURFACE = (
    Entry("**/views.base", "bytes",
          "вид принадлежит плагину целиком (§13)"),
    Entry("**/README.md#frontmatter:archetype,values", "frontmatter-value",
          "два ключа объявления коллекции; тело README не трогается"),
    Entry(".claude/rules/*.md", "bytes",
          "правила рецепта принадлежат плагину целиком"),
    Entry("CLAUDE.md#section:Zone map,Placement rule", "section",
          "форм-секции побайтово из каркаса; остальное — авторское"),
    Entry("areas/README.md#table", "table-row",
          "строка таблицы — форма; фраза назначения в ней — авторская"),
    Entry("*/README.md#absent", "create",
          "README зоны создаётся, если файла нет"),
    Entry("**/items/*.md#frontmatter:absent-key", "frontmatter-add",
          "добавление отсутствующего ключа; существующее не переписывается"),
    Entry(".gitignore#append", "append",
          "дописывание строк каркаса; авторские не удаляются"),
    Entry(".claude/settings.json#merge:permissions.deny,claudeMdExcludes",
          "merge", "слияние без дублей"),
    Entry(".twinkle-repo-builder#json:version", "json-value",
          "значение версии рецепта"),
    Entry("OPEN-THREADS.md#append", "append",
          "дописывание; существующие строки не изменяются"),
)


def _inside_a_submodule(rel):
    """Внутренность чужого репозитория в `knowledge/`.

    Единственное исключение над перечислением, и оно не про содержимое, а
    про чужой репозиторий: рецепт запрещает туда писать статически
    (`zones.DENY_PATTERNS` — `knowledge/*/**`), и коллекций этого дерева там
    не бывает. `knowledge/README.md` сам по себе исключением не накрыт: он
    принадлежит зоне, а не сабмодулю, и создаётся из каркаса (наблюдение 1
    фикстуры).

    Имя зоны берётся из `zones.READ_ONLY`, второго списка здесь нет.
    """
    parts = rel.split("/")
    return len(parts) >= 3 and parts[0] in zones.READ_ONLY


def _match(rel, pattern):
    """Посегментное сопоставление. `fnmatchcase` здесь не годится: его `*`
    пересекает косую, и `*/README.md` совпал бы с `a/b/c/README.md`, то есть
    поверхность формы стала бы шире отсуженной. Подгонять поверхность под
    сопоставитель нельзя — она и есть предмет спора."""
    if pattern.startswith("**/"):
        tail = pattern[3:]
        parts = rel.split("/")
        return any(_match("/".join(parts[start:]), tail)
                   for start in range(len(parts)))
    expected = pattern.split("/")
    actual = rel.split("/")
    if len(expected) != len(actual):
        return False
    return all(fnmatchcase(part, want)
               for part, want in zip(actual, expected))


def covers(rel, what):
    """Разрешает ли поверхность правку такого рода по этому пути."""
    if _inside_a_submodule(rel):
        return False
    return any(_match(rel, entry.pattern.split("#")[0])
               for entry in SURFACE if entry.what == what)


def names(rel, what):
    """Имена, названные строкой поверхности: секции `CLAUDE.md`, ключи
    frontmatter README коллекции, ключи слияния настроек.

    Второго такого списка в пакете нет, и это не косметика. Список секций,
    объявленный отдельно в том, кто чинит, разошёлся бы со списком в том,
    кто доказывает «содержимое не тронуто», — и расхождение выглядело бы
    как законная починка, откатывающая себя на каждом прогоне.
    """
    if _inside_a_submodule(rel):
        return ()
    out = []
    for entry in SURFACE:
        if entry.what != what:
            continue
        head, _, fragment = entry.pattern.partition("#")
        if not _match(rel, head):
            continue
        _, _, listed = fragment.partition(":")
        out.extend(name.strip() for name in listed.split(",") if name.strip())
    return tuple(out)


# Секция второго уровня. `###` сюда не попадает: `\s+` требует пробела, а
# после `##` у вложенного заголовка стоит решётка.
_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.M)


def _span(text, title):
    """(начало, конец) секции вместе с заголовком, или `None`.

    Границей служит следующий заголовок второго уровня, а не пустая строка:
    секция формы — это заголовок и всё под ним до соседа, включая вложенные
    подзаголовки.
    """
    matches = list(_HEADING.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1) != title:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return match.start(), end
    return None


def section(text, title):
    """Секция целиком или пустая строка, если такой секции нет."""
    span = _span(text, title)
    return text[span[0]:span[1]] if span else ""


def replace_section(text, title, replacement):
    """Замена секции по индексам, а не по подстроке.

    `str.replace` заменил бы первое вхождение текста секции, а оно не
    обязано быть той самой секцией: две одинаковые таблицы в одном файле —
    не выдумка, и вырезало бы тогда чужую.
    """
    span = _span(text, title)
    if span is None:
        return text
    return text[:span[0]] + replacement + text[span[1]:]


def without_sections(text, titles):
    """Остаток файла без названных секций — то, что обязано совпасть побайтово.

    Вырезание идёт **с конца**: вырезав первую секцию, спан второй сдвинулся
    бы на её длину, и из файла ушёл бы кусок соседнего текста.
    """
    spans = sorted((span for span in (_span(text, t) for t in titles) if span),
                   reverse=True)
    for start, end in spans:
        text = text[:start] + text[end:]
    return text
