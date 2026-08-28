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
_ABSOLUTE_PREFIXES = (
    "/" + "Users/", "/" + "home/", "/" + "root/", "/" + "opt/", "/" + "etc/",
    "/" + "tmp/", "/" + "var/", "/" + "usr/", "/" + "srv/", "/" + "mnt/",
    "/" + "media/", "/" + "private/", "/" + "Volumes/", "/" + "Applications/",
    "/" + "Library/", "/" + "System/", "~" + "/",
)
ABSOLUTE = re.compile(
    "(?<![\\w.])(?:%s)" % "|".join(re.escape(p) for p in _ABSOLUTE_PREFIXES)
    # Буква диска Windows: одна латинская буква, двоеточие и разделитель
    # пути. Однобуквенность и отсутствие слова слева разводят её с
    # `http` + двоеточие, где перед двоеточием стоит `p`.
    + r"|(?<![\w.])[A-Za-z]:[\\/]"
    # UNC \\сервер\ресурс
    + r"|(?<![\w.])\\\\[A-Za-z0-9._-]+\\"
)
# Вызов скрипта пакета из прозы скилла.
SCRIPT_CALL = re.compile(r"(?:python3?\s+|sh\s+|bash\s+|\./)\S*scripts/\S+")
# Разрушающий пример в инструкциях ADOPT.
DESTRUCTIVE = re.compile(r"(?<![\w-])(?:mv|rm)\s+[^\s`]")

# Инструменты разработки плагина, в пакет не идут (секция 21). Плюс восемь
# зон рецепта (`zones.ZONES`, единственное определение — не копия): этот
# репозиторий сам удваивается под контекст-репозиторий своей собственной
# разработки («inbox/», «sources/» с материалами исследования), и их
# содержимое — данные зоны, а не код пакета. Абсолютный путь в чужой цитате
# внутри `sources/agent-research/*.md` не находка проверки пакета.
SKIP_DIRS = {".git", "fixtures", "tests", "docs", "__pycache__"} | set(zones.ZONES)

# Прогон тестов, вложенный в собственную проверку (см. _check_tests_touched_product),
# сам пересобирает весь набор тестов, включая тест, что зовёт этот скрипт
# подпроцессом (TestThisPackage.test_our_own_package_is_green). Без метки во
# вложенном окружении это самовоспроизводящаяся рекурсия без дна. Метка
# ставится ровно вложенному прогону и обрывает её на первом уровне.
_NESTED_RUN_GUARD = "TWINKLE_CHECK_PACKAGE_NESTED_RUN"


def _iter_package_files(root):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        # Только первый сегмент, как zones.zone_of(): зоны этого репозитория
        # (inbox/, sources/ — материалы собственной разработки) живут в корне
        # и нигде больше. Проверка по любому сегменту на любой глубине снимала
        # с прохода целые поддеревья пакета — skills/inbox/ (скилл, чьё имя
        # совпало с зоной) и весь scaffold/ (буквально восемь папок-зон) —
        # ровно то, что должно быть просканировано.
        if path.relative_to(root).parts[0] in SKIP_DIRS:
            continue
        if path.suffix in (".md", ".py", ".sh", ".json", ".base", ".txt") or path.name == "check":
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
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.split("\n"), start=1):
            if ABSOLUTE.search(line):
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
