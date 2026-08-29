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
"""

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
