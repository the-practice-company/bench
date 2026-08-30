#!/usr/bin/env python3
"""Форма коллекции: `README.md`, `views.base`, `items/` и первая запись.

Порядок обратный тому, как читается §20: сначала запись, потом единица.
Развернуть скелет, спросить и откатить отвергнуто — оборванный прогон
оставил бы пустую коллекцию, а пустая коллекция не сигналит ничем (§17).

Один генератор на две волны: этап 2 ADOPT зовёт эту же функцию. Поэтому
здесь нет ни одного допущения, верного только внутри MAINTAIN: аргументы
чистые, отчёта и кода возврата функция не знает, в `OPEN-THREADS.md` не
пишет. Отказ — исключение, и что с ним делать, решает вызывающий.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import paths as pathlib_rules

# Архетип зарабатывает существование готовым видом и готовым гейтом, а не
# шаблоном контента (§5). Множество закрыто.
ARCHETYPES = ("journal", "pipeline", "registry")

# Словарь принадлежит конвейеру. У журнала статуса нет вовсе, у реестра
# выраженного жизненного цикла нет по определению.
#
# Слова английские: §25 относит к форме закрытые машинные словари, которые
# рецепт заводит сам. Совпадение с зоной `decisions` каркаса — совпадение
# смысла, а не общий источник: словарь зоны объявлен в её README и правится
# автором вместе с ней, а этот — умолчание генератора для коллекции, которой
# ещё нет. Свести их в одну константу значило бы, что правка README зоны
# молча меняет форму всех будущих коллекций.
VOCABULARIES = {"pipeline": ("open", "decided", "revisited")}

# Форма вида — та же, что у фикстур волны 1 (`fixtures/green/decisions/
# views.base`): `filters` верхним уровнем, `views` со `groupBy` и `order`.
# Форма с блоком `sort:` разобрана и **отвергнута**: `_identifiers` в
# `scripts/basefile.py` вытаскивает из неё `property`, `direction` и `DESC`
# как имена полей, и гейт frontmatter начинает требовать их от каждой
# записи. Проверено разбором, а не выведено из документации.
_VIEW = {
    "journal": ("По дате", "created"),
    "pipeline": ("По статусу", "status"),
    "registry": ("По типу", "type"),
}


class NoContent(Exception):
    """Единица не заводится без содержимого. Это инвариант, а не ошибка ввода."""


def _readme(collection, archetype):
    title = collection.rsplit("/", 1)[-1]
    lines = ["---", "archetype: %s" % archetype]
    vocabulary = VOCABULARIES.get(archetype)
    if vocabulary:
        lines.append("values:")
        lines.append("  status:")
        lines.extend("    - %s" % value for value in vocabulary)
    lines.extend(["---", "", "# %s" % title, "",
                  "Коллекция архетипа `%s`." % archetype, ""])
    return "\n".join(lines)


def _views(collection, archetype):
    name, group = _VIEW[archetype]
    lines = [
        "filters:",
        "  and:",
        '    - file.inFolder("%s/items")' % collection,
        "views:",
        "  - type: table",
        "    name: %s" % name,
        "    groupBy: %s" % group,
        "    order:",
        "      - created",
        "",
    ]
    return "\n".join(lines)


def create(root, collection, archetype, record_name, record_text):
    """(созданные пути). Ничего не пишет, пока не проверено всё.

    Оба имени судятся до первой записи на диск, потому что зовёт эту функцию
    и ADOPT — по чужому дереву, где имя файла приходит извне. `..` в имени
    записи вывел бы её из коллекции, а то и из репозитория: незыблемое №6
    проверяется тем же примитивом волны 1, а не вторым прочтением пути.
    """
    if archetype not in ARCHETYPES:
        raise ValueError("архетип вне закрытого множества: %r" % (archetype,))
    if pathlib_rules.escapes_root(collection):
        raise ValueError("путь коллекции выводит за корень: %r" % (collection,))
    if not record_name or not (record_text or "").strip():
        raise NoContent("первая настоящая запись обязательна: %s" % collection)
    if "/" in record_name or "\\" in record_name or record_name in (".", ".."):
        raise ValueError("имя записи — имя файла, а не путь: %r" % (record_name,))
    root = Path(root)
    base = root / collection
    if base.exists():
        raise ValueError("путь уже занят: %s" % collection)

    created = [collection]
    (base / "items").mkdir(parents=True)
    (base / "README.md").write_text(_readme(collection, archetype),
                                    encoding="utf-8")
    created.append("%s/README.md" % collection)
    created.append("%s/items" % collection)
    (base / "items" / record_name).write_text(record_text, encoding="utf-8")
    created.append("%s/items/%s" % (collection, record_name))
    (base / "views.base").write_text(_views(collection, archetype),
                                     encoding="utf-8")
    created.append("%s/views.base" % collection)
    return sorted(created)
