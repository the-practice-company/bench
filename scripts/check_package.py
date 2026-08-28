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

from scripts.findings import Finding, Report
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter

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
    if matcher == "*":
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
    # UNC \\сервер\ресурс
    + r"|(?<![\w.])\\\\[A-Za-z0-9._-]+\\"
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
# Вызов скрипта пакета из прозы скилла.
SCRIPT_CALL = re.compile(r"(?:python3?\s+|sh\s+|bash\s+|\./)\S*scripts/\S+")
# Разрушающий пример в инструкциях ADOPT.
DESTRUCTIVE = re.compile(r"(?<![\w-])(?:mv|rm)\s+[^\s`]")

# Каталоги, не входящие в пакет (dev-инструменты секции 21). `inbox/` и
# `sources/` — материалы собственной разработки: этот репозиторий удваивается
# под контекст-репозиторий своей же разработки, и абсолютный путь в чужой
# цитате внутри них не находка проверки пакета. Остальные шесть имён зон
# отсюда убраны: раньше исключались все восемь, и любой каталог пакета, чьё
# имя совпало с зоной, уходил из скана целиком.
SKIP_DIRS = {".git", ".claude", "fixtures", "tests", "docs", "__pycache__",
             "inbox", "sources"}

# Прогон тестов, вложенный в собственную проверку (см. _check_tests_touched_product),
# сам пересобирает весь набор тестов, включая тест, что зовёт этот скрипт
# подпроцессом (TestThisPackage.test_our_own_package_is_green). Без метки во
# вложенном окружении это самовоспроизводящаяся рекурсия без дна. Метка
# ставится ровно вложенному прогону и обрывает её на первом уровне.
_NESTED_RUN_GUARD = "TWINKLE_CHECK_PACKAGE_NESTED_RUN"


def _iter_package_files(root):
    """Все файлы пакета, которые читаются как текст.

    Формат определяется тем, декодируется ли файл в UTF-8, а не расширением:
    фильтр по списку расширений уводил из-под проверки файлы без расширения,
    `.yaml`, `.toml` и `Makefile`. Бинарные отсеиваются на чтении, в `check()`.

    Проверяется только первый сегмент, как в `zones.zone_of()`: проверка по
    любому сегменту на любой глубине снимала со скана `skills/inbox/` — скилл,
    чьё имя совпало с зоной.
    """
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.relative_to(root).parts[0] in SKIP_DIRS:
            continue
        yield path


def check(root):
    root = Path(root)
    findings = []

    hooks_file = root / "hooks" / "hooks.json"
    if hooks_file.exists():
        try:
            data = json.loads(hooks_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            # Невосстановимое значение уходит в отчёт, а не роняет всю проверку
            # (незыблемое №4): битый hooks.json не обязан гасить остальные находки.
            findings.append(Finding("unparseable", "hooks/hooks.json", error.lineno, str(error)))
            data = None
        if data is not None:
            for event, entries in (data.get("hooks") or {}).items():
                if event not in HOOK_EVENTS:
                    findings.append(Finding("unknown-hook-event", "hooks/hooks.json", 1, event))
                for entry in entries or []:
                    matcher = entry.get("matcher", "*")
                    if not matcher_is_known(matcher):
                        findings.append(Finding("unknown-matcher", "hooks/hooks.json", 1, str(matcher)))
                    for hook in entry.get("hooks") or []:
                        if hook.get("type") not in HOOK_TYPES:
                            findings.append(Finding("unknown-hook-type", "hooks/hooks.json", 1,
                                                    str(hook.get("type"))))

    skills_dir = root / "skills"
    if skills_dir.exists():
        for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            rel = skill.relative_to(root).as_posix()
            manifest = skill / "SKILL.md"
            if not manifest.exists():
                findings.append(Finding("skill-without-description", rel, 1, "нет SKILL.md"))
                continue
            try:
                fields = parse_frontmatter(manifest.read_text(encoding="utf-8"))
            except FrontmatterError as error:
                findings.append(Finding("unparseable", rel + "/SKILL.md", error.line, str(error)))
                continue
            if not fields.get("description"):
                findings.append(Finding("skill-without-description", rel, 1, "пустое описание"))
            if fields.get("name") != skill.name:
                findings.append(Finding("skill-name-mismatch", rel, 1,
                                        "%r != %r" % (fields.get("name"), skill.name)))
            if not (skill / "eval.txt").exists():
                findings.append(Finding("skill-without-eval", rel, 1,
                                        "нет eval.txt: срабатывание не проверяется"))

    for path in _iter_package_files(root):
        rel = path.relative_to(root).as_posix()
        # Байт-код не входит в пакет и не пишется руками, зато после свёртки
        # констант содержит те абсолютные префиксы, которые в исходнике
        # собраны из фрагментов. Пока `.pyc` не декодировался, он отсеивался
        # сам собой; чтение с заменой (ниже) сделало его видимым, и проверка
        # на собственном репозитории покраснела на своём же `__pycache__`.
        # Первым сегментом он уже отсеян в `_iter_package_files`, вложенный —
        # нет; `_tree_hash` и `_product_hash` исключают обе формы давно.
        if "__pycache__/" in rel:
            continue
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
            # и вся заявленная функциональность молча не работала.
            if rel.startswith("skills/") and SCRIPT_CALL.search(line) \
                    and "${CLAUDE_PLUGIN_ROOT}" not in line:
                findings.append(Finding("relative-path-in-skill", rel, lineno,
                                        line.strip()[:80]))
            # ADOPT мутирует чужое дерево; пример mv или rm в его инструкциях
            # рано или поздно исполнят буквально.
            if rel.startswith("skills/adopt-") and DESTRUCTIVE.search(line):
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
    """Хеш дерева: имя, размер и содержимое каждого файла, кроме служебного."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith((".git/", "__pycache__/")) or "/__pycache__/" in rel:
            continue
        digest.update(rel.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def check_read_only(root, gate, fixture):
    """Гейт обязан доказать read-only хешем дерева до и после."""
    before = _tree_hash(fixture)
    subprocess.run([sys.executable, str(root / "scripts" / gate), str(fixture)],
                   capture_output=True, text=True)
    after = _tree_hash(fixture)
    if before != after:
        return [Finding("gate-not-read-only", "scripts/" + gate, 1,
                        "дерево фикстуры изменилось после прогона")]
    return []


def _product_hash(root):
    """Хеш `scripts/` и `.claude-plugin/`: единственное, чего тесты не вправе трогать."""
    digest = hashlib.sha256()
    for sub in ("scripts", ".claude-plugin"):
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
    а продукт — `scripts/` и `.claude-plugin/`, а не одна фикстура.
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
                        "scripts/ или .claude-plugin/ изменились после прогона тестов")]
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
