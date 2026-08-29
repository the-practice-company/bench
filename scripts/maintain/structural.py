#!/usr/bin/env python3
"""Слой «форма содержательно»: чего гейт не видит.

Молча чинится ровно одно — отсутствующая папка зоны, и только потому, что
зон всегда восемь и они фиксированы §9. Всё остальное показывается:
«починка» была бы либо правкой фиксированной карты, либо переездом
содержимого, а ни то ни другое плагину не принадлежит.

Архетип показывается **числами, а не приводится**. Поведение записей
вычислимо из git, и это честная половина требования §19; вторая половина
отвергнута: §20 относит выбор архетипа к суждению автора, а тихая смена
`journal → pipeline` сделала бы `status` обязательным — то есть починка
формы произвела бы N новых ошибок гейта. Гейт, покрасневший от собственной
починки, — худший из исходов.

Порога в байтах у бинаря нет. Предикат — не «сверх порога», а
«игнорируется git и на него никто не сослался»: порог §7 управляет решением
автора о `.gitignore`, а MAINTAIN наблюдает следствие, а не причину.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import check_links, zones
from scripts.adopt import tree
from scripts.findings import Finding
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter
from scripts.maintain import surface

ROOT = Path(__file__).resolve().parent.parent.parent
SCAFFOLD = ROOT / "scaffold"


def _git_out(root, *args):
    """Вывод git или отказ. Пустая строка при ненулевом коде — заглушка.

    Каждый вопрос этого слоя к git — вопрос о существовании находки: сколько
    коммитов тронуло запись, что игнорируется. Отказ git, прочитанный как
    пустой ответ, означает «ничего не нашлось», то есть зелёный прогон, не
    проверивший ничего (незыблемое №4). Тот же приём, что у `dirty` слоя
    «форма механически».
    """
    proc = tree.git(root, *args)
    if proc.returncode != 0:
        raise RuntimeError("git %s не отработал в %s: %s"
                           % (args[0], root, proc.stderr.strip()))
    return proc.stdout


def _commits(root, *args):
    """SHA'и `git log --format=%H`. Кавычек здесь не бывает: вывод — хеши."""
    return _git_out(root, "log", "--format=%H", *args).split()


def _directions(root):
    base = root / "areas"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


# Направление названо в README зоны так, как его пишут: путём от корня.
# Ужатых форм здесь две отвергнутых, обе измерены на фикстуре: wikilink
# `[[areas/...]]` в перечислении не встречается вовсе, а backtick-токен из
# одних словесных знаков не совпадает с `areas/work/` — в нём косая. Признак,
# не увидевший ни одной строки перечисления, красит все направления подряд,
# и посаженное наблюдение (`areas/hiring`) при этом остаётся на месте: тест
# такого признака не отличит, пока не утверждает список целиком.
_DIRECTION = re.compile(r"areas/([\w-]+)")


def _listed_directions(root):
    readme = root / "areas" / "README.md"
    if not readme.exists():
        return set()
    return set(_DIRECTION.findall(readme.read_text(encoding="utf-8")))


def _archetype_behaviour(root, collection):
    """Числа о поведении записей: правок после первого коммита и смен status.

    Вычислимо из git, поэтому показывается. Приведение архетипа к поведению
    отвергнуто: §20 относит выбор архетипа к суждению, а смена архетипа
    делает `status` обязательным — то есть тихая починка формы производит
    N новых ошибок гейта.
    """
    edits = statuses = 0
    items = root / collection / "items"
    for path in sorted(items.glob("*.md")) if items.is_dir() else []:
        rel = path.relative_to(root).as_posix()
        if len(_commits(root, "--", rel)) > 1:
            edits += 1
        # `-G`, а не `-S`: `-S` ищет изменение **числа** вхождений строки, и
        # смена `status: open` на `status: decided` для него не изменение
        # вовсе — вхождение как было одно, так и осталось. Измерено: на
        # такой правке `-S` возвращает один коммит, `-G` — два.
        if len(_commits(root, "-G", "^status:", "--", rel)) > 1:
            statuses += 1
    return edits, statuses


def _collections(root):
    """(путь коллекции, объявленный архетип) по всему дереву.

    Коллекцией зовётся папка, где README объявляет архетип и рядом лежит
    `views.base`: второго определения формы коллекции волна не заводит.
    """
    out = []
    for readme in sorted(root.rglob("README.md")):
        if not (readme.parent / "views.base").exists():
            continue
        try:
            fields = parse_frontmatter(readme.read_text(encoding="utf-8"))
        except (FrontmatterError, UnicodeDecodeError):
            continue
        if fields.get("archetype"):
            out.append((readme.parent.relative_to(root).as_posix(),
                        fields["archetype"]))
    return out


def _create_missing_zones(root):
    """Папка зоны и её README из каркаса. Единственная молчаливая починка.

    README пишется не потому, что так решено здесь, а потому, что строка
    поверхности `*/README.md#absent` это разрешает, — и спрошена она
    исполняемо. Убери её из `surface` — и починка перестанет происходить,
    а не разойдётся с доказательством молча (тот же приём, что у
    `mechanical._whole_files`).
    """
    created = []
    for zone in zones.ZONES:
        target = root / zone
        if not target.is_dir():
            target.mkdir(parents=True)
            created.append(zone)
        rel = "%s/README.md" % zone
        reference = SCAFFOLD / rel
        if (target / "README.md").exists() or not reference.exists():
            continue
        if not surface.covers(rel, "create"):
            continue
        (target / "README.md").write_bytes(reference.read_bytes())
        created.append(rel)
    return created


def _ignored_files(root):
    """Игнорируемые файлы поимённо.

    Источник — `ls-files`, а не `status --ignored`: последний схлопывает в
    одну строку каталог, где игнорируется **всё** содержимое, и файл внутри
    него исчезает из отчёта целиком. Измерено на живом git: `tmp/dumps/` с
    одним игнорируемым файлом внутри приходит строкой `!! tmp/dumps/`, и
    `--ignored=matching` схлопывает его так же.

    Условие «всё содержимое» существенно: `sources/` этой фикстуры держит
    отслеженные файлы, поэтому не схлопывается, и на нём оба источника
    отвечают одинаково. Разводит их только собранный случай —
    `TestTheSourceOfTheIgnoredList`; без него подмена источника прошла бы
    зелёным прогоном.

    `-z` обязателен: без него git отдаёт не-ASCII имя в C-кавычках, и
    `sources/дубль.bin` вернулся бы строкой, которой в дереве нет, — то
    есть наблюдение потерялось бы молча. Правило пакета про пути из git
    записано в `scripts/adopt/tree.py`.

    Строка с косой на конце — вложенный репозиторий: git в него не
    спускается. Это `foreign-repo` волны 4, не бинарь и не забота этого
    слоя.
    """
    out = _git_out(root, "ls-files", "--others", "--ignored",
                   "--exclude-standard", "-z")
    return [rel for rel in out.split("\0") if rel and not rel.endswith("/")]


def run(root):
    """(созданные пути, находки)."""
    root = Path(root)
    created = _create_missing_zones(root)
    findings = []

    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if entry.name in zones.ZONES:
            continue
        findings.append(Finding("map-tree-divergence", entry.name, 1,
                                "папка верхнего уровня, которой нет в карте зон"))

    listed = _listed_directions(root)
    for direction in _directions(root):
        if direction in listed:
            continue
        findings.append(Finding("map-tree-divergence", "areas/%s" % direction, 1,
                                "направление без строки в areas/README.md"))

    for collection, archetype in _collections(root):
        edits, statuses = _archetype_behaviour(root, collection)
        if archetype == "registry" and statuses:
            findings.append(Finding(
                "archetype-mismatch", collection, 1,
                "объявлен registry, записей со сменой status: %d "
                "(правок после первого коммита: %d)" % (statuses, edits)))
        elif archetype == "journal" and edits:
            findings.append(Finding(
                "archetype-mismatch", collection, 1,
                "объявлен journal, записей с правкой после первого "
                "коммита: %d (смен status: %d)" % (edits, statuses)))

    referenced = set()
    occs, _ = check_links.occurrences(root)
    for hit in occs:
        referenced.update(hit.candidates)
    for rel in _ignored_files(root):
        if rel in referenced or not (root / rel).is_file():
            continue
        findings.append(Finding("unreferenced-ignored-binary", rel, 1,
                                "файл вне git, на него никто не сослался"))

    return sorted(created), findings
