#!/usr/bin/env python3
"""Машинная таблица массовой мутации и сходимость счётчиков.

Один формат и один модуль на все мутации волн 4 и 5. Формат на команду
отвергнут ценой, которую спека уже измерила: две копии парсера, одна из
которых не исполняется никогда.

TSV с заголовком, сортировка по пути, ноль абсолютных путей, часы не
читаются — те же правила, что у отчётов гейтов и у `scan-tree`.

Массовая мутация — изменяющая больше одного уже существующего файла;
создание новых под определение не подпадает.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import paths as path_rules
from scripts.findings import Finding

COLUMNS = ("path", "field", "before", "after", "origin", "rule")

# Три исхода на запись, и ни одного четвёртого.
ORIGINS = ("computed", "synthetic", "deferred")

# Закрытый список объясняющих токенов. Свободный токен позволил бы
# объяснить расхождение любым словом, то есть не объяснить ничем.
TOKENS = ("undecodable", "unparseable-frontmatter", "not-a-record", "dirty-path")


def name(operation, arguments):
    """Имя файла таблицы: из операции и аргументов, **никогда** из даты.

    Метка времени вернула бы часы и сломала побайтовую воспроизводимость.
    Перезапись прежнего файла законна: `tmp/` транзитна, прошлый прогон
    лежит в git.

    Одиночный аргумент принимается и строкой: строка — последовательность
    символов, и разобранная как список аргументов она дала бы имя по
    буквам, ничего про это не сказав.
    """
    if isinstance(arguments, str):
        arguments = (arguments,)
    parts = [operation] + [str(a).replace("/", "-") for a in arguments]
    return "tmp/field-map-%s.tsv" % "-".join(parts)


def render(rows):
    """TSV таблицы. Строка, которой нельзя верить, роняет вызов, а не едет.

    Четыре отказа, и каждый — про молчание, а не про красоту: путь вне
    корня, ширина не та, разделитель внутри ячейки (сдвинул бы колонки),
    происхождение вне закрытого множества. Пятый — та же пара
    `(путь, поле)` дважды: `content_diff` кладёт строки в словарь по этой
    паре, из двух уцелеет одна, и какая именно — не сказано нигде.
    """
    out = ["\t".join(COLUMNS)]
    seen = set()
    for row in sorted(rows):
        if len(row) != len(COLUMNS):
            raise ValueError("строка таблицы не той ширины: %r" % (row,))
        cells = [str(cell) for cell in row]
        if path_rules.escapes_root(cells[0]):
            raise ValueError("путь вне корня репозитория: %r" % (cells[0],))
        if row[4] not in ORIGINS:
            raise ValueError("происхождение вне закрытого множества: %r" % (row[4],))
        for cell in cells:
            if "\t" in cell or "\n" in cell:
                raise ValueError("разделитель внутри ячейки: %r" % (cell,))
        key = (cells[0], cells[1])
        if key in seen:
            raise ValueError("пара «путь, поле» в таблице дважды: %r" % (key,))
        seen.add(key)
        out.append("\t".join(cells))
    return "\n".join(out) + "\n"


def reconcile(expected, rows, explained):
    """Дифф ожидаемого и фактического, обе половины.

    Ожидаемое считается **до** мутации из множества записей коллекции —
    того же, которое выводит гейт frontmatter из `file.inFolder(...)`.
    Фактическое — строки таблицы. Кто это множество перечисляет и что
    сверка доказывает, а что нет, — в `backfill.expected_records`;
    до неё у этой функции не было производителя вовсе, и по незыблемому
    №2 половина критерия 5 была объявленной, а не существующей.

    Недостача объясняется токеном из закрытого списка; без токена — и с
    токеном не из списка — это `unexplained-count`.

    Излишек не объясняется ничем: все четыре токена говорят, почему записи
    в таблице нет, и ни один не говорит, откуда взялась лишняя. Половина
    эта не декоративна: строка таблицы оправдывает появление поля в
    `content_diff`, так что строка мимо множества записей — это открытый
    гейт содержимого.
    """
    present = {row[0] for row in rows}
    findings = []
    for rel in sorted(expected):
        if rel in present:
            continue
        if explained.get(rel) in TOKENS:
            continue
        findings.append(Finding(
            "unexplained-count", rel, 1,
            "запись ожидалась в таблице и её там нет, объяснения тоже"))
    wanted = set(expected)
    for rel in sorted(present):
        if rel in wanted:
            continue
        findings.append(Finding(
            "unexplained-count", rel, 1,
            "строка в таблице есть, а запись не ожидалась"))
    return findings


def audit(rows, report_section, written=()):
    """`silent-substitution`: два производителя, оба про молчание.

    Первый — `deferred` без строки в отчёте: значение не записано и об этом
    никому не сказано. Второй — значение на диске без строки в таблице:
    записано и не названо.

    `synthetic` отчёту ничего не должен: незыблемое №4 требует одного из
    двух, а токен `unknown` лежит на диске и виден там, где значение
    читают.

    Названным считается путь и поле **в одной строке** раздела. Поиск по
    всему тексту сразу засчитал бы путь из одного сообщения и поле из
    другого — два разных сообщения, вместе не говорящих про эту запись
    ничего.
    """
    lines = [line for line in str(report_section).split("\n") if line.strip()]
    findings = []
    for row in sorted(rows):
        if row[4] != "deferred":
            continue
        if any(row[0] in line and row[1] in line for line in lines):
            continue
        findings.append(Finding("silent-substitution", row[0], 1,
                                "отложено и не названо в отчёте: %s" % row[1]))
    known = {(row[0], row[1]) for row in rows}
    for rel, field in sorted(written):
        if (rel, field) not in known:
            findings.append(Finding("silent-substitution", rel, 1,
                                    "значение записано мимо таблицы: %s" % field))
    return findings
