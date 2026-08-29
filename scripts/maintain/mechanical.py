#!/usr/bin/env python3
"""Слой «форма механически»: оба гейта плюс детерминированные починки.

Чинится не находка, а **файл**: форм-файл возвращается к эталону из
`scaffold/`. Третьего определения формы волна не заводит, и второго тоже:
что именно возвращается целиком и какие секции `CLAUDE.md` принадлежат
плагину, спрашивается у `surface`, а не объявляется здесь заново.

Что не чинится — уходит в отчёт целиком, вместе с находкой гейта. Чинить
`unresolved` по догадке о basename отвергнуто: ссылка начнёт резолвиться,
гейт позеленеет, а указывать будет не туда, куда автор писал.

**`unresolved` в `views.base` этот слой не чинит, и это расхождение с
таблицей спеки волны**, вынесенное автору. Класса там не бывает: периметр
гейта ссылок — markdown-файлы, а backtick-сканирование сверх того ограничено
`CLAUDE.md`, `README.md`, `SKILL.md` и `.claude/rules/*.md` (решение волны 1,
закрытое в CLAUDE.md разделом «Не переоткрывать»). `.base` не читает ни одна
из двух веток, поэтому находки, которую строка таблицы велит чинить, гейт не
производит ни при каких входных данных. Заводить под неё починку значило бы
завести механизм, чинящий то, чего никто не наблюдал, — незыблемое №3. Стало
папке вида пусто или её не стало вовсе, показывает слой «форма содержательно»
классом `view-selects-nothing`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import check_frontmatter, check_links
from scripts.adopt import tree
from scripts.maintain import surface

ROOT = Path(__file__).resolve().parent.parent.parent
SCAFFOLD = ROOT / "scaffold"

CLAUDE = "CLAUDE.md"


def dirty(root):
    """Пути с незакоммиченными изменениями. Их MAINTAIN не трогает.

    Публично, потому что спрашивают двое: этот слой — чтобы не переписать
    работу человека, и `run` — чтобы сравнить дерево до и после прогона.
    Второй разбор `git status` разошёлся бы с первым молча.

    Три подробности вызова, каждая с ценой бездействия.

    `-z`: без него git обрамляет не-ASCII путь кавычками и экранирует его
    восьмеричными последовательностями — `sources/дубль.md` вернулся бы
    именем, которого в дереве нет, и грязный путь прочитался бы чистым.

    `-uall`: без него неотслеженное поддерево возвращается одной строкой
    каталога (`?? .claude/rules/`), и файл внутри неё не совпал бы ни с
    одним ключом.

    Переименование даёт **две** записи подряд, и вторая приходит голой, без
    префикса состояния. Прочитанная как обычная, она потеряла бы три первых
    знака имени.

    Отказ git — исключение, а не пустое множество: пустое здесь значило бы
    «всё чисто», то есть молчаливую заглушку, за которой слой переписал бы
    форму дерева, о котором ничего не знает (незыблемое №4).
    """
    proc = tree.git(root, "status", "--porcelain", "-z", "-uall")
    if proc.returncode != 0:
        raise RuntimeError("git status не отработал в %s: %s"
                           % (root, proc.stderr.strip()))
    entries = [line for line in proc.stdout.split("\0") if line]
    out = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        out.add(entry[3:])
        if set(entry[:2]) & {"R", "C"} and index < len(entries):
            out.add(entries[index])
            index += 1
    return out


def _whole_files():
    """Файлы каркаса, которые поверхность отдаёт плагину целиком.

    Не список литералом, а вопрос к `surface`: строка `bytes` поверхности —
    единственное основание переписать чужой файл побайтово, и спросить её
    надо исполняемо. Убери её оттуда — и починка перестанет происходить,
    а не разойдётся с доказательством молча.
    """
    out = []
    for path in sorted(SCAFFOLD.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(SCAFFOLD).as_posix()
        if surface.covers(rel, "bytes"):
            out.append((rel, path))
    return out


def _restore_whole(root, dirty_paths, fixed, skipped):
    for rel, reference in _whole_files():
        target = root / rel
        if target.exists() and target.read_bytes() == reference.read_bytes():
            continue
        if rel in dirty_paths:
            skipped.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(reference.read_bytes())
        fixed.append(rel)


def _restore_sections(root, dirty_paths, fixed, skipped):
    """Форм-секции `CLAUDE.md` — по секции, а не файлом.

    Файлом нельзя: в том же файле стоит описание домена, и оно авторское.
    Отсутствующего файла этот слой не создаёт — создание `CLAUDE.md`
    поверхность не разрешает ни одной строкой.
    """
    path = root / CLAUDE
    if not path.exists():
        return
    titles = surface.names(CLAUDE, "section")
    reference = (SCAFFOLD / CLAUDE).read_text(encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    changed = text
    for title in titles:
        want = surface.section(reference, title)
        have = surface.section(changed, title)
        # Отсутствующая секция не дописывается: место, куда её вставить,
        # определяется прозой вокруг, а проза авторская.
        if want and have and want != have:
            changed = surface.replace_section(changed, title, want)
    if changed == text:
        return
    if CLAUDE in dirty_paths:
        skipped.append(CLAUDE)
        return
    path.write_text(changed, encoding="utf-8")
    fixed.append(CLAUDE)


def run(root):
    """(исправленные пути, находки, пропущенные грязные пути).

    Находки снимаются **после** починок. Отчёт этого слоя — то, что осталось
    автору, а не то, что MAINTAIN нашёл и тут же починил сам: снятый до
    починок, он назвал бы автору уже несуществующее и не покраснел бы
    оттого, что починка не состоялась.

    Пропущенное — **строка отчёта, а не находка**: класс утверждал бы, что
    что-то не так с деревом, а не так здесь ровно ничего — просто путь
    сейчас в работе у человека. Спека волны так и говорит: «такой путь
    уходит в отчёт». Заводить под это одиннадцатый класс значило бы завести
    имя без стоящего за ним нарушения.

    Пропущенным зовётся то, что чинилось бы, да нельзя. Файл, которому
    чинить нечего, в этой строке не значится, даже будучи грязным: иначе
    отчёт рос бы от любой правки рядом.
    """
    root = Path(root)
    dirty_paths = dirty(root)
    fixed, skipped = [], []

    _restore_whole(root, dirty_paths, fixed, skipped)
    _restore_sections(root, dirty_paths, fixed, skipped)

    findings = list(check_links.scan(root).findings)
    findings.extend(check_frontmatter.scan(root).findings)
    return sorted(fixed), findings, sorted(skipped)
