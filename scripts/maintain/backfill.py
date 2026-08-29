#!/usr/bin/env python3
"""`backfill`: три исхода на запись и ни одного четвёртого.

`unknown` — единственный синтетический токен рецепта, введённый волной 4 для
`created` без истории. Второго не заводится. Он не является датой и не станет
ею никогда — именно то свойство, ради которого §20 запрещает молчаливую
подстановку: подставленное значение от настоящего неотличимо, `unknown`
отличим всегда.

Помечать синтетику соседним полем-списком отвергнуто: второй учёт того же
факта, а §22 уже запретил хранить выводимое. Токен на месте самодостаточен,
происхождение лежит в `field-map`.

**Пишется только отсутствующий ключ** — ровно строка поверхности формы
`**/items/*.md#frontmatter:absent-key`. Ключ, стоящий пустым, не трогается:
дописать второй такой же значило бы сделать frontmatter неразбираемым
(повторный ключ — исключение разбора), а переписать — выйти за поверхность.
Пустое значение остаётся находкой гейта и остаётся авторским.

**Записи, которых не прочитать, не исчезают.** `continue` без следа — это и
есть молчаливая заглушка, запрещённая незыблемым №4: запись уходит в отчёт с
токеном из закрытого списка `field_map.TOKENS`.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import check_frontmatter
from scripts.adopt import dates
from scripts.adopt.dates import UNKNOWN
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter
from scripts.maintain import field_map

# Второго перечисления исходов в пакете нет. Своё разошлось бы с тем, по
# которому `field_map.render` роняет строку, и разошедшаяся половина вылезла
# бы исключением на живой таблице — там, где чинить дороже всего.
OUTCOMES = field_map.ORIGINS

_DELIM = "---"
_DATE_IN_NAME = re.compile(r"\A(\d{4}-\d{2}-\d{2})")


def _git_first_commit(root, rel, _text):
    """Первый коммит пути — тем же кодом, которым его считает волна 4.

    Второй такой функции в пакете нет намеренно: «что git говорит про дату
    создания» — один вопрос, и две реализации разошлись бы на первом же
    переименовании. Там же живут и `:(literal)`, и авторская дата вместо
    коммиттерской, и обе не догадки, а измеренные поломки.
    """
    value = dates.created(root, rel)
    return None if value == UNKNOWN else value


def _filename_date(_root, rel, _text):
    match = _DATE_IN_NAME.match(Path(rel).name)
    return match.group(1) if match else None


def _filename_source(_root, rel, _text):
    stem = Path(rel).stem
    return stem.split("--", 1)[0] if "--" in stem else None


def _body_words(_root, _rel, text):
    body = text.split(_DELIM, 2)[-1]
    return str(len(body.split()))


# Правила поимённо. Множество расширяется по потребителю, §2 задаёт правило.
RULES = {
    "git-first-commit": _git_first_commit,
    "filename-date": _filename_date,
    "filename-source": _filename_source,
    "body-words": _body_words,
}

# Какое правило пробуется для какого поля, по порядку.
#
# У `created` имя файла идёт **раньше** git: дата в имени — утверждение
# автора о событии, дата первого коммита — обстоятельство того, когда запись
# донесли до репозитория. Обратный порядок отдал бы записи, внесённой задним
# числом, дату внесения — тот самый «`created`, получающий дату прогона»,
# который спека волны называет измеренной поломкой.
FOR_FIELD = {
    "created": ("filename-date", "git-first-commit"),
    "source": ("filename-source",),
    "words": ("body-words",),
}


def _vocabulary_declared(root, collection, field):
    """Объявлен ли у поля словарь. `None` — объявление не прочитано.

    Определение словаря берётся у гейта, который и производит
    `value-outside-vocabulary`: вся третья ветка обоснована именно тем, что
    `unknown` стал бы его находкой, и читать «что такое объявленный словарь»
    двумя способами здесь нельзя.

    Нечитаемое объявление не считается отсутствующим: коллекция со словарём
    превратилась бы в коллекцию без него, и `unknown` встал бы туда, где он
    запрещён. Незыблемое №4 дословно — невосстановимое уходит в отчёт.
    """
    problems = []
    _, vocabulary = check_frontmatter._declaration(
        Path(root), Path(root) / collection / "README.md", problems)
    if problems:
        return None
    return field in vocabulary


def _frontmatter_starts(text):
    """Открыт ли файл разделителем frontmatter. Пустой словарь от разбора
    этого не говорит: так же выглядит и запись с пустым frontmatter."""
    head = text.split("\n", 1)[0]
    return head.strip() == _DELIM


def _insert(text, field, value):
    """Текст с добавленным ключом — первой строкой frontmatter.

    Ключ кладётся строкой, а не перенабором frontmatter: перенабранный
    целиком блок переставил бы авторские ключи и кавычки, а само-проверка
    сравнивает байты тела и значения полей.
    """
    lines = text.split("\n")
    return "\n".join([lines[0], "%s: %s" % (field, value)] + lines[1:])


def plan(root, collection, field):
    """(строки `field-map`, непрочитанные записи). Ничего не пишет.

    Вторая половина — словарь «путь → токен из `field_map.TOKENS`»: запись,
    которую не разобрать, обязана быть названа, а не пропущена.
    """
    root = Path(root)
    declared = _vocabulary_declared(root, collection, field)
    items = root / collection / "items"
    rows, skipped = [], {}
    for path in sorted(items.glob("*.md")) if items.is_dir() else []:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped[rel] = "undecodable"
            continue
        if not _frontmatter_starts(text):
            skipped[rel] = "not-a-record"
            continue
        try:
            fields = parse_frontmatter(text)
        except FrontmatterError:
            skipped[rel] = "unparseable-frontmatter"
            continue
        if field in fields:
            continue
        value, used = None, None
        for name in FOR_FIELD.get(field, ()):
            value = RULES[name](root, rel, text)
            if value is not None:
                used = name
                break
        if value is not None:
            rows.append((rel, field, "", value, "computed", used))
        elif declared is None:
            rows.append((rel, field, "", "", "deferred", "vocabulary-unreadable"))
        elif declared:
            rows.append((rel, field, "", "", "deferred", "vocabulary-declared"))
        else:
            rows.append((rel, field, "", UNKNOWN, "synthetic", "no-rule"))
    return rows, skipped


def _write(root, rows):
    """Записать всё, что не `deferred`. Возвращает пути по возрастанию."""
    written = []
    for rel, field, _before, value, origin, _rule in rows:
        if origin == "deferred":
            continue
        path = Path(root) / rel
        path.write_text(_insert(path.read_text(encoding="utf-8"), field, value),
                        encoding="utf-8")
        written.append(rel)
    return sorted(written)


def _line(rel, field, why):
    """Путь и поле **в одной строке**: `field_map.audit` засчитывает названным
    только их встречу, и не зря — путь из одного сообщения и поле из другого
    вместе не говорят про эту запись ничего."""
    return "%s %s (%s)" % (rel, field, why)


def report(rows, skipped):
    """Что осталось автору: отложенное и непрочитанное.

    Синтетики здесь нет, и это не пропуск: незыблемое №4 требует одного из
    двух, а токен `unknown` лежит в самой записи и виден там, где значение
    читают. Строка отчёта была бы вторым учётом того же факта.
    """
    lines = []
    deferred = [row for row in rows if row[4] == "deferred"]
    if deferred:
        lines.append("отложено, значение принадлежит автору:")
        lines.extend(_line(row[0], row[1], row[5]) for row in deferred)
    if skipped:
        lines.append("не прочитано как запись:")
        lines.extend("%s (%s)" % pair for pair in sorted(skipped.items()))
    return "\n".join(lines) + "\n" if lines else ""


def run(root, collection, field):
    """(строки таблицы, отчёт). Пишет всё, что не `deferred`."""
    rows, skipped = plan(root, collection, field)
    _write(root, rows)
    return rows, report(rows, skipped)


def run_silently(root, collection, field):
    """Что MAINTAIN вправе сделать без спроса: **только полностью вычислимое**.

    §19 относит backfill к молчаливому. Здесь это сужено: backfill трогает
    каждую запись коллекции, и режим без присмотра не имеет права
    проштамповать `unknown` по двумстам файлам, не имея кому это сказать.

    Непрочитанная запись останавливает прогон наравне с невычислимой: «всё
    вычислимо» и «про часть записей ничего не известно» — разные утверждения.
    """
    rows, skipped = plan(root, collection, field)
    unclear = [row for row in rows if row[4] != "computed"]
    if not unclear and not skipped:
        return _write(root, rows), ""
    lines = ["backfill %s не выполнен молча: невычислимо у %d записей"
             % (field, len(unclear) + len(skipped))]
    lines.extend(_line(row[0], row[1], row[4]) for row in unclear)
    lines.extend(_line(rel, field, token) for rel, token in sorted(skipped.items()))
    return [], "\n".join(lines) + "\n"


def write_table(root, collection, field, rows):
    """Положить таблицу мутации в `tmp/`. Возвращает путь от корня.

    Первый и единственный производитель формата в пакете: `field_map.name` и
    `field_map.render` до этой двери не звал никто, и формат массовой
    мутации был описан, проверен и не производился ничем.

    Кого таблица описывает, решает вызывающий. Строка `deferred` в ней
    законна — это исход, а не пропуск; таблицы нет только там, где не
    записано ни байта и записать было нечего.
    """
    rel = field_map.name("backfill", (collection, field))
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(field_map.render(rows), encoding="utf-8")
    return rel


def main(argv=None):
    """Дверь для скилла `extend-structure`: заполнить одно поле в одной
    коллекции.

    `--silently` — то, что вправе сделать режим без присмотра: пишет только
    полностью вычислимое, а на первой невычислимой записи не пишет ничего и
    отвечает отказом. Отказ — код 2, а не тишина с нулём: «поле не
    заполнено» обязано доехать до вызвавшего, иначе молчаливой становится
    сама несделанная работа.

    Отложенное в обычном режиме кодом не красится: команда сделала ровно то,
    что ей позволено, и назвала остаток. Красный код здесь означал бы, что
    значение, принадлежащее автору, — поломка.
    """
    parser = argparse.ArgumentParser(
        description="fill in a missing field: computed, synthetic or deferred")
    parser.add_argument("root")
    parser.add_argument("collection")
    parser.add_argument("field")
    parser.add_argument("--silently", action="store_true",
                        help="писать, только если вычислимо всё; иначе не писать ничего")
    args = parser.parse_args(argv)
    root = Path(args.root)

    # Опечатка в имени коллекции доезжала до конца зелёной: записей нет,
    # потому что нет папки, — и отчёт «строк ноль» неотличим от коллекции,
    # где поле уже стоит у каждой записи. Молчаливым тут становится весь
    # прогон, а не одно значение.
    if not (root / args.collection / "items").is_dir():
        sys.stdout.write("отказ: у коллекции нет папки items: %s\n"
                         % args.collection)
        return EXIT_VIOLATION

    # Строки считаются здесь, до мутации, потому что после неё поле стоит у
    # каждой записи и таблица вышла бы пустой. `run` и `run_silently` считают
    # их заново сами: решение о том, что писать, остаётся в одном месте, а
    # `plan` ничего не пишет и повторного чтения дереву не стоит.
    rows, _ = plan(root, args.collection, args.field)
    if args.silently:
        written, text = run_silently(root, args.collection, args.field)
        sys.stdout.write(text)
        if not written:
            return EXIT_VIOLATION
    else:
        _, text = run(root, args.collection, args.field)
        sys.stdout.write(text)
    sys.stdout.write("таблица: %s\n"
                     % write_table(root, args.collection, args.field, rows))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
