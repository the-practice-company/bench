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
            # Образец переехал вместе с резолвом: волна 4 вынесла обход из
            # `scan` в `occurrences`, и строка резолва wikilink'а сменила
            # отступ. Мутация та же — запрещённый откат на basename, — но
            # искать её надо там, где резолвер теперь живёт.
            substitution(
                "scripts/check_links.py",
                "                candidates = index.get(target, [])\n",
                "                candidates = index.get(target, [])\n"
                '                if not candidates and "/" in target:\n'
                "                    candidates = index.get("
                'target.rsplit("/", 1)[-1], [])\n',
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
        # Эта мутация выжила, когда была посажена, и это был правильный вывод:
        # `st_mtime` — настоящее чтение часов внутри `scan()`, а тест искал
        # пять строковых литералов, ни один из которых его не содержит.
        # Критерий 2 держался на списке подстрок, а не на признаке обращения
        # к часам. Оснастка тогда честно показала выжившую строку вместо того,
        # чтобы её спрятать, — тест после этого переписан на разбор дерева
        # кода, и мутация умирает. Оставлена как регрессия: вернётся подстрочный
        # поиск — эта строка снова позеленеет.
        criterion="в1 К2",
        name="часы: st_mtime внутри scan, мимо списка маркеров",
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
                'SKIP_AT_ROOT = ({"fixtures", "tests", "docs", "dev"}\n'
                "                | set(zones.READ_ONLY) | set(zones.SELF_DEVELOPMENT))\n",
                'SKIP_AT_ROOT = {"fixtures", "tests", "docs", "dev",\n'
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
                "scripts/boundary.py",
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

    # Волна 3. Критериев выхода четыре — четыре мутации, по одной на каждый.
    # Плюс три под меткой `в3 гейт`: они правят `check_frontmatter`, ни одному
    # критерию выхода не принадлежат и потому подписаны не критерием. Метка не
    # в форме `вN КM` намеренно — `tests/test_mutation_claims.py` требует
    # строку в `docs/criteria-coverage.md` под каждую мутацию с меткой
    # критерия, а таких у этих трёх нет. Названы они там прозой.
    Mutation(
        # Посажена так, что **полный** каркас остаётся зелёным: файл, на
        # который указывает токен, существует, и оба гейта на нём молчат.
        # Краснеет ровно прогон с удалённым `.claude/` — вторая половина
        # критерия, у которой своего фальсификатора не было ни одного.
        # Несуществующий путь убил бы мутацию любым гейтовым тестом, и вторая
        # половина осталась бы недоказанной.
        #
        # Попутно краснеют ещё два теста того же модуля, и оба — про то же
        # самое: `test_no_surviving_file_points_into_the_claude_directory`
        # (он и назван «причина, по которой предыдущий тест зелёный») и
        # `test_no_zone_readme_lists_files` (токен с закрытым расширением
        # в README зоны). Это не «КРАСНОЕ НЕ ТО»: объявленный тест в разнице
        # есть, а соседи проверяют ту же ссылку с двух других сторон.
        criterion="в3 К1",
        name="каркас ссылается в свой .claude",
        module="tests.test_scaffold",
        expect="tests.test_scaffold.TestScaffoldPassesBothGates"
               ".test_both_gates_are_still_silent_without_the_claude_directory",
        steps=(
            substitution(
                "scaffold/core/README.md",
                "**Nothing here yet.**",
                "The zone rule lives in `.claude/rules/core.md`.\n\n"
                "**Nothing here yet.**",
            ),
        ),
    ),
    Mutation(
        # Один добавленный байт на файл: копия перестаёт быть копией, а
        # каталог инстанса по-прежнему выглядит правильным. Критерий 2
        # утверждает равенство **побайтовое**, и мутация сажает ровно то,
        # что отличает его от «файлы на месте».
        criterion="в3 К2",
        name="установщик правит байты по дороге",
        module="tests.test_install_scaffold",
        expect="tests.test_install_scaffold.TestFirstCommit"
               ".test_the_commit_carries_the_scaffold_blob_for_blob",
        steps=(
            # Образец — три строки цикла копирования, а не одна строка
            # записи. Одной хватало ровно до волны 4: `merge` задачи 11
            # завёл вторую такую же запись — создание целиком, когда чужого
            # файла нет, — и мутация отчиталась «не легла», то есть о чужой
            # правке, а не об установщике. Цикл `for source, target, rel in
            # plan` в файле один, и байты портятся там, где они копируются
            # каркасом.
            substitution(
                "scripts/install_scaffold.py",
                "    for source, target, rel in plan:\n"
                "        target.parent.mkdir(parents=True, exist_ok=True)\n"
                "        target.write_bytes(source.read_bytes())\n",
                "    for source, target, rel in plan:\n"
                "        target.parent.mkdir(parents=True, exist_ok=True)\n"
                '        target.write_bytes(source.read_bytes() + b"\\n")\n',
            ),
        ),
    ),
    Mutation(
        # Вид берётся из зелёной фикстуры, а не пишется здесь: файл с
        # `views.base` в каркасе — это ровно «структурная единица без
        # настоящей записи», которую критерий 3 запрещает, и взятый из
        # фикстуры он ещё и валиден, то есть краснеет инвентарь, а не разбор.
        criterion="в3 К3",
        name="каркас везёт коллекцию без записей",
        module="tests.test_scaffold",
        expect="tests.test_scaffold.TestScaffoldInventory"
               ".test_the_scaffold_carries_no_collection",
        steps=(
            copied_file("fixtures/green/decisions/views.base",
                        "scaffold/decisions/views.base"),
        ),
    ),
    Mutation(
        criterion="в3 К4",
        name="перечисление файлов в порождённом CLAUDE.md",
        module="tests.test_scaffold",
        expect="tests.test_scaffold.TestGeneratedClaudeMd.test_it_lists_no_files",
        steps=(
            substitution(
                "scaffold/CLAUDE.md",
                "## Placement rule\n",
                "## Files\n\n- core/me.md — who we are\n\n## Placement rule\n",
            ),
        ),
    ),
    Mutation(
        # **Метка — не критерий, и это не опечатка.** План волны предлагал
        # подписать эту строку «в3 К1», и своей же прозой рядом называл её
        # «одной на правку гейта» — то есть пятой сверх четырёх критериев.
        # Критерий 1 говорит о каркасе («проходит оба гейта с нулём находок»),
        # а каркас не везёт ни одного `views.base`: `check_frontmatter.scan`
        # в него не заходит вовсе, и эта мутация не меняет на каркасе ничего.
        # Зелёная фикстура тоже не меняется — её вид отбирает из
        # `decisions/items`, где README коллекции не лежит. Подписать строку
        # критерием 1 значило бы приписать ему доказательство, которого у него
        # нет: ровно тот подлог, который аудит уже нашёл однажды у мутации
        # «глоб снова считается конкретным путём».
        #
        # Метка не в форме `вN КM` намеренно: `tests/test_mutation_claims.py`
        # требует строку в `docs/criteria-coverage.md` под каждую мутацию
        # своей волны, а строки таблицы там — критерии. Мутация, не
        # принадлежащая ни одному, названа прозой того же документа.
        #
        # Анкер — на поведении, а не на строках Task 1. Мутация снимает
        # **ветку, исключающую README коллекции из перечисления**, и
        # опознаёт её по двум коротким приметам: сама сверка (`== declaration`,
        # без отступа и без имени слева) и её `continue`. Как записана
        # сверка — `rel == declaration_rel`, `record.resolve() == declaration`
        # или что-то третье — мутации всё равно, отступ в маркер не входит,
        # комментарий внутри ветки её не сдвигает.
        #
        # Почему не дословный кусок: первая редакция этой строки цитировала
        # две строки Task 1 вместе с шестнадцатью пробелами отступа — и
        # устарела до первого прогона, потому что Task 1 переписали. Таблица
        # мутаций, цитирующая реализацию, гниёт при каждом касании
        # реализации; `substitution` отчиталась бы «не легла», то есть о
        # чужой правке, а не о гейте (тот же довод, что у `line_removal`
        # и `block_replacement` в их докстрингах).
        #
        # `line_removal` здесь не годится: снятая одна строка `if` оставляет
        # голый `continue`, гейт перестаёт проверять записи вовсе и
        # `test_the_collections_own_readme_is_not_a_record` — он ждёт пустого
        # списка — становится **зелёным**. Мутация выжила бы, ничего не сказав.
        criterion="в3 гейт",
        name="README коллекции снова перечисляется как запись",
        module="tests.test_check_frontmatter",
        expect="tests.test_check_frontmatter.TestCollectionOwnReadme"
               ".test_the_collections_own_readme_is_not_a_record",
        steps=(
            block_replacement(
                "scripts/check_frontmatter.py",
                "== declaration",
                "continue",
                "",
            ),
        ),
    ),
    Mutation(
        # Два рубежа периметра, закрывавшие друг друга. Проба задачи 1 волны 3
        # сняла каждый по отдельности и получила зелёный набор из 466 тестов:
        # фикстуры `TestPerimeter` клали за периметр коллекцию целиком, поэтому
        # вид отсекался первым рубежом, записи — вторым, и отсутствие любого
        # было невидимо. Тесты под оба заведены тогда же, трекер записал
        # «обе мутации стоит завести» — вот они.
        #
        # Этот снимает рубеж у `views.base`. Собой находку дают вид и
        # объявление: кривой README архивной коллекции — `unparseable`.
        # Через записи это не видно, их отсекает второй рубеж.
        criterion="в3 гейт",
        name="периметр frontmatter снят у views.base",
        module="tests.test_check_frontmatter",
        expect="tests.test_check_frontmatter.TestPerimeter"
               ".test_a_declaration_outside_the_perimeter_is_not_read_at_all",
        steps=(
            block_replacement(
                "scripts/check_frontmatter.py",
                "_in_perimeter(rel_base",
                "continue",
                "",
            ),
        ),
    ),
    Mutation(
        # Второй рубеж, у записи. Держит он случай, когда коллекция жива, а
        # часть её записей — нет: игнорируемое поддерево внутри `items/` либо
        # живой вид с `file.inFolder("archive/...")`. `archive/` снимается
        # префиксом **от корня**, поэтому такой вид первый рубеж проходит.
        #
        # Маркер — `_in_perimeter(rel,` с запятой: без неё он совпал бы и с
        # `_in_perimeter(rel_base`, то есть с соседним рубежом, и мутация
        # отчиталась бы «строк с маркером две».
        criterion="в3 гейт",
        name="периметр frontmatter снят у записи",
        module="tests.test_check_frontmatter",
        expect="tests.test_check_frontmatter.TestPerimeter"
               ".test_an_ignored_subtree_under_a_live_collection_is_outside",
        steps=(
            block_replacement(
                "scripts/check_frontmatter.py",
                "_in_perimeter(rel,",
                "continue",
                "",
            ),
        ),
    ),

    # Волна 4. Критериев выхода пять — пять мутаций, по одной на каждый.
    # Плюс одна под меткой `в4 Д1`: она правит `created`, ни одному критерию
    # выхода не принадлежит и потому подписана не критерием. Метка не в форме
    # `вN КM` намеренно — тот же приём, что у `в3 гейт`: строку в
    # `docs/criteria-coverage.md` `tests/test_mutation_claims.py` требует под
    # каждую мутацию с меткой критерия, а такой у неё нет. Названа она там
    # прозой.
    Mutation(
        # Буквальная команда секции 18 вместо выкладки из `HEAD`. Она
        # восстанавливает из **индекса**, а каждая мутация цепочки индекс уже
        # изменила: после `git mv notes areas/work/notes` путь `notes` в
        # индексе отсутствует и команда падает на pathspec, а `archive`,
        # снятый `git rm`, не возвращается вовсе.
        #
        # `_sweep` остаётся на месте, и это часть посадки: неудалённой целью
        # мутация не пользуется. Дерево расходится с манифестом на **том**,
        # чего буквальная команда не умеет, — на пропавшем доноре и на
        # невернувшемся архиве.
        #
        # `TestFalsifiers.test_the_literal_command_from_the_spec_does_not_restore`
        # от мутации не краснеет и краснеть не обязан: он зовёт git напрямую,
        # мимо `revert`. Фальсификатор утверждает, что команда не работает;
        # мутация утверждает, что набор это заметит, если её вернуть в код.
        criterion="в4 К1",
        name="revert по букве секции 18: выкладка из индекса",
        module="tests.test_revert",
        expect="tests.test_revert.TestByteForByte"
               ".test_the_manifest_returns_to_what_it_was",
        steps=(
            substitution(
                "scripts/adopt/revert.py",
                '    tree.git(root, "reset", "-q", "HEAD", "--", path)\n'
                '    if tree.git_zlines(root, "ls-tree", "-r", "--name-only", "-z",\n'
                '                       "HEAD", "--", path):\n'
                '        tree.git(root, "checkout", "HEAD", "--", path)\n',
                '    tree.git(root, "checkout", "--", path)\n',
            ),
        ),
    ),
    Mutation(
        # Правка, знающая только голую форму: путевые wikilink'и она
        # пропускает. Это и есть третий фальсификатор критерия 2 —
        # **зеркальный** тому, что назван в спеке волны. Спека называет
        # правку, знающую только путевую форму, «при переезде, создающем
        # коллизию basename»; коллизия R не двигает, потому что неоднозначная
        # ссылка считается одним вхождением по решению той же спеки.
        # Двигает R слепота к форме — любой из двух, и обе половины
        # `test_the_chain_preserves_R` меряет за один прогон: переезд
        # каталога роняет R здесь на первом шаге.
        criterion="в4 К2",
        name="rewrite-refs слеп к путевой форме wikilink'а",
        module="tests.test_rewrite_refs",
        expect="tests.test_rewrite_refs.TestChain.test_the_chain_preserves_R",
        steps=(
            substitution(
                "scripts/adopt/rewrite_refs.py",
                "        candidate = next((c for c in hit.candidates "
                "if _under(c, source)), None)\n"
                "        if candidate is None:\n"
                "            continue\n",
                "        candidate = next((c for c in hit.candidates "
                "if _under(c, source)), None)\n"
                '        if candidate is None or "/" in hit.target:\n'
                "            continue\n",
            ),
        ),
    ),
    Mutation(
        # Снимается **проверка согласия**, а не обязательность `--plan`.
        # План остаётся аргументом и остаётся прочитанным; исчезает ровно то,
        # о чём говорит критерий 3 — «before the author has agreed». Мутация
        # на обязательности аргумента объявленный тест не уронила бы: он
        # передаёт план и получает отказ по строке без крестика.
        criterion="в4 К3",
        name="move исполняет строку без крестика",
        module="tests.test_move",
        expect="tests.test_move.TestMove"
               ".test_an_unagreed_line_is_refused_with_a_named_reason",
        steps=(
            substitution(
                "scripts/adopt/move.py",
                "        if not line.agreed:\n"
                '            return None, ("строка не согласована: `%s` -> `%s`"\n'
                "                          % (line.source, line.target))\n",
                "",
            ),
        ),
    ),
    Mutation(
        # Ветка отказа перестаёт достигаться, и `init-tree` заводит git там,
        # где автор сказал «нет». Критерий 4 требует двух вещей сразу — план
        # написан и **ни один файл не изменён**; здесь ломается вторая, и
        # ломается видимо: `.git` появляется в дереве, которого ADOPT обещал
        # не трогать.
        criterion="в4 К4",
        name="init-tree заводит git вопреки --no-git",
        module="tests.test_declined",
        expect="tests.test_declined.TestDeclined"
               ".test_nothing_but_the_plan_appears_and_nothing_changes",
        steps=(
            substitution(
                "scripts/adopt/init_tree.py",
                "    if no_git:\n",
                "    if False:\n",
            ),
        ),
    ),
    Mutation(
        # Обход остаётся, находка не заводится: план становится «полным»
        # при любом составе дерева. Это и есть механизм критерия 5 — молчание
        # наблюдаемо ровно потому, что план обязан быть тотальным, — и без
        # этой строки он держался бы на обещании.
        criterion="в4 К5",
        name="непокрытый путь перестаёт называться находкой",
        module="tests.test_adopt_plan",
        expect="tests.test_adopt_plan.TestCoverage"
               ".test_an_unmentioned_directory_is_reported_once_at_its_top",
        steps=(
            substitution(
                "scripts/adopt/plan.py",
                '            out.append(Finding("uncovered-path", plan_rel, 1,\n'
                '                               "путь не покрыт ни одной строкой: %s" % child))\n',
                "            continue\n",
            ),
        ),
    ),
    Mutation(
        # Ловушка, измеренная спекой: 235 файлов необратимо несут дату
        # прогона миграции. Подставленная дата от настоящей неотличима, и
        # именно поэтому мутация сажает **чтение часов**, а не подмену токена
        # `UNKNOWN`. Подмена константы оставила бы тест зелёным: он сверяет
        # ответ с `dates.UNKNOWN`, то есть с той же самой константой.
        #
        # Метка — не критерий: `created` не назван ни одним из пяти. Прозой
        # он назван в разделе волны 4 документа покрытия.
        criterion="в4 Д1",
        name="created подставляет дату прогона вместо unknown",
        module="tests.test_dates",
        expect="tests.test_dates.TestCreated"
               ".test_without_history_the_token_is_unknown_not_today",
        steps=(
            substitution(
                "scripts/adopt/dates.py",
                "import sys\nfrom pathlib import Path\n",
                "import datetime\nimport sys\nfrom pathlib import Path\n",
            ),
            substitution(
                "scripts/adopt/dates.py",
                "        return UNKNOWN                  "
                "# ни git, ни коммитов — истории нет\n",
                "        return datetime.date.today().isoformat()\n",
            ),
        ),
    ),

    # Волна 5. Критериев выхода пять; мутаций двадцать шесть, и распределены
    # они неровно намеренно. Критерий 5 несёт одиннадцать: половина «дифф
    # счётчиков» получила производителя последней, и её пробовали отдельной
    # оснасткой — таблица оттуда перенесена сюда целиком, а не пересказана.
    # Плюс пять под метками не в форме `вN КM`: `в5 Д1` — инвариант 2 волны
    # («второй прогон не меняет ни байта»), `в5 Д2` — инвариант
    # `drain-inbox`. Ни один из них не критерий выхода, и `criteria-coverage`
    # называет их прозой, а не строкой таблицы: `tests/test_mutation_claims.py`
    # требует строку под каждую мутацию **с меткой критерия**.
    Mutation(
        # Критерий 1 двусторонний: «чинит форму» и «не изменяет содержимое».
        # Мутация сажает вторую половину и сажает её так, как она и случилась
        # бы по-настоящему — под видом полезной починки: `unresolved` в теле
        # записи снимает скобки и уходит из отчёта. Гейт зеленеет, автор
        # ничего не заметил, а текст, который он писал, переписан.
        criterion="в5 К1",
        name="MAINTAIN чинит unresolved в теле записи",
        module="tests.test_mechanical",
        expect="tests.test_mechanical.TestWhatIsReported"
               ".test_an_unresolved_link_in_a_record_body_is_reported_not_guessed",
        steps=(
            substitution(
                "scripts/maintain/mechanical.py",
                "    findings = list(check_links.scan(root).findings)\n"
                "    findings.extend(check_frontmatter.scan(root).findings)\n"
                "    return sorted(fixed), findings, sorted(skipped)\n",
                "    findings = list(check_links.scan(root).findings)\n"
                "    for finding in [f for f in findings "
                'if f.cls == "unresolved"]:\n'
                "        target = root / finding.path\n"
                '        text = target.read_text(encoding="utf-8", '
                'errors="replace")\n'
                "        changed = text.replace(finding.detail, "
                'finding.detail.strip("[]"))\n'
                "        if changed == text or finding.path in dirty_paths:\n"
                "            continue\n"
                '        target.write_text(changed, encoding="utf-8")\n'
                "        fixed.append(finding.path)\n"
                "        findings.remove(finding)\n"
                "    findings.extend(check_frontmatter.scan(root).findings)\n"
                "    return sorted(fixed), findings, sorted(skipped)\n",
            ),
        ),
    ),
    Mutation(
        # Первая половина того же критерия, и атакована она у корня: вся
        # проверка «содержимое не тронуто» сравнивает дерево с **объявленной**
        # поверхностью. Выведенная из прогона, она исключает ровно то, что
        # прогон записал, — и `content_diff` перестаёт краснеть навсегда, ни
        # разу не сказав об этом вслух. Здесь она выводится из каркаса: файл
        # лежит в `scaffold/` — значит, форма.
        criterion="в5 К1",
        name="поверхность формы выводится из каркаса, а не объявлена",
        module="tests.test_content_diff",
        expect="tests.test_content_diff.TestSurfaceIsStatic"
               ".test_the_surface_is_a_literal_and_not_derived_from_a_run",
        steps=(
            block_replacement(
                "scripts/maintain/surface.py", "SURFACE = (", ")",
                "_SCAFFOLD = Path(__file__).resolve().parent.parent.parent "
                '/ "scaffold"\n'
                "SURFACE = tuple(\n"
                '    Entry(path.relative_to(_SCAFFOLD).as_posix(), "bytes",\n'
                '          "выведено из прогона: что лежит в каркасе, то и форма")\n'
                "    for path in sorted(_SCAFFOLD.rglob(\"*\")) if path.is_file())",
            ),
        ),
    ),
    Mutation(
        # Критерий 2 держится на трёх мутациях, потому что «показывает спрос и
        # не действует по нему» ломается тремя разными способами, и ни один не
        # выводится из двух других: дата приходит не от автора; возраст мерится
        # не по истории; порог стоит не там, где обещан.
        #
        # Здесь — дата. Умолчание из часов возвращает в мутирующий режим ровно
        # ту зависимость, которую волна 1 выкорчёвывала дважды, и цена здесь
        # выше: у гейта отсутствие даты меняет текст отчёта, тут — удаляет
        # папку.
        criterion="в5 К2",
        name="--today получает умолчание из часов",
        module="tests.test_demand",
        expect="tests.test_demand.TestAges.test_today_is_mandatory",
        steps=(
            substitution(
                "scripts/maintain/demand.py",
                "import argparse\nimport sys\nfrom pathlib import Path\n",
                "import argparse\nimport datetime\nimport sys\n"
                "from pathlib import Path\n",
            ),
            substitution(
                "scripts/maintain/demand.py",
                "def run(root, today):\n"
                '    """(отчёт, находки). Ничего не пишет на диск."""\n'
                "    root = Path(root)\n",
                "def run(root, today=None):\n"
                '    """(отчёт, находки). Ничего не пишет на диск."""\n'
                "    if today is None:\n"
                "        today = datetime.date.today().isoformat()\n"
                "    root = Path(root)\n",
            ),
        ),
    ),
    Mutation(
        # Возраст по `st_mtime`. Чекаут переставляет его, и ответ начинает
        # зависеть от того, когда гоняли набор, — та же поломка, что пережила
        # проверку волны 1. Объявленный тест сверяет ровно число: у
        # устаревшей коллекции фикстуры git знает 2026-07-01, а файловая
        # система — день её развёртывания.
        criterion="в5 К2",
        name="возраст считается по st_mtime, а не по истории",
        module="tests.test_prune",
        expect="tests.test_prune.TestFalsifiers"
               ".test_st_mtime_instead_of_git_gives_a_different_age",
        steps=(
            substitution(
                "scripts/maintain/demand.py",
                "import argparse\nimport sys\nfrom pathlib import Path\n",
                "import argparse\nimport sys\nimport time\n"
                "from pathlib import Path\n",
            ),
            substitution(
                "scripts/maintain/demand.py",
                "def age(root, rel, today):\n"
                '    """Дней с последнего коммита, затронувшего путь, либо '
                'токен."""\n'
                "    root = Path(root)\n"
                "    return _age(last_touch(root, rel), first_commit(root), today)\n",
                "def age(root, rel, today):\n"
                '    """Дней с последнего коммита, затронувшего путь, либо '
                'токен."""\n'
                "    root = Path(root)\n"
                '    touched = time.strftime("%Y-%m-%d",\n'
                "                            time.localtime("
                "(root / rel).stat().st_mtime))\n"
                "    return _age(touched, first_commit(root), today)\n",
            ),
        ),
    ),
    Mutation(
        # Порог, сдвинутый на день: ровно разница между `>=` и `>`. Граница
        # объявлена включающей, и утверждается она поимённо — 30 дней удалено,
        # 29 нет. Сдвиг на единицу невидим в любом отчёте и виден только на
        # самой границе.
        criterion="в5 К2",
        name="порог пустой коллекции сдвинут на день",
        module="tests.test_prune",
        expect="tests.test_prune.TestThreshold"
               ".test_exactly_thirty_days_is_removed_and_twenty_nine_is_not",
        steps=(
            substitution("scripts/maintain/demand.py",
                         "THRESHOLD_DAYS = 30\n", "THRESHOLD_DAYS = 31\n"),
        ),
    ),
    Mutation(
        # Критерий 3 — «единица не заводится без содержимого» — у `add-view`
        # читается так: вид над папкой с нулём записей есть структурная
        # единица без содержимого. Проверка снимается целиком, разбор вида
        # остаётся: краснеет отказ, а не парсер.
        criterion="в5 К3",
        name="add-view перестаёт проверять пустоту папки",
        module="tests.test_extend",
        expect="tests.test_extend.TestAddView"
               ".test_a_view_over_an_empty_folder_is_refused",
        steps=(
            substitution(
                "scripts/maintain/extend.py",
                "    for folder in sorted(set(base.folders)):\n"
                "        target = root / folder\n"
                '        if not target.is_dir() or not sorted(target.glob("*.md")):\n'
                '            return ("отказ: file.inFolder называет папку с нулём '
                'записей: %s\\n"\n'
                "                    % folder), EXIT_VIOLATION\n",
                "",
            ),
        ),
    ),
    Mutation(
        # Вторая половина того же критерия, у `add-area`: папка направления
        # заведена, строки в перечислении нет. Единица есть, содержимого о ней
        # — ни строки, и дрейф заведён по построению. Обязательство это волна 3
        # передала волне 5 отдельной строкой roadmap'а.
        criterion="в5 К3",
        name="add-area не трогает areas/README.md",
        module="tests.test_extend",
        expect="tests.test_extend.TestAddArea"
               ".test_a_direction_with_a_purpose_gets_a_folder_and_a_row",
        steps=(
            substitution("scripts/maintain/extend.py",
                         '    readme.write_text(listing, encoding="utf-8")\n', ""),
        ),
    ),
    Mutation(
        # Критерий 4 — «не пишет синтетику молча». Первая половина: писать
        # вообще нечего там, где значение уже стоит. Снятая проверка «ключ
        # есть» переписывает авторское — и делает это тихо, потому что вторым
        # таким же ключом frontmatter перестаёт разбираться вовсе.
        criterion="в5 К4",
        name="backfill переписывает существующее значение",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestNothingIsOverwritten"
               ".test_a_collection_where_everyone_has_the_field_produces_nothing",
        steps=(
            substitution("scripts/maintain/backfill.py",
                         "        if field in fields:\n            continue\n", ""),
        ),
    ),
    Mutation(
        # Вторая половина: `unknown` в поле с объявленным словарём — починка,
        # производящая ошибку гейта (`value-outside-vocabulary`). Ветка
        # `deferred` подменяется штампом, и подменяется молча: отчёт про такую
        # запись не говорит ничего, потому что синтетике отчёт не положен —
        # токен виден в самой записи.
        criterion="в5 К4",
        name="backfill штампует unknown в поле со словарём",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestDeferred"
               ".test_a_field_with_a_declared_vocabulary_is_deferred_not_stamped",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                "        elif declared:\n"
                '            rows.append((rel, field, "", "", "deferred", '
                '"vocabulary-declared"))\n',
                "        elif declared:\n"
                '            rows.append((rel, field, "", UNKNOWN, "synthetic", '
                '"no-rule"))\n',
            ),
        ),
    ),
    Mutation(
        # Критерий 5, первая половина на уровне самого диффа: недостача
        # перестаёт называться находкой. Обход остаётся, множество ожидаемых
        # считается, сверка происходит — и молчит. Ровно тот случай, ради
        # которого дифф и заведён: таблица накрыла не то, что собиралась, и
        # сказать об этом некому.
        criterion="в5 К5",
        name="дифф счётчиков молча проглатывает недостачу",
        module="tests.test_field_map",
        expect="tests.test_field_map.TestCounts"
               ".test_a_shortfall_without_a_token_is_unexplained_count",
        steps=(
            substitution(
                "scripts/maintain/field_map.py",
                "    for rel in sorted(expected):\n"
                "        if rel in present:\n"
                "            continue\n"
                "        if explained.get(rel) in TOKENS:\n"
                "            continue\n"
                "        findings.append(Finding(\n"
                '            "unexplained-count", rel, 1,\n'
                '            "запись ожидалась в таблице и её там нет, '
                'объяснения тоже"))\n',
                "    for rel in sorted(expected):\n"
                "        continue\n",
            ),
        ),
    ),

    # Десять мутаций критерия 5 на уровне производителя. Прогнаны они были
    # отдельной оснасткой — задача, строившая дифф, не имела права трогать
    # этот файл, — и перенесены сюда дословно, а не пересказаны. Каждая
    # перепрогнана здесь: перенесённая строка, которая на самом деле не
    # краснеет, хуже отсутствующей.
    Mutation(
        # **Анти-тавтология, и это главная строка критерия 5.** Ожидаемое
        # берётся у вида коллекции (`check_frontmatter.record_paths`), а не у
        # обхода `plan`. Взятое у обхода, оно сверяет обход с самим собой:
        # дифф зеленеет по построению и не краснеет уже никогда. Запись в
        # `drafts` — запись для вида и невидимка для `**/items/*.md`.
        criterion="в5 К5",
        name="ожидаемое берётся у обхода backfill, а не у вида",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestTheCounterDiff"
               ".test_a_record_the_view_names_and_the_walk_misses_is_unexplained",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                "    for rel in check_frontmatter.record_paths("
                "root, base_path, base, ignored):\n",
                "    for rel in sorted(p.relative_to(root).as_posix()\n"
                '                      for p in (root / collection / "items")'
                '.glob("*.md")):\n',
            ),
        ),
    ),
    Mutation(
        # Канал объяснённой недостачи отрезан: `skipped` не доезжает до
        # `reconcile`. Непрочитанная запись для вида — запись, для обхода —
        # пропуск с токеном, и без третьего аргумента каждая такая становится
        # сюрпризом. Дифф начинает краснеть там, где всё сошлось.
        criterion="в5 К5",
        name="skipped не доезжает до reconcile",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestTheCounterDiff"
               ".test_a_shortfall_carrying_a_token_of_the_closed_list_is_explained",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                "    return findings + field_map.reconcile(expected, rows, skipped)",
                "    return findings + field_map.reconcile(expected, rows, {})",
            ),
        ),
    ),
    Mutation(
        # «Ожидаемых ноль» вместо «ожидаемое не установлено». Коллекция без
        # вида перечислять нечем, и тихий ноль объявляет сюрпризом каждую
        # строку таблицы разом — то есть красит сошедшийся прогон и молчит про
        # разошедшийся.
        criterion="в5 К5",
        name="коллекция без вида тихо ожидает ноль записей",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestTheCounterDiff"
               ".test_a_collection_without_a_view_does_not_quietly_expect_zero",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                "    if not base_path.is_file():\n"
                '        return refused("вида у коллекции нет")',
                "    if not base_path.is_file():\n        return [], []",
            ),
        ),
    ),
    Mutation(
        # Порядок: ожидаемое считается **после** мутации. Посчитанное после,
        # оно пусто — поле уже стоит у каждой записи, — и каждая строка
        # таблицы становится строкой без ожидаемой записи. Два шага, потому
        # что мутация не удаляет вычисление, а переносит его вниз: удалённое,
        # оно уронило бы `Report(diff)` именем, а не диффом.
        criterion="в5 К5",
        name="ожидаемое считается после мутации, а не до",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestCommandLine"
               ".test_the_expected_set_is_taken_before_the_mutation",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                "    diff = counter_diff(root, args.collection, args.field, "
                "rows, skipped)\n\n    if args.silently:",
                "    if args.silently:",
            ),
            substitution(
                "scripts/maintain/backfill.py",
                '    sys.stdout.write("таблица: %s\\n"\n'
                "                     % write_table(root, args.collection, "
                "args.field, rows))",
                '    sys.stdout.write("таблица: %s\\n"\n'
                "                     % write_table(root, args.collection, "
                "args.field, rows))\n"
                "    diff = counter_diff(root, args.collection, args.field, "
                "rows, skipped)",
            ),
        ),
    ),
    Mutation(
        # Дифф посчитан и никуда не поехал: ни в stdout, ни в код возврата.
        # Половина критерия, требующая «emit», — про то, что расхождение
        # доезжает до вызвавшего, а не про то, что оно вычислено.
        criterion="в5 К5",
        name="дифф счётчиков не печатается и не красит код",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestCommandLine"
               ".test_the_counter_diff_reaches_stdout_and_paints_the_code",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                "    report = Report(diff)\n    rendered = report.render()\n"
                '    if rendered:\n        sys.stdout.write(rendered + "\\n")\n'
                "    return report.exit_code()",
                "    return 0",
            ),
        ),
    ),
    Mutation(
        # Нечитаемый `.gitignore` проглочен: периметр молча сужается до
        # умолчаний, а вместе с ним и множество записей коллекции. Гейт
        # frontmatter называет этот отказ своим последствием — дифф обязан
        # назвать своим, иначе он сверяет два множества, собранные не из того
        # текста.
        criterion="в5 К5",
        name="нечитаемый .gitignore не называется диффом",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestTheCounterDiff"
               ".test_an_unreadable_gitignore_is_named_rather_than_narrowed_silently",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                "    if ignored.undecodable is not None:\n"
                "        findings.append(_undecodable(\n"
                '            ".gitignore", ignored.undecodable,\n'
                '            "множество записей коллекции собрано без него"))',
                "    if False:\n        pass",
            ),
        ),
    ),
    Mutation(
        # Вид, не назвавший ни одной папки, читается как пустая коллекция.
        # Разница та же, что и у вида, которого нет вовсе: перечислять нечем,
        # а ответ выглядит перечислением.
        criterion="в5 К5",
        name="вид без папок читается как пустая коллекция",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestTheCounterDiff"
               ".test_a_view_naming_no_folder_is_named_too",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                '    if not base.folders:\n        return refused("вид не назвал '
                'ни одной папки")',
                "    if False:\n        pass",
            ),
        ),
    ),
    Mutation(
        # Непрочитанная запись выпадает из ожидаемого молча. Стоит ли у неё
        # поле — неизвестно, и выкинуть её отсюда значит решить за неё: дифф
        # перестаёт видеть недостачу ровно там, где о записи не известно
        # ничего.
        criterion="в5 К5",
        name="непрочитанная запись выпадает из ожидаемого",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestTheCounterDiff"
               ".test_a_shortfall_carrying_a_token_of_the_closed_list_is_explained",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                "        except (UnicodeDecodeError, FrontmatterError):\n"
                "            expected.add(rel)\n            continue",
                "        except (UnicodeDecodeError, FrontmatterError):\n"
                "            continue",
            ),
        ),
    ),
    Mutation(
        # Нечитаемый вид читается с заменой байта. Папка `"\ufffd\ufffd"`
        # существует не больше, чем не прочитанный вид называет папок, — но
        # выглядит названной, и сверка идёт с пустым множеством вместо отказа.
        criterion="в5 К5",
        name="нечитаемый вид читается с заменой байта",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestTheCounterDiff"
               ".test_a_view_that_does_not_decode_is_not_read_as_an_empty_one",
        steps=(
            substitution(
                "scripts/maintain/backfill.py",
                "        base = parse_base(_read(base_path))",
                "        base = parse_base(base_path.read_text("
                'encoding="utf-8", errors="replace"))',
            ),
        ),
    ),
    Mutation(
        # Та же правка гейта, что и у мутации `периметр frontmatter снят у
        # записи`, — и это не дубль: там объявленный тест принадлежит гейту
        # frontmatter, здесь диффу счётчиков. Утверждения разные: гейт обязан
        # не читать игнорируемую запись, дифф обязан заметить строку таблицы,
        # написанную по пути, который записью не считается.
        criterion="в5 К5",
        name="периметр .gitignore снят с перечисления записей (дифф)",
        module="tests.test_backfill",
        expect="tests.test_backfill.TestTheCounterDiff"
               ".test_a_row_for_a_path_the_view_does_not_count_as_a_record_"
               "is_unexplained",
        steps=(
            block_replacement(
                "scripts/check_frontmatter.py",
                "_in_perimeter(rel,",
                "continue",
                "",
            ),
        ),
    ),

    # Инвариант 2 волны: второй прогон по тому же дереву не меняет ни байта.
    # Ни одному критерию выхода не принадлежит, метка поэтому не в форме
    # `вN КM`.
    Mutation(
        # Ключ нити снят. Отчёт продолжает дописываться, дерево грязнеет на
        # каждом ходе — а грязное дерево по решению §8 значит «здесь работал
        # человек». Проверку «содержимое не тронуто» такая правка проходит:
        # дописывание поверхность разрешает.
        criterion="в5 Д1",
        name="нить дописывается без ключа",
        module="tests.test_maintain_run",
        expect="tests.test_maintain_run.TestRun"
               ".test_open_threads_is_appended_idempotently",
        steps=(
            substitution(
                "scripts/maintain/run.py",
                "        mark = MARK % (cls, rel)\n"
                "        if mark in text:\n"
                "            continue\n"
                '        added.append("- %s %s: %s %s"\n'
                '                     % (cls, rel, "; ".join(sorted(details)), '
                "mark))\n",
                '        added.append("- %s %s: %s"\n'
                '                     % (cls, rel, "; ".join(sorted(details))))\n',
            ),
        ),
    ),

    # Инвариант `drain-inbox`: элемент покидает зону, содержимое остаётся в
    # истории. Четыре мутации, по одной на исход §6, и все четыре правят
    # **вход** — снимают крестик у одной строки плана, — а не продукт. Иначе и
    # нельзя: инвариант утверждает не поведение одной команды, а то, что
    # цепочка из четырёх разных исходов опустошает зону. Снятый крестик —
    # единственная правка, которая останавливает ровно один исход и не трогает
    # остальные три.
    #
    # Объявленный тест у всех четырёх один и тот же — сам инвариант. Это
    # намеренно: доказывается, что он читает дерево, а не отчёт команды, и
    # читает его для каждого из четырёх исходов по отдельности. Тест про
    # «свой» исход краснеет попутно и назван в документе покрытия.
    #
    # **Метка `в5 Д2`, а не имя зоны, и это не вкусовщина.** Первая редакция
    # подписывала эти четыре строки самой зоной; голое её имя оказалось в
    # файле шестым именем зоны, а шесть имён в одном файле пакета
    # `tests/test_zones.py` считает второй таблицей зон — набор покраснел на
    # `test_no_second_zone_table_in_package`. Тот же довод, что у
    # `_ZONES_AS_LITERALS` выше: оснастка, доказывающая критерий 5, не имеет
    # права его нарушать. Имена мутаций уцелели дефисом: в `drain-inbox`
    # признака голого имени нет.
    Mutation(
        criterion="в5 Д2",
        name="drain-inbox: не согласована строка «стало записью»",
        module="tests.test_drain_inbox",
        expect="tests.test_drain_inbox.TestFourOutcomesOnOneInbox"
               ".test_the_zone_holds_nothing_but_its_readme",
        steps=(
            substitution(
                "tests/test_drain_inbox.py",
                "    out.extend(_entry(True, source, target, why) "
                "for source, target, why in triage)",
                "    out.extend(_entry(source != RECORD, source, target, why)\n"
                "                for source, target, why in triage)",
            ),
        ),
    ),
    Mutation(
        criterion="в5 Д2",
        name="drain-inbox: не согласована строка «растворилось»",
        module="tests.test_drain_inbox",
        expect="tests.test_drain_inbox.TestFourOutcomesOnOneInbox"
               ".test_the_zone_holds_nothing_but_its_readme",
        steps=(
            substitution(
                "tests/test_drain_inbox.py",
                "    out.extend(_entry(True, source, target, why) "
                "for source, target, why in triage)",
                "    out.extend(_entry(source != DISSOLVED, source, target, why)\n"
                "                for source, target, why in triage)",
            ),
        ),
    ),
    Mutation(
        criterion="в5 Д2",
        name="drain-inbox: не согласована строка «это было сырьё»",
        module="tests.test_drain_inbox",
        expect="tests.test_drain_inbox.TestFourOutcomesOnOneInbox"
               ".test_the_zone_holds_nothing_but_its_readme",
        steps=(
            substitution(
                "tests/test_drain_inbox.py",
                "    out.extend(_entry(True, source, target, why) "
                "for source, target, why in triage)",
                "    out.extend(_entry(source != RAW, source, target, why)\n"
                "                for source, target, why in triage)",
            ),
        ),
    ),
    Mutation(
        criterion="в5 Д2",
        name="drain-inbox: не согласована строка «отвергнуто»",
        module="tests.test_drain_inbox",
        expect="tests.test_drain_inbox.TestFourOutcomesOnOneInbox"
               ".test_the_zone_holds_nothing_but_its_readme",
        steps=(
            substitution(
                "tests/test_drain_inbox.py",
                "    out.extend(_entry(True, source, target, why) "
                "for source, target, why in triage)",
                "    out.extend(_entry(source != REJECTED, source, target, why)\n"
                "                for source, target, why in triage)",
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
            print("[%02d] %-15s %-7s %-48s %s"
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
