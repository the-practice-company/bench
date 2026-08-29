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
"""

import argparse
import sys
import unicodedata
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import check_links
from scripts.adopt import refs, tree
from scripts.adopt.move import agreed_line
from scripts.findings import EXIT_OK, EXIT_VIOLATION


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
    markdown = [hit for hit in hits if hit.kind == "mdlink"]

    edits, kept = {}, 0
    for hit in hits:
        if hit.kind != "wikilink":
            continue
        candidate = next((c for c in hit.candidates if _under(c, source)), None)
        if candidate is None:
            continue
        new_path = unicodedata.normalize(
            "NFC", _moved(candidate, source, target))
        if "/" not in hit.target and _still_leads(new_path, hit.target):
            kept += 1
            continue
        edits.setdefault(hit.path, []).append(
            (hit.line, hit.raw,
             _rewritten(hit.raw, hit.target, _reference(new_path))))

    for rel, changes in sorted(edits.items()):
        path = root / rel
        path.write_text(_applied(path.read_text(encoding="utf-8"), changes),
                        encoding="utf-8")

    if edits:
        tree.record_touched(root, source, sorted(edits))

    # Нечитаемый файл называется первым. Ссылки в нём не прочитаны, значит и
    # не переписаны, и «переписано 0» про такое дерево — половина правды:
    # незыблемое №4 запрещает подставлять невосстановимое молча.
    out = ["не прочитан: %s — ссылки в нём не переписаны" % rel
           for rel, _, _ in unreadable]
    out.append("ссылок переписано: %d" % sum(len(v) for v in edits.values()))
    out.append("голых ссылок оставлено: %d" % kept)
    out.append("файлов затронуто: %d" % len(edits))
    out.append("markdown-ссылок не тронуто: %d" % len(markdown))
    return "\n".join(out) + "\n", EXIT_OK


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
