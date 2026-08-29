#!/usr/bin/env python3
"""Слой спроса: объявленное и неиспользуемое, числами и датами.

Ни «протухло», ни «мало», ни «пора». §27 отверг меру потому, что порога
назвать нельзя, и это остаётся верным: разница между показом и мерой в том,
кто делает вывод.

Мерится по **структурным единицам** — восемь зон, направления, коллекции.
Единиц десятки, а не тысячи; по файлам git не опрашивается никогда.

Часы не читаются. «Сегодня» приходит параметром и обязателен, «последнее
касание» — из git. `st_mtime` запрещён: чекаут его переставляет, и результат
начинает зависеть от того, когда гоняли набор.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import zones
from scripts.adopt import tree
from scripts.basefile import parse_base
from scripts.findings import Finding, Report
from scripts.maintain import surface

# Порог живёт здесь, а не у того, кто удаляет: он нужен обоим, а второе
# определение разошлось бы с первым молча. Показу порог нужен не для
# вердикта, а ровно для одного — сказать, что числа нет: пока видимая
# история короче порога, любое число дней меньше него по построению и
# решить ничего не может.
THRESHOLD_DAYS = 30

# Токен вместо числа. Тот же запрет молчаливой заглушки, что `no-git` у
# `scan-tree` и `unknown` у `created`: отсутствующее значение называется, а
# не подменяется правдоподобным.
HISTORY_STARTS = "history-starts-%s"

# Касания нет вовсе: путь в истории не встречается. Так выглядит папка зоны,
# только что заведённая слоем «форма содержательно», — пустота на этом месте
# прочиталась бы как «тронуто сегодня».
NO_COMMIT = "no-commit"


def _git_out(root, *args):
    """Вывод git или отказ. Пустая строка при ненулевом коде — заглушка.

    Каждый вопрос этого слоя к git — вопрос о дате. Отказ git, прочитанный
    как пустой ответ, дал бы `no-commit` по неотличимой причине: так же
    выглядел бы путь, которого в истории нет (незыблемое №4). Тот же приём,
    что у `structural._git_out` и `mechanical._dirty`.
    """
    proc = tree.git(root, *args)
    if proc.returncode != 0:
        raise RuntimeError("git %s не отработал в %s: %s"
                           % (args[0], root, proc.stderr.strip()))
    return proc.stdout


# Дней от начала каждого месяца невисокосного года. Календарь считается
# здесь, а не берётся у `datetime`, и это не педантизм: критерий 2 требует,
# чтобы часов в `scripts/` не было **вовсе**, и запрет выражен именами
# модулей (`tests/test_fixtures.py::test_no_module_in_scripts_reads_the_clock`).
# Разбор даты часов не читает — но исключение, открытое ради него, открыло бы
# заодно `date.today()`, а десяток строк арифметики не открывает ничего.
# Совпадение с `datetime.date.toordinal` утверждается набором: сверять руками
# високосные годы незачем, а расходиться с образцом нельзя.
_MONTH_STARTS = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def _leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _ordinal(text):
    """Номер дня григорианского календаря. Наружу уходят только разности."""
    year, month, day = (int(part) for part in text.split("-"))
    passed = year - 1
    count = (passed * 365 + passed // 4 - passed // 100 + passed // 400
             + _MONTH_STARTS[month - 1] + day)
    return count + 1 if month > 2 and _leap(year) else count


def _lines(text):
    return [line.strip() for line in text.split("\n") if line.strip()]


def first_commit(root):
    """Дата первого коммита дерева — начало видимой истории."""
    dates = _lines(_git_out(root, "log", "--date=short", "--format=%cd",
                            "--reverse"))
    return dates[0] if dates else None


def last_touch(root, rel):
    """Дата последнего коммита, затронувшего путь, либо None.

    Путь уезжает в git с магией `:(literal)`. Измерено волной 4: без неё имя
    со звёздочкой или скобкой — шаблон, а не путь, и ответом приезжает
    настоящая дата от другого файла.
    """
    dates = _lines(_git_out(root, "log", "-1", "--date=short", "--format=%cd",
                            "--", ":(literal)%s" % rel))
    return dates[0] if dates else None


def _age(touched, started, today):
    """Дней с последнего касания либо токен. Ядро, общее с отчётом.

    Три случая, где числа нет, и каждый называется своим токеном.

    Касания нет в истории вовсе — `no-commit`.

    Видимая история короче порога — `history-starts-<дата>`. Это названное
    ограничение спеки: после ADOPT история начинается коммитом «как было»,
    у каждого пути последний коммит сегодняшний, и «ноль дней» было бы
    правдоподобной неправдой про коллекцию, куда не писали три года.

    Касание позже названного дня — тот же токен: коммита, которого на
    `today` ещё не было, в видимой истории нет, а число дней вышло бы
    отрицательным, то есть неправдой со знаком.
    """
    if touched is None or started is None:
        return NO_COMMIT
    if _ordinal(today) - _ordinal(started) < THRESHOLD_DAYS:
        return HISTORY_STARTS % started
    days = _ordinal(today) - _ordinal(touched)
    return days if days >= 0 else HISTORY_STARTS % started


def age(root, rel, today):
    """Дней с последнего коммита, затронувшего путь, либо токен."""
    root = Path(root)
    return _age(last_touch(root, rel), first_commit(root), today)


def records(root, collection):
    """Записи коллекции поимённо.

    `.gitkeep` записью не является: он существует только потому, что git не
    хранит пустых каталогов.
    """
    items = Path(root) / collection / "items"
    if not items.is_dir():
        return []
    return sorted(p.name for p in items.glob("*.md"))


def collections(root):
    """Пути коллекций дерева: папки, где лежит `views.base`.

    Чужой репозиторий в `knowledge/` пропускается, и спрашивается это у
    поверхности формы, а не вторым списком: вид внутри сабмодуля
    принадлежит его хозяину — рецепт закрывает туда запись статически
    (`zones.DENY_PATTERNS`), а `surface` то же самое знает предикатом.
    Посчитанная здесь чужая коллекция ушла бы дальше в удаление по порогу,
    то есть плагин дотянулся бы до чужого дерева (незыблемое №6).
    """
    root = Path(root)
    out = []
    for path in sorted(root.rglob("views.base")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        if not surface.covers(rel, "bytes"):
            continue
        out.append(path.parent.relative_to(root).as_posix())
    return sorted(out)


def empty_past_threshold(root, rel, today):
    """Пустая коллекция за порогом: проверенный факт, а не флаг.

    Живёт здесь, а не у того, кто удаляет: все четыре слагаемых — список
    коллекций, список записей, возраст и сам порог — принадлежат этому слою,
    и второе их определение разошлось бы с первым молча.

    Три условия, и ни одно не выводится из другого. Путь обязан быть
    коллекцией: зона без видов тоже бывает пустой, но пустая зона — это
    наблюдение, а не повод удалять папку, фиксированную §9. Записей ноль:
    линия ответственности проходит по содержимому, и в непустой коллекции
    оно есть. Возраст — **число** не меньше порога: токен вместо числа
    значит, что возраста нет, а не что он мал, и `no-commit` у только что
    заведённой папки разрешал бы удаление ровно там, где о ней ничего не
    известно.
    """
    root = Path(root)
    if rel not in collections(root):
        return False
    if records(root, rel):
        return False
    days = age(root, rel, today)
    return isinstance(days, int) and days >= THRESHOLD_DAYS


def directions(root):
    """Направления зоны `areas` — папки первого уровня под ней."""
    base = Path(root) / "areas"
    if not base.is_dir():
        return []
    return sorted("areas/%s" % p.name for p in base.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


def _material(root, rel):
    """Записи поддерева. README формой считается и материалом не бывает."""
    return [p for p in (Path(root) / rel).rglob("*.md") if p.name != "README.md"]


def _touch_text(root, rel, started, today):
    """Дата и число дней, либо один токен вместо обоих.

    Токен печатается без даты не из экономии: числа нет ровно тогда, когда
    названная дата ничего не измеряет, — и поставленная рядом, она читалась
    бы как измерение.
    """
    touched = last_touch(root, rel)
    value = _age(touched, started, today)
    if isinstance(value, int):
        return "последнее касание %s, дней %d" % (touched, value)
    return "последнее касание %s" % value


def _pins(root):
    """(путь сабмодуля, дата коммита, где пин записан).

    Источник — `ls-files --stage -z`, а не `git submodule status`: последний
    отказывается работать (код 128) на записи без строки в `.gitmodules`, а
    пути отдаёт без `-z`, то есть не-ASCII имя приехало бы в C-кавычках.
    Правило пакета про пути из git записано в `scripts/adopt/tree.py`.

    Свежести пина здесь нет и быть не может: она требует сети (незыблемое
    №5). Печатается дата закоммиченного пина — без порога и без вердикта.
    """
    out = []
    for entry in _git_out(root, "ls-files", "--stage", "-z").split("\0"):
        if not entry:
            continue
        head, _, rel = entry.partition("\t")
        if head.split()[0] != "160000":
            continue
        out.append((rel, last_touch(root, rel)))
    return sorted(out)


def run(root, today):
    """(отчёт, находки). Ничего не пишет на диск."""
    root = Path(root)
    started = first_commit(root)
    findings = []
    lines = ["# спрос today=%s" % today]

    for zone in zones.ZONES:
        if not (root / zone).is_dir():
            # Зона из карты без папки — наблюдение слоя «форма содержательно»,
            # он же её и заводит. Молчать о ней здесь нельзя: зон всегда
            # восемь, и строк о зонах в отчёте тоже восемь.
            lines.append("зона %s: папки нет" % zone)
            continue
        material = _material(root, zone)
        lines.append("зона %s: материала %d, %s"
                     % (zone, len(material),
                        _touch_text(root, zone, started, today)))
        if not material:
            findings.append(Finding("declared-unused", zone, 1,
                                    "зона объявлена, материала нет"))

    for direction in directions(root):
        material = _material(root, direction)
        lines.append("направление %s: материала %d, %s"
                     % (direction, len(material),
                        _touch_text(root, direction, started, today)))
        if not material:
            findings.append(Finding("declared-unused", direction, 1,
                                    "направление объявлено, материала нет"))

    for collection in collections(root):
        kept = records(root, collection)
        lines.append("коллекция %s: записей %d, %s"
                     % (collection, len(kept),
                        _touch_text(root, collection, started, today)))
        if not kept:
            findings.append(Finding("empty-collection", collection, 1,
                                    "виды есть, записей ноль"))
        base = parse_base((root / collection / "views.base")
                          .read_text(encoding="utf-8"))
        for folder in sorted(set(base.folders)):
            target = root / folder
            if target.is_dir() and not sorted(target.glob("*.md")):
                findings.append(Finding(
                    "view-selects-nothing", collection, 1,
                    "file.inFolder называет папку с нулём записей: %s" % folder))

    for rel, pinned in _pins(root):
        lines.append("пин сабмодуля %s: %s" % (rel, pinned or NO_COMMIT))

    return "\n".join(lines) + "\n", findings


def main(argv=None):
    parser = argparse.ArgumentParser(description="declared and unused, in numbers and dates")
    parser.add_argument("root")
    parser.add_argument("--today", required=True,
                        help="обязателен: у MAINTAIN дата удаляет папку, а не меняет текст")
    args = parser.parse_args(argv)
    report, findings = run(args.root, args.today)
    sys.stdout.write(report)
    observed = Report(findings, today=args.today)
    rendered = observed.render()
    if rendered:
        sys.stdout.write(rendered + "\n")
    return observed.exit_code()


if __name__ == "__main__":
    sys.exit(main())
