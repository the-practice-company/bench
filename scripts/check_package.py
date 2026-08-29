#!/usr/bin/env python3
"""Проверка пакета перед выпуском. Запускается руками, CI нет.

Самый дешёвый артефакт разбора: одна строка с неподдерживаемым типом хука
жила у изученного аналога три с половиной месяца.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import zones
from scripts.findings import Finding, Report
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter
# Что этот репозиторий игнорирует, разбирается ровно в одном месте пакета —
# в гейте ссылок. Своя копия разбора `.gitignore` здесь была бы второй
# таблицей того же самого, а разошедшиеся копии одной таблицы этому
# репозиторию уже стоили критерия выхода (tests/test_zones.py). Импорт
# служебного имени — цена единственного определения, и она меньше.
from scripts.check_links import _ignored as ignored_prefixes, _in_perimeter

HOOK_EVENTS = frozenset({
    "SessionStart", "PreToolUse", "PostToolUse", "Stop", "PreCompact",
    "UserPromptSubmit", "SubagentStop", "Notification", "SessionEnd",
})
HOOK_TYPES = frozenset({"command"})
# Матчер хука — имя инструмента, `*` или альтернатива через `|`. Закрытое
# множество, а не форма: `^[A-Za-z*|_]+$` принимал любое слово, поэтому
# опечатка `Bahs` проходила зелёной — ровно та поломка, ради которой
# проверка и заводилась. Новый инструмент добавляется правкой этого списка;
# в этом и смысл закрытого множества.
TOOL_NAMES = frozenset({
    "Bash", "Edit", "Glob", "Grep", "NotebookEdit", "Read", "Task",
    "TodoWrite", "WebFetch", "WebSearch", "Write",
})


def matcher_is_known(matcher):
    matcher = str(matcher)
    # Пустой матчер — документированная форма «совпадает со всем» для
    # событий, у которых инструмента нет вовсе (SessionStart и соседи).
    # Разбор ронял её на ровном месте: `"".split("|")` даёт `[""]`, пустой
    # строки в TOOL_NAMES нет, и законная запись объявлялась находкой. Это
    # дефект разбора, а не вопрос о составе закрытого множества.
    # Послабление — ровно на всё значение: пустой член альтернативы
    # (`Edit|`) остаётся находкой, потому что это опечатка.
    if matcher in ("*", ""):
        return True
    parts = matcher.split("|")
    return all(part in TOOL_NAMES for part in parts)

# Абсолютный путь верен ровно на одной машине. Список префиксов собран из
# фрагментов, а не записан литералом, чтобы в тексте этого файла не было
# непрерывной подстроки, совпадающей с тем, что ищет сам детектор: тогда
# файл сканируется на общих основаниях, без самоисключения из периметра.
# Граница каждого фрагмента обязана попадать внутрь префикса, известного
# детектору, — иначе файл находит сам себя. Проверка одна: после правки
# этого места прогнать скрипт на собственном репозитории и увидеть тишину.
_ABSOLUTE_PREFIXES = (
    "/" + "Users/", "/" + "home/", "/" + "root/", "/" + "opt/", "/" + "etc/",
    "/" + "tmp/", "/" + "var/", "/" + "usr/", "/" + "srv/", "/" + "mnt/",
    "/" + "media/", "/" + "private/", "/" + "Volumes/", "/" + "Applications/",
    "/" + "Library/", "/" + "System/",
    # Корни, которых список не знал вовсе. Из-за этой дыры shebang с
    # захардкоженным интерпретатором проходил зелёным — не потому, что
    # портируем, а потому что был невидим целиком; собственный `./check`
    # этого репозитория проверка пропускала мимо, пока комментарий рядом
    # и спека утверждали обратное.
    "/" + "bin/", "/" + "sbin/", "/" + "dev/", "/" + "sys/", "/" + "proc/",
    "/" + "run/", "/" + "lib/", "/" + "lib64/", "/" + "boot/", "/" + "snap/",
    "/" + "nix/", "/" + "cores/", "/" + "Network/",
    # Корни контейнеров и облачных сред: `workspace` — почти любой образ,
    # `workspaces` — умолчание GitHub Codespaces, `data` — смонтированный
    # том. Путь оттуда верен ровно в одном контейнере, то есть это та же
    # машинная зависимость, ради которой класс заведён, — а списку они не
    # были известны вовсе.
    "/" + "workspace/", "/" + "workspaces/", "/" + "data/",
)
ABSOLUTE = re.compile(
    "(?<![\\w.])(?:%s)" % "|".join(re.escape(p) for p in _ABSOLUTE_PREFIXES)
    # Домашний каталог: свой (тильда и косая) и чужой (тильда, имя
    # пользователя, косая). Вторая форма — ровно та же машинная
    # зависимость, что и первая, и оставалась зелёной, пока ветки не было.
    + r"|(?<![\w.])~(?:[A-Za-z_][A-Za-z0-9._-]*)?/"
    # Буква диска Windows: заглавная латинская буква, двоеточие и
    # разделитель пути. Однобуквенность и отсутствие слова слева разводят
    # её с `http` + двоеточие, где перед двоеточием стоит `p`. Двух
    # ограничений на этом не хватило: скан пошёл по всем текстовым файлам,
    # и ветка начала ловить схему URI из одной буквы (`s:` + две косые) и
    # тернарник минифицированного JS (`?b:` и регулярка следом). Отсюда
    # ещё два: вторая косая подряд — признак схемы, а не диска; строчная
    # буква перед двоеточием в тексте кода — переменная или ключ, а не
    # диск, который пишут заглавной.
    + r"|(?<![\w.])[A-Z]:(?:/(?!/)|\\)"
    # UNC \\сервер\ресурс. Сегмент имени сервера обязан нести хоть один
    # нецифровой знак, потому что ветка ищет имя хоста, а последовательность
    # из одних цифр — не имя: хоста из одних цифр не бывает, а адрес всегда
    # несёт точки. Без этого условия веткой ловилась пара обратных косых с
    # цифрами следом — не путь, а проза про octal-escape'ы вывода git, — и
    # находка утверждала абсолютный путь там, где его нет; собственный
    # репозиторий она красила. Точка нецифровая, поэтому IP-адрес вида
    # 192.168.1.1 остаётся находкой, как и запись через удвоенную обратную
    # косую внутри строкового литерала.
    + r"|(?<![\w.])\\\\[0-9]*[A-Za-z._-][A-Za-z0-9._-]*\\"
)
# Портируемый shebang первой строки — единственное именованное исключение
# из absolute-path. Ядро требует абсолютный путь интерпретатора на первой
# строке файла, относительной формы не существует. Портируемых форм ровно
# две: `env` из стандартного каталога и шелл, гарантированный стандартом
# POSIX по своему пути. Обе верны на каждой POSIX-машине — ровно обратное
# тому, ради чего класс заведён. Всё остальное в shebang остаётся находкой:
# захардкоженный интерпретатор — это и есть машинная зависимость, и сосед
# шелла по каталогу тоже (`bash` там не гарантирован никем: на NixOS его
# нет, на macOS это другая сборка). Фрагменты строк — по той же причине,
# что и у `_ABSOLUTE_PREFIXES` выше.
_PORTABLE_SHEBANGS = ("/" + "usr/bin/env", "/" + "bin/sh")
# Снимается токен, а не строка целиком. `env -S` — тоже портируемая форма,
# и она несёт произвольную команду с аргументами; исключая строку, гейт
# слеп ровно к тому месту, куда абсолютный путь в такой строке и попадает.
_PORTABLE_SHEBANG = re.compile(
    r"^#!(?:%s)(?=\s|$)" % "|".join(re.escape(s) for s in _PORTABLE_SHEBANGS))
# Каталоги пакета, в которых лежит исполняемое. Ссылка сюда без
# `${CLAUDE_PLUGIN_ROOT}` разрешается от рабочего каталога — репозитория
# пользователя, а не плагина. Список закрытый: появился новый каталог с
# кодом — он дописывается сюда, как и `TOOL_NAMES` выше.
_PACKAGE_DIRS = ("scripts", "hooks")
# Ссылка на файл пакета по относительному пути. Запускающего слова не
# требуется: `Запусти scripts/check_links.py` — та же самая ссылка, которую
# агент разрешит от чужого корня. Прежняя форма требовала `python3`, `sh`,
# `bash` или `./` и знала ровно один каталог, поэтому мимо неё проходили и
# проза без префикса, и `uv run`, и всё, что лежит не в `scripts/`. Косая
# слева в запрете — ровно исключение законной формы: в
# `${CLAUDE_PLUGIN_ROOT}/scripts/x.py` перед именем каталога стоит она.
SCRIPT_CALL = re.compile(
    r"(?<![\w./~-])(?:%s)/[\w.-]*\.[A-Za-z0-9]+" % "|".join(_PACKAGE_DIRS)
    # Форма `-m` адресует тот же файл точкой, а не косой, и разбор, искавший
    # косую, не видел её вовсе.
    + r"|(?<![\w./~-])-m\s+(?:%s)\.[\w.]+" % "|".join(_PACKAGE_DIRS)
)
# Цель усекающего перенаправления — один токен, похожий на путь: с косой
# или с коротким расширением. Без этого условия ветка ловила бы цитату
# markdown (`> строка текста`), а в инструкциях ADOPT цитаты — обычная
# проза: класс, краснеющий на каждой цитате, перестаёт быть проверкой.
_REDIRECT_TARGET = r"[^\s`'\"|>]*(?:/|\.[A-Za-z0-9]{1,4})[^\s`'\"|>]*(?=[\s`'\"]|$)"
# Разрушающий пример в инструкциях ADOPT. Разрушают не только `mv` и `rm`:
# удаление каталога, чистка рабочего дерева git, `find -delete`, `rmtree`,
# усекающее перенаправление, откат правок, зеркалирование с `--delete`,
# усечение файла и `reset --hard` — всё это исполнят буквально на чужом
# дереве, и всё это класс пропускал зелёным.
DESTRUCTIVE = re.compile(
    r"(?<![\w-])(?:mv|rmdir|rm)\s+[^\s`]"
    r"|(?<![\w-])git\s+clean(?![\w-])"
    r"|(?<![\w-])git\s+checkout\s+--(?:\s|$)"
    r"|(?<![\w-])git\s+reset\s+--hard(?![\w-])"
    r"|(?<![\w-])find\s[^`]*(?<![\w-])-delete(?![\w-])"
    r"|(?<![\w.])(?:shutil\.)?rmtree\s*\("
    r"|(?<![\w-])rsync\s[^`]*(?<![\w-])--delete(?![\w-])"
    r"|(?<![\w-])truncate\s[^`]*(?<![\w-])-s\s+0(?![\w])"
    # Стрелка (`->`, `=>`) и закрывающая скобка разметки — не
    # перенаправление, поэтому знак слева от `>` ограничен; `>>` дописывает,
    # а не усекает.
    r"|(?<![-=<>])>(?!>)\s*" + _REDIRECT_TARGET
)

# Каталоги, не входящие в пакет. Списка два, потому что правила разные, и
# смешаны они были не зря: у каждого своя поломка.
#
# Служебное имя пропускается на любой глубине. В корне `__pycache__` не лежит
# никогда, поэтому в списке первого сегмента строка была мёртвой:
# `scripts/__pycache__/note.txt` уходил в скан. Байт-код в пакет не входит и
# руками не пишется, зато после свёртки констант содержит ровно те абсолютные
# префиксы, которые в исходнике собраны из фрагментов, — пока `.pyc` не
# декодировался, он отсеивался сам собой, а чтение с заменой сделало его
# видимым. Вложенный `.git` — каталог сабмодуля, та же история.
SKIP_ANY_DEPTH = {".git", "__pycache__"}
# Остальное пропускается только первым сегментом, как в `zones.zone_of()`.
# Проверка по любому сегменту на любой глубине снимала со скана `skills/inbox/`
# — скилл, чьё имя совпало с зоной. Из восьми имён зон здесь ровно три, и обе
# группы — чужое содержимое: `knowledge/` — чужие git-сабмодули, `inbox/` и
# `sources/` — материалы собственной разработки (мотивировка у обеих в
# `scripts/zones.py`). Остальные пять убраны: раньше исключались все восемь, и
# любой каталог пакета, чьё имя совпало с зоной, уходил из скана целиком.
SKIP_AT_ROOT = ({"fixtures", "tests", "docs"}
                | set(zones.READ_ONLY) | set(zones.SELF_DEVELOPMENT))

# Прогон тестов, вложенный в собственную проверку (см. _check_tests_touched_product),
# сам пересобирает весь набор тестов, включая тест, что зовёт этот скрипт
# подпроцессом (TestThisPackage.test_our_own_package_is_green). Без метки во
# вложенном окружении это самовоспроизводящаяся рекурсия без дна. Метка
# ставится ровно вложенному прогону и обрывает её на первом уровне.
_NESTED_RUN_GUARD = "TWINKLE_CHECK_PACKAGE_NESTED_RUN"


def _is_ignored(rel, ignored):
    """Игнорирует ли репозиторий этот путь: поддеревом или файлом поимённо.

    Префиксы считает `check_links._ignored` — единственное место в пакете,
    которое разбирает `.gitignore`. Оттуда же взят разбор поддерева
    (`_in_perimeter`), но одного его мало: `.gitignore` называет и отдельные
    файлы (`.claude/settings.local.json`), а префикс с косой на конце такой
    записи не совпадает ни с чем. Вторая форма добавлена здесь, а не там:
    гейт ссылок читает только `*.md`, и для него разницы нет.
    """
    if not _in_perimeter(rel, ignored):
        return True
    return any(rel == prefix.rstrip("/") for prefix in ignored)


def _iter_package_files(root):
    """Все файлы пакета, которые читаются как текст.

    Формат определяется тем, декодируется ли файл в UTF-8, а не расширением:
    фильтр по списку расширений уводил из-под проверки файлы без расширения,
    `.yaml`, `.toml` и `Makefile`. Бинарные отсеиваются на чтении, в `check()`.

    Вердикт не зависит от неотслеживаемого локального состояния: игнорируемое
    репозиторием за периметр не попадает. Пока список расширений держал мусор
    снаружи сам собой, этого не требовалось; со снятием списка `python3 -m
    venv .venv` стал красить `./check` на чистом коммите — `.venv/bin/activate`
    расширения не имеет, в пакет не входит и держит абсолютный путь по
    построению. Разбор `.gitignore`, а не вызов git: у фикстур git-репозитория
    нет, а проверка обязана работать и на них.
    """
    ignored = ignored_prefixes(root)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_ANY_DEPTH for part in rel.parts[:-1]):
            continue
        # Пропуск первого сегмента — про каталог, а не про имя: файл `docs`
        # в корне репозитория остаётся файлом пакета и сканируется.
        if len(rel.parts) > 1 and rel.parts[0] in SKIP_AT_ROOT:
            continue
        if _is_ignored(rel.as_posix(), ignored):
            continue
        yield path


def _hooks_shape(detail, line=1):
    """Находка о форме hooks.json. Класс — `unparseable`, потому что файл
    неверной формы не читается как контракт хуков, даже когда он валидный
    JSON. Другого класса под это в `scripts/findings.py` нет, а заводить
    свой ради одного места — вторая таблица того же самого."""
    return Finding("unparseable", "hooks/hooks.json", line, detail)


def _check_hooks(root):
    """Контракт хуков: сначала форма файла целиком, потом известность имён.

    Промах формы — не опечатка в одном поле, а тихое отключение всего
    пакета. Файл без верхнего ключа `hooks` Claude Code не читает вовсе:
    ни один объявленный хук не запускается, а `(data.get("hooks") or {})`
    возвращал на такой файл пустой контракт и тишину — ровно та поломка,
    которую docstring модуля называет стоившей аналогу трёх с половиной
    месяцев. Валидный JSON неверной формы вдобавок ронял всю проверку
    исключением: находки остальных гейтов терялись, а код возврата
    становился 1, которого в контракте `scripts/findings.py` нет.
    Поэтому форма утверждается на каждом уровне и каждое расхождение
    называется путём внутри файла, а не общим «битый hooks.json».
    """
    path = root / "hooks" / "hooks.json"
    if not path.exists():
        return []
    # Замена, а не исключение: недекодируемый байт делает файл непригодным
    # как JSON и уходит в отчёт находкой, а не роняет проверку (№4).
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as error:
        return [_hooks_shape(str(error), error.lineno)]

    if not isinstance(data, dict):
        return [_hooks_shape("верхний уровень не объект, а %s" % _type_name(data))]
    if "hooks" not in data:
        return [_hooks_shape("нет ключа hooks: контракт хуков не объявлен")]
    events = data["hooks"]
    if not isinstance(events, dict):
        return [_hooks_shape("hooks не объект, а %s" % _type_name(events))]

    findings = []
    for event, entries in events.items():
        if event not in HOOK_EVENTS:
            findings.append(Finding("unknown-hook-event", "hooks/hooks.json", 1, event))
        if not isinstance(entries, list):
            findings.append(_hooks_shape(
                "hooks.%s не список, а %s" % (event, _type_name(entries))))
            continue
        for index, entry in enumerate(entries):
            where = "hooks.%s[%d]" % (event, index)
            if not isinstance(entry, dict):
                findings.append(_hooks_shape(
                    "%s не объект, а %s" % (where, _type_name(entry))))
                continue
            matcher = entry.get("matcher", "*")
            if not matcher_is_known(matcher):
                findings.append(Finding("unknown-matcher", "hooks/hooks.json", 1,
                                        str(matcher)))
            hooks = entry.get("hooks", [])
            if not isinstance(hooks, list):
                findings.append(_hooks_shape(
                    "%s.hooks не список, а %s" % (where, _type_name(hooks))))
                continue
            for hook_index, hook in enumerate(hooks):
                if not isinstance(hook, dict):
                    findings.append(_hooks_shape(
                        "%s.hooks[%d] не объект, а %s"
                        % (where, hook_index, _type_name(hook))))
                    continue
                if hook.get("type") not in HOOK_TYPES:
                    findings.append(Finding("unknown-hook-type", "hooks/hooks.json", 1,
                                            str(hook.get("type"))))
    return findings


def _type_name(value):
    return type(value).__name__


def _nonblank(value):
    """Поле заполнено по существу, а не по признаку «не None».

    `description: "   "` — кавычки сохраняют пробелы, парсер возвращает
    строку, и `not fields.get(...)` объявлял её заполненной. Незакавыченная
    форма ловилась случайно: там пробелы съедает сам разбор frontmatter.
    """
    return value is not None and str(value).strip() != ""


def _is_adopt_file(rel):
    """Файл внутри скилла усыновления, на любой глубине вложенности.

    `rel.startswith("skills/adopt-")` требовал дефиса: каталог
    `skills/adopt/` — самое естественное имя для этого скилла — выключал
    `destructive-example` целиком. Имя файла из проверки исключено: скилл
    `drain-inbox` с заметкой `adopt.md` усыновлением не становится.
    """
    parts = rel.split("/")
    if parts[0] != "skills":
        return False
    return any(part == "adopt" or part.startswith("adopt-")
               for part in parts[1:-1])


def check(root):
    root = Path(root)
    findings = []

    findings.extend(_check_hooks(root))

    skills_dir = root / "skills"
    if skills_dir.exists():
        # Скилл — каталог с SKILL.md, на любой глубине под `skills/`. Плоский
        # `iterdir()` видел только первый уровень: на `skills/group/` садилась
        # находка «нет SKILL.md» — неверная и по пути, и по существу, — а
        # лежащий внутри настоящий скилл не проверялся вовсе.
        manifests = sorted(p for p in skills_dir.rglob("SKILL.md") if p.is_file())
        for top in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            if not any(top == m.parent or top in m.parents for m in manifests):
                findings.append(Finding("skill-without-description",
                                        top.relative_to(root).as_posix(), 1,
                                        "нет SKILL.md"))
        for manifest in manifests:
            skill = manifest.parent
            rel = skill.relative_to(root).as_posix()
            try:
                fields = parse_frontmatter(
                    manifest.read_text(encoding="utf-8", errors="replace"))
            except FrontmatterError as error:
                findings.append(Finding("unparseable", rel + "/SKILL.md", error.line, str(error)))
                continue
            if not _nonblank(fields.get("description")):
                findings.append(Finding("skill-without-description", rel, 1, "пустое описание"))
            if fields.get("name") != skill.name:
                findings.append(Finding("skill-name-mismatch", rel, 1,
                                        "%r != %r" % (fields.get("name"), skill.name)))
            if not (skill / "eval.txt").exists():
                findings.append(Finding("skill-without-eval", rel, 1,
                                        "нет eval.txt: срабатывание не проверяется"))
            # Пустой файл — не эвал: `exists()` был всей проверкой, и файл из
            # одних пробелов считался доказательством срабатывания. Критерий 4
            # то же самое уже установил для пустой причины. Условие полное, а
            # не `elif`: две причины одного класса — две независимые проверки,
            # и снятие любой из них обязано оставлять вторую на месте.
            if (skill / "eval.txt").exists() and not (skill / "eval.txt").read_text(
                    encoding="utf-8", errors="replace").strip():
                findings.append(Finding("skill-without-eval", rel, 1,
                                        "пустой eval.txt: срабатывание не проверяется"))

    for path in _iter_package_files(root):
        rel = path.relative_to(root).as_posix()
        # Один недекодируемый байт уводил файл из-под гейта целиком: `continue`
        # по UnicodeDecodeError делал сокрытие абсолютного пути правкой в один
        # байт. Замена оставляет невосстановимым ровно этот байт, а не весь
        # файл, — незыблемое №4 запрещает молча терять остальное. Бинарник
        # по-прежнему тих: в его замещающих символах абсолютного пути нет.
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.split("\n"), start=1):
            scanned = line
            if lineno == 1:
                shebang = _PORTABLE_SHEBANG.match(line)
                if shebang:
                    scanned = line[shebang.end():]
            if ABSOLUTE.search(scanned):
                # Деталь — исходная строка, а не остаток: в отчёте автор
                # должен видеть то, что написано в файле.
                findings.append(Finding("absolute-path", rel, lineno, line.strip()[:80]))
            # Восемь скиллов у изученного аналога звали скрипт относительным
            # путём: рабочим каталогом оказался репозиторий пользователя,
            # и вся заявленная функциональность молча не работала. Периметр —
            # скиллы и hooks.json: команда хука — такой же путь, и такой же
            # чужой, а проверялись до этого только скиллы.
            if (rel.startswith("skills/") or rel == "hooks/hooks.json") \
                    and SCRIPT_CALL.search(line) \
                    and "${CLAUDE_PLUGIN_ROOT}" not in line:
                findings.append(Finding("relative-path-in-skill", rel, lineno,
                                        line.strip()[:80]))
            # ADOPT мутирует чужое дерево; разрушающий пример в его инструкциях
            # рано или поздно исполнят буквально.
            if _is_adopt_file(rel) and DESTRUCTIVE.search(line):
                findings.append(Finding("destructive-example", rel, lineno,
                                        line.strip()[:80]))

    broken_fixture = root / "fixtures" / "broken"
    if broken_fixture.exists():
        for gate in ("check_links.py", "check_frontmatter.py"):
            if (root / "scripts" / gate).exists():
                findings.extend(check_read_only(root, gate, broken_fixture))

    if (root / "tests").exists():
        findings.extend(_check_tests_touched_product(root))

    return Report(findings)


def _tree_hash(root):
    """Хеш дерева: путь и содержимое каждого файла, кроме служебного.

    Служебные каталоги отсекаются на спуске, а не после обхода: снимок
    берётся со всего корня репозитория, и заходить внутрь `.git` ради
    того, чтобы каждый его объект потом отбросить, незачем.
    """
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_ANY_DEPTH)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if not path.is_file():
                continue
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def check_read_only(root, gate, fixture):
    """Гейт обязан доказать read-only хешем дерева до и после.

    Хешируется весь корень репозитория, а не одна фикстура. Гейт, который
    пишет мимо неё, фикстурному хешу не доказывает ничего: посаженный
    образец создавал файл двумя уровнями выше, `counts()` оставался
    пустым, а файл действительно появлялся. Незыблемое №6 запрещает
    плагину писать что бы то ни было вне корня, и снимок корня — форма
    этой проверки, видящая нарушение целиком, а не в одном подкаталоге.
    За корень снимок не выходит: запись в чужое дерево ловится границей
    рабочего каталога в хуках, а не здесь.
    """
    before = _tree_hash(root)
    subprocess.run([sys.executable, str(root / "scripts" / gate), str(fixture)],
                   capture_output=True, text=True)
    after = _tree_hash(root)
    if before != after:
        return [Finding("gate-not-read-only", "scripts/" + gate, 1,
                        "дерево репозитория изменилось после прогона")]
    return []


# Продукт: всё, что уезжает в пакет. `hooks/` и `skills/` в снимке не было,
# хотя docstring рядом называл его «единственным, чего тесты не вправе
# трогать»: тест, переписывающий `hooks/hook.py`, был невидим, а `hooks/` —
# уже отгруженный продукт.
_PRODUCT_DIRS = ("scripts", ".claude-plugin", "hooks", "skills")


def _product_hash(root):
    """Хеш продуктовых каталогов: единственное, чего тесты не вправе трогать."""
    digest = hashlib.sha256()
    for sub in _PRODUCT_DIRS:
        base = root / sub
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel.startswith("__pycache__/") or "/__pycache__/" in rel:
                continue
            digest.update(rel.encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _check_tests_touched_product(root):
    """`tests-touched-product`: тесты не создали и не изменили ни одного файла продукта.

    Тот же приём, что и check_read_only, только вокруг всего набора тестов,
    а снимок — `_PRODUCT_DIRS`, а не одна фикстура.
    """
    if _NESTED_RUN_GUARD in os.environ:
        return []
    before = _product_hash(root)
    env = dict(os.environ)
    env[_NESTED_RUN_GUARD] = "1"
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"],
                   cwd=str(root), capture_output=True, text=True, env=env)
    after = _product_hash(root)
    if before != after:
        return [Finding("tests-touched-product", "tests", 1,
                        "продукт изменился после прогона тестов")]
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description="package check")
    parser.add_argument("root")
    args = parser.parse_args(argv)
    report = check(args.root)
    rendered = report.render()
    if rendered:
        print(rendered)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
