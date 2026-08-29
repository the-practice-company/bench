#!/usr/bin/env python3
"""Разворачивание каркаса рецепта в репозиторий.

Одна детерминированная операция, поэтому скрипт, а не шаг скилла: каркас
уезжает в каждый инстанс, и одинаковость инстансов проверяется сравнением
байтов, а не доверием к генератору. Потребителей у этой копии двое —
CREATE волны 3 и ADOPT волны 4, — и оба обязаны получить один и тот же
объект.

Ровно один файл каркаса не копируется: `settings-fragment.json` сливается
в `.claude/settings.json`. Копия поверх затёрла бы `enabledPlugins`, которым
включён сам плагин, и плагин выключил бы себя первым же действием.

Ещё два имени каркас делит с чужим деревом — `CLAUDE.md` и `.gitignore`. В
CREATE их там нет; в ADOPT они существуют до усыновления, значит подпадают
под инвариант волны 4, и меняет их не установка каркаса, а `merge` по
согласованной строке плана. Установка о них знает ровно одно: названные ей
занятые имена она не пишет и отказом на них не отвечает.

Отказ приходит до первой записи, а не посреди неё: половина каркаса в чужом
дереве хуже, чем ни одного файла, — её нечем отличить от работы автора.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import boundary
from scripts.adopt.plan import MERGE_MARKER
from scripts.findings import EXIT_OK, EXIT_VIOLATION

FRAGMENT = ".claude/settings-fragment.json"
SETTINGS = ".claude/settings.json"
SCAFFOLD = Path(__file__).resolve().parent.parent / "scaffold"

# Закрытое множество. Слияние — операция над формой; расширять её на
# содержимое чужого дерева плагин не вправе (незыблемое №1).
MERGEABLE = ("CLAUDE.md", ".gitignore")

# Синтаксис комментария у каждого из двух свой, и маркер обязан быть
# комментарием в обоих: голой строкой в `.gitignore` он становится шаблоном
# игнорирования, то есть слияние формы меняло бы поведение git.
_COMMENT = {"CLAUDE.md": "<!-- %s -->", ".gitignore": "# %s"}


class Refused(Exception):
    """Установка не состоялась, и причина названа.

    Отдельный класс, а не находка гейта: у находок закрытый список классов
    и таблица покрытия, а это не гейт, а отказ операции.
    """


def _extend(current, addition, where):
    """Список, дополненный без дублей. Значение другой формы — отказ.

    `list(current)` на строке рассыпает её посимвольно: `"**/knowledge/**"`
    превращается в пятнадцать элементов, и настройки автора портятся без
    единой строки об этом. Незыблемое №4 запрещает не только тихую
    подстановку, но и тихую подгонку чужого значения под ожидаемую форму:
    что делать с ключом, который автор написал иначе, решает автор.
    """
    if current is None:
        current = []
    if not isinstance(current, list):
        raise Refused("%s: в настройках лежит %s, а фрагмент дополняет список. "
                      "Чужое значение рецепт не переписывает"
                      % (where, type(current).__name__))
    out = list(current)
    for item in addition:
        if item not in out:
            out.append(item)
    return out


def merge_settings(existing, fragment):
    """Слияние без потерь: чужие ключи остаются, списки дополняются без дублей.

    Идемпотентно: повторное слияние того же фрагмента не меняет ничего —
    иначе обновление версии дописывало бы одно и то же правило каждый раз.

    Исходный объект не меняется: вызвавший держит ссылку на разобранные
    настройки, и правка на месте показала бы ему дописанное рецептом как
    прочитанное с диска.

    `existing` — уже разобранный объект настроек; проверку «верхний уровень
    объект» делает `install`, где известно имя файла.
    """
    merged = dict(existing)
    for key, value in fragment.items():
        if key == "permissions" and isinstance(value, dict):
            permissions = merged.get(key)
            if permissions is None:
                permissions = {}
            if not isinstance(permissions, dict):
                raise Refused("%s: в настройках лежит %s, а не объект. Чужое "
                              "значение рецепт не переписывает"
                              % (key, type(permissions).__name__))
            permissions = dict(permissions)
            for rule_key, rules in value.items():
                permissions[rule_key] = _extend(permissions.get(rule_key), rules,
                                                "%s.%s" % (key, rule_key))
            merged[key] = permissions
        elif isinstance(value, list):
            merged[key] = _extend(merged.get(key), value, key)
        else:
            merged[key] = value
    return merged


def _existing_settings(root):
    """Разобранные настройки инстанса, либо `{}`, если файла нет.

    Три исхода вместо двух: файла нет — сливать не с чем и это норма; файл
    есть и читается — сливаем; файл есть и настройками не читается — отказ.
    Третий случай не сводится ко второму: `dict([])` отдаёт пустой объект,
    то есть чужое содержимое подменяется каркасным молча.
    """
    path = root / SETTINGS
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise Refused("%s не разобран (%s): файл есть, значит его писали, "
                      "и затирать его нельзя" % (SETTINGS, error))
    if not isinstance(data, dict):
        raise Refused("%s не разобран (верхний уровень %s, а не объект): файл "
                      "есть, значит его писали, и затирать его нельзя"
                      % (SETTINGS, type(data).__name__))
    return data


def merge(root, rel, scaffold=SCAFFOLD):
    """Дописывает каркасную часть в существующий чужой файл.

    Файла нет — он создаётся целиком и маркера не несёт: создание не
    изменение, под инвариант волны 4 оно не подпадает и в плане строкой не
    нуждается. Файл есть — дописывается блок под маркером, и повторный вызов
    ничего не делает: состояние строки `merge` читается именно из маркера.

    Маркер ставится и тогда, когда дописывать нечего: без него состояние
    строки навсегда `pending`, то есть слияние повторяется на каждом запуске.

    Возвращает True, если каркасная часть дописана в чужой файл: создание
    целиком и повторный вызов — оба False, и оба ничего не дописали.
    """
    if rel not in MERGEABLE:
        raise ValueError("слиянию подлежат только %s" % ", ".join(MERGEABLE))
    root = Path(root)
    source = Path(scaffold) / rel
    target = root / rel
    if not target.exists():
        target.write_bytes(source.read_bytes())
        return False
    text = target.read_text(encoding="utf-8")
    if MERGE_MARKER in text:
        return False
    mark = _COMMENT[rel] % MERGE_MARKER
    if rel == ".gitignore":
        # Построчно и без комментариев каркаса: у автора здесь свои правила и
        # свои пояснения к ним, и дописывать к ним чужую прозу незачем.
        # Шаблон, который у автора уже есть, вторым вхождением не поедет.
        have = {line.strip() for line in text.split("\n")}
        missing = [line for line in source.read_text(encoding="utf-8").split("\n")
                   if line.strip() and not line.startswith("#")
                   and line.strip() not in have]
        block = "\n".join([mark] + missing)
    else:
        block = mark + "\n" + source.read_text(encoding="utf-8")
    target.write_text(text.rstrip("\n") + "\n\n" + block + "\n", encoding="utf-8")
    return True


def deferred(root, merging):
    """Пути каркаса, которые кладёт не он: план согласовал слить их строкой.

    Отложенным путь становится, только **существуя**: которого в чужом дереве
    нет, тот пишется целиком и сливать его потом не с чем. Названный, но
    отложенный молча путь не остаётся: `plan.coverage` требует строку на
    каждый путь дерева, и файл, отложенный без строки `merge`, приезжает
    автору находкой `uncovered-path`.
    """
    root = Path(root)
    return [rel for rel in merging if (root / rel).exists()]


def install(scaffold, root, merging=()):
    """Копирует каркас в `root`, сливает настройки. Возвращает список путей.

    Ничего не перезаписывает: существующий файл — это работа автора либо
    повторный запуск, и оба случая решаются человеком, а не молча. Занятые
    имена называются все разом: усыновление приходит в чужое дерево, где
    занято обычно не одно, и отказ по одному файлу за прогон превращает
    разбор в двадцать четыре прогона.

    `merging` — занятые имена, которые план усыновления согласовал слить
    строкой `merge`. Они не пишутся и отказа не вызывают; остальные занятые
    имена останавливают прогон, как и раньше. Без этого списка ADOPT не
    ставит каркас вовсе: `CLAUDE.md` и `.gitignore` в чужом дереве обычно
    уже есть, и коммит 1 — чисто аддитивный — не собирается ни при каких
    условиях. Множество закрыто тем же кортежем, что и само слияние.
    """
    unknown = [rel for rel in merging if rel not in MERGEABLE]
    if unknown:
        raise ValueError("слиянию подлежат только %s, а не %s"
                         % (", ".join(MERGEABLE), ", ".join(unknown)))
    scaffold = Path(scaffold)
    root = Path(root)
    postponed = set(deferred(root, merging))

    if not (root / ".git").exists():
        raise Refused("нет git: `git init` делается до первой записи, "
                      "иначе ничего из написанного не откатывается")

    sources = sorted(p for p in scaffold.rglob("*") if p.is_file())
    plan, escaping, occupied = [], [], []
    for source in sources:
        rel = source.relative_to(scaffold).as_posix()
        if rel == FRAGMENT:
            continue
        target = root / rel
        # Незыблемое №6, и спрошено оно у единственного места, которое на
        # этот вопрос отвечает. Своя проверка здесь была бы вторым
        # определением границы — см. tests/test_boundary.py.
        #
        # Вопрос не праздный: сами цели склеены из корня и наружу не смотрят,
        # но склейка ничего не знает о симлинке **внутри** корня, а усыновление
        # приходит в дерево, где симлинки ставил не плагин.
        if boundary.outside(target, root):
            escaping.append(rel)
        elif rel in postponed:
            continue
        elif target.exists():
            occupied.append(rel)
        else:
            plan.append((source, target, rel))

    if escaping:
        raise Refused("путь уходит за корень репозитория: %s"
                      % ", ".join(escaping))
    if occupied:
        raise Refused("файлы уже существуют, каркас не пишется поверх: %s"
                      % ", ".join(occupied))

    fragment = json.loads((scaffold / FRAGMENT).read_text(encoding="utf-8"))
    existing = _existing_settings(root)
    merged = merge_settings(existing, fragment)

    written = []
    for source, target, rel in plan:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        written.append(rel)

    settings_path = root / SETTINGS
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    written.append(SETTINGS)
    return sorted(written)


def main(argv=None):
    parser = argparse.ArgumentParser(description="install the recipe scaffold")
    parser.add_argument("root")
    parser.add_argument("--scaffold", default=str(SCAFFOLD))
    # `choices`, а не проверка внутри: закрытое множество здесь — дверь мимо
    # отказа по занятому имени, и закрыта она разбором аргументов, а не
    # дисциплиной вызывающего. Тот же приём, что у обязательного `--plan`
    # мутирующих команд ADOPT.
    parser.add_argument("--merging", action="append", default=[],
                        choices=MERGEABLE, metavar="ПУТЬ",
                        help="занятое имя, которое план согласовал слить "
                             "строкой `merge`: каркас его не пишет")
    args = parser.parse_args(argv)
    try:
        written = install(args.scaffold, args.root, args.merging)
    except Refused as error:
        print("каркас не развёрнут: %s" % error, file=sys.stderr)
        return EXIT_VIOLATION
    for rel in written:
        print(rel)
    # Не в stdout: коммит 1 собирается из напечатанных путей, и заметка среди
    # них стала бы путём, которого нет. Молчать тоже нельзя — незыблемое №4:
    # каркасного файла в дереве не появилось, и сказано об этом вслух.
    for rel in deferred(args.root, args.merging):
        print("отложено на слияние: %s" % rel, file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
