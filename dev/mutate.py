#!/usr/bin/env python3
"""Состязательная проверка: сажает мутацию в копию дерева и смотрит, покраснеет ли набор.

Зелёный набор тестов не доказывает, что проверка работает. Доказывает ровно
одно — посаженное нарушение, от которого набор краснеет. Волну 1 один раз уже
объявляли закрытой на зелёном `./check`; мутации показали, что четыре критерия
из пяти выполнены только по виду, а проверка слепа там, где заявляла покрытие.
Дыры починены, но каждая мутация была разовым куском shell в переписке. Волн
впереди ещё четыре, и каждой нужно то же доказательство — отсюда таблица ниже.

**Оснастка однажды имела ровно тот дефект, который ловит.** Вердикт считался
кодом возврата: `0` — выжила, иначе убита. Из этого следовали три подлога.

Первый: набор мог быть красным ещё *до* мутации. В момент аудита посторонний
файл нёс строку, ронявшую `test_our_own_package_is_green`, — и все восемь
мутаций критерия 3 заверялись тестом, который к ним не относится вовсе.
Состояние было преходящим и невидимым. Отсюда **база**: тот же модуль сперва
гоняется на неизменённой копии, набор упавших запоминается, и мутация судится
по **разнице**, а не по коду возврата.

Второй: мутация, ломающая продукт целиком, тоже давала ненулевой код.
Посаженный `import nonexistent_module_xyz` объявлялся убитым — «покраснел»
неотличим от «покраснел, потому что нечего стало импортировать». Отсюда
**дымовая проверка**: тронутые файлы обязаны разбираться и импортироваться,
иначе это дефект мутации, а не убийство.

Третий: печаталось «первым упал X», где X — первый по алфавиту, а не по делу.
Отсюда **объявленный тест**: каждая мутация называет тест, который обязан
упасть именно от неё. «Убита» значит «проверка, которая заявляла это место,
его увидела», а не «что-то покраснело».

Пять исходов, названные по-разному намеренно:

- **убита** — объявленный тест появился в разнице. Проверка в этом месте видит.
- **ВЫЖИЛА** — разница пуста. Это находка: критерий держится на честном слове.
  Ослаблять мутацию, чтобы она «прошла», запрещено — чинится проверка.
- **КРАСНОЕ НЕ ТО** — разница есть, объявленного теста в ней нет. Тоже находка:
  место закрыто не тем тестом, который на него ссылается, — или объявление
  устарело. Считать это убийством значит вернуть подлог номер три.
- **не легла** — образца замены в файле нет, либо замена ничего не изменила.
  Это другая поломка: устарела таблица здесь, а не гейт. Смешать её с
  выжившей значит спрятать обе — пустая замена «выживает» тривиально.
- **СЛОМАЛА ПРОДУКТ** — тронутый файл перестал разбираться или импортироваться.
  Дефект мутации; чинить надо строку таблицы, а не гейт.

Рабочее дерево не трогается: мутация живёт в одноразовой копии под
`tempfile.TemporaryDirectory()` и умирает вместе с ней. Слепок дерева снимается
**один раз** на прогон, и база с мутациями считаются от одного и того же
слепка: иначе правка в рабочем каталоге посреди прогона разъезжает базу с
мутантом и разница врёт.

В `./check` инструмент не включается: слепок дерева и прогон тестового модуля
на каждую мутацию — десятки секунд, а `./check` обязан оставаться достаточно
дешёвым, чтобы его гоняли постоянно. Запускается руками:

    python3 dev/mutate.py

Код возврата: 0 — все мутации убиты; 2 — есть выжившая или покрасневшая не тем
тестом (находка о проверке); 1 — есть не легшая или сломавшая продукт (дефект
таблицы здесь).
"""

import collections
import json
import os
import py_compile
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
ELSEWHERE = "КРАСНОЕ НЕ ТО"
NOT_APPLIED = "не легла"
BROKEN = "СЛОМАЛА ПРОДУКТ"

# Порядок печати сводки: сперва то, ради чего инструмент существует.
OUTCOMES = (KILLED, SURVIVED, ELSEWHERE, NOT_APPLIED, BROKEN)


class NotApplied(Exception):
    """Мутация не легла на дерево.

    Замена, чей образец в файле не найден, молча не делает ничего — и дальше
    «выживает» тривиально, потому что мутировать было нечего. Отдельный класс
    исключения разводит этот исход со слепой проверкой.
    """


def _short(text, width=70):
    """Первая непустая строка образца, обрезанная до читаемого размера."""
    for line in text.split("\n"):
        line = line.strip()
        if line:
            return line[:width]
    return text[:width]


def _last_line(text, width=70):
    """Последняя непустая строка — у трассировки и у PyCompileError там суть.

    Первая строка обеих несёт путь во временный каталог: он меняется от
    прогона к прогону и в отчёте бесполезен.
    """
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return lines[-1][:width] if lines else "без причины"


def _tail(test_id):
    """`Класс.метод` из полного идентификатора: модуль и так известен."""
    return ".".join(test_id.split(".")[-2:])


def substitution(path, find, replace):
    """Замена ровно одного вхождения `find` в файле `path` копии.

    Единственность — часть проверки применимости: два вхождения означают, что
    образец перестал указывать на конкретное место, и мутация уже не та,
    которая описана в таблице.

    Возвращает тронутые пути: по ним считается дымовая проверка и сверка
    байтов со слепком.
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
        return (path,)
    return step


def line_removal(path, marker):
    """Удаление единственной строки, содержащей `marker`.

    Форма для веток регулярного выражения. Дословный образец на них не
    держится: комментарий рядом переписывают при каждой найденной дыре, и
    мутация «не ложится» из-за прозы, а не из-за кода. Маркер — кусок самой
    ветки, короткий и не встречающийся больше нигде в файле.
    """
    def step(root):
        target = root / path
        if not target.exists():
            raise NotApplied("нет файла %s" % path)
        lines = target.read_text(encoding="utf-8").split("\n")
        hits = [number for number, line in enumerate(lines) if marker in line]
        if len(hits) != 1:
            raise NotApplied("в %s строк с «%s» %d, а не одна"
                             % (path, _short(marker), len(hits)))
        del lines[hits[0]]
        target.write_text("\n".join(lines), encoding="utf-8")
        return (path,)
    return step


def block_replacement(path, opening, closing, replacement):
    """Замена блока от строки с `opening` до первой строки, равной `closing`.

    Форма для растущих списков. Дословный образец куска списка ложится, пока
    список не переписали, — и «не легла» тогда сообщает о чужой работе, а не
    о мутации. Границы блока переживают и дописанные элементы, и вставленные
    внутрь комментарии.
    """
    def step(root):
        target = root / path
        if not target.exists():
            raise NotApplied("нет файла %s" % path)
        lines = target.read_text(encoding="utf-8").split("\n")
        starts = [number for number, line in enumerate(lines) if opening in line]
        if len(starts) != 1:
            raise NotApplied("в %s строк с «%s» %d, а не одна"
                             % (path, _short(opening), len(starts)))
        start = starts[0]
        ends = [number for number in range(start + 1, len(lines))
                if lines[number].strip() == closing]
        if not ends:
            raise NotApplied("в %s после «%s» нет закрывающей «%s»"
                             % (path, _short(opening), closing))
        lines[start:ends[0] + 1] = replacement.split("\n")
        target.write_text("\n".join(lines), encoding="utf-8")
        return (path,)
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
        return (dst,)
    return step


def stripped_exec_bit(path):
    """Снятие права на запуск. Единственная мутация, не меняющая ни байта.

    Содержимое файла остаётся тем же, меняется режим, — и потому сверка
    байтов в `_unchanged` обязана смотреть ещё и на режим, иначе эта мутация
    отчитается «не легла», хотя легла и сработала.
    """
    def step(root):
        target = root / path
        if not target.exists():
            raise NotApplied("нет файла %s" % path)
        mode = target.stat().st_mode
        if not mode & 0o111:
            raise NotApplied("%s и так не исполняется" % path)
        target.chmod(mode & ~0o111)
        return (path,)
    return step


# Ветки буквы диска и UNC снимаются по маркеру внутри самой ветки, а не
# дословным куском файла вместе с комментариями. Дословный образец здесь уже
# отвалился: комментарий над веткой UNC переписали, объясняя новую дыру, и
# мутация отчиталась «не легла» — то есть о чужой правке прозы, а не о гейте.
# Комментарии остаются на месте: на поведение они не влияют, а мутация обязана
# менять поведение.
_WINDOWS_DRIVE_BRANCH = "[A-Z]:(?:"
_UNC_BRANCH = r"(?<![\w.])\\\\"

# Пять префиксов вместо всего списка: ровно тот объём, с которым проверка
# однажды и жила. Блок заменяется целиком, потому что список дописывают —
# за один прогон он вырос на три корня контейнеров.
_FIVE_PREFIXES = '_ABSOLUTE_PREFIXES = (\n' + (
    '    "/" + "Users/", "/" + "home/", "/" + "opt/", "/" + "etc/", "/" + "root/",\n'
) + ')'

# Имена зон для мутации SKIP_DIRS берутся из scripts.zones, а не переписываются
# сюда литералами. Переписанные, они и были копией таблицы зон — тем самым
# нарушением, которое ловит критерий 5: tests/test_zones.py назвал этот файл
# офендером на первом же прогоне `./check`. Оснастка, доказывающая критерий,
# не имеет права его нарушать.
_ZONES_AS_LITERALS = ", ".join('"%s"' % name for name in zones.ZONES)

# `expect` — тест, который обязан упасть **именно от этой мутации**. Не
# «какой-нибудь»: unittest гоняет по алфавиту, и без объявления в отчёт
# попадал первый по имени, а не по делу. Мутация «absolute-path: пять
# префиксов» так рекламировала `test_a_bash_shebang_is_still_caught`, тогда
# как по существу её ловит `test_every_absolute_form_is_caught`.
Mutation = collections.namedtuple("Mutation", "criterion name module expect steps")

# `criterion` — метка раздела в docs/roadmap.md, а не всегда номер волны 1:
# одна мутация доказывает критерий волны 3 и подписана так честно.
# Соответствие «критерий → мутации → тестовый модуль» продублировано прозой в
# docs/criteria-coverage.md; таблицы обязаны сходиться.
MUTATIONS = (
    # Критерий 1 волны 1 держится на трёх мутациях, а не на четырёх, как
    # считала таблица до аудита: «глоб снова считается конкретным путём»
    # ниже переподписана волной 3 — она не трогает битую фикстуру вовсе.
    Mutation(
        criterion="в1 К1",
        name="dead-allow: две причины схлопнуты в одну",
        module="tests.test_fixtures",
        expect="tests.test_fixtures.TestExactFindings"
               ".test_every_link_finding_sits_on_its_own_specimen",
        steps=(
            substitution(
                "scripts/check_links.py",
                "строка без причины: ",
                "правило ничего не исключает, удалите: ",
            ),
        ),
    ),
    Mutation(
        criterion="в1 К1",
        name="wikilink: запрещённый откат на basename",
        module="tests.test_fixtures",
        expect="tests.test_fixtures.TestExactFindings"
               ".test_every_link_finding_sits_on_its_own_specimen",
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
        # Подписана волной 3 после аудита. Раньше стояла под критерием 1
        # волны 1 — «каждый гейт находит на битой фикстуре ровно то, что
        # утверждает тест», — и это была неправда: битая фикстура от неё не
        # меняется вовсе, 14 находок до и 14 после. Меняется **зелёная**:
        # `.claude/settings.json` каркаса набирает три `unresolved`. Ровно
        # это и есть критерий 1 волны 3 — «каркас проходит оба гейта с нулём
        # находок». Оставить прежнюю подпись значило приписать критерию 1
        # волны 1 доказательство, которого у него нет.
        criterion="в3 К1",
        name="глоб снова считается конкретным путём",
        module="tests.test_fixtures",
        expect="tests.test_fixtures.TestExactFindings"
               ".test_green_sample_is_silent_on_both_gates",
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
        criterion="в1 К1",
        name="шаблон уходит из-под проверки корня",
        module="tests.test_fixtures",
        expect="tests.test_fixtures.TestExactFindings"
               ".test_every_link_finding_sits_on_its_own_specimen",
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
        # Доказывает ровно одно: список маркеров в тесте читается. Тест —
        # подстрочный поиск пяти литералов, и мутация сажает первый из них,
        # то есть проверяет саму себя. Настоящее чтение часов она не
        # доказывает: следующая мутация сажает такое чтение и выживает.
        criterion="в1 К2",
        name="часы: import datetime в гейте ссылок",
        module="tests.test_fixtures",
        expect="tests.test_fixtures.TestDeterminism"
               ".test_no_module_in_scripts_reads_the_clock",
        steps=(
            substitution(
                "scripts/check_links.py",
                "import argparse\nimport re\n",
                "import argparse\nimport datetime\nimport re\n",
            ),
        ),
    ),
    Mutation(
        # Ожидается **ВЫЖИЛА**, и это правильный вывод, а не поломка оснастки.
        # `st_mtime` — настоящее чтение часов внутри `scan()`, и ни один из
        # пяти маркеров теста его не содержит. Критерий 2 в этой половине
        # держится на списке подстрок, а не на признаке обращения к часам.
        # Ослабить мутацию, чтобы строка позеленела, запрещено: чинится тест.
        criterion="в1 К2",
        name="часы: st_mtime внутри scan (ожидаемо выживает)",
        module="tests.test_fixtures",
        expect="tests.test_fixtures.TestDeterminism"
               ".test_no_module_in_scripts_reads_the_clock",
        steps=(
            substitution(
                "scripts/check_links.py",
                "def scan(root, today=None):\n"
                "    root = Path(root)\n",
                "def scan(root, today=None):\n"
                "    _stamp = Path(__file__).stat().st_mtime\n"
                "    root = Path(root)\n",
            ),
        ),
    ),
    Mutation(
        criterion="в1 К2",
        name="Report молча теряет переданную дату",
        module="tests.test_fixtures",
        expect="tests.test_fixtures.TestDeterminism.test_today_is_carried_on_the_report",
        steps=(
            substitution(
                "scripts/findings.py",
                "        self.today = today\n",
                "        self.today = None\n",
            ),
        ),
    ),
    Mutation(
        criterion="в1 К3",
        name="матчер: любой принимается за известный",
        module="tests.test_check_package",
        expect="tests.test_check_package.TestPackageCheck.test_matcher_typo_is_caught",
        steps=(
            # Образец — две решающие строки, а не всё тело функции: комментарий
            # внутри неё однажды уже сделал мутацию «не легшей», хотя проверять
            # она собиралась не комментарий.
            substitution(
                "scripts/check_package.py",
                '    parts = matcher.split("|")\n'
                "    return all(part in TOOL_NAMES for part in parts)\n",
                "    return True\n",
            ),
        ),
    ),
    Mutation(
        criterion="в1 К3",
        name="absolute-path: пять префиксов, без Windows и UNC",
        module="tests.test_check_package",
        expect="tests.test_check_package.TestPackageCheck.test_every_absolute_form_is_caught",
        steps=(
            block_replacement("scripts/check_package.py",
                              "_ABSOLUTE_PREFIXES = (", ")", _FIVE_PREFIXES),
            line_removal("scripts/check_package.py", _WINDOWS_DRIVE_BRANCH),
            line_removal("scripts/check_package.py", _UNC_BRANCH),
        ),
    ),
    Mutation(
        criterion="в1 К3",
        name="shebang: исключение снимает строку целиком",
        module="tests.test_check_package",
        expect="tests.test_check_package.TestPackageCheck"
               ".test_an_absolute_path_in_shebang_arguments_is_caught",
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
        criterion="в1 К3",
        name="скан: файл с недекодируемым байтом пропускается",
        module="tests.test_check_package",
        expect="tests.test_check_package.TestPackageCheck"
               ".test_an_undecodable_byte_does_not_remove_the_file_from_the_scan",
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
        criterion="в1 К3",
        name="скан пакета: фильтр по списку расширений",
        module="tests.test_check_package",
        expect="tests.test_check_package.TestPackageCheck"
               ".test_extensionless_and_yaml_files_are_scanned",
        steps=(
            substitution(
                "scripts/check_package.py",
                "        yield path\n",
                '        if (path.suffix not in {".md", ".py", ".sh", ".json", ".base", ".txt"}\n'
                '                and path.name != "check"):\n'
                "            continue\n"
                "        yield path\n",
            ),
        ),
    ),
    Mutation(
        criterion="в1 К3",
        name="периметр снова слеп к .gitignore",
        module="tests.test_check_package",
        expect="tests.test_check_package.TestPackageCheck"
               ".test_gitignored_paths_are_outside_the_package",
        steps=(
            substitution(
                "scripts/check_package.py",
                "    ignored = ignored_prefixes(root)\n",
                "    ignored = ()\n",
            ),
        ),
    ),
    Mutation(
        criterion="в1 К3",
        name="SKIP_AT_ROOT: все восемь имён зон обратно",
        module="tests.test_check_package",
        expect="tests.test_check_package.TestPackageCheck"
               ".test_the_only_skipped_zones_are_the_ones_the_table_names",
        steps=(
            substitution(
                "scripts/check_package.py",
                'SKIP_AT_ROOT = ({"fixtures", "tests", "docs"}\n'
                "                | set(zones.READ_ONLY) | set(zones.SELF_DEVELOPMENT))\n",
                'SKIP_AT_ROOT = {"fixtures", "tests", "docs",\n'
                "                " + _ZONES_AS_LITERALS + "}\n",
            ),
        ),
    ),
    Mutation(
        criterion="в1 К3",
        name="skill-without-eval удалён из проверки",
        module="tests.test_check_package",
        expect="tests.test_check_package.TestPackageCheck"
               ".test_skill_without_trigger_eval_fails",
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
        criterion="в1 К4",
        name="удалён тест, на который ссылается таблица",
        module="tests.test_gate_coverage",
        expect="tests.test_gate_coverage.TestEveryClassIsProven.test_the_real_table_is_sound",
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
        # Заменила мутацию «цитата в таблице заменена прозой». Та роняла тот
        # же `test_the_real_table_is_sound`, что и соседняя выше, и та же
        # ветка `_problems` уже проверена на синтетической строке
        # (`test_prose_instead_of_a_citation_is_caught`) — второго факта она
        # не устанавливала. Вторая половина критерия 4 — «каждый класс вообще
        # назван в таблице» — не была атакована ничем: строку класса можно
        # было вынести, и набор оставался зелёным по этой мутации.
        criterion="в1 К4",
        name="из таблицы покрытия вынут целый класс",
        module="tests.test_gate_coverage",
        expect="tests.test_gate_coverage.TestEveryClassIsProven"
               ".test_coverage_table_lists_every_class",
        steps=(
            substitution(
                "docs/gate-coverage.md",
                "| `orphan` | битая фикстура, 1 находка в `sources` | "
                "`tests/test_fixtures.py::TestExactFindings::"
                "test_every_link_finding_sits_on_its_own_specimen` |\n",
                "",
            ),
        ),
    ),
    Mutation(
        criterion="в1 К5",
        name="второе определение зон: hooks/zones.py",
        module="tests.test_zones",
        expect="tests.test_zones.TestSingleDefinition.test_no_second_zone_table_in_package",
        steps=(
            copied_file("scripts/zones.py", "hooks/zones.py"),
        ),
    ),

    # Волна 2. Пять критериев — пять мутаций, по одной на каждый.
    Mutation(
        # **Косвенная, и это сказано вслух.** Критерий говорит о свойстве
        # *тестов* — «хук прогоняется настоящим подпроцессом», — а мутация
        # правит продукт. Прямо опровергнуть свойство тестов правкой продукта
        # нельзя вообще: тест, зовущий `hook.main()` напрямую, останется
        # зелёным при любой мутации шима, потому что шим у него не участвует.
        #
        # Снятый бит исполнения — ближайшее честное приближение: он ломает
        # ровно те тесты, которые действительно запускают `hook.sh`, и не
        # трогает ни одного, который зовёт логику. Объявлен поэтому не
        # `test_shim_is_executable` (тот читает права файла и покраснел бы
        # даже у набора, целиком зовущего логику напрямую), а обычный тест
        # поведения: он падает `PermissionError` внутри `subprocess.run` —
        # то есть предъявляет сам факт запуска.
        #
        # Чего мутация не доказывает: что подпроцессом прогоняется **каждый**
        # хук. Она доказывает это про те тесты, что покраснели, и молчит про
        # те, что остались зелёными по другой причине.
        criterion="в2 К1",
        name="шим лишается бита исполнения",
        module="tests.test_hook_entry",
        expect="tests.test_hook_entry.TestEntryContract"
               ".test_unknown_event_is_not_a_violation",
        steps=(
            stripped_exec_bit("hooks/hook.sh"),
        ),
    ),
    Mutation(
        # Код возврата остаётся 2, исчезает только строка причины: набор,
        # проверяющий один `returncode`, останется зелёным. Ровно это и
        # утверждает критерий — что утверждаются **оба**.
        criterion="в2 К2",
        name="блок за границей теряет текст причины",
        module="tests.test_hook_events",
        expect="tests.test_hook_events.TestPreToolUseWrite"
               ".test_write_outside_root_is_blocked_and_names_the_boundary",
        steps=(
            substitution(
                "hooks/hook.py",
                '    if boundary.outside(target, root):\n'
                '        print("граница рабочего каталога: %s лежит вне корня %s. Плагин "\n'
                '              "не пишет наружу никогда" % (target, root), file=sys.stderr)\n'
                "        return EXIT_VIOLATION\n",
                "    if boundary.outside(target, root):\n"
                "        return EXIT_VIOLATION\n",
            ),
        ),
    ),
    Mutation(
        # План предлагал глушить stderr шима через `2>/dev/null`. Такую
        # мутацию убивает `TestNoSilencing.test_shim_never_silences` —
        # подстрочный поиск трёх запрещённых литералов в файле, — и
        # доказывала бы она ровно одно: что поиск читает файл. Про поведение
        # «не смог» она не сказала бы ничего.
        #
        # Здесь снимается сама строка причины в ветке отсутствующего
        # интерпретатора. Код 0 на месте, `TestNoSilencing` остаётся зелёным
        # (запрещённых литералов в файле не появилось), краснеет только тест
        # поведения — и краснеет на второй половине критерия, на видимой
        # строке, а не на коде возврата.
        criterion="в2 К3",
        name="«не смог» теряет строку про интерпретатор",
        module="tests.test_hook_entry",
        expect="tests.test_hook_entry.TestEntryContract"
               ".test_missing_interpreter_is_visible_and_not_a_violation",
        steps=(
            line_removal("hooks/hook.sh", "гейт не выполнился: интерпретатор"),
        ),
    ),
    Mutation(
        # Нормализация снимается, посегментное сравнение остаётся: критерий
        # говорит «resolves outside … **after normalisation**», и мутация
        # сажает ровно это, а не заодно и сравнение по префиксу строки.
        #
        # Модуль — `tests.test_boundary`, и это выбор, а не умолчание. На
        # уровне хука та же мутация краснеет наизнанку: `tempfile` на macOS
        # отдаёт `/var/...`, `find_root` нормализует корень в `/private/var/...`,
        # и ненормализованное сравнение объявляет наружными **законные**
        # записи. Проверено: `test_symlink_out_of_root_is_blocked` остаётся
        # зелёным, а падают семь тестов про запись внутрь. Это «КРАСНОЕ НЕ ТО»
        # — набор покраснел, но по обратной причине. Вторую половину критерия
        # («код 2, названа граница») держит мутация в2 К2, на уровне хука.
        criterion="в2 К4",
        name="граница сравнивается без нормализации",
        module="tests.test_boundary",
        expect="tests.test_boundary.TestOutside.test_dotdot_above_root_is_outside",
        steps=(
            substitution(
                "hooks/boundary.py",
                "    resolved = Path(os.path.realpath(str(path)))\n"
                "    base = Path(os.path.realpath(str(root)))\n",
                "    resolved = Path(path)\n"
                "    base = Path(root)\n",
            ),
        ),
    ),
    Mutation(
        # `False` вместо чтения поля, а не `True`: сдача по умолчанию сделала
        # бы `Stop` неблокирующим всегда, и покраснело бы полмодуля — сказав
        # про блокировку, а не про флаг. С `False` блок остаётся на месте
        # везде, кроме второго захода, — краснеет ровно тот тест, который про
        # `stop_hook_active` и есть.
        criterion="в2 К5",
        name="stop_hook_active перестаёт читаться",
        module="tests.test_hook_events",
        expect="tests.test_hook_events.TestStop.test_stop_hook_active_gives_up_out_loud",
        steps=(
            substitution(
                "hooks/hook.py",
                '    active = payload.get("stop_hook_active")\n',
                "    active = False\n",
            ),
        ),
    ),
)


# Идентификаторы упавших тестов снимаются с объектов тестов, а не разбором
# вывода `-v`: у теста с docstring исход уезжает на следующую строку, и разбор
# по «FAIL: » уже однажды печатал первого по алфавиту вместо первого по делу.
# Отчёт пишется в файл **вне копии дерева**: печать самих тестов в stdout
# перемешалась бы с ним, а лишний файл внутри копии увидел бы скан пакета.
_COLLECTOR = '''\
import json
import os
import sys
import unittest

# Скрипт лежит вне копии, поэтому sys.path[0] указывает не туда: модули берутся
# из рабочего каталога, то есть из копии дерева.
sys.path.insert(0, os.getcwd())

module, out = sys.argv[1], sys.argv[2]
report = {"failed": [], "ran": 0, "crashed": None}
try:
    suite = unittest.TestLoader().loadTestsFromName(module)
    with open(os.devnull, "w") as sink:
        result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
    # У subTest идентификатор несёт хвост вида ` [form=...]`: без обрезки один
    # и тот же тест давал бы разные имена и не совпал бы с объявленным.
    report["failed"] = sorted({t.id().split(" ")[0]
                               for t, _ in result.failures + result.errors})
    report["ran"] = result.testsRun
except BaseException as error:
    report["crashed"] = "%s: %s" % (type(error).__name__, error)
with open(out, "w") as handle:
    json.dump(report, handle)
'''

# Импорт по пути файла, а не по точечному имени: у `hooks/` нет `__init__.py`,
# и точечная форма выдала бы за поломку продукта то, что ею не является.
_IMPORT_PROBE = '''\
import importlib.util
import os
import sys

sys.path.insert(0, os.getcwd())

for number, path in enumerate(sys.argv[1:]):
    spec = importlib.util.spec_from_file_location("_probe_%d" % number, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
'''

Run = collections.namedtuple("Run", "failed ran crashed")
Session = collections.namedtuple("Session", "snapshot tools baselines")


def _session(workdir):
    """Слепок дерева и вспомогательные скрипты — один раз на прогон.

    Слепок один намеренно: база и мутанты обязаны считаться от одного и того
    же дерева. Если снимать его заново на каждую мутацию, правка в рабочем
    каталоге посреди прогона попадёт в мутанта и не попадёт в базу — разница
    покажет чужую работу и назовёт её убийством.
    """
    snapshot = workdir / "snapshot"
    shutil.copytree(ROOT, snapshot,
                    ignore=shutil.ignore_patterns(".git", "__pycache__"))
    tools = workdir / "tools"
    tools.mkdir()
    (tools / "collect.py").write_text(_COLLECTOR, encoding="utf-8")
    (tools / "probe.py").write_text(_IMPORT_PROBE, encoding="utf-8")
    return Session(snapshot=snapshot, tools=tools, baselines={})


def _fresh_copy(session, tmp, name):
    """Копия слепка под своим именем: база и мутант живут рядом, не поверх."""
    copy = Path(tmp) / name
    shutil.copytree(session.snapshot, copy)
    return copy


def _collect(session, copy, module, tmp, name):
    """Множество упавших тестов модуля в этой копии дерева."""
    out = Path(tmp) / ("failed-%s.json" % name)
    result = subprocess.run(
        [sys.executable, str(session.tools / "collect.py"), module, str(out)],
        cwd=str(copy), capture_output=True, text=True,
    )
    if not out.exists():
        return Run(failed=frozenset(), ran=0,
                   crashed="сборщик не отчитался (код %d): %s"
                           % (result.returncode, _last_line(result.stderr)))
    report = json.loads(out.read_text(encoding="utf-8"))
    return Run(failed=frozenset(report["failed"]), ran=report["ran"],
               crashed=report["crashed"])


def _baseline(session, module, tmp):
    """Что в этом модуле красное **до** мутации.

    Без этого набора вердикт врал самым тихим способом: посторонняя правка в
    дереве роняла один тест, и каждая мутация этого модуля объявлялась убитой
    тестом, к ней не относящимся. Считается один раз на модуль — несколько
    мутаций делят его, и платить за прогон повторно незачем.
    """
    if module not in session.baselines:
        copy = _fresh_copy(session, tmp, "base")
        session.baselines[module] = _collect(session, copy, module, tmp, "base")
    return session.baselines[module]


def _unchanged(session, copy, touched):
    """Правда ли, что мутация не изменила ни байта содержимого и ни бита режима.

    Замена строки на саму себя проходит проверку применимости и дальше
    «выживает» — то есть врёт про слепую проверку там, где проверять было
    нечего. Мутация без единого изменённого байта — устаревшая строка
    таблицы, а не находка о гейте.

    Режим сверяется наравне с содержимым, потому что бит исполнения — тоже
    свойство продукта: `hook.sh` без него не запускается ни одним тестом.
    Одной сверки байтов хватало ровно до появления такой мутации, и без
    второй половины она отчиталась бы «не легла».
    """
    for rel in touched:
        before = session.snapshot / rel
        if not before.exists():
            return False
        after = copy / rel
        if before.read_bytes() != after.read_bytes():
            return False
        if (before.stat().st_mode & 0o777) != (after.stat().st_mode & 0o777):
            return False
    return True


def _smoke(session, copy, touched, tmp):
    """Продукт после мутации обязан разбираться и импортироваться.

    Мутация, ломающая импорт или синтаксис, роняет модуль целиком — и по коду
    возврата «покраснел от мутации» неотличим от «покраснел, потому что
    нечего стало импортировать». Посаженный `import nonexistent_module_xyz`
    этим и объявлялся убитым. Такая мутация — дефект строки таблицы, а не
    доказательство, что гейт видит.

    Оболочка проверяется наравне с питоном. Шим — тоже продукт, и мутация,
    сломавшая его разбор, объявлялась бы убитой по той же причине, по какой
    объявлялся убитым сломанный импорт: `sh` печатает свою ошибку и выходит
    ненулевым, а тесты, ждущие нуля, краснеют. Различить это по разнице
    нельзя — только разбором.

    Возвращает причину поломки или None.
    """
    shells = [rel for rel in touched if rel.endswith(".sh")]
    for rel in shells:
        result = subprocess.run(["/bin/sh", "-n", str(copy / rel)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            return "%s не разбирается оболочкой: %s" % (rel, _last_line(result.stderr))

    sources = [rel for rel in touched if rel.endswith(".py")]
    if not sources:
        return None
    cache = Path(tmp) / "probe.pyc"
    for rel in sources:
        try:
            py_compile.compile(str(copy / rel), cfile=str(cache), doraise=True)
        except py_compile.PyCompileError as error:
            return "%s не разбирается: %s" % (rel, _last_line(str(error)))
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, str(session.tools / "probe.py")] + sources,
        cwd=str(copy), capture_output=True, text=True, env=environment,
    )
    if result.returncode != 0:
        return "не импортируется: %s" % _last_line(result.stderr)
    return None


def run(mutation, session):
    """Ставит мутацию в одноразовую копию и возвращает (исход, деталь)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = _baseline(session, mutation.module, tmp)
        if base.crashed:
            return BROKEN, "база %s не считается: %s" % (mutation.module, base.crashed)

        copy = _fresh_copy(session, tmp, "mutant")
        touched = []
        try:
            for step in mutation.steps:
                # Несколько шагов правят один файл: в списке он нужен один
                # раз, иначе дымовая проверка импортирует его трижды.
                touched.extend(rel for rel in step(copy) if rel not in touched)
        except NotApplied as error:
            return NOT_APPLIED, str(error)
        if _unchanged(session, copy, touched):
            return NOT_APPLIED, "образец найден, но ни один байт не изменился"

        broken = _smoke(session, copy, touched, tmp)
        if broken:
            return BROKEN, broken

        after = _collect(session, copy, mutation.module, tmp, "mutant")
        if after.crashed:
            return BROKEN, "прогон не состоялся: %s" % after.crashed

        delta = sorted(after.failed - base.failed)
        if not delta:
            return SURVIVED, ("ничего нового не покраснело; в базе модуля "
                              "красных: %d из %d" % (len(base.failed), base.ran))
        if mutation.expect in delta:
            extra = "" if len(delta) == 1 else " (+%d попутно)" % (len(delta) - 1)
            return KILLED, _tail(mutation.expect) + extra
        return ELSEWHERE, "ждали %s, покраснело: %s" % (
            _tail(mutation.expect), ", ".join(_tail(name) for name in delta))


def _self_check():
    """Строки таблицы, противоречащие себе.

    Объявленный тест обязан жить в объявленном модуле: иначе он не может
    попасть в разницу никогда, и мутация обречена на «КРАСНОЕ НЕ ТО» по
    опечатке, а не по существу.
    """
    problems = []
    seen = set()
    for mutation in MUTATIONS:
        if not mutation.expect.startswith(mutation.module + "."):
            problems.append("%s: объявлен %s, а модуль %s"
                            % (mutation.name, mutation.expect, mutation.module))
        if mutation.name in seen:
            problems.append("%s: имя встречается дважды" % mutation.name)
        seen.add(mutation.name)
    return problems


def main():
    problems = _self_check()
    if problems:
        print("Таблица мутаций противоречит себе:")
        for problem in problems:
            print("  %s" % problem)
        return 1

    verdicts = []
    with tempfile.TemporaryDirectory() as workdir:
        session = _session(Path(workdir))
        for number, mutation in enumerate(MUTATIONS, 1):
            outcome, detail = run(mutation, session)
            verdicts.append((outcome, mutation, detail))
            print("[%02d] %-15s %-6s %-48s %s"
                  % (number, outcome, mutation.criterion, mutation.name, detail),
                  flush=True)

    counts = collections.Counter(outcome for outcome, _, _ in verdicts)
    print("\n%d мутаций: %s" % (
        len(MUTATIONS),
        ", ".join("%s — %d" % (name, counts[name]) for name in OUTCOMES)))

    unkilled = [(o, m, d) for o, m, d in verdicts if o != KILLED]
    if unkilled:
        print("\nНе убиты:")
        for outcome, mutation, detail in unkilled:
            print("  %-15s %s — %s" % (outcome, mutation.name, detail))

    if counts[SURVIVED]:
        print("Выжившая мутация — находка: критерий выполнен только по виду.")
    if counts[ELSEWHERE]:
        print("Покрасневшее не тем тестом — тоже находка: место закрыто не тем, "
              "что на него ссылается.")
    if counts[NOT_APPLIED]:
        print("Мутация не легла: устарела таблица в dev/mutate.py, а не гейт.")
    if counts[BROKEN]:
        print("Мутация сломала продукт: дефект строки таблицы; такой прогон "
              "ничего не доказывает.")

    if counts[NOT_APPLIED] or counts[BROKEN]:
        return 1
    if counts[SURVIVED] or counts[ELSEWHERE]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
