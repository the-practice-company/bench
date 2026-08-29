#!/usr/bin/env python3
"""План усыновления: разбор, полнота, непересечение, состояние строк.

Форма — строгая шапка и свободное тело. Шапку читает машина, тело пишет и
читает человек, и оно обязано быть непустым: строка без основания через
месяц нечитаема, а здесь она ещё и главный носитель того, что
классификацию делал кто-то, кто смотрел в файлы. Дословно то же правило,
что у аллоулиста секции 13, и по той же причине.

Нераспознанная строка — находка, а не пропуск. Пропуск означал бы, что
правка автора рукой тихо выносит строку из исполнения, то есть отменяет
собственное согласие, не заметив этого.
"""

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.check_links import _gitignore_prefixes, _in_perimeter
from scripts.findings import Finding

# Стрелка в двух написаниях: файл правит человек в Obsidian, и `→` там
# получается сам собой из автозамены.
_HEAD = re.compile(r"\A- \[([ x])\] `([^`]+)`\s*(?:->|→)\s*`([^`]+)`\s*\Z")
_STAGE = re.compile(r"\A##\s+(.+?)\s*\Z")

# Цели, которые значат не «сюда переехать», а что-то ещё. Отсортированы,
# потому что множество утверждается тестом поимённо.
RESERVED = ("foreign-repo", "git-history", "merge", "stay")

_ACTIONS = {"git-history": "drop", "merge": "merge",
            "foreign-repo": None, "stay": None}

# Маркер, которым установщик каркаса помечает слитый файл. Живёт здесь, а не
# в install_scaffold: состояние строки `merge` читает его, и разошедшиеся
# копии маркера означали бы вечное `pending` — то есть повторное слияние на
# каждом запуске.
#
# Голая строка без обрамления, потому что сливаются два файла с разным
# синтаксисом комментария: в `CLAUDE.md` она уезжает внутрь `<!-- -->`,
# в `.gitignore` — после решётки. Проверка вхождения работает для обоих.
MERGE_MARKER = "twinkle-repo-builder: рецепт"

# Отказ автора заводить git живёт в шапке плана, а не в `OPEN-THREADS.md`:
# этот файл в чужом дереве может уже существовать, и дописать в него —
# изменение файла, запрещённое критерием 4. Повторный запуск читает шапку и
# не переспрашивает — ровно то, ради чего §18 отказ и записывал.
DECLINED = "автор отказался заводить git"


class PlanLine:
    __slots__ = ("lineno", "agreed", "source", "target", "body", "stage")

    def __init__(self, lineno, agreed, source, target, stage):
        self.lineno = lineno
        self.agreed = agreed
        self.source = source
        self.target = target
        self.body = ""
        self.stage = stage

    def __repr__(self):
        return "PlanLine(%d, %r, %r -> %r)" % (
            self.lineno, self.agreed, self.source, self.target)


def _path(raw):
    """Путь строки: NFC и без хвостовой косой.

    `journal/` и `journal` — один путь. Иначе полнота плана начинает
    зависеть от того, как автор набрал строку, а это ровно тот класс
    молчаливой разницы, против которого полнота и заведена.
    """
    return unicodedata.normalize("NFC", raw.strip()).rstrip("/")


def is_question(target):
    """Вопрос — любая цель, содержащая `?`, а не только цель `?` целиком.

    §18: «Цель со знаком `?` не исполняется даже с крестиком». Форма
    `areas/<?>/journal` — самая частая: зона известна, область нет.
    """
    return "?" in target


def action(line):
    """Чем исполняется строка, или None, если ничем и никогда."""
    if is_question(line.target):
        return None
    if line.target in _ACTIONS:
        return _ACTIONS[line.target]
    return "move"


def parse(text, plan_rel):
    """(строки, находки). Разбор не бросает: несогласие — это находка."""
    lines, found = [], []
    stage = None
    current = None
    body = []
    # Шапка отвергнута — её тело уже описано находкой про шапку. Без этой
    # памяти опечатка в одной строке даёт находку на каждую строку абзаца
    # под ней, и в отчёте тонет вторая сломанная строка.
    rejected = False

    def close():
        if current is None:
            return
        if not "".join(body).strip():
            found.append(Finding(
                "plan-unparseable", plan_rel, current.lineno,
                "строка без тела: `%s` -> `%s`" % (current.source, current.target)))
        else:
            current.body = "\n".join(body).strip()
            lines.append(current)

    for lineno, raw in enumerate(text.split("\n"), start=1):
        if not raw.strip():
            continue
        if raw[0] in " \t":
            if current is None:
                if not rejected:
                    found.append(Finding("plan-unparseable", plan_rel, lineno,
                                         "тело без строки: %s" % raw.strip()))
                continue
            body.append(raw.strip())
            continue
        # Всё дальнейшее — с нулевой позиции, значит закрывает предыдущую.
        close()
        current, body, rejected = None, [], False
        stage_match = _STAGE.match(raw)
        if stage_match:
            stage = stage_match.group(1)
            continue
        if raw.startswith("#"):
            continue
        head = _HEAD.match(raw)
        if head:
            source, target = _path(head.group(2)), _path(head.group(3))
            # Пустой путь — не согласие ни на что: `/` после снятия
            # хвостовой косой не совпадёт в дереве ни с чем и в полноте
            # промолчит, оставаясь на вид согласованной строкой.
            if not source or not target:
                found.append(Finding("plan-unparseable", plan_rel, lineno,
                                     "пустой путь в строке: %s" % raw.strip()))
                rejected = True
                continue
            current = PlanLine(lineno, head.group(1) == "x",
                               source, target, stage)
            continue
        found.append(Finding("plan-unparseable", plan_rel, lineno,
                             "строка не разобрана: %s" % raw.strip()))
        rejected = True
    close()
    return lines, found


def header(text):
    """Шапка: комментарии до первой строки плана и до первого этапа.

    Комментарий ниже по файлу шапкой не является. Иначе «шапка» значит «где
    угодно», и фраза, дописанная в тело задним числом, читается как решение,
    принятое до усыновления.
    """
    out = []
    for raw in text.split("\n"):
        if not raw.strip() or raw[0] in " \t":
            continue
        if raw.startswith("##") or not raw.startswith("#"):
            break
        out.append(raw)
    return out


def declined(text):
    """Записан ли в шапке отказ автора заводить git."""
    return any(DECLINED in line for line in header(text))


def _under(child, parent):
    """Лежит ли `child` внутри `parent`. Посегментно, а не по подстроке:
    `a` не предок `ab`, и сравнение подстрокой сказало бы обратное."""
    return child == parent or child.startswith(parent + "/")


def overlaps(lines, plan_rel):
    """`overlapping-line`: источник строки накрыт источником другой.

    Альтернатива — «побеждает ближайший предок» — отвергнута: смысл плана
    начал бы зависеть от порядка строк, а перекрытая строка стала бы
    невидимой ошибкой. Тот же класс тихой гнили, что `dead-allow`.

    Смотрит в обе стороны, а не только назад. Взгляд назад означал бы, что
    те же две строки, переставленные местами, ошибки не дают, — то есть
    смысл плана снова зависел бы от порядка, ровно от чего запрет и
    заведён. Находка всегда одна и всегда на накрытой строке; для двух
    одинаковых источников накрытой считается вторая, иначе один конфликт
    назывался бы дважды.
    """
    out = []
    for index, line in enumerate(lines):
        for other_index, other in enumerate(lines):
            if other_index == index or not _under(line.source, other.source):
                continue
            if line.source == other.source and other_index > index:
                continue
            out.append(Finding(
                "overlapping-line", plan_rel, line.lineno,
                "источник `%s` накрыт строкой %d: `%s`"
                % (line.source, other.lineno, other.source)))
            break
    return out


def coverage(root, lines, plan_rel):
    """`uncovered-path`: путь дерева, о котором план не сказал ничего.

    Называется **самый мелкий** непокрытый путь: спуск прекращается, как
    только путь покрыт или признан непокрытым. Иначе один забытый каталог
    заливает отчёт семьюстами строками, и отчёт перестают читать.

    Из дерева вычитается ровно одно имя — сам файл плана, а не каталог
    вокруг него: сосед плана обязан быть назван. `.git/` и игнорируемое
    `.gitignore`-ом не входят изначально.

    Покрывают путь источники строк и, сверх них, цели **исполненных**
    переносов: перенесённое лежит там, куда его отправила согласованная
    строка, и требовать на него второй строки значило бы объявлять план
    неполным ровно за то, что он исполнен. Только исполненных: цель, куда
    ещё не переезжали, совпала бы с уже существующим чужим каталогом и
    тихо сняла бы его с разбора.
    """
    root = Path(root)
    ignored = _gitignore_prefixes(root)
    covering = [line.source for line in lines]
    covering.extend(line.target for line in lines
                    if action(line) == "move" and state(root, line) == "done")
    out = []

    def walk(rel):
        base = root / rel if rel else root
        for entry in sorted(base.iterdir(), key=lambda p: p.name):
            if entry.name == ".git" or entry.is_symlink():
                continue
            child = unicodedata.normalize(
                "NFC", entry.name if not rel else "%s/%s" % (rel, entry.name))
            if child == plan_rel or not _in_perimeter(child, ignored):
                continue
            if any(_under(child, source) for source in covering):
                continue
            if entry.is_dir() and (_under(plan_rel, child) or
                                   any(_under(source, child) for source in covering)):
                walk(child)
                continue
            out.append(Finding("uncovered-path", plan_rel, 1,
                               "путь не покрыт ни одной строкой: %s" % child))

    walk("")
    return out


def state(root, line):
    """Состояние строки, вычисленное из дерева. None — строка не исполняется.

    В файле состояние не хранится вовсе. Машинная колонка разошлась бы с
    деревом в первый же раз, когда автор передвинул что-то руками; дерево
    врать не умеет. Тот же приём, которым §19 меряет спрос из git.
    """
    what = action(line)
    if what is None:
        return None
    root = Path(root)
    source = (root / line.source).exists()
    if what == "drop":
        return "pending" if source else "done"
    if what == "merge":
        # У слияния источник и цель — один путь: файл существует и до, и
        # после. Существованием тут ничего не различишь, различает маркер.
        if not source:
            return "lost"
        try:
            text = (root / line.source).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return "pending"
        return "done" if MERGE_MARKER in text else "pending"
    target = (root / line.target).exists()
    if source and not target:
        return "pending"
    if target and not source:
        return "done"
    return "collision" if source else "lost"


def conflicts(root, lines, plan_rel):
    """`line-state-conflict`: столкновение или потеря по таблице состояний."""
    out = []
    for line in lines:
        current = state(root, line)
        if current == "collision":
            out.append(Finding(
                "line-state-conflict", plan_rel, line.lineno,
                "источник и цель существуют оба: `%s` -> `%s`"
                % (line.source, line.target)))
        elif current == "lost":
            out.append(Finding(
                "line-state-conflict", plan_rel, line.lineno,
                "ни источника, ни цели: `%s` -> `%s`"
                % (line.source, line.target)))
    return out


def _rel(root, path):
    return Path(path).relative_to(Path(root)).as_posix()


def read(root, path):
    """Разбор файла плана. Путь в находках — относительный, как у гейтов."""
    return parse(Path(path).read_text(encoding="utf-8"), _rel(root, path))


def load(root, path):
    """Всё вместе: строки и все находки о плане.

    Единственная точка входа для `read-plan`, `check-plan` и трёх мутирующих
    команд — иначе каждая завела бы свой набор проверок, они разошлись бы,
    и половина команд поехала бы по плану, который вторая половина уже
    назвала сломанным.
    """
    lines, found = read(root, path)
    plan_rel = _rel(root, path)
    found = list(found)
    found.extend(overlaps(lines, plan_rel))
    found.extend(coverage(root, lines, plan_rel))
    found.extend(conflicts(root, lines, plan_rel))
    return lines, found
