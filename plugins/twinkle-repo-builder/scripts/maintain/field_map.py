#!/usr/bin/env python3
"""Машинная таблица массовой мутации и сходимость счётчиков.

Один формат и один модуль на все мутации волн 4 и 5. Формат на команду
отвергнут ценой, которую спека уже измерила: две копии парсера, одна из
которых не исполняется никогда.

TSV с заголовком, сортировка по пути, ноль абсолютных путей, часы не
читаются — те же правила, что у отчётов гейтов и у `scan-tree`.

Массовая мутация — изменяющая больше одного уже существующего файла;
создание новых под определение не подпадает.

**Таблиц две, дисциплина одна.** `backfill` меняет значение поля записи,
`rewrite-refs` — цель ссылки, и колонки у них разные: происхождения
(`computed` / `synthetic` / `deferred`) у переписанной ссылки нет вовсе — её
не восстанавливало правило, её перенесла согласованная строка плана. Втащить
ссылку в словарь происхождений ради переиспользования функции значило бы
получить таблицу, у которой врёт колонка, а это хуже честного счётчика.
Поэтому различия вынесены в данные (`Table`), а проверка осталась одна:
второй рендер с теми же четырьмя отказами разошёлся бы с этим на первом же
новом правиле, и разошедшиеся копии одного правила этому репозиторию уже
стоили критерия выхода.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import paths as path_rules
from scripts.findings import Finding

COLUMNS = ("path", "field", "before", "after", "origin", "rule")
REF_COLUMNS = ("path", "line", "before", "after", "plan")

# Три исхода на запись, и ни одного четвёртого.
ORIGINS = ("computed", "synthetic", "deferred")

# Закрытые списки объясняющих токенов, по одному на таблицу. Свободный токен
# позволил бы объяснить расхождение любым словом, то есть не объяснить ничем;
# общий на две таблицы — объяснить непрочитанной записью пропущенную ссылку.
TOKENS = ("undecodable", "unparseable-frontmatter", "not-a-record", "dirty-path")
REF_TOKENS = ("bare-still-resolves", "md-link", "not-a-wikilink")


def _unit(value):
    """Единица диффа кортежем строк.

    Одноколоночная единица принимается и голой строкой: у таблицы полей она
    и есть путь, и требовать `("a.md",)` от каждого вызывающего значило бы
    брать налог формой там, где форма ничего не значит.
    """
    parts = value if isinstance(value, tuple) else (value,)
    return tuple(str(part) for part in parts)


class Table:
    """Форма одной таблицы: колонки, ключ, словари, объяснения, слова диффа.

    `key` — колонки, по которым строка обязана быть единственной: у полей это
    пара «путь, поле» (`content_diff` кладёт строки в словарь по ней), у
    ссылок — путь, строка и текст ссылки.

    `identity` — единица, которую считает дифф. Она начинается путём, а у
    таблицы, чья вторая колонка `line`, вторым идёт номер строки: отсюда
    находка диффа встаёт на свою строку, а не на строку 1 всегда.

    `vocabularies` — «номер колонки → закрытое множество». Пусто значит, что
    закрытых словарей у таблицы нет, а не что проверка забыта.
    """

    __slots__ = ("prefix", "columns", "key", "identity", "vocabularies",
                 "tokens", "missing", "extra")

    def __init__(self, prefix, columns, key, identity, vocabularies, tokens,
                 missing, extra):
        self.prefix = prefix
        self.columns = columns
        self.key = key
        self.identity = identity
        self.vocabularies = vocabularies
        self.tokens = tokens
        self.missing = missing
        self.extra = extra

    @property
    def numbered(self):
        """Несёт ли таблица номер строки. Спрашивается у колонок, а не
        объявляется вторым полем: разойтись им было бы негде и незачем."""
        return self.columns[1] == "line"

    def unit(self, row):
        return _unit(tuple(row[at] for at in self.identity))

    def place(self, unit):
        """Путь и строка находки диффа про эту единицу."""
        return unit[0], int(unit[1]) if self.numbered else 1


FIELDS = Table(
    prefix="field-map", columns=COLUMNS, key=(0, 1), identity=(0,),
    vocabularies={4: ORIGINS}, tokens=TOKENS,
    missing="запись ожидалась в таблице и её там нет, объяснения тоже",
    extra="строка в таблице есть, а запись не ожидалась")

REFS = Table(
    prefix="ref-map", columns=REF_COLUMNS, key=(0, 1, 2), identity=(0, 1, 2),
    vocabularies={}, tokens=REF_TOKENS,
    missing="ссылка ожидалась в таблице и её там нет, объяснения тоже",
    extra="строка в таблице есть, а такой ссылки не было")


def name(operation, arguments, table=FIELDS):
    """Имя файла таблицы: из формы, операции и аргументов, **никогда** из даты.

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
    return "tmp/%s-%s.tsv" % (table.prefix, "-".join(parts))


def is_artefact(rel):
    """Машинная таблица мутации, положенная самим рецептом.

    Спрашивают об этом там, где дерево судят как авторское: полнота плана
    усыновления требует строки на **каждый** путь, а таблица не авторский
    путь и появляется после того, как план написан. Требовать на неё строку
    значит требовать от автора классифицировать вывод плагина, а от плагина
    — дописывать себе разрешение в файл согласия.

    Предикат живёт рядом с `name`, потому что это одно правило с двух
    сторон: что рецепт кладёт и что он же обязан узнать. Разъехавшись, они
    дали бы отказ «план не разобран» на ровном месте — ровно то, чем этот
    предикат и был вызван к жизни.

    Цена правила по имени названа вслух: авторский файл, случайно
    названный `tmp/ref-map-….tsv`, из полноты плана выпадет. Узнать таблицу
    иначе нечем — списка написанного за прогон полнота не видит, — а сосед
    плана под любым другим именем остаётся названным.
    """
    return rel.endswith(".tsv") and rel.startswith(
        tuple("tmp/%s-" % table.prefix for table in (FIELDS, REFS)))


def render(rows, table=FIELDS):
    """TSV таблицы. Строка, которой нельзя верить, роняет вызов, а не едет.

    Четыре отказа, и каждый — про молчание, а не про красоту: путь вне
    корня, ширина не та, разделитель внутри ячейки (сдвинул бы колонки),
    значение колонки вне её закрытого словаря. Пятый — ключ строки дважды:
    у полей `content_diff` кладёт строки в словарь по паре «путь, поле», у
    ссылок вторая строка описывала бы ту же правку второй раз; из двух
    уцелеет одна, и какая именно — не сказано нигде.
    """
    out = ["\t".join(table.columns)]
    seen = set()
    for row in sorted(rows):
        if len(row) != len(table.columns):
            raise ValueError("строка таблицы не той ширины: %r" % (row,))
        cells = [str(cell) for cell in row]
        if path_rules.escapes_root(cells[0]):
            raise ValueError("путь вне корня репозитория: %r" % (cells[0],))
        for at, closed in table.vocabularies.items():
            if row[at] not in closed:
                raise ValueError("колонка `%s` вне закрытого множества: %r"
                                 % (table.columns[at], row[at]))
        for cell in cells:
            if "\t" in cell or "\n" in cell:
                raise ValueError("разделитель внутри ячейки: %r" % (cell,))
        key = tuple(cells[at] for at in table.key)
        if key in seen:
            raise ValueError("ключ строки в таблице дважды: %r" % (key,))
        seen.add(key)
        out.append("\t".join(cells))
    return "\n".join(out) + "\n"


def write(root, operation, arguments, rows, table=FIELDS):
    """Положить таблицу мутации в `tmp/`. Возвращает путь от корня.

    Кого таблица описывает, решает вызывающий. Строка `deferred` в ней
    законна — это исход, а не пропуск; таблицы нет только там, где мутации
    не было вовсе: отказ таблицей не документируется.

    Дверь одна на обе таблицы по той же причине, по которой один рендер:
    вторая копия «имя, каталог, запись» разошлась бы с этой на первом же
    правиле про имя.
    """
    rel = name(operation, arguments, table)
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(rows, table), encoding="utf-8")
    return rel


def reconcile(expected, rows, explained, table=FIELDS):
    """Дифф ожидаемого и фактического, обе половины.

    Ожидаемое считается **до** мутации и **не** из того цикла, который
    мутацию делает: у `backfill` его перечисляет вид коллекции, у
    `rewrite-refs` — резолвер гейта. Что именно каждая пара доказывает, а
    что нет, сказано у производителей — `backfill.expected_records` и
    `rewrite_refs.expected_refs`; до них у этой функции не было
    производителя вовсе, и по незыблемому №2 половина критерия 5 была
    объявленной, а не существующей.

    Недостача объясняется токеном из закрытого списка **своей** таблицы;
    без токена — и с токеном чужого списка — это `unexplained-count`.

    Излишек не объясняется ничем: токены говорят, почему единицы в таблице
    нет, и ни один не говорит, откуда взялась лишняя. Половина эта не
    декоративна: у полей строка таблицы оправдывает появление поля в
    `content_diff`, у ссылок — правку авторского текста мимо согласованной
    строки плана.
    """
    present = {table.unit(row) for row in rows}
    wanted = {_unit(item) for item in expected}
    excused = {_unit(key): token for key, token in explained.items()}
    findings = []

    def ordered(units):
        return sorted(units, key=lambda unit: (table.place(unit), unit))

    for unit in ordered(wanted):
        if unit in present:
            continue
        if excused.get(unit) in table.tokens:
            continue
        path, line = table.place(unit)
        findings.append(Finding("unexplained-count", path, line, table.missing))
    for unit in ordered(present):
        if unit in wanted:
            continue
        path, line = table.place(unit)
        findings.append(Finding("unexplained-count", path, line, table.extra))
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
