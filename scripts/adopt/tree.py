#!/usr/bin/env python3
"""Общее для мутирующих команд ADOPT: git, точка отката, манифест.

Границу рабочего каталога здесь не переопределяют: предикат один на пакет и
живёт в `scripts/boundary.py`. Копия расходится молча — три разошедшиеся
таблицы зон однажды стоили этому репозиторию критерия выхода.

Пути из git читаются **только** через `git_zlines`, то есть с `-z`. Без него
git отдаёт не-ASCII имена в C-кавычках: `local/заметка.md` приезжает строкой
`"local/\\320\\267..."`, и всё, что с ней делают дальше, работает не с тем
файлом. Проверено на живом git; чужие деревья в этом пакете русские целиком,
так что случай не редкий, а обычный.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import boundary

# Точка отката живёт внутри `.git`: это единственное место внутри корня,
# невидимое для `git status`, и файл там принадлежит плагину, а не автору.
# Тот же приём, что у волны 2.
BASE_FILE = "adopt-base"

# Журнал файлов, изменённых правкой ссылок. Без него переписанный файл
# выглядит уходом с плана: он был в коммите «как было», изменился, а
# источником ни одной строки не является — то есть `unagreed-change` по
# построению. Журнал здесь механизм, а не исключение в проверке: исключение
# пришлось бы вписать в `check-plan` словами, и оно молча накрыло бы любую
# другую правку тех же файлов.
TOUCHED_FILE = "adopt-touched"


def git(root, *args, env=None):
    """Ход git в корне. `env` — среда целиком, а не добавка к текущей.

    Нужна она ровно одному вызывающему: MAINTAIN пиннит дату собственного
    коммита через `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`, потому что дату
    этого коммита слой спроса потом читает обратно. Смысл ключей живёт у
    вызывающего: обёртка, дописывающая дату сама, решала бы за ADOPT, чем
    датировать его коммиты, а ADOPT датирует их часами машины по делу.
    """
    return subprocess.run(["git", *args], cwd=str(root), env=env,
                          capture_output=True, text=True)


def git_zlines(root, *args):
    """Строки вывода `git ... -z`: разделитель — нулевой байт, кавычек нет.

    Флаг `-z` ставит вызывающий, а не эта обёртка: у разных подкоманд он
    стоит в разных местах командной строки, и обёртка, дописывающая его
    сама, ошиблась бы позицией.
    """
    return [line for line in git(root, *args).stdout.split("\0") if line]


def head(root):
    proc = git(root, "rev-parse", "--verify", "-q", "HEAD")
    return proc.stdout.strip() if proc.returncode == 0 else None


def _meta(root, name):
    return Path(root) / ".git" / name


def read_base(root):
    path = _meta(root, BASE_FILE)
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def write_base(root, sha):
    _meta(root, BASE_FILE).write_text(sha + "\n", encoding="utf-8")


def read_touched(root):
    """Пары `(источник строки плана, изменённый файл)`, по одной на строку."""
    path = _meta(root, TOUCHED_FILE)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line:
            continue
        source, _, rel = line.partition("\t")
        out.append((source, rel))
    return out


def record_touched(root, source, files):
    """Дописать записи журнала. Накопительно и без дублей.

    Накопительно, потому что этапов много: файл, переписанный ради одной
    строки плана, обязан остаться названным, когда исполняется следующая.
    Без дублей, потому что цепочка повторно входима — оборвавшийся ход
    доводится вторым запуском, и второй запуск не должен выглядеть вторым
    изменением того же файла.
    """
    entries = set(read_touched(root))
    entries.update((source, rel) for rel in files)
    _write_touched(root, entries)


def _write_touched(root, entries):
    _meta(root, TOUCHED_FILE).write_text(
        "".join("%s\t%s\n" % pair for pair in sorted(entries)),
        encoding="utf-8")


def forget_touched(root, paths):
    """Снять записи журнала об этих путях. Возвращает число снятых.

    Запись журнала оправдывает правку файла под согласованной строкой:
    `check-plan` видит изменившийся файл, находит запись и молчит. Откат
    возвращает файл в `HEAD`, и оправдание перестаёт что-либо описывать —
    но, оставшись, оно продолжает работать. Следующая правка того же файла,
    уже мимо плана, оправдывается им молча, то есть настоящий
    `unagreed-change` не называется.

    Ложного обвинения из устаревшей записи не выйдет: журнал только
    оправдывает. Выйдет пропуск, а пропуск здесь дороже.

    Сравнение посегментное, а не по подстроке: `journal` не предок
    `journalism.md`, и запись о соседнем имени снимать не за что.
    """
    entries = read_touched(root)
    kept = [(source, rel) for source, rel in entries
            if not any(rel == p or rel.startswith(p.rstrip("/") + "/")
                       for p in paths)]
    if len(kept) != len(entries):
        _write_touched(root, kept)
    return len(entries) - len(kept)


def inside(root, target):
    """Путь внутри корня. Предикат чужой, здесь только вопрос.

    Порядок аргументов `boundary.outside(путь, корень)` — не деталь вкуса:
    переставленный, он делает `inside` тождественно ложным, и `revert`
    отказывает по каждому пути, а тест на отказ по пути вне корня проходит
    зелёным. Разводит это `TestInside`.
    """
    return not boundary.outside(Path(root) / target, Path(root))


def nested_repositories(root):
    """Каталоги с `.git` внутри, кроме самого корня. Единственный механически
    определяемый факт о чужом репозитории (§18)."""
    root = Path(root)
    out = []

    def walk(base, rel):
        for entry in sorted(base.iterdir(), key=lambda p: p.name):
            if not entry.is_dir() or entry.is_symlink():
                continue
            if entry.name == ".git":
                continue
            child = entry.name if not rel else "%s/%s" % (rel, entry.name)
            if (entry / ".git").exists():
                out.append(child)
                continue        # внутрь чужого репозитория не спускаемся
            walk(entry, child)

    walk(root, "")
    return out


def manifest(root):
    """путь → (sha256 содержимого, режим), плюс множество непустых каталогов.

    Каталоги в манифесте — только непустые: git пустых каталогов не знает и
    вернуть их не может, и требовать этого от `revert` значило бы требовать
    невозможного. Опустевшие каталоги — названный остаток, он уходит в отчёт.

    Режим берётся вместе с содержимым и это не педантизм: `git mv` его
    сохраняет, а восстановление записью байтов — нет, и манифест без режима
    объявил бы такой откат побайтовым.

    Файлы внутри вложенного репозитория берутся — не потому, что `revert` их
    возвращает (он не может), а потому, что их равенство доказывает, что до
    них никто не дотянулся.
    """
    root = Path(root)
    files, dirs = {}, set()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files[rel] = (digest, path.stat().st_mode & 0o777)
        dirs.add(path.parent.relative_to(root).as_posix())
    return files, frozenset(dirs)
