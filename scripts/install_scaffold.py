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

Отказ приходит до первой записи, а не посреди неё: половина каркаса в чужом
дереве хуже, чем ни одного файла, — её нечем отличить от работы автора.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import boundary
from scripts.findings import EXIT_OK, EXIT_VIOLATION

FRAGMENT = ".claude/settings-fragment.json"
SETTINGS = ".claude/settings.json"


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


def install(scaffold, root):
    """Копирует каркас в `root`, сливает настройки. Возвращает список путей.

    Ничего не перезаписывает: существующий файл — это работа автора либо
    повторный запуск, и оба случая решаются человеком, а не молча. Занятые
    имена называются все разом: усыновление приходит в чужое дерево, где
    занято обычно не одно, и отказ по одному файлу за прогон превращает
    разбор в двадцать четыре прогона.
    """
    scaffold = Path(scaffold)
    root = Path(root)

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
    parser.add_argument("--scaffold",
                        default=str(Path(__file__).resolve().parent.parent
                                    / "scaffold"))
    args = parser.parse_args(argv)
    try:
        for rel in install(args.scaffold, args.root):
            print(rel)
    except Refused as error:
        print("каркас не развёрнут: %s" % error, file=sys.stderr)
        return EXIT_VIOLATION
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
