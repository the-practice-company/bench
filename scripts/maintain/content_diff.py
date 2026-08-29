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
  знает три: `bytes`, `section` и `append`. Каждая снята **вместе с починкой,
  которая её производит**, и раньше неё не снимается: `section` — потому что
  слой «форма механически» возвращает форм-секции `CLAUDE.md`, `append` —
  потому что `run` дописывает предложения в `OPEN-THREADS.md`. Правка на
  уровне строки перечисления (`areas/README.md`), слияния
  (`.claude/settings.json`) и значения JSON (`.twinkle-repo-builder`)
  прочитается здесь как `content-modified`. Пока ни одного производителя
  таких правок **внутри `maintain run`** нет, это строгость, а не дыра;
  заводить механизм раньше поломки — незыблемое №3.

  Единственный производитель строки перечисления в пакете — `add_area` из
  `extend`, и он в `run` не входит: `extend-structure` вызывается автором
  отдельно, а само-проверка сравнивает снимки одного прогона `run`. Поэтому
  `listing-row` остаётся неснятым, и снимет его тот, кто впервые научит `run`
  править это перечисление.
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


def _only_form_sections_moved(rel, shot, now):
    """Изменились ли **ровно** форм-секции файла и ничего кроме них.

    Вторая из одиннадцати гранулярностей поверхности, снятая вместе с
    починкой, которая её производит (слой «форма механически» возвращает
    `## Zone map` и `## Placement rule` в `CLAUDE.md` из каркаса). Без неё
    законная починка читалась бы как правка содержимого, и само-проверка
    откатывала бы каждый прогон.

    Проверяется не то, что секции совпали, а то, что совпало **всё
    остальное**: секции вырезаются из обеих сторон и сравнивается остаток.
    Прощать изменение внутри секции и при этом ослепнуть к правке прозы
    рядом с ней — это и была бы дыра.
    """
    titles = surface.names(rel, "section")
    if not titles:
        return False
    if not isinstance(shot.body, str) or not isinstance(now.body, str):
        return False
    return (surface.without_sections(shot.body, titles) ==
            surface.without_sections(now.body, titles))


def _only_appended(rel, shot, now):
    """Дописано ли **в конец** файла, которому поверхность это разрешает.

    Третья из одиннадцати гранулярностей, снятая вместе с починкой, которая
    её производит: `run` дописывает предложения в `OPEN-THREADS.md`. Без неё
    само-проверка откатывала бы каждый прогон, у которого нашлось хоть одно
    предложение.

    Проверяется не «файл вырос», а то, что прежние байты остались его
    **префиксом**. Файл растёт и от перестановки нитей местами, и от правки
    уже записанной, — а дописыванием ни то ни другое не является: строка
    поверхности говорит «существующие строки не изменяются».
    """
    return surface.covers(rel, "append") and now.bytes.startswith(shot.bytes)


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
        if _only_form_sections_moved(rel, shot, now):
            continue
        if _only_appended(rel, shot, now):
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
