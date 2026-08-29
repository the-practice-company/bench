#!/usr/bin/env python3
"""Снимок дерева и сравнение с поверхностью формы.

Третья форма доказательства «что именно не изменилось». Первые две — из
волны 1: `check_read_only` хеширует всё дерево (годится инструменту, который
не пишет вовсе), `_check_tests_touched_product` — названные каталоги
(годится, когда граница проходит по путям). MAINTAIN пишет, и граница
проходит **внутри файлов**, поэтому здесь не хеш, а сравнение с закрытым
перечислением исключений (`surface`).

Что сравнение **не** проверяет, названо вслух, чтобы не считалось
проверенным:

- **Появление нового файла.** Правил сравнения на него в спеке нет: создание
  README зоны и формы коллекции аддитивно и содержимого не трогает. Что
  созданное не пусто, утверждает другой класс — `structure-without-content`.
- **Гранулярности тоньше файла.** Из одиннадцати строк поверхности сравнение
  сегодня знает одну — `bytes`. Правка на уровне секции (`CLAUDE.md`),
  строки таблицы (`areas/README.md`), дописывания (`OPEN-THREADS.md`,
  `.gitignore`), слияния (`.claude/settings.json`) и значения JSON
  (`.twinkle-repo-builder`) прочитается здесь как `content-modified`. Пока
  ни одного производителя таких правок в пакете нет, это строгость, а не
  дыра; заводить механизм раньше поломки — незыблемое №3. Задачам 4 и 9
  волны придётся снять этот долг вместе со своими починками, иначе само-
  проверка задачи 8 откатит каждый прогон.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.findings import Finding
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter
from scripts.maintain import surface


class Shot:
    __slots__ = ("bytes", "fields", "body")

    def __init__(self, raw, fields, body):
        self.bytes = raw
        self.fields = fields
        self.body = body


def _split(raw):
    """(поля, тело). Неразбираемый frontmatter — пустые поля и всё в тело:
    угадывать здесь нечего, а сравнение байтов всё равно состоится."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {}, raw
    try:
        fields = parse_frontmatter(text)
    except FrontmatterError:
        return {}, text
    if not fields:
        return {}, text
    _, _, rest = text.partition("---")
    _, _, body = rest.partition("---")
    return fields, body


def snapshot(root):
    """Путь -> Shot по всем файлам дерева, кроме `.git/`.

    Периметр — дерево, а не индекс git: игнорируемое и неотслеженное здесь
    есть. Иначе правка в игнорируемый файл прошла бы мимо сравнения молча.
    `.git/` исключён по обратной причине — он меняется от каждого хода git,
    включая собственный коммит MAINTAIN.
    """
    root = Path(root)
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/") or not path.is_file():
            continue
        raw = path.read_bytes()
        fields, body = _split(raw) if rel.endswith(".md") else ({}, raw)
        out[rel] = Shot(raw, fields, body)
    return out


def _deleted_here(rel, deleted):
    """Покрыт ли путь предикатом удаления. Сравнение посегментное: удаление
    `projects/stale` не оправдывает `projects/stale-2`."""
    return any(rel == d or rel.startswith(d + "/") for d in deleted)


def compare(before, after, field_map=(), deleted=()):
    """`content-modified` по правилам сравнения спеки волны.

    `field_map` — единственное, что берётся из прогона, и берётся оно узко:
    строка оправдывает **появление** ключа с **этим** значением по **этому**
    пути, и ничего больше. Иначе таблица оправдывала бы что угодно, назвав
    поле: существующее значение под названным ключом переписывалось бы
    молча, а одна строка накрывала бы то же поле во всём дереве.
    """
    allowed = {(row[0], row[1]): row[3] for row in field_map}
    findings = []

    def modified(rel, detail):
        findings.append(Finding("content-modified", rel, 1, detail))

    for rel, shot in sorted(before.items()):
        if _deleted_here(rel, deleted):
            continue
        if rel not in after:
            modified(rel, "файл исчез")
            continue
        now = after[rel]
        if shot.bytes == now.bytes:
            continue
        if surface.covers(rel, "bytes"):
            continue
        if shot.body != now.body:
            # Слово про запись сказать нельзя: телом здесь считается и проза
            # `CLAUDE.md`, и байты бинаря. Отчёт называет наблюдение, а не
            # роль файла, о которой в этом месте ничего не известно.
            modified(rel, "тело markdown-файла изменилось" if rel.endswith(".md")
                     else "байты файла изменились")
            continue
        for key, value in sorted(shot.fields.items()):
            if key not in now.fields:
                modified(rel, "ключ frontmatter исчез: %s" % key)
            elif now.fields[key] != value:
                modified(rel, "значение поля изменилось: %s" % key)
        for key, value in sorted(now.fields.items()):
            if key in shot.fields:
                continue
            expected = allowed.get((rel, key))
            if expected is None or str(expected) != str(value):
                modified(rel, "поле появилось мимо field-map: %s" % key)
    return findings
