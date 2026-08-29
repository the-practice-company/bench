#!/usr/bin/env python3
"""Состязательная проверка: сажает мутацию в копию дерева и смотрит, покраснеет ли набор.

Зелёный набор тестов не доказывает, что проверка работает. Доказывает ровно
одно — посаженное нарушение, от которого набор краснеет. Волну 1 один раз уже
объявляли закрытой на зелёном `./check`; мутации показали, что четыре критерия
из пяти выполнены только по виду, а проверка слепа там, где заявляла покрытие.
Дыры починены, но каждая мутация была разовым куском shell в переписке. Волн
впереди ещё четыре, и каждой нужно то же доказательство — отсюда таблица ниже.

Три исхода, названные по-разному намеренно:

- **убита** — набор покраснел. Проверка в этом месте видит.
- **ВЫЖИЛА** — набор остался зелёным. Это находка: критерий держится на честном
  слове. Ослаблять мутацию, чтобы она «прошла», запрещено — чинится проверка.
- **не легла** — искомого текста в файле уже нет. Это другая поломка: устарела
  таблица здесь, а не гейт. Смешать её с выжившей значит спрятать обе.

Рабочее дерево не трогается: мутация живёт в одноразовой копии под
`tempfile.TemporaryDirectory()` и умирает вместе с ней.

В `./check` инструмент не включается: шестнадцать копий дерева и шестнадцать
прогонов тестового модуля в них — десятки секунд, а `./check` обязан оставаться
достаточно дешёвым, чтобы его гоняли постоянно. Запускается руками:

    python3 dev/mutate.py

Код возврата: 0 — все мутации убиты, 2 — есть выжившая, 1 — таблица устарела.
"""

import collections
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import zones

KILLED = "убита"
SURVIVED = "ВЫЖИЛА"
NOT_APPLIED = "не легла"


class NotApplied(Exception):
    """Мутация не легла на дерево.

    Замена, чей образец в файле не найден, молча не делает ничего — и дальше
    «выживает» тривиально, потому что мутировать было нечего. Отдельный класс
    исключения разводит этот исход со слепой проверкой.
    """


def _short(text):
    """Первая непустая строка образца, обрезанная до читаемого размера."""
    for line in text.split("\n"):
        line = line.strip()
        if line:
            return line[:60]
    return text[:60]


def substitution(path, find, replace):
    """Замена ровно одного вхождения `find` в файле `path` копии.

    Единственность — часть проверки применимости: два вхождения означают, что
    образец перестал указывать на конкретное место, и мутация уже не та,
    которая описана в таблице.
    """
    def step(root):
        target = root / path
        if not target.exists():
            raise NotApplied("нет файла %s" % path)
        text = target.read_text(encoding="utf-8")
        hits = text.count(find)
        if hits != 1:
            raise NotApplied("в %s вхождений %d, а не одно: %s"
                             % (path, hits, _short(find)))
        target.write_text(text.replace(find, replace), encoding="utf-8")
    return step


def copied_file(src, dst):
    """Копия файла в новое место копии дерева, вместе с недостающими каталогами."""
    def step(root):
        source = root / src
        target = root / dst
        if not source.exists():
            raise NotApplied("нет файла %s" % src)
        if target.exists():
            raise NotApplied("%s уже существует, мутация ничего не меняет" % dst)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return step


# Комментарии Windows и UNC вырезаются вместе с ветками: отдельно они не
# осмысленны, а ведущий перевод строки убирает за собой пустую строку внутри
# вызова re.compile.
_WINDOWS_AND_UNC_BRANCHES = r'''
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
    + r"|(?<![\w.])\\\\[A-Za-z0-9._-]+\\"'''

# Имена зон для мутации SKIP_DIRS берутся из scripts.zones, а не переписываются
# сюда литералами. Переписанные, они и были копией таблицы зон — тем самым
# нарушением, которое ловит критерий 5: tests/test_zones.py назвал этот файл
# офендером на первом же прогоне `./check`. Оснастка, доказывающая критерий,
# не имеет права его нарушать.
_ZONES_AS_LITERALS = ", ".join('"%s"' % name for name in zones.ZONES)

Mutation = collections.namedtuple("Mutation", "criterion name module steps")

# Критерии — по номерам раздела «Волна 1» в docs/roadmap.md. Соответствие
# «критерий → мутации → тестовый модуль» продублировано прозой в
# docs/criteria-coverage.md; таблицы обязаны сходиться.
MUTATIONS = (
    Mutation(
        criterion=1,
        name="dead-allow: две причины схлопнуты в одну",
        module="tests.test_fixtures",
        steps=(
            substitution(
                "scripts/check_links.py",
                "строка без причины: ",
                "правило ничего не исключает, удалите: ",
            ),
        ),
    ),
    Mutation(
        criterion=1,
        name="wikilink: запрещённый откат на basename",
        module="tests.test_fixtures",
        steps=(
            substitution(
                "scripts/check_links.py",
                "            candidates = index.get(target, [])\n",
                "            candidates = index.get(target, [])\n"
                '            if not candidates and "/" in target:\n'
                '                candidates = index.get(target.rsplit("/", 1)[-1], [])\n',
            ),
        ),
    ),
    Mutation(
        criterion=1,
        name="глоб снова считается конкретным путём",
        module="tests.test_fixtures",
        steps=(
            substitution(
                "scripts/paths.py",
                '    return "*" in token or "?" in token '
                "or bool(_GLOB_CLASS.search(token))\n",
                "    return False\n",
            ),
        ),
    ),
    Mutation(
        criterion=1,
        name="шаблон уходит из-под проверки корня",
        module="tests.test_fixtures",
        steps=(
            substitution(
                "scripts/check_links.py",
                '    if pathlib_rules.escapes_root(token, base=""):\n'
                '        return "escapes-root"\n'
                "    if pathlib_rules.is_pattern(token):\n"
                "        return None\n",
                "    if pathlib_rules.is_pattern(token):\n"
                "        return None\n"
                '    if pathlib_rules.escapes_root(token, base=""):\n'
                '        return "escapes-root"\n',
            ),
        ),
    ),
    Mutation(
        criterion=2,
        name="часы: import datetime в гейте ссылок",
        module="tests.test_fixtures",
        steps=(
            substitution(
                "scripts/check_links.py",
                "import argparse\nimport re\n",
                "import argparse\nimport datetime\nimport re\n",
            ),
        ),
    ),
    Mutation(
        criterion=2,
        name="Report молча теряет переданную дату",
        module="tests.test_fixtures",
        steps=(
            substitution(
                "scripts/findings.py",
                "        self.today = today\n",
                "        self.today = None\n",
            ),
        ),
    ),
    Mutation(
        criterion=3,
        name="матчер: любой принимается за известный",
        module="tests.test_check_package",
        steps=(
            substitution(
                "scripts/check_package.py",
                "def matcher_is_known(matcher):\n"
                "    matcher = str(matcher)\n"
                '    if matcher == "*":\n'
                "        return True\n"
                '    parts = matcher.split("|")\n'
                "    return all(part in TOOL_NAMES for part in parts)\n",
                "def matcher_is_known(matcher):\n"
                "    return True\n",
            ),
        ),
    ),
    Mutation(
        criterion=3,
        name="absolute-path: пять префиксов, без Windows и UNC",
        module="tests.test_check_package",
        steps=(
            substitution(
                "scripts/check_package.py",
                '    "/" + "Users/", "/" + "home/", "/" + "root/", "/" + "opt/", "/" + "etc/",\n'
                '    "/" + "tmp/", "/" + "var/", "/" + "usr/", "/" + "srv/", "/" + "mnt/",\n'
                '    "/" + "media/", "/" + "private/", "/" + "Volumes/", "/" + "Applications/",\n'
                '    "/" + "Library/", "/" + "System/",\n'
                "    # Корни, которых список не знал вовсе. Из-за этой дыры shebang с\n"
                "    # захардкоженным интерпретатором проходил зелёным — не потому, что\n"
                "    # портируем, а потому что был невидим целиком; собственный `./check`\n"
                "    # этого репозитория проверка пропускала мимо, пока комментарий рядом\n"
                "    # и спека утверждали обратное.\n"
                '    "/" + "bin/", "/" + "sbin/", "/" + "dev/", "/" + "sys/", "/" + "proc/",\n'
                '    "/" + "run/", "/" + "lib/", "/" + "lib64/", "/" + "boot/", "/" + "snap/",\n'
                '    "/" + "nix/", "/" + "cores/", "/" + "Network/",\n',
                '    "/" + "Users/", "/" + "home/", "/" + "opt/", "/" + "etc/", "/" + "root/",\n',
            ),
            substitution(
                "scripts/check_package.py",
                _WINDOWS_AND_UNC_BRANCHES,
                "",
            ),
        ),
    ),
    Mutation(
        criterion=3,
        name="shebang: исключение снимает строку целиком",
        module="tests.test_check_package",
        steps=(
            substitution(
                "scripts/check_package.py",
                "            scanned = line\n"
                "            if lineno == 1:\n"
                "                shebang = _PORTABLE_SHEBANG.match(line)\n"
                "                if shebang:\n"
                "                    scanned = line[shebang.end():]\n"
                "            if ABSOLUTE.search(scanned):\n",
                "            if ABSOLUTE.search(line) and not "
                "(lineno == 1 and _PORTABLE_SHEBANG.match(line)):\n",
            ),
        ),
    ),
    Mutation(
        criterion=3,
        name="скан: файл с недекодируемым байтом пропускается",
        module="tests.test_check_package",
        steps=(
            substitution(
                "scripts/check_package.py",
                '        text = path.read_text(encoding="utf-8", errors="replace")\n',
                "        try:\n"
                '            text = path.read_text(encoding="utf-8")\n'
                "        except UnicodeDecodeError:\n"
                "            continue\n",
            ),
        ),
    ),
    Mutation(
        criterion=3,
        name="скан пакета: фильтр по списку расширений",
        module="tests.test_check_package",
        steps=(
            substitution(
                "scripts/check_package.py",
                "        if path.relative_to(root).parts[0] in SKIP_DIRS:\n"
                "            continue\n"
                "        yield path\n",
                "        if path.relative_to(root).parts[0] in SKIP_DIRS:\n"
                "            continue\n"
                '        if (path.suffix not in {".md", ".py", ".sh", ".json", ".base", ".txt"}\n'
                '                and path.name != "check"):\n'
                "            continue\n"
                "        yield path\n",
            ),
        ),
    ),
    Mutation(
        criterion=3,
        name="SKIP_DIRS: все восемь имён зон обратно",
        module="tests.test_check_package",
        steps=(
            substitution(
                "scripts/check_package.py",
                'SKIP_DIRS = {".git", ".claude", "fixtures", "tests", "docs", "__pycache__",\n'
                '             "inbox", "sources"}\n',
                'SKIP_DIRS = {".git", ".claude", "fixtures", "tests", "docs", "__pycache__",\n'
                "             " + _ZONES_AS_LITERALS + "}\n",
            ),
        ),
    ),
    Mutation(
        criterion=3,
        name="skill-without-eval удалён из проверки",
        module="tests.test_check_package",
        steps=(
            substitution(
                "scripts/check_package.py",
                '            if not (skill / "eval.txt").exists():\n'
                '                findings.append(Finding("skill-without-eval", rel, 1,\n'
                '                                        "нет eval.txt: срабатывание не проверяется"))\n',
                "",
            ),
        ),
    ),
    Mutation(
        criterion=4,
        name="удалён тест, на который ссылается таблица",
        module="tests.test_gate_coverage",
        steps=(
            substitution(
                "tests/test_check_package.py",
                "    def test_skill_without_trigger_eval_fails(self):\n"
                "        with tempfile.TemporaryDirectory() as tmp:\n"
                "            root = _minimal_package(Path(tmp))\n"
                '            (root / "skills" / "drain-inbox" / "eval.txt").unlink()\n'
                '            self.assertIn("skill-without-eval", check(root).counts())\n'
                "\n",
                "",
            ),
        ),
    ),
    Mutation(
        criterion=4,
        name="цитата в таблице заменена прозой",
        module="tests.test_gate_coverage",
        steps=(
            substitution(
                "docs/gate-coverage.md",
                "| `orphan` | битая фикстура, 1 находка в `sources` | "
                "`tests/test_fixtures.py::TestExactFindings::"
                "test_every_link_finding_sits_on_its_own_specimen` |",
                "| `orphan` | битая фикстура, 1 находка в `sources` | покрыто тестами |",
            ),
        ),
    ),
    Mutation(
        criterion=5,
        name="второе определение зон: hooks/zones.py",
        module="tests.test_zones",
        steps=(
            copied_file("scripts/zones.py", "hooks/zones.py"),
        ),
    ),
)


def _why_red(stderr):
    """Почему набор покраснел: первый упавший тест и итоговый счёт.

    Мутация обязана ронять набор в том месте, ради которого посажена. Без
    имени теста «покраснел» неотличим от «покраснел по другой причине» —
    например, потому что мутация сломала импорт.
    """
    first = ""
    tally = ""
    for line in stderr.split("\n"):
        if not first and (line.startswith("FAIL: ") or line.startswith("ERROR: ")):
            first = line.split(":", 1)[1].strip().split(" ")[0]
        if line.startswith("FAILED") or line.startswith("OK"):
            tally = line.strip()
    return "%s, первым упал %s" % (tally or "красный", first or "неизвестно кто")


def run(mutation):
    """Ставит мутацию в одноразовую копию и возвращает (исход, деталь)."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "repo"
        shutil.copytree(ROOT, copy,
                        ignore=shutil.ignore_patterns(".git", "__pycache__"))
        try:
            for step in mutation.steps:
                step(copy)
        except NotApplied as error:
            return NOT_APPLIED, str(error)
        result = subprocess.run(
            [sys.executable, "-m", "unittest", mutation.module, "-q"],
            cwd=str(copy), capture_output=True, text=True,
        )
        if result.returncode == 0:
            return SURVIVED, "набор остался зелёным — проверка здесь слепа"
        return KILLED, _why_red(result.stderr)


def main():
    outcomes = []
    for mutation in MUTATIONS:
        outcome, detail = run(mutation)
        outcomes.append(outcome)
        print("%-9s К%d  %-50s %-25s %s"
              % (outcome, mutation.criterion, mutation.name, mutation.module, detail),
              flush=True)

    killed = outcomes.count(KILLED)
    survived = outcomes.count(SURVIVED)
    stale = outcomes.count(NOT_APPLIED)
    print("\n%d мутаций: %d убито, %d выжило, %d не легло"
          % (len(MUTATIONS), killed, survived, stale))
    if survived:
        print("Выжившая мутация — находка: критерий выполнен только по виду.")
        return 2
    if stale:
        print("Мутация не легла: устарела таблица в dev/mutate.py, а не гейт.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
