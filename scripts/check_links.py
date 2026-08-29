#!/usr/bin/env python3
"""Гейт ссылок.

Классы: unresolved, md-link-to-file, link-to-transient, escapes-root,
dead-allow, broad-allow, ambiguous, orphan, undecodable. Секция 13 спеки
плюс два класса, которых в её таблице нет: `broad-allow` и `undecodable`
заведены под наблюдённые поломки этого гейта и вынесены автору правкой
спеки (незыблемое №7).
"""

import argparse
import re
import sys
import unicodedata
from fnmatch import fnmatchcase
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import paths as pathlib_rules
from scripts import zones
from scripts.findings import Finding, Report
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter

_FENCE = re.compile(r"```.*?```", re.S)
# Ограничитель inline-кода — прогон из N backtick'ов, закрывает его такой же
# прогон: ``двойным`` оборачивают текст, в котором backtick и встречается.
# Форма «backtick, не-backtick, backtick» знала только N=1, и на ``пути``
# расходились оба прохода: backtick-цикл видел две пустые вставки и терял
# токен целиком, а wikilink-цикл переставал считать содержимое кодом
# и читал пример как живую ссылку.
_INLINE = re.compile(r"(?<!`)(`+)([^\n]*?)\1(?!`)")
_WIKILINK = re.compile(r"!?\[\[([^\]\n]+)\]\]")
_MDLINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")
# Ссылка-сноска: `[метка]: цель "заголовок"`. Даёт ту же цель, что инлайновая
# форма, но `](` в ней нет, поэтому мимо `_MDLINK` проходили сразу два класса,
# `escapes-root` и `md-link-to-file`. Определение занимает строку целиком:
# в цели нет пробелов, после неё допустим только заголовок в кавычках. Иначе
# ссылкой считалась бы проза вида `[1]: см. ниже, в разделе про зоны`.
# `[^метка]:` — примечание Obsidian, а не ссылка: его текст цели не называет
# вовсе, и однословное примечание иначе становилось бы `md-link-to-file`.
_MDREF = re.compile(
    r"^ {0,3}\[(?!\^)([^\]\n]+)\]:[ \t]*(<[^>\n]*>|\S+)"
    r"(?:[ \t]+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^)\n]*\)))?[ \t]*$")

SCANNED_FOR_TOKENS = ("CLAUDE.md", "README.md", "SKILL.md")
RULES_PREFIX = ".claude/rules/"

ALLOWLIST_NAME = ".link-allow"

# Закрытый словарь архетипов спеки английский: journal / pipeline / registry
# (секции 9 и 28). Пока здесь стояло русское слово, периметр сирот у любой
# коллекции, созданной рецептом, был пуст — класс `orphan` на живом выводе
# не мог сработать ни разу.
REGISTRY_ARCHETYPE = "registry"


def _read(path):
    """Текст файла строго в UTF-8. Отказ уходит наверх, а не заменяется.

    Здесь **нельзя** то, что верно в `check_package._iter_package_files`.
    Там чтение с `errors="replace"` правильно: замещающий знак ни на что не
    похож, абсолютным путём он не станет никогда, и замена стоит ровно
    одного невосстановимого байта. Здесь тот же приём давал обратное. Гейт
    ссылок читает текст **целей**, а замещающий знак от имени файла ничем не
    отличается, и находка называла цель, которой никто не писал:

        `core/заметка.md` есть, `core/utf8.md` и `core/cp1251.md` несут
        дословно одну и ту же ссылку `[[заметка]]` в двух кодировках —
        вторая давала `unresolved [[???????]]` и код возврата 2.

    С другой стороны та же замена глотала файл целиком: `.md` в UTF-16
    давал пустой отчёт, ни одной ссылки не видно. Сказать неправду хуже,
    чем промолчать, но здесь было и то и другое сразу.

    Незыблемое №4: невосстановимое значение уходит в отчёт. Файл, который
    не читается, — находка `undecodable` про сам файл; ссылки в нём не
    разбираются вовсе, потому что знать их неоткуда. Крах, ради которого
    заводилась замена, при этом не возвращается: исключение ловят все
    вызывающие, отчёт остаётся, код возврата — 2, как и был.
    """
    return path.read_text(encoding="utf-8")


def _undecodable(rel, error, consequence):
    """Находка про файл, который не прочитан. Строка — 1, и это не заглушка.

    Номера строки у такого файла нет: строки появляются после декодирования,
    а его не было. Считать `\\n` в байтах — угадывать: в UTF-16 перевод
    строки байтом `0x0a` не записан. Подставить угаданное — ровно тот
    подлог, ради устранения которого класс и заведён, поэтому находка
    ставится на файл (строка 1), как `orphan` и `skill-without-eval`.

    Байт и позиция — из самого исключения, то есть наблюдаемы и
    воспроизводимы; `consequence` называет, что именно осталось
    непроверенным, потому что у разных читателей это разное.
    """
    return Finding("undecodable", rel, 1,
                   "не читается как UTF-8: байт 0x%02x в позиции %d, %s"
                   % (error.object[error.start], error.start, consequence))


class AllowEntry:
    """Запись аллоулиста и множество целей, которые она погасила.

    `hits` — множество, а не флаг `used`. Флаг отвечал на один вопрос
    («сработала ли»), а вопросов два: правило может не гасить ничего
    (`dead-allow`) и может гасить что угодно (`broad-allow`). Второе
    по флагу неотличимо от здоровой записи — оно и не отличалось.
    """

    __slots__ = ("pattern", "reason", "line", "hits")

    def __init__(self, pattern, reason, line):
        self.pattern = pattern
        self.reason = reason
        self.line = line
        self.hits = set()


def parse_allowlist(text):
    entries = []
    for lineno, raw in enumerate(text.split("\n"), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "#" in stripped:
            pattern, reason = stripped.split("#", 1)
            entries.append(AllowEntry(pattern.strip(), reason.strip() or None, lineno))
        else:
            entries.append(AllowEntry(stripped, None, lineno))
    return entries


def allow_is_anchored(pattern):
    """Есть ли в шаблоне хоть один сегмент пути без глоб-метасимволов.

    Признак «правило слишком широко». Запрет голой подстроки (`a`) закрыл
    синтаксис и не закрыл семантику: `*a*`, `*`, `?*`, `[a-z]*` гасят
    `unresolved` по всему репозиторию, а `dead-allow` о них молчит —
    правило-то сработало. Уцелевшее исключение, тихо ослабляющее гейт, —
    это ровно то, против чего спека завела `dead-allow`; здесь ослабление
    шире и вдобавок выглядит живым.

    Считается литеральный сегмент, а не литеральное начало. Строгий признак
    «первый сегмент литерален» отнял бы `**/items/*` — правило, называющее
    имя коллекции, а не место, — и это уже не наблюдённая поломка, а
    догадка. Ни одного литерального сегмента значит, что правило не
    называет ни места, ни имени: подпасть под него может что угодно.

    Чего признак не ловит: якорь ничего не говорит о размере. `черновики/*`
    погасит хоть сотню целей — и это законная «строка на паттерн» секции 13,
    а не поломка: раздел, которого ещё нет, называется именно так. Сузить
    правило до одной цели значило бы отменить паттерны вовсе.
    """
    return any(segment and not pathlib_rules.is_pattern(segment)
               for segment in pattern.split("/"))


class Link:
    __slots__ = ("target", "line", "raw", "kind")

    def __init__(self, target, line, raw, kind):
        self.target = target
        self.line = line
        self.raw = raw
        self.kind = kind


def _blank_fences(text):
    """Вырезает только ```-блоки, сохраняя переводы строк и inline-код внутри строк.

    Отдельно от _blank_code: backtick-сканирование ниже само читает inline-код
    (это его источник токенов), ему нужно только не видеть fenced-примеры.
    """
    def keep_newlines(match):
        return re.sub(r"[^\n]", " ", match.group(0))
    return _FENCE.sub(keep_newlines, text)


def _blank_code(text):
    """Вырезает код, сохраняя переводы строк, чтобы номера не поехали."""
    def keep_newlines(match):
        return re.sub(r"[^\n]", " ", match.group(0))
    return _INLINE.sub(keep_newlines, _blank_fences(text))


def extract_links(text):
    clean = _blank_code(text)
    out = []
    for lineno, line in enumerate(clean.split("\n"), start=1):
        for match in _WIKILINK.finditer(line):
            target = match.group(1).split("|")[0].split("#")[0].split("^")[0].strip()
            out.append(Link(target, lineno, match.group(0), "wikilink"))
        for match in _MDLINK.finditer(line):
            out.append(Link(match.group(1).strip(), lineno, match.group(0), "mdlink"))
        # Определение ссылки-сноски судится как markdown-ссылка: цель у них
        # одна и та же, а `[метка]` в тексте — только указатель на эту строку.
        # В отчёт идёт строка целиком: `[out]` без цели автору ничего не
        # говорит, чинить нужно именно здесь.
        match = _MDREF.match(line)
        if match:
            target = match.group(2).strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1].strip()
            out.append(Link(target, lineno, line.strip(), "mdlink"))
    return out


def _index(root, ignored):
    """basename без расширения -> список относительных путей.

    Для файла в корне репозитория basename и относительный путь без
    расширения — одна и та же строка (`README` == `README`): нельзя
    регистрировать её дважды под одним ключом, иначе один файл выглядит
    как два кандидата и bare-ссылка на него ложно помечается ambiguous.

    Тот же периметр (`_ignored`/`_in_perimeter`), что у обоих главных
    циклов: иначе файл из архива или .gitignore-поддерева становится
    резолвящейся целью, хотя гейт его нигде больше не читает.
    """
    index = {}
    for path in root.rglob("*.md"):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        stem = unicodedata.normalize("NFC", path.stem)
        rel_stem = unicodedata.normalize("NFC", rel[:-3])
        for key in {stem, rel_stem}:
            bucket = index.setdefault(key, [])
            if rel not in bucket:
                bucket.append(rel)
    return index


class Occurrence:
    """Одно вхождение ссылки в периметре гейта и то, что нашёл резолвер.

    `candidates` — существующие пути **от корня репозитория**, в той же
    форме, в какой их держит `_index`. Форма записи в тексте сюда не
    протекает: `Edit(./core/me.md)` и `core/me.md` называют одну цель, и
    потребитель, спросивший про вторую, обязан найти первую. Пусто значит
    «цели нет», а не «не искали»: не искали — это `unreadable` из
    `occurrences`.
    """

    __slots__ = ("path", "line", "raw", "target", "kind", "candidates")

    def __init__(self, path, line, raw, target, kind, candidates):
        self.path = path
        self.line = line
        self.raw = raw
        self.target = target
        self.kind = kind
        self.candidates = list(candidates)

    def key(self):
        return (self.path, self.line, self.kind, self.target)

    def __repr__(self):
        return "Occurrence(%r, %d, %r, %r, %r)" % (
            self.path, self.line, self.kind, self.target, self.candidates)


OCCURRENCE_KINDS = ("mdlink", "settings", "token", "wikilink")

# Виды, чьи вхождения считаются в R. Markdown-ссылка на локальный файл не
# входит никогда: §13 делает её ошибкой всегда, и резолв гейт для неё не
# ведёт. Следствие названо вслух в спеке волны 4 — переезд её ломает при
# неизменной R, поэтому `find-refs` показывает такие ссылки числом.
RESOLVING_KINDS = ("settings", "token", "wikilink")


def _token_candidates(root, token):
    """Кандидат токена: путь от корня, если такой есть в дереве.

    Нормализация здесь не косметика. Токен приходит в той форме, в какой
    его записал автор (`./core/me.md` в правиле разрешений), а кандидат
    обязан быть сравним с путём из `_index`, иначе один резолвер отвечает
    в двух разных системах координат.
    """
    if not _exists_exactly(root, token):
        return []
    return [pathlib_rules.normalise(token).rstrip("/")]


def occurrences(root, ignored=None):
    """Все вхождения ссылок в периметре гейта, с резолвом. Один на пакет.

    Возвращает `(вхождения, нечитаемые)`; нечитаемые — список
    `(rel, ошибка, следствие)`. Класс `undecodable` поднимает вызывающий:
    это суждение гейта, а не свойство вхождения. Молча они не теряются —
    незыблемое №4 запрещает и это.

    Два потребителя: `scan` судит вхождения классами находок, ADOPT
    считает по ним R и ищет ссылки на переезжающий путь. Второго резолвера
    в пакете нет и заводить его нельзя: разошедшиеся копии одного правила
    уже стоили этому репозиторию критерия выхода.

    Порядок — по `Occurrence.key`, то есть не зависит от обхода дерева:
    отчёт `find-refs` обязан быть тем же из любого места клона.
    """
    root = Path(root)
    if ignored is None:
        ignored = _ignored(root)
    index = _index(root, ignored)
    out, unreadable = [], []

    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        try:
            text = _read(path)
        except UnicodeDecodeError as error:
            unreadable.append((rel, error, "ссылки в нём не проверены"))
            continue
        for link in extract_links(text):
            target = unicodedata.normalize("NFC", link.target)
            if link.kind == "wikilink":
                candidates = index.get(target, [])
            else:
                # `base` — путь ссылающегося файла: та же форма, что у
                # `escapes_root`, и по той же причине. Иначе `you.md` рядом
                # с `core/me.md` резолвился бы в `core/me.md/you.md`.
                resolved = pathlib_rules.resolve(target, rel)
                escaped = resolved == ".." or resolved.startswith("../")
                candidates = ([resolved]
                              if not escaped and _exists_exactly(root, resolved)
                              else [])
            out.append(Occurrence(rel, link.line, link.raw, target,
                                  link.kind, candidates))
        if not _scanned_for_tokens(rel, path.name):
            continue
        for lineno, line in enumerate(_blank_fences(text).split("\n"), start=1):
            for match in _INLINE.finditer(line):
                token = match.group(2).strip()
                if not pathlib_rules.is_path_token(token):
                    continue
                out.append(Occurrence(rel, lineno, "`%s`" % token, token,
                                      "token", _token_candidates(root, token)))

    # `.claude/settings*.json`: в отчёт идёт токен как он записан в файле,
    # а судится развёрнутый (`Edit(X)` и `Write(X)` на одной строке иначе
    # дают две неразличимые находки, и автор не понимает, что чинить).
    for path in sorted(root.glob(".claude/settings*.json")):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        try:
            text = _read(path)
        except UnicodeDecodeError as error:
            unreadable.append((rel, error, "пути в нём не проверены"))
            continue
        for lineno, line in enumerate(text.split("\n"), start=1):
            for raw in re.findall(r'"([^"]+)"', line):
                token = pathlib_rules.unwrap_tool(raw)
                if not pathlib_rules.is_path_token(token):
                    continue
                out.append(Occurrence(rel, lineno, raw, token, "settings",
                                      _token_candidates(root, token)))

    out.sort(key=Occurrence.key)
    return out, unreadable


def count_resolvable(root, ignored=None):
    """R: число вхождений, для которых резолвер нашёл существующую цель.

    Живёт рядом с индексом, а не в ADOPT: потребителей двое — счёт критерия 2
    и `find-refs`, — и оба обязаны считать одно и то же. Неоднозначная ссылка
    считается **одним** вхождением: цель существует, спор идёт о том, какая.
    Иначе переезд, меняющий победителя, двигал бы R, ничего не сломав.
    """
    occs, _ = occurrences(root, ignored)
    return sum(1 for o in occs if o.kind in RESOLVING_KINDS and o.candidates)


def _orphan_perimeter(root, ignored):
    """Пути, где отсутствие входящей ссылки означает что-то определённое.

    Тот же периметр, что у главных циклов: без него поддерево, которое
    гейт нигде не читает ради ссылок (архив, .gitignore), всё равно
    проверяется на сирот — и оказывается сиротским по построению, потому
    что связывающие его ссылки никто не сканирует.
    """
    perimeter = set()
    for path in root.rglob("*.md"):
        rel = path.relative_to(root).as_posix()
        if not _in_perimeter(rel, ignored):
            continue
        if zones.zone_of(rel) == "sources" and "/items/" in rel:
            perimeter.add(rel)
    for readme in root.rglob("README.md"):
        rel_readme = readme.relative_to(root).as_posix()
        if not _in_perimeter(rel_readme, ignored):
            continue
        # Нечитаемый README не называется здесь второй раз: главный цикл
        # по `.md` встречает тот же файл и уже поднял на него `undecodable`.
        # Архетипа у него нет, значит и периметра сирот он не задаёт.
        try:
            fields = parse_frontmatter(_read(readme))
        except (FrontmatterError, UnicodeDecodeError):
            continue
        if fields.get("archetype") != REGISTRY_ARCHETYPE:
            continue
        items = readme.parent / "items"
        for path in items.rglob("*.md") if items.exists() else []:
            rel_item = path.relative_to(root).as_posix()
            if not _in_perimeter(rel_item, ignored):
                continue
            perimeter.add(rel_item)
    return perimeter


def classify_mdlink(target):
    """None, если markdown-ссылка допустима; иначе класс находки."""
    target = target.strip()
    if pathlib_rules.is_url(target) or target.startswith("#"):
        return None
    return "md-link-to-file"


def _transient_violation(source_rel, target):
    """Ссылка из долгоживущей зоны в исчезающую — отложенная поломка.

    `target` — путь цели, а не текст ссылки: у `[[scratch]]` зоны в тексте
    нет вовсе. Вызывается после резолва, по каждому кандидату.
    """
    source_zone = zones.zone_of(source_rel)
    target_zone = zones.zone_of(target)
    if source_zone in zones.LONG_LIVED and target_zone in zones.TRANSIENT:
        return True
    return False


class Ignored(tuple):
    """Префиксы `.gitignore`, его же отрицания (`!`) и отказ чтения.

    Кортеж, потому что `str.startswith` принимает именно кортеж, и оба гейта
    на этом стоят: `check_package` импортирует отсюда и `_ignored`,
    и `_in_perimeter`. Отрицания едут рядом, а не вторым возвращаемым
    значением, — иначе их пришлось бы протаскивать через чужую сигнатуру
    и периметры двух гейтов снова разошлись бы. `undecodable` едет тем же
    вагоном: периметр, собранный не из того текста, — это чужой периметр
    молча, и вызывающий обязан иметь возможность сказать об этом вслух.
    """

    negated = ()
    undecodable = None

    def __new__(cls, prefixes, negated=(), undecodable=None):
        self = super().__new__(cls, tuple(sorted(prefixes)))
        self.negated = tuple(negated)
        self.undecodable = undecodable
        return self


def _gitignore_prefixes(root):
    """Ровно то, что игнорирует сам репозиторий, плюс `.git/`.

    `!`-строка возвращает путь в дерево, и периметр обязан её применять:
    выброшенная, она делала игнорируемое множество строго шире того, что
    репозиторий игнорирует на самом деле, — ровно наоборот тому, что здесь
    написано. Одно отличие от git осознанное: git отказывается возвращать
    файл из исключённого каталога, здесь отрицание сильнее каталога.
    Сдвиг в сторону «прочитать лишний файл»: лишнее гейт назовёт вслух,
    а непрочитанное молчит.

    Нечитаемый `.gitignore` не проглатывается: периметр собирается из
    умолчаний, а само исключение едет на `Ignored.undecodable`, чтобы
    вызывающий положил его в отчёт.

    Отдельно от `_ignored` потому, что `archive/` — исключение **гейта
    ссылок** (секция 13), а не свойство дерева. Инвентарь ADOPT архив
    обязан видеть: не увидев, он не положит его в план усыновления, а
    положить обязан (§18).
    """
    prefixes = {".git/"}
    negated = []
    failure = None
    ignore = root / ".gitignore"
    if ignore.exists():
        try:
            text = _read(ignore)
        except UnicodeDecodeError as error:
            text, failure = "", error
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("!"):
                negated.append(line[1:].lstrip("/"))
            else:
                prefixes.add(line.rstrip("/") + "/")
    return Ignored(prefixes, negated, failure)


def _ignored(root):
    """Периметр гейта ссылок: `.gitignore` плюс исключение `archive/` (§13).

    Ни байта поведения сверх того, что было до разделения: отрицания и отказ
    чтения едут дальше как есть, добавляется ровно один префикс.
    """
    base = _gitignore_prefixes(root)
    return Ignored(set(base) | {"archive/"}, base.negated, base.undecodable)


def _in_perimeter(rel, ignored):
    """Читает ли гейт этот путь. Отрицание `.gitignore` сильнее префикса.

    Две формы записи, а не одна. Поддерево ловится префиксом; запись,
    называющая **один файл** (`.claude/settings.local.json`), префиксом не
    ловится ни при каких условиях — `_gitignore_prefixes` дописывает ей косую, и
    получается `.claude/settings.local.json/`, не совпадающее ни с чем.
    Отличить файл от каталога по самому шаблону нечем, поэтому проверяются
    обе формы. Цена бездействия известна поимённо: абсолютный путь в
    машинно-локальных настройках автора становился `escapes-root` в каждом
    экземпляре, собранном рецептом.

    Форма файла сверяется `fnmatchcase`, как и отрицание строкой выше:
    у git запись `*.log` — тоже запись про файлы, и разбирать её иначе, чем
    `!*.log`, значило бы держать в одной функции два разных `.gitignore`.

    `getattr`, а не атрибут напрямую: сюда приходит и голый кортеж —
    из `check_package`, и из мутации «периметр снова слеп к .gitignore».
    """
    for pattern in getattr(ignored, "negated", ()):
        if fnmatchcase(rel, pattern) or rel.startswith(pattern.rstrip("/") + "/"):
            return True
    if rel.startswith(tuple(ignored)):
        return False
    return not any(fnmatchcase(rel, prefix.rstrip("/")) for prefix in ignored)


def _scanned_for_tokens(rel, name):
    """Периметр backtick-сканирования: четыре строки таблицы, и ни строкой больше."""
    return name in SCANNED_FOR_TOKENS or rel.startswith(RULES_PREFIX)


def _exists_exactly(root, token):
    """Есть ли такой путь — с точностью до регистра и формы Unicode.

    `(root / token).exists()` спрашивает файловую систему, а она на macOS
    отвечает «да» на `Scripts/Check_Links.py`, на Linux — «нет»: один
    репозиторий давал два разных вердикта. Резолв wikilink регистр при этом
    различал всегда (поиск по словарю), то есть две половины одного гейта
    расходились между собой. Критерий 2 — про отчёт, не зависящий от места
    клона; платформа — тот же довод одной ступенью выше.

    Сравнение посегментное, по именам из каталога. NFC с обеих сторон:
    macOS отдаёт имена в NFD, текст файла почти всегда в NFC, и без
    приведения та же строка разъезжается на ровном месте.
    """
    rel = pathlib_rules.normalise(token).rstrip("/")
    if not rel or rel == ".":
        return True
    current = root
    for part in rel.split("/"):
        part = unicodedata.normalize("NFC", part)
        try:
            names = {unicodedata.normalize("NFC", child.name)
                     for child in current.iterdir()}
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return True


def _classify_token(token, root, allowed):
    """Судьба токена-пути: класс находки или None. Единственное определение.

    Сюда ходят оба места, где гейт судит токен, — backtick-цикл и
    `.claude/settings*.json`. Второй копии этой лестницы в пакете быть
    не должно: три разошедшиеся копии одной таблицы уже стоили этому
    репозиторию критерия выхода (`tests/test_zones.py::TestSingleDefinition`),
    а здесь разойтись особенно легко — обе копии выглядят одинаково
    безобидно и обе решают, выпустить ли ссылку за корень.

    Порядок ступеней и есть правило (секция 13):

    1. Выход за корень судится первым и не зависит от того, шаблон перед
       нами или конкретный путь. Глоб по чужому домашнему каталогу —
       находка `escapes-root` ровно так же, как конкретный файл в нём:
       шаблон снимает вопрос «есть ли такой файл», но не даёт права выйти
       из репозитория. Образец лежит в битой фикстуре, а не здесь: строка
       с таким токеном в самом пакете — находка `absolute-path`
       (проверка пакета поймала её на первом же прогоне).
    2. Шаблон дальше не проверяется. `**/knowledge/**` называет множество,
       и спрашивать о существовании множества — ошибка категории. Без этой
       ступени каркас, предписанный секциями 4 и 9, не проходил гейт,
       предписанный секцией 13, — блокер, на который упёрлась волна 3.
    3. Конкретный путь проверяется как прежде — но существование спрашивается
       у дерева, а не у файловой системы (`_exists_exactly`): иначе вердикт
       зависел от регистрочувствительности тома. Ослабления нет:
       `areas/hiring/items/` метасимволов не содержит и остаётся находкой.
    """
    if pathlib_rules.escapes_root(token, base=""):
        return "escapes-root"
    if pathlib_rules.is_pattern(token):
        return None
    if not _exists_exactly(root, token) and not allowed(token):
        return "unresolved"
    return None


def scan(root, today=None):
    root = Path(root)
    ignored = _ignored(root)
    findings = []
    referenced = set()

    if ignored.undecodable is not None:
        findings.append(_undecodable(".gitignore", ignored.undecodable,
                                     "периметр прочитан без него"))

    allow = []
    allow_path = root / ALLOWLIST_NAME
    if allow_path.exists():
        # Прочитанный с заменой аллоулист гасит не то, что в нём написано:
        # запись `черновик` в cp1251 становится набором замещающих знаков,
        # ни одной цели не совпадает — и автор видит `unresolved` там, где
        # исключение объявлено. Молчаливая подстановка в обе стороны.
        try:
            allow = parse_allowlist(_read(allow_path))
        except UnicodeDecodeError as error:
            findings.append(_undecodable(ALLOWLIST_NAME, error,
                                         "записи аллоулиста не прочитаны"))

    def allowed(target):
        """Гасит ли аллоулист эту цель. Погашенное запоминается поимённо.

        Совпадение — с целью целиком, глоб-метасимволы работают
        (`черновики/*`). Голая подстрока запрещена: запись `a` гасила
        `unresolved` по всему репозиторию и при этом считалась
        использованной, поэтому `dead-allow` о ней молчал — исключение
        ослабляло гейт везде, выглядя живым. Весь аргумент спеки за
        `dead-allow` в том, что уцелевшее исключение тихо ослабляет
        проверку; подстрочное совпадение делало это ослабление ещё
        и ненаблюдаемым. «Строка на паттерн» читается как шаблон,
        а не как обрывок пути.

        Запрета синтаксиса мало: `*a*`, `*`, `?*`, `[a-z]*` — та же
        подстрока в глоб-написании. Поэтому цели копятся в `entry.hits`:
        по ним `broad-allow` ниже показывает автору, что именно правило
        проглотило, а не сообщает догадку о намерении.
        """
        target = unicodedata.normalize("NFC", target)
        for entry in allow:
            if entry.pattern and fnmatchcase(
                    target, unicodedata.normalize("NFC", entry.pattern)):
                entry.hits.add(target)
                return True
        return False

    # Обход и резолв — не здесь: `occurrences` один на пакет, и `scan` его
    # первый потребитель. Второе место, считающее то же самое, значит второй
    # резолвер, а разошедшиеся копии одного правила уже стоили этому
    # репозиторию критерия выхода. Судит вхождения по-прежнему этот код —
    # классами находок, — и ни одна ступень классификации в резолвер не
    # переехала.
    occs, unreadable = occurrences(root, ignored)

    # Файл, который не декодируется, называется здесь — и на этом разбор его
    # ссылок кончается. Чем они были, знать неоткуда, а догадка про
    # `[[???????]]` — то самое ложное обвинение, ради снятия которого класс
    # заведён (см. `_read`). Имя ровно одно на файл: два прохода по дереву
    # были деталью устройства гейта, а не двумя разными фактами для автора,
    # и после выноса прохода такой файл читается один раз.
    for rel, error, consequence in unreadable:
        findings.append(_undecodable(rel, error, consequence))

    for occ in occs:
        rel = occ.path

        # Backtick-токены и `.claude/settings*.json`: пути и команды
        # вперемешку, признак — is_path_token, периметр backtick'ов — ровно
        # четыре строки таблицы «Что проверяется» (собран в `occurrences`).
        # Судьбу отобранного токена решает _classify_token — одно место на
        # оба вида: правило про глоб и границу корня второй копии не имеет.
        # Лестница спрашивается целиком и здесь, а не наполовину в резолвере:
        # разложить её ступени по двум местам — ровно то расхождение, против
        # которого она и заведена.
        if occ.kind in ("token", "settings"):
            cls = _classify_token(occ.target, root, allowed)
            if cls:
                findings.append(Finding(cls, rel, occ.line, occ.raw))
            continue

        target = occ.target

        if pathlib_rules.escapes_root(target, base=rel):
            findings.append(Finding("escapes-root", rel, occ.line, occ.raw))
            continue

        if occ.kind == "mdlink":
            cls = classify_mdlink(target)
            if cls:
                findings.append(Finding(cls, rel, occ.line, occ.raw))
            continue

        # Ниже — только wikilink'и, и `referenced` пополняется только ими.
        # Цели markdown-ссылок и токенов в него не попадали никогда: первая
        # по §13 ошибка всегда, второй в периметре сирот не бывает. Сдвинуть
        # это значило бы тихо погасить `orphan` выносом обхода.
        candidates = occ.candidates
        for candidate in candidates:
            referenced.add(candidate)          # относительный путь цели

        # `link-to-transient` — про цель ссылки, а не про её текст.
        # `[[scratch]]`, единственная форма, которую пишет Obsidian, зоны
        # в тексте не несёт вовсе, и проверка до резолва молчала ровно
        # там, где класс и нужен. Текст остаётся вторым источником для
        # случая, когда зону он называет, а файла нет: `[[tmp/ghost]]` —
        # по-прежнему отложенная поломка, а не ссылка в никуда.
        transient = [c for c in candidates if _transient_violation(rel, c)]
        if not candidates and _transient_violation(rel, target):
            transient = [target]
        if transient:
            detail = occ.raw
            if candidates:
                detail = "%s → %s" % (occ.raw, ", ".join(sorted(transient)))
            findings.append(Finding("link-to-transient", rel, occ.line, detail))

        # Неоднозначность и исчезающая цель — два разных факта об одной
        # ссылке, и чинятся они по-разному: первая — полным путём, вторая
        # — отказом ссылаться в `tmp/`. Поэтому сообщаются оба. Погасить
        # ошибку предупреждением нельзя: `ambiguous` гейт не роняет,
        # и ссылка, которая по построению протухнет, ушла бы зелёной.
        if len(candidates) > 1:
            findings.append(Finding("ambiguous", rel, occ.line,
                                    "%s → %s" % (occ.raw, ", ".join(sorted(candidates)))))
        elif not candidates and not transient and not allowed(target):
            findings.append(Finding("unresolved", rel, occ.line, occ.raw))

    # Мёртвые записи аллоулиста оцениваются последними: только к этому
    # моменту все места, поднимающие unresolved (wikilink-цикл, backtick-
    # цикл, settings.json), уже прогнали через него свои цели и пометили
    # использованные записи — иначе запись, разрешающая находку из более
    # позднего прохода, выглядит неиспользованной и гейт противоречит сам
    # себе: одновременно unresolved и «удалите правило, которое это гасит».
    # Три взаимоисключающих вердикта о строке, а не три независимых
    # проверки: про одну строку одна находка. Порядок — от того, что
    # чинится безусловно, к тому, что зависит от сегодняшнего дерева.
    # `broad-allow` отдельным классом, потому что `dead-allow` утверждает
    # «правило ничего не исключает», а про правило, погасившее две цели,
    # это неправда — и сказать про правило неправду ровно то, что чинится
    # в этом заходе.
    #
    # **Остаточный риск, названный вслух.** «Ничего не исключает» и `orphan`
    # ниже — утверждения об **отсутствии**: такой цели в дереве нет, такой
    # ссылки на файл нет. Файл, помеченный `undecodable`, не прочитан, и
    # отсутствие в нём недоказуемо: правило, гасящее ровно одну цель из
    # такого файла, будет названо мёртвым по ошибке. Гасить оба класса при
    # первом же нечитаемом файле — лечение хуже болезни: в живом репозитории
    # один битый файл снял бы `dead-allow` и `orphan` со всего дерева
    # надолго, а `dead-allow` заведён ровно против такого тихого ослабления.
    # Прогон при этом красный, и причина в нём названа рядом.
    for entry in allow:
        if entry.reason is None:
            findings.append(Finding("dead-allow", ALLOWLIST_NAME, entry.line,
                                    "строка без причины: %s" % entry.pattern))
        elif not entry.hits:
            findings.append(Finding("dead-allow", ALLOWLIST_NAME, entry.line,
                                    "правило ничего не исключает, удалите: %s" % entry.pattern))
        elif not allow_is_anchored(entry.pattern):
            findings.append(Finding(
                "broad-allow", ALLOWLIST_NAME, entry.line,
                "правило не привязано ни к месту, ни к имени, сузьте: %s (гасит: %s)"
                % (entry.pattern, ", ".join(sorted(entry.hits)))))

    for rel in sorted(_orphan_perimeter(root, ignored)):
        if rel not in referenced:
            findings.append(Finding("orphan", rel, 1, "на файл никто не сослался"))

    return Report(findings, today=today)


def main(argv=None):
    parser = argparse.ArgumentParser(description="link gate")
    parser.add_argument("root")
    parser.add_argument("--today", default=None,
                        help="дата явным параметром: без неё у проверки не бывает фикстуры")
    args = parser.parse_args(argv)
    report = scan(args.root, today=args.today)
    rendered = report.render()
    if rendered:
        print(rendered)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
