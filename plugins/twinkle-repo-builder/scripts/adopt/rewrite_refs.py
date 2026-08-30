#!/usr/bin/env python3
"""`rewrite-refs`: ссылки на переезжающий путь. Ничего не перемещает.

Правит только wikilink'и, и две их формы — по-разному. Ссылка с путём
(`[[notes/meeting]]`) несёт место в тексте, и переезд обязан переписать его.
Голая (`[[meeting]]`) места не несёт вовсе и переезда обычно не замечает:
она остаётся как есть, **если после переезда basename по-прежнему ведёт к
переехавшему файлу**. Если перестал вести — а перестаёт он от
переименования, — дописывается полный новый путь.

Чего эта команда не делает намеренно: не разводит неоднозначность, которая
была в дереве **до** переезда. `[[meeting]]`, ведущая к двум файлам сразу,
после переезда одного из них ведёт к тем же двум, просто по новым путям;
дописать сюда путь значило бы выбрать за автора, какую из двух встреч он
имел в виду. Это содержимое, а не форма, и правит его автор — гейт называет
такую ссылку `ambiguous` и продолжает называть.

Markdown-ссылки на локальные файлы не трогаются: §13 отправляет конвертацию
в отдельную массовую мутацию со своим планом. Здесь они считаются и
показываются числом, потому что R их не видит — значит переезд их ломает,
а счётчик молчит.

**Массовая мутация, а значит таблица и дифф счётчиков** (§20). Четыре
счётчика отвечали на вопрос «сколько», а требование — «что и во скольких
файлах»: поимённо счётчик не называет ни одной правки, и сходимость держал
один инвариант «R до = R после». Таблица — `tmp/ref-map-*.tsv`, формат общий
с `backfill`; ожидаемое перечисляет резолвер гейта, и каждая ссылка, которую
правка не переписала, обязана нести токен из закрытого списка
`field_map.REF_TOKENS`.
"""

import argparse
import sys
import unicodedata
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import check_links
from scripts.adopt import refs, tree
from scripts.adopt.move import agreed_line
from scripts.findings import EXIT_VIOLATION, Report
from scripts.maintain import field_map


def _under(child, parent):
    return child == parent or child.startswith(parent + "/")


def _moved(rel, source, target):
    """Куда переедет путь **из-под** источника.

    Вне источника не зовётся и звана быть не может: для чужого пути
    `target + rel[len(source):]` даёт обрубок, который выглядит путём и
    никуда не ведёт.
    """
    return target if rel == source else target + rel[len(source):]


def _reference(path):
    """Как путь пишется внутри `[[...]]`: без расширения `.md`.

    Резолв wikilink'а идёт по ключам индекса, а в них расширения нет:
    `[[notes/meeting.md]]` не резолвится ни во что. Новая запись берётся
    от **пути цели**, а не подстановкой в текст старой ссылки:
    переименование меняет и basename, и место сразу, и строковая правка
    старого текста дала бы `[[core/устав.md]]` — вид пути при пустом
    резолве.
    """
    return path[:-3] if path.endswith(".md") else path


def _rewritten(raw, old, new):
    """Новая запись ссылки: меняется только цель.

    Всё после `#`, `^` и `|` остаётся на месте, ведущий `!` тоже: эти части
    пишет автор, и переезд про них ничего не знает. Первое вхождение — и
    есть цель: до неё в записи стоят только `[[` и, может быть, `!`.
    """
    return raw.replace(old, new, 1)


def _still_leads(new_path, bare):
    """Ведёт ли голое имя к файлу после переезда.

    Спрашивается у одного basename, а не у будущего индекса дерева. Индекс
    отвечал бы на тот же вопрос дороже и ни разу не иначе: файл лежит в нём
    ровно под своим новым basename, и попадание в этот список — то же
    равенство имён. Лишние однофамильцы ответа не меняют: голая ссылка
    ведёт к файлу и когда ведёт не только к нему.
    """
    return unicodedata.normalize("NFC", PurePosixPath(new_path).stem) == bare


def _applied(text, changes):
    """Текст с новыми ссылками. Правка по позициям, а не по подстроке.

    `str.replace` чинит первое вхождение в строке, а первым вполне может
    стоять пример в backtick'ах: гейт его ссылкой не считает и чинить не
    просил, живая ссылка справа при этом оставалась старой. Правка попадала
    ровно мимо того, ради чего заведена, и оба промаха тихие.

    Позиции берутся у `_blank_code` гейта — того же, которым он сам
    отбирает ссылки: код гасится пробелами, длина строки не меняется, и
    колонка в погашенном тексте совпадает с колонкой в исходном.
    """
    lines = text.split("\n")
    blanked = check_links._blank_code(text).split("\n")
    wanted = {}
    for lineno, raw, new_raw in changes:
        wanted.setdefault(lineno, {})[raw] = new_raw
    for lineno, by_raw in wanted.items():
        line, source = lines[lineno - 1], blanked[lineno - 1]
        out, last = [], 0
        for match in check_links._WIKILINK.finditer(source):
            new_raw = by_raw.get(match.group(0))
            if new_raw is None:
                continue
            out.append(line[last:match.start()])
            out.append(new_raw)
            last = match.end()
        out.append(line[last:])
        lines[lineno - 1] = "".join(out)
    return "\n".join(lines)


def _unit(hit):
    """Единица сверки: файл, строка и текст ссылки как он записан.

    Два одинаковых вхождения на одной строке — одна единица, и это не
    потеря: правит их `_applied` одной инструкцией (словарь по тексту
    ссылки), а различить их между собой нечем — колонки у вхождения нет.
    Вторая строка таблицы описывала бы ту же правку второй раз, и `render`
    такую таблицу роняет. Счётчик правок считает то же самое, что таблица:
    два числа про одно в одном отчёте расходятся первыми.
    """
    return (hit.path, hit.line, hit.raw)


def expected_refs(hits):
    """Ссылки, которые обязана накрыть правка. Считается **не** циклом правки.

    Перечисляет их резолвер гейта по дереву до мутации — тот же
    `check_links.occurrences`, которым считается R, — а `find` оставляет из
    них ведущие под источник. Что это доказывает, сказано здесь дословно,
    чтобы не считалось доказанным большее:

    - половины **не независимы** в том, что считать ссылкой и куда она
      ведёт: резолвер в пакете один, и обе берут ответ у него;
    - независимы они ровно в одном — **что цикл правки сделал с каждой из
      названных**. Ссылка, которую цикл пропустил молча, и строка таблицы,
      которой резолвер не называл, — то, и только то, что дифф ловит.

    Ссылки в непрочитанном файле сюда не входят: их не видел никто, и брать
    их неоткуда. Такой файл называется отдельной строкой отчёта — незыблемое
    №4 требует именно этого, а не нуля в счётчике.

    Второе перечисление, со своим предикатом «ведёт под источник», здесь
    заведено не будет: две копии одного правила разошлись бы молча, а
    `refs.find` — то самое единственное место, где оно записано.
    """
    return {_unit(hit) for hit in hits}


def plan_rewrites(hits, source, target, agreed):
    """(строки таблицы, объяснённые пропуски). Ничего не пишет.

    Строки — словарь «единица → строка таблицы», объяснения — словарь
    «единица → токен из `field_map.REF_TOKENS`». Ссылка, которую правка не
    переписала, обязана нести токен: без него это `unexplained-count`, а не
    пропуск.

    Три токена, и различие между ними не косметическое. `bare-still-resolves`
    — ссылка, которую переезд не ломает вовсе. `md-link` — ломает, но у неё
    есть названный преемник: §13 отдаёт конвертацию отдельной массовой
    мутации со своим планом. `not-a-wikilink` — ломает, и преемника нет:
    путь в backtick'ах и путь в правиле разрешений R считает, переезд их
    рвёт, и чинит их автор рукой.
    """
    rows, explained = {}, {}
    for hit in hits:
        unit = _unit(hit)
        if hit.kind == "mdlink":
            explained[unit] = "md-link"
            continue
        if hit.kind != "wikilink":
            explained[unit] = "not-a-wikilink"
            continue
        candidate = next((c for c in hit.candidates if _under(c, source)), None)
        if candidate is None:
            # Ни строки, ни токена, и это намеренно: резолвер назвал ссылку
            # ведущей под источник, а цикл её таковой не узнал. Объяснять
            # тут нечего — расхождение двух чтений одного источника и есть
            # то, что обязан назвать дифф.
            continue
        new_path = unicodedata.normalize(
            "NFC", _moved(candidate, source, target))
        if "/" not in hit.target and _still_leads(new_path, hit.target):
            explained[unit] = "bare-still-resolves"
            continue
        rows[unit] = (hit.path, hit.line, hit.raw,
                      _rewritten(hit.raw, hit.target, _reference(new_path)),
                      agreed)
    return rows, explained


def counter_diff(hits, rows, explained):
    """Дифф ожидаемого и фактического — находками, а не текстом.

    `explained` едет в `reconcile` как есть: это и есть канал объяснённой
    недостачи, и второго такого механизма не заводится.
    """
    return field_map.reconcile(expected_refs(hits), rows, explained,
                               field_map.REFS)


def write_table(root, source, target, rows):
    """Положить таблицу мутации в `tmp/`. Возвращает путь от корня.

    Имя выводится из операции и её аргументов и никогда из даты; форма —
    `field_map.REFS`, потому что колонки у ссылки свои. Отказ таблицей не
    документируется: она — запись о состоявшейся мутации, а не о попытке.
    """
    return field_map.write(root, "rewrite-refs", (source, target), rows,
                           field_map.REFS)


def _apply(root, rows):
    """Записать правки на диск. Возвращает затронутые пути по возрастанию."""
    by_path = {}
    for rel, line, raw, new_raw, _agreed in rows:
        by_path.setdefault(rel, []).append((line, raw, new_raw))
    for rel, changes in sorted(by_path.items()):
        path = root / rel
        path.write_text(_applied(path.read_text(encoding="utf-8"), changes),
                        encoding="utf-8")
    return sorted(by_path)


def run(root, source, target, plan_path):
    root = Path(root)
    line, reason = agreed_line(root, source, target, plan_path, "move")
    if line is None:
        return reason + "\n", EXIT_VIOLATION
    for path in (source, target):
        if not tree.inside(root, path):
            return "отказ: путь вне корня: %s\n" % path, EXIT_VIOLATION
    # Точка отката спрашивается здесь, а не оставляется на `move`. У переноса
    # её спрашивает сам git — без репозитория `git mv` не идёт; запись в файл
    # не спрашивает никого, проходит молча и не возвращается ничем. Правка
    # ссылок идёт **раньше** переноса, то есть первой необратимой была бы она.
    if tree.read_base(root) is None:
        return ("отказ: точки отката нет, правка ссылок не идёт: "
                "сначала `init-tree`\n"), EXIT_VIOLATION

    hits, unreadable = refs.find(root, source)
    rows, explained = plan_rewrites(hits, source, target,
                                    "%s -> %s" % (line.source, line.target))
    touched = _apply(root, rows.values())
    if touched:
        tree.record_touched(root, source, touched)

    # Нечитаемый файл называется первым. Ссылки в нём не прочитаны, значит и
    # не переписаны, и «переписано 0» про такое дерево — половина правды:
    # незыблемое №4 запрещает подставлять невосстановимое молча.
    out = ["не прочитан: %s — ссылки в нём не переписаны" % rel
           for rel, _, _ in unreadable]
    # Путь, у которого преемника нет, называется поимённо, markdown-ссылка —
    # числом. Автору нужно разное: одну ему чинить рукой сейчас, вторую
    # исполнит будущая мутация §13.
    out.extend("не переписано: %s:%d %s (not-a-wikilink)" % unit
               for unit in sorted(unit for unit, token in explained.items()
                                  if token == "not-a-wikilink"))
    tokens = list(explained.values())
    out.append("ссылок переписано: %d" % len(rows))
    out.append("голых ссылок оставлено: %d" % tokens.count("bare-still-resolves"))
    out.append("файлов затронуто: %d" % len(touched))
    out.append("markdown-ссылок не тронуто: %d" % tokens.count("md-link"))
    out.append("таблица: %s" % write_table(root, source, target, rows.values()))

    # Дифф печатается после таблицы и красит код: мутация, про которую нельзя
    # сказать, что она накрыла ровно названные резолвером ссылки, зелёной не
    # уезжает — иначе критерий держится на счётчике, который сам себе судья.
    report = Report(counter_diff(hits, rows.values(), explained))
    rendered = report.render()
    if rendered:
        out.append(rendered)
    return "\n".join(out) + "\n", report.exit_code()


def main(argv=None):
    parser = argparse.ArgumentParser(description="rewrite links to a moving path")
    parser.add_argument("root")
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--plan", required=True,
                        help="план усыновления: без него мутация не идёт")
    args = parser.parse_args(argv)
    report, code = run(args.root, args.source, args.target, args.plan)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
