#!/usr/bin/env python3
"""`extend-structure`: заводит единицу только вместе с её содержимым.

Порядок обратный §20: сначала запись, потом единица. Инвариант выполняется
механически ровно одним способом — не создавать до того.

Каждая команда: проверить всё, потом писать; отказ — код 2 с названной
причиной и вопросом в `OPEN-THREADS.md`. Форму коллекции команда не знает —
её знает `form_collection`, тот же генератор, который зовёт этап 2 ADOPT.
Второй копии формы в пакете нет.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import paths as path_rules
from scripts.basefile import parse_base
from scripts.findings import EXIT_OK, EXIT_VIOLATION, Finding, Report
from scripts.maintain import form_collection

DIRECTIONS_HEADING = "## Directions"
# Строка «пусто» каркаса. Строкой перечисления она не является и уступает
# место первому направлению: сравнение по началу строки, потому что за
# маркером идёт авторское объяснение.
EMPTY_LISTING = "**Nothing here yet.**"
_NAME = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")
# Имя вида целиком, а не подстрокой: `"name: Всё" in text` считало бы имя
# занятым и при `name: Всё вместе`, то есть команда отказывала бы, ссылаясь
# на вид, которого нет.
_VIEW_NAME = re.compile(r"\A\s*(?:-\s+)?name:\s*(.*?)\s*\Z")
THREADS = "OPEN-THREADS.md"


def _ask(root, key, question):
    """Вопрос в открытые нити. Идемпотентно: у вопроса стабильный ключ."""
    path = Path(root) / THREADS
    text = path.read_text(encoding="utf-8") if path.exists() else "# Open threads\n"
    if key in text:
        return
    path.write_text(text.rstrip("\n") + "\n- %s <!-- %s -->\n" % (question, key),
                    encoding="utf-8")


def _remove(root, collection):
    """Снос только что созданного. Обратимо по построению: до команды тут
    не было ничего, поэтому чужого содержимого здесь быть не может.

    Пустые промежуточные каталоги уходят вместе с единицей: `mkdir(parents)`
    создаёт их заодно, и оставленный `projects/deep/` — это ровно та
    пережившая откат половина единицы, ради запрета которой заведён
    критерий 3. Каталог с чем-то внутри не трогается: он был до команды.
    """
    root = Path(root)
    base = root / collection
    for path in sorted(base.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    if base.exists():
        base.rmdir()
    parent = base.parent
    while parent != root and root in parent.parents and parent.is_dir():
        if any(parent.iterdir()):
            break
        parent.rmdir()
        parent = parent.parent


def add_collection(root, collection, archetype, record_name, record_text):
    root = Path(root)
    try:
        created = form_collection.create(root, collection, archetype,
                                         record_name, record_text)
    except form_collection.NoContent:
        _ask(root, "add-collection %s" % collection,
             "какая первая настоящая запись ляжет в %s" % collection)
        return ("отказ: коллекция не заводится без первой записи: %s\n"
                % collection), EXIT_VIOLATION
    except ValueError as error:
        return "отказ: %s\n" % error, EXIT_VIOLATION

    # Постусловие, а не обход дерева. Обходом класс ловил бы и пустые
    # коллекции слоя спроса, у которых своё имя (`empty-collection`):
    # то — наблюдение о дереве, это — нарушенное обещание команды о себе.
    items = root / collection / "items"
    if not (items.is_dir() and sorted(items.glob("*.md"))):
        _remove(root, collection)
        return (Report([Finding("structure-without-content", collection, 1,
                                "единица дошла до диска без записи")]).render()
                + "\nсоздание отменено\n"), EXIT_VIOLATION
    return ("заведена коллекция: %s\nсоздано: %s\n"
            % (collection, ", ".join(created))), EXIT_OK


def _heading_index(lines):
    """Номер строки заголовка перечисления или None. Строка целиком:
    заголовок — место, а не подстрока где-нибудь в прозе."""
    for i, line in enumerate(lines):
        if line.strip() == DIRECTIONS_HEADING:
            return i
    return None


def _with_direction(text, row):
    """Текст README зоны со строкой перечисления. None — заголовка нет.

    Строка «пусто» замещается первым направлением; дальше новые строки
    ложатся **в конец** списка: порядок перечисления авторский, и вставка
    поверх первой строки переставляла бы его при каждом заведении.
    """
    lines = text.split("\n")
    start = _heading_index(lines)
    if start is None:
        return None
    i = start + 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].strip().startswith(EMPTY_LISTING):
        lines[i] = row
        return "\n".join(lines)
    while i < len(lines) and lines[i].lstrip().startswith("-"):
        i += 1
    lines.insert(i, row)
    return "\n".join(lines)


def add_area(root, name, purpose):
    root = Path(root)
    if not _NAME.match(name):
        return "отказ: не имя папки: %s\n" % name, EXIT_VIOLATION
    if (root / "areas" / name).exists():
        return "отказ: имя занято: %s\n" % name, EXIT_VIOLATION
    if not (purpose or "").strip():
        _ask(root, "add-area %s" % name,
             "какое назначение у направления %s" % name)
        return ("отказ: направление не заводится без фразы назначения: %s\n"
                % name), EXIT_VIOLATION

    readme = root / "areas" / "README.md"
    # Отсутствующий README — тот же случай, что README без заголовка: класть
    # строку некуда. Второго места для перечисления команда не выдумывает.
    text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    row = "- [[areas/%s/README|%s]] — %s" % (name, name, purpose.strip())
    listing = _with_direction(text, row)
    if listing is None:
        return "отказ: в areas/README.md нет заголовка перечисления\n", EXIT_VIOLATION

    (root / "areas" / name).mkdir(parents=True)
    (root / "areas" / name / "README.md").write_text(
        "# %s\n\n%s\n" % (name, purpose.strip()), encoding="utf-8")
    readme.write_text(listing, encoding="utf-8")
    return "заведено направление: areas/%s\n" % name, EXIT_OK


def _view_names(text):
    out = []
    for line in text.split("\n"):
        match = _VIEW_NAME.match(line)
        if match:
            out.append(match.group(1))
    return out


def _with_view(text, name):
    """Текст `views.base` с дописанным видом. None — списка видов нет.

    Форма — та же, что у `form_collection._views`, за вычетом `groupBy`:
    группировка требует поля от каждой записи (секция 14), а поля этого
    команде никто не называл. Добавить его по догадке значило бы покрасить
    гейт frontmatter собственной правкой.
    """
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.rstrip() == "views:":
            start = i
            break
    if start is None:
        return None
    last = start
    i = start + 1
    while i < len(lines):
        line = lines[i]
        if line.strip() and not (line.startswith((" ", "\t")) or line.startswith("-")):
            break
        if line.strip():
            last = i
        i += 1
    lines[last + 1:last + 1] = ["  - type: table", "    name: %s" % name,
                                "    order:", "      - created"]
    return "\n".join(lines)


def add_view(root, collection, name):
    root = Path(root)
    base_path = root / collection / "views.base"
    if not base_path.exists():
        return "отказ: у %s нет views.base\n" % collection, EXIT_VIOLATION
    if not (name or "").strip():
        return "отказ: вид не заводится без имени\n", EXIT_VIOLATION
    text = base_path.read_text(encoding="utf-8")
    if name in _view_names(text):
        return "отказ: имя вида занято: %s\n" % name, EXIT_VIOLATION

    # Проверяется только статически разрешимый случай: папка, названную
    # `file.inFolder(...)`, пуста. Фильтр не вычисляется — движка фильтров
    # Obsidian Bases пакет не строит, и реализация фильтра по догадке, на
    # основании которой **удаляется** авторский вид, была бы худшим обменом
    # этой волны.
    base = parse_base(text)
    for folder in sorted(set(base.folders)):
        target = root / folder
        if not target.is_dir() or not sorted(target.glob("*.md")):
            return ("отказ: file.inFolder называет папку с нулём записей: %s\n"
                    % folder), EXIT_VIOLATION

    updated = _with_view(text, name)
    if updated is None:
        return "отказ: в %s нет списка видов\n" % collection, EXIT_VIOLATION
    base_path.write_text(updated, encoding="utf-8")
    return "добавлен вид: %s\n" % name, EXIT_OK


def _record_from_file(root, rel):
    """(текст, имя, отказ). Ровно один из трёх последних не None.

    Непрочитанный вход — **не** пустая запись. Свести их в один исход
    значило бы дописать в открытые нити вопрос «какая первая запись ляжет
    сюда» автору, который эту запись уже написал; незыблемое №4 запрещает
    ровно такую подмену невосстановимого молчанием.

    Путь считается от корня, а не от рабочего каталога: команду зовут из
    скилла, у которого корень — аргумент, и два прочтения одного аргумента
    расходились бы ровно тогда, когда корень не совпал с рабочим каталогом.
    """
    if path_rules.escapes_root(rel):
        return None, None, "отказ: путь записи вне корня репозитория: %s" % rel
    path = Path(root) / rel
    try:
        return path.read_text(encoding="utf-8"), path.name, None
    except (OSError, UnicodeDecodeError) as error:
        return None, None, "отказ: файл первой записи не прочитан: %s (%s)" % (
            rel, type(error).__name__)


def _add_collection_from_args(root, args):
    text, name = args.record_text, args.record_name
    if args.record_file is not None:
        text, from_file, refusal = _record_from_file(root, args.record_file)
        if refusal:
            return refusal + "\n", EXIT_VIOLATION
        name = name or from_file
    # Имя записи не выводится ниоткуда: придумать его — сочинить содержимое.
    # Отказ называет **эту** причину и вопроса в нити не пишет: спрашивать
    # про запись, которая уже передана текстом, не о чем.
    if text is not None and not name:
        return "отказ: имя записи не названо: --record-name\n", EXIT_VIOLATION
    return add_collection(root, args.collection, args.archetype,
                          record_name=name, record_text=text)


def main(argv=None):
    """Три команды одной дверью. Умолчания подкоманды нет: опечатка в имени
    команды стала бы записью в дерево, которой никто не просил."""
    parser = argparse.ArgumentParser(
        description="add a collection, an area or a view — record first, unit second")
    parser.add_argument("root")
    commands = parser.add_subparsers(dest="command", required=True)

    collection = commands.add_parser("add-collection")
    collection.add_argument("collection")
    collection.add_argument("--archetype", required=True,
                            choices=list(form_collection.ARCHETYPES))
    collection.add_argument("--record-name",
                            help="имя файла первой записи; по умолчанию — имя файла, из которого она взята")
    source = collection.add_mutually_exclusive_group()
    source.add_argument("--record-file", help="путь первой записи от корня репозитория")
    source.add_argument("--record-text", help="текст первой записи целиком")

    area = commands.add_parser("add-area")
    area.add_argument("name")
    area.add_argument("--purpose", default="",
                      help="фраза назначения; без неё направление не заводится")

    view = commands.add_parser("add-view")
    view.add_argument("collection")
    view.add_argument("name")

    args = parser.parse_args(argv)
    if args.command == "add-collection":
        report, code = _add_collection_from_args(args.root, args)
    elif args.command == "add-area":
        report, code = add_area(args.root, args.name, args.purpose)
    else:
        report, code = add_view(args.root, args.collection, args.name)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
