#!/usr/bin/env python3
"""`scan-tree`: инвентарь чужого дерева каталогами, а не файлами.

Строка на каталог — это и есть механизм «не втянуть 733 файла в контекст»,
и он проверяется буквально: строк столько, сколько каталогов, и ни одного
имени файла. Формат TSV с заголовком, сортировка по пути, байтово
детерминирован — как отчёты гейтов.

Часы не читаются. Даты приходят из git, а «сегодня» — параметром `--today`,
как у гейтов волны 1. Без этого у инвентаря не бывает фикстуры.

Периметр берётся у `_gitignore_prefixes`, а не у `_ignored`: `archive/` —
исключение **гейта ссылок** (секция 13), и инвентарь, унаследовавший его,
оказался бы слеп ровно к той папке, которую §18 обязывает положить в план
усыновления строкой `-> git-history`.
"""

import argparse
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.check_links import _gitignore_prefixes, _in_perimeter
from scripts.findings import EXIT_OK
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter

COLUMNS = ("path", "files", "files_subtree", "bytes_subtree", "extensions",
           "frontmatter", "first_commit", "last_commit", "mark")

NO_GIT = "no-git"
NO_HISTORY = "no-history"
NONE = "-"
FOREIGN = "foreign-repo"
NO_EXTENSION = "none"

# Синтетическое поле для записи, у которой frontmatter не прочитан. Именем
# настоящего поля стать не может: разбор не принимает ключ, начинающийся
# с `#` (`scripts/frontmatter._KEY`). Незыблемое №4 — невосстановимое либо
# помечается синтетическим, либо уходит в отчёт; отчёта у инвентаря нет,
# значит помечается здесь. Тихая пустота на этом месте утверждала бы за
# автора, что у файла полей нет, — а их просто не узнать.
UNREADABLE = "#unreadable"

# Списки обрезаются на восьми с явным хвостом. Строки каталогов не
# обрезаются никогда: выпавший каталог и есть та самая дыра, ради которой
# инвентарь пишется.
LIMIT = 8


class Node:
    __slots__ = ("rel", "files", "exts", "fields", "size", "subtree", "mark")

    def __init__(self, rel):
        self.rel = rel
        self.files = 0
        self.exts = {}
        self.fields = {}
        self.size = 0
        self.subtree = (0, 0)   # файлов и байт **в потомках**, без своих
        self.mark = NONE


def _counted(pairs):
    """`имя:число` по убыванию числа, при равенстве по имени; хвост `+N`."""
    if not pairs:
        return NONE
    items = sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(items) > LIMIT:
        head = ",".join("%s:%d" % kv for kv in items[:LIMIT])
        return "%s,+%d" % (head, len(items) - LIMIT)
    return ",".join("%s:%d" % kv for kv in items)


def _extension(name):
    suffix = Path(name).suffix
    return suffix[1:] if suffix else NO_EXTENSION


def _fields_of(path):
    """Имена полей frontmatter; `None`, если их не узнать.

    Три исхода, а не два: поля есть, полей нет (пустой кортеж) и файл
    не прочитан либо не разобран (`None`). Последнее считается отдельно,
    под `UNREADABLE`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    try:
        return tuple(parse_frontmatter(text))
    except FrontmatterError:
        return None


def _collect(base, rel, ignored, nodes):
    """Один каталог и его потомки. Возвращает (файлов в поддереве, байт).

    `base` — настоящий путь каталога, `rel` — то, как он попадёт в отчёт
    (NFC). Обход идёт по первому: macOS отдаёт имена в NFD, и путь,
    пересобранный из нормализованной строки, на томе, который нормализацию
    при поиске не делает, не открывается вовсе.
    """
    node = Node(rel)
    nodes.append(node)
    if rel != "." and (base / ".git").exists():
        node.mark = FOREIGN
        return 0, 0
    subtree_files, subtree_size = 0, 0
    for entry in sorted(base.iterdir(), key=lambda p: p.name):
        child = unicodedata.normalize(
            "NFC", entry.name if rel == "." else "%s/%s" % (rel, entry.name))
        if entry.is_symlink():
            continue
        if entry.is_dir():
            if entry.name == ".git" or not _in_perimeter(child, ignored):
                continue
            files, size = _collect(entry, child, ignored, nodes)
            subtree_files += files
            subtree_size += size
            continue
        if not entry.is_file() or not _in_perimeter(child, ignored):
            continue
        node.files += 1
        size = entry.stat().st_size
        node.size += size
        ext = _extension(entry.name)
        node.exts[ext] = node.exts.get(ext, 0) + 1
        if ext == "md":
            fields = _fields_of(entry)
            for field in (fields if fields is not None else (UNREADABLE,)):
                node.fields[field] = node.fields.get(field, 0) + 1
    node.subtree = (subtree_files, subtree_size)
    return subtree_files + node.files, subtree_size + node.size


def _history(root):
    """Что git знает про это дерево: (есть репозиторий, есть коммиты).

    Остаточный риск назван вслух: чужая папка, лежащая внутри чужого же
    репозитория, ответит «репозиторий есть», и даты приедут из объемлющего.
    Это не заглушка — история у файлов настоящая, — но токен `no-git`
    в таком дереве не появится. Механизм под это не заводится, пока
    поломка не наблюдена (незыблемое №3).
    """
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                            cwd=str(root), capture_output=True, text=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return False, False
    head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"],
                          cwd=str(root), capture_output=True, text=True)
    return True, head.returncode == 0


def _dates(root, rel, has_git, has_history):
    if not has_git:
        return NO_GIT, NO_GIT
    if not has_history:
        return NO_HISTORY, NO_HISTORY
    proc = subprocess.run(
        ["git", "log", "--date=short", "--format=%cd", "--", rel],
        cwd=str(root), capture_output=True, text=True)
    dates = [line.strip() for line in proc.stdout.split("\n") if line.strip()]
    if not dates:
        return NONE, NONE
    return dates[-1], dates[0]


def render(root, today=None):
    root = Path(root)
    ignored = _gitignore_prefixes(root)
    nodes = []
    _collect(root, ".", ignored, nodes)
    has_git, has_history = _history(root)
    out = ["# scan-tree today=%s" % (today or "unset"), "\t".join(COLUMNS)]
    for node in sorted(nodes, key=lambda n: n.rel):
        first, last = _dates(root, node.rel, has_git, has_history)
        if node.mark == FOREIGN:
            cells = [node.rel, NONE, NONE, NONE, NONE, NONE, first, last, FOREIGN]
        else:
            subtree_files, subtree_size = node.subtree
            cells = [node.rel,
                     str(node.files),
                     str(subtree_files + node.files),
                     str(subtree_size + node.size),
                     _counted(node.exts),
                     _counted(node.fields),
                     first, last, node.mark]
        out.append("\t".join(cells))
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="inventory of a foreign tree")
    parser.add_argument("root")
    parser.add_argument("--today", default=None,
                        help="дата явным параметром: без неё у инвентаря не бывает фикстуры")
    args = parser.parse_args(argv)
    sys.stdout.write(render(args.root, today=args.today))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
