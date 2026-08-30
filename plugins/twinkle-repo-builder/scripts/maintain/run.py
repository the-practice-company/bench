#!/usr/bin/env python3
"""MAINTAIN: три слоя, само-проверка, откат, отдельный коммит.

Порядок обязателен: снимок «до» снимается раньше первой починки, иначе
доказывать нечем. На любой находке `content-modified` прогон откатывает себя
целиком через `revert` волны 4 — не потому, что откат красив, а потому, что
режим работает без присмотра на репозитории, полном авторской работы.
Покрыть критерий 1 одними тестами на фикстуре отвергнуто: тесты доказывают
поведение на фикстуре, а проверка, которой нет в бою, в бою и не работает.

**Множество изменённых путей берётся из `git status`, а не из намерений
слоёв.** Слой, не отчитавшийся о записи, — это ровно тот случай, ради
которого само-проверка заведена, и верить его списку значило бы откатывать
не то. Появление нового файла `content_diff` не ловит вовсе (правил
сравнения на него нет), и виден такой файл только отсюда.

**Откат обходит пути, грязные до прогона.** `revert` возвращает путь в
`HEAD`, и для пути, где у человека лежит несохранённая работа, это её потеря
— то самое, ради чего MAINTAIN такой путь и не трогает. Обойдённое
называется в отчёте: молча оставленная чужая правка выглядела бы откатом,
которого не было.

**Код возврата 2 — только про обещание плагина о себе.** Находки гейтов,
оставшиеся автору, режим не судит: гейты гоняет `Stop`, а MAINTAIN чинит
форму и показывает остаток. Красный код на чужом `unresolved` означал бы,
что починка не удалась, — а она удалась ровно настолько, насколько могла.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.adopt import revert, tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION, Report
from scripts.maintain import content_diff, demand, mechanical, prune, structural

SECTIONS = ("Форма механически", "Форма содержательно", "Спрос")
COMMIT_SUBJECT = "MAINTAIN: починки формы"
THREADS = "OPEN-THREADS.md"

# Ключ предложения — класс плюс путь, — и живёт он в самой строке нити.
# Отдельным журналом он разошёлся бы с текстом от первой же авторской правки,
# а нить, потерявшая ключ, дописалась бы вторым прогоном заново.
MARK = "<!-- maintain:%s %s -->"


def _git(root, *args, env=None):
    """Ход git или отказ. Молчаливый провал — заглушка.

    Провалившийся коммит оставляет починки незакоммиченными, то есть ровно
    в том состоянии, ради ухода из которого он и делается: `SessionStart`
    следующей сессии прочитает их как работу человека (§8). Прочитанный как
    успех, он делает это молча (незыблемое №4).
    """
    proc = tree.git(root, *args, env=env)
    if proc.returncode != 0:
        raise RuntimeError("git %s не отработал в %s: %s"
                           % (args[0], root, proc.stderr.strip()))
    return proc.stdout


def _suggestions(findings):
    """(класс, путь) -> детали. Ключ стабилен, деталей под ним бывает больше
    одной: один вид, отбирающий две пустые папки, даёт две находки с одним
    ключом. Слитые в одну нить, они обе остаются названными; дописанные
    двумя строками — дописались бы второй раз только одна из них."""
    out = {}
    for finding in findings:
        out.setdefault((finding.cls, finding.path), set()).add(finding.detail)
    return out


def _append_threads(root, suggestions):
    """Дописать предложения в `OPEN-THREADS.md`. Возвращает число дописанных.

    Дописывание идемпотентно: уже присутствующий ключ не дописывается, и
    второй прогон не меняет ни байта — инвариант 2 волны.

    Байты уходят **в конец**, а файл не перенабирается. Поверхность формы
    разрешает этому файлу ровно дописывание, и `content_diff` проверяет это
    префиксом: перенабранный целиком, хоть бы и с тем же смыслом, файл
    прочитался бы правкой содержимого и откатил бы прогон.
    """
    path = Path(root) / THREADS
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    added = []
    for (cls, rel), details in sorted(suggestions.items()):
        mark = MARK % (cls, rel)
        if mark in text:
            continue
        added.append("- %s %s: %s %s"
                     % (cls, rel, "; ".join(sorted(details)), mark))
    if not added:
        return 0
    head = text if not text or text.endswith("\n") else text + "\n"
    path.write_text(head + ("\n" if head else "") + "\n".join(added) + "\n",
                    encoding="utf-8")
    return len(added)


def _commit(root, written, removed, today):
    """Отдельный коммит по названным путям. Возвращает то, что в него ушло.

    `git add` — только по путям, которые MAINTAIN записал, никогда `-A`.
    Коммит — **тоже по путям**, а не из индекса: индекс принадлежит человеку,
    и `git commit -m` без списка путей забирает его целиком, вместе с тем,
    что человек приготовил себе. Измерено на живом git; неотслеженный файл
    ловит первое правило, заиндексированный — только второе.

    Дата коммита — `--today`, а не показание часов. Иначе часы возвращаются
    в режим с чёрного хода: слой спроса читает дату последнего коммита,
    затронувшего путь, и после первого прогона этим коммитом становится
    коммит самого MAINTAIN — то есть отчёт начинает зависеть от того, когда
    его гоняли. Ровно та поломка, из-за которой запрещён `st_mtime`.

    Каталог в `git add` не уезжает: пути называются пофайлово. Каталог
    подобрал бы всё, что внутри, — а внутри бывает и то, чего MAINTAIN не
    писал. Пустой каталог не коммитится вовсе: git их не знает.
    """
    files = [rel for rel in written if (root / rel).is_file()]
    paths = files + list(removed)
    if not paths:
        return []
    if files:
        _git(root, "add", "--", *files)
    stamp = "%sT12:00:00+00:00" % today
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = stamp
    env["GIT_COMMITTER_DATE"] = stamp
    _git(root, "commit", "-q", "-m", COMMIT_SUBJECT, "--", *paths, env=env)
    return paths


def _roll_back(root, violations, written, removed, changed, dirty_before):
    """Откат прогона целиком и отчёт отказом."""
    touched = (set(written) | set(removed)
               | {finding.path for finding in violations} | changed)
    held = sorted(touched & dirty_before)
    rollback = sorted(touched - dirty_before)

    lines = [Report(violations).render()]
    if rollback:
        # Пустой список путей `revert`-у не отдаётся: его подметание спросило
        # бы `ls-files --others` без ограничения и снесло бы всё неотслеженное
        # в дереве, включая чужое.
        report, _ = revert.run(root, rollback)
        lines.append(report.rstrip("\n"))
    lines.append("прогон откатил себя целиком: %s"
                 % (", ".join(rollback) or "откатывать нечего"))
    if held:
        lines.append("не откачено, путь был грязным до прогона: %s"
                     % ", ".join(held))
    return "\n".join(part for part in lines if part) + "\n", EXIT_VIOLATION


def run(root, today):
    """(отчёт, код возврата). Три слоя, само-проверка, откат, коммит."""
    root = Path(root)
    before = content_diff.snapshot(root)
    dirty_before = mechanical.dirty(root)

    fixed, mech_findings, skipped = mechanical.run(root)
    created, struct_findings = structural.run(root)
    removed, prune_report = prune.run(root, today=today)
    demand_report, demand_findings = demand.run(root, today=today)

    appended = _append_threads(
        root, _suggestions(struct_findings + demand_findings))
    written = sorted(set(fixed) | set(created)
                     | ({THREADS} if appended else set()))

    violations = content_diff.compare(before, content_diff.snapshot(root),
                                      deleted=removed)
    changed = mechanical.dirty(root) - dirty_before
    if violations:
        return _roll_back(root, violations, written, removed, changed,
                          dirty_before)

    staged = _commit(root, written, removed, today)
    left = sorted(mechanical.dirty(root) - dirty_before)

    out = ["## %s" % SECTIONS[0],
           Report(mech_findings).render(),
           "исправлено: %s" % (", ".join(fixed) or "ничего"),
           "пропущено как незакоммиченное: %s" % (", ".join(skipped) or "ничего"),
           "## %s" % SECTIONS[1],
           Report(struct_findings).render(),
           "создано: %s" % (", ".join(created) or "ничего"),
           "## %s" % SECTIONS[2],
           demand_report.rstrip("\n"),
           prune_report.rstrip("\n"),
           Report(demand_findings).render(),
           "дописано нитей в %s: %d" % (THREADS, appended),
           "закоммичено: %s" % (", ".join(staged) or "ничего")]
    if left:
        out.append("незакоммиченное после прогона: %s" % ", ".join(left))
    return "\n".join(part for part in out if part) + "\n", EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="fix form, show demand")
    parser.add_argument("root")
    parser.add_argument("--today", required=True,
                        help="обязателен: здесь дата удаляет папку, а не меняет текст")
    args = parser.parse_args(argv)
    report, code = run(args.root, args.today)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
