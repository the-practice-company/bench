"""Сводка старта сессии и чекпоинт незакоммиченного.

На диск не пишется ничего: сводка вычисляется и печатается в stdout, откуда
попадает в контекст сессии. Вычисляемое не обязано лежать на диске — оно
вычисляется, а файл, перезаписываемый на каждом старте, делает дерево грязным
навсегда и ломает разводку «незакоммиченное означает, что здесь работал
человек», на которой стоят и этот хук, и `Stop`.

Цена названа честно: сводки не видно в Obsidian, её читает только агент внутри
сессии.

Каждый ответ git берётся ровно один раз и складывается в `State`. Между двумя
`git status` человек в Obsidian успевает сохранить файл — и тогда отчёт говорит
про одно дерево, а чекпоинт забирает другое.

Все разборы вывода git идут через `-z`. Без него git отдаёт путь с кириллицей
закавыченным, а каждую букву — тройкой восьмеричных цифр после обратной косой;
русские имена в контекстном репозитории норма, а не край, и ни один такой путь
не совпал бы ни со своей находкой, ни со своим файлом. Образец этой записи
здесь не приведён нарочно: он неотличим от UNC-пути, и гейт пакета находит
в нём absolute-path — ровно так, как и должен.
"""

import datetime
import subprocess
import unicodedata
from pathlib import Path

from scripts.findings import severity

INBOX = "inbox"
CHECKPOINT_MESSAGE = "чекпоинт: изменения, сделанные вне сессии"

# Личность коммиттера передаётся флагами, а не берётся из конфига. Причин две:
# коммит делает плагин на своей власти и подписывать им человека нечестно,
# и `user.email` в среде может быть не настроен вовсе — тогда `git commit`
# падает не по делу.
_IDENTITY = ("-c", "user.email=twinkle@local", "-c", "user.name=twinkle")


class GitSilent(Exception):
    """git не ответил: значение невосстановимо.

    Отдельный тип, а не пустой ответ, потому что пустой ответ `git status`
    означает «дерево чистое». Спутать эти два состояния — завести молчаливую
    заглушку (незыблемое №4): сводка сказала бы «незакоммиченного: нет» ровно
    там, где не знает ничего, и чекпоинт промолчал бы о чужой работе.
    """


def _git(root, *args):
    """stdout git или `GitSilent` с причиной. Никогда не пустая строка молча."""
    try:
        result = subprocess.run(["git", *args], cwd=str(root),
                                capture_output=True, text=True)
    except OSError as error:
        # git может отсутствовать целиком. Обвал здесь дошёл бы до шима и стал
        # бы строкой «hook.py вернул 1» — кодом возврата вместо причины.
        raise GitSilent("git не запустился: %s" % error)
    if result.returncode != 0:
        first = (result.stderr.strip().split("\n") or [""])[0]
        raise GitSilent("git %s вернул %d: %s" % (args[0], result.returncode, first))
    return result.stdout


def _plural(count, one, few, many):
    """Русское число словами. Сводку читает человек, и «1 файлов» в ней —
    такой же шум, как неверная дата."""
    if count % 100 in (11, 12, 13, 14):
        return many
    if count % 10 == 1:
        return one
    if count % 10 in (2, 3, 4):
        return few
    return many


def _date(text):
    """Дата из вывода git или None. Нечитаемая дата — не повод обвалить хук."""
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def _unmerged(code):
    """Строка `git status` про незавершённое слияние.

    Правило дословно из формата: конфликт — это `U` в любой колонке плюс две
    пары, где обе стороны сделали одно и то же (`AA`, `DD`).
    """
    return "U" in code or code in ("AA", "DD")


def status(root):
    """Незакоммиченные пути и признак незавершённого слияния.

    `-uall` не украшение: без него git схлопывает целиком неотслеженный
    каталог в одну строку `?? areas/`. Находка гейта приходит на
    `areas/bad.md`, в списке незакоммиченного лежит `areas/` — они не
    совпадают ни одним символом, и красное молча уезжает в чекпоинт.

    Переименование в `-z` приходит двумя полями подряд, новый путь и старый;
    в список идут оба: `git add` по исчезнувшему пути записывает удаление,
    без него чекпоинт оставил бы половину переименования.
    """
    fields = _git(root, "status", "--porcelain", "-z", "-uall").split("\0")
    dirty = []
    unmerged = False
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        unmerged = unmerged or _unmerged(code)
        dirty.append(path)
        if "R" in code or "C" in code:
            if index < len(fields) and fields[index]:
                dirty.append(fields[index])
            index += 1
    return dirty, unmerged


def git_root(root):
    """Корень git, от которого `--porcelain` считает свои пути.

    Спрашивается отдельной функцией, потому что спрашивают дважды: сводка
    отказывается от чекпоинта на разъехавшихся корнях, `Stop` на них сводит
    пути к одной форме. Два места, задающие один вопрос двумя способами,
    однажды получат на него два разных ответа.
    """
    return _git(root, "rev-parse", "--show-toplevel").strip()


def last_checkpoint(root):
    """Дата последнего коммита и число файлов в нём. `(None, None)` — истории нет.

    Зовётся только после успешного `git status`, то есть в заведомо git-овом
    каталоге: единственная причина, по которой `git log` здесь молчит, —
    пустая история, и она не отказ, а ответ.
    """
    try:
        date = _git(root, "log", "-1", "--format=%ad", "--date=short").strip()
    except GitSilent:
        return None, None
    names = _git(root, "show", "--format=", "--name-only", "-z",
                 "--first-parent", "-m", "HEAD")
    return date, len([name for name in names.split("\0") if name])


def inbox_items(root):
    """Элементы inbox, пути от корня, в NFC.

    NFC — потому что то же приведение делает индекс ссылок: macOS отдаёт имя
    файла и git отдаёт имя файла в разных нормализациях, и несведённые к одной
    они не совпадают, оставаясь одинаковыми на вид.
    """
    folder = Path(root) / INBOX
    if not folder.exists():
        return []
    return sorted(unicodedata.normalize("NFC", path.relative_to(root).as_posix())
                  for path in folder.rglob("*.md"))


def first_seen(root):
    """Дата первого коммита каждого элемента inbox — одним проходом git log.

    Один проход, а не вызов на файл: inbox — это место, где файлов много по
    построению, и десяток подпроцессов на старте сессии человек увидит.

    Формат разбирается по своим разделителям: `%x00` перед датой отбивает
    начало записи о коммите, `-z` отбивает имена. `git log` идёт от новых
    к старым, поэтому последняя увиденная дата пути — самая ранняя.
    """
    raw = _git(root, "log", "--diff-filter=A", "--format=%x00%ad",
               "--date=short", "--name-only", "-z", "--", INBOX)
    seen = {}
    date = None
    expect_date = True
    for field in raw.split("\0"):
        if not field:
            expect_date = True
            continue
        if expect_date:
            date, expect_date = field, False
            continue
        rel = unicodedata.normalize("NFC", field.lstrip("\n"))
        if rel:
            seen[rel] = date
    return seen


def inbox_state(root, last_date):
    """Сколько элементов в inbox, возраст старшего в днях и сколько не в git.

    Возраст берётся как разница между датой последнего коммита репозитория
    и датой первого коммита файла: обе даты приходят из git, поэтому сводка
    воспроизводима и не зависит ни от часов машины, ни от дня прогона.

    Элемент, которого в git нет, датировать нечем. Подставить ему ноль дней —
    молчаливая заглушка (незыблемое №4), и соврала бы она ровно про тот
    элемент, который дольше всех лежит неучтённым. Такие считаются отдельно
    и называются в отчёте числом.
    """
    items = inbox_items(root)
    if not items or last_date is None:
        return len(items), None, len(items)
    seen = first_seen(root)
    dates = [_date(seen[rel]) for rel in items if rel in seen]
    dates = [d for d in dates if d is not None]
    undated = len(items) - len(dates)
    last = _date(last_date)
    if not dates or last is None:
        return len(items), None, len(items)
    return len(items), (last - min(dates)).days, undated


class State:
    """Всё, что сводка знает о репозитории, посчитанное за один проход.

    `dirty is None` и `dirty == []` — разные состояния: «не спросили» против
    «спросили, чисто». Различие несёт тип, а не значение, потому что второе
    разрешает чекпоинт, а первое запрещает его.
    """

    __slots__ = ("git_root", "last_date", "last_files", "dirty", "unmerged",
                 "inbox_count", "inbox_days", "inbox_undated", "problems")

    def __init__(self):
        self.git_root = None
        self.last_date = None
        self.last_files = None
        self.dirty = None
        self.unmerged = False
        self.inbox_count = 0
        self.inbox_days = None
        self.inbox_undated = 0
        self.problems = []


def collect(root):
    """Один проход по git и файловой системе. Отказы копятся, а не всплывают.

    Отказ любого вопроса оставляет своё поле неизвестным и добавляет строку
    в `problems`: сводка печатается всегда, а невосстановимое значение
    называется словом, а не подменяется правдоподобным.
    """
    state = State()
    try:
        state.dirty, state.unmerged = status(root)
    except GitSilent as error:
        state.problems.append("состояние дерева не прочитано: %s" % error)
    if state.dirty is not None:
        try:
            state.git_root = git_root(root)
        except GitSilent as error:
            state.problems.append("корень git не прочитан: %s" % error)
        try:
            state.last_date, state.last_files = last_checkpoint(root)
        except GitSilent as error:
            state.problems.append("последний коммит не прочитан: %s" % error)
    try:
        state.inbox_count, state.inbox_days, state.inbox_undated = inbox_state(
            root, state.last_date)
    except GitSilent as error:
        state.inbox_count = len(inbox_items(root))
        state.inbox_undated = state.inbox_count
        state.problems.append("возраст inbox не прочитан: %s" % error)
    return state


def render(state):
    """Три строки сводки, дословно по секции 1 спеки."""
    if state.dirty is None:
        first = "последний чекпоинт: неизвестно — git не ответил"
        second = "незакоммиченного: неизвестно — git не ответил"
    else:
        if state.last_date is None:
            first = "последний чекпоинт: коммитов ещё нет"
        else:
            first = "последний чекпоинт: %s, %d %s" % (
                state.last_date, state.last_files,
                _plural(state.last_files, "файл", "файла", "файлов"))
        if not state.dirty:
            second = "незакоммиченного: нет"
        else:
            second = "незакоммиченного: %d %s" % (
                len(state.dirty),
                _plural(len(state.dirty), "файл", "файла", "файлов"))

    if not state.inbox_count:
        third = "inbox: 0"
    elif state.inbox_days is not None:
        third = "inbox: %d, старшему %d %s" % (
            state.inbox_count, state.inbox_days,
            _plural(state.inbox_days, "день", "дня", "дней"))
        if state.inbox_undated:
            third += " (%d ещё не в git)" % state.inbox_undated
    elif state.problems:
        third = "inbox: %d, возраст неизвестен: git не ответил" % state.inbox_count
    else:
        # git ответил на всё, что спрашивали, а возраста нет: датировать нечем,
        # ни один элемент ещё не закоммичен.
        third = ("inbox: %d, возраст неизвестен: ни один элемент не в git"
                 % state.inbox_count)
    return "\n".join([first, second, third])


def errors(findings):
    """Красное — то, что делает `./check` красным, то есть тяжесть `error`.

    `orphan` — тяжесть `report`, `ambiguous` — `warning`; ни одна из них не
    красная нигде больше в этом репозитории. Считать красной всякую находку
    значит запретить чекпоинт репозиторию, где просто есть файл, на который
    никто не сослался, — то есть запретить навсегда.
    """
    return [f for f in findings if severity(f.cls) == "error"]


def committable(root, paths):
    """Пути, которые можно ставить в индекс, и пропущенные каталоги.

    Сдвинутый указатель сабмодуля приходит в `git status` одной строкой
    с путём каталога. Назвать его поимённо не лучше, чем забрать всё дерево
    разом: спека запрещает второе именно потому, что оно уносит указатели
    `knowledge/`, а чужой репозиторий двигает его владелец, не плагин.
    """
    staged, skipped = [], []
    for rel in paths:
        (skipped if (Path(root) / rel).is_dir() else staged).append(rel)
    return staged, skipped


def checkpoint(root, paths):
    """`git add` по названным путям и коммит. Никогда по всему дереву.

    Взять дерево целиком значило бы забрать сдвиги указателей сабмодулей
    `knowledge/` и параллельные правки человека в Obsidian в коммит, который
    плагин делает на своей власти.
    """
    if not paths:
        return
    _git(root, "add", "--", *paths)
    _git(root, *_IDENTITY, "commit", "-q", "-m", CHECKPOINT_MESSAGE)
