#!/usr/bin/env python3
"""План усыновления: разбор строк, состояние и действие.

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


def read(root, path):
    """Разбор файла плана. Путь в находках — относительный, как у гейтов."""
    root, path = Path(root), Path(path)
    rel = path.relative_to(root).as_posix()
    return parse(path.read_text(encoding="utf-8"), rel)
