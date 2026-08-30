#!/usr/bin/env python3
"""Версия рецепта: манифест пакета и маркер инстанса.

Секция 21, «Версия одна»: `plugin.json` → `.twinkle-repo-builder`. Отдельных
версий схемы, манифеста и правил нет. Секция 21, «Обновление ленивое»: плагин
приезжает из маркетплейса на машину, а в репозиторий — при следующей сессии
в нём, и расхождение версий есть **событие**, о котором говорят вслух.

Пока этого модуля не было, связь между двумя числами держал один тест
репозитория плагина: он утверждал, что каркас несёт версию манифеста. Это
утверждение о дереве разработчика. В отгруженном пакете манифест не читал
никто, и инстанс, отставший на релиз, не отличался от свежего ничем.

**Порядок версий не выдумывается.** Строку, которая не является точечной
записью целых чисел, сравнивать нечем: `2026-08-30` старше `0.1.0` или младше
— вопрос без ответа, и ответ на него был бы молчаливой заглушкой (незыблемое
№4). Такое расхождение называется расхождением, а порядок — нет.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import boundary

ROOT = Path(__file__).resolve().parent.parent
# Единственное место в пакете, где написан путь к манифесту. До этого он
# стоял литералом в двух наборах тестов и ни в одной строке продукта.
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
# Имя маркера инстанса — из `boundary`, а не своей строкой. Второй литерал
# того же имени разошёлся бы молча: корень репозитория ищут по одному
# написанию, версию читают по другому, и в день переименования маркера
# сверка версий начала бы читать несуществующий файл, а корень находиться.
MARKER = boundary.MARKER

# Точечная запись целых чисел — единственная форма, у которой порядок
# вычислим. Всё остальное сравнивается на равенство и не более того.
_NUMERIC = re.compile(r"\d+(?:\.\d+)*\Z")


class Unreadable(Exception):
    """Версия невосстановима, и причина названа.

    Отдельный тип, а не `None`: `None` пришлось бы отличать от «версии
    совпали», а спутать эти два состояния — объявить необновлённый инстанс
    обновлённым. Незыблемое №4 запрещает подставлять сюда что бы то ни было,
    поэтому наружу уезжает причина, а не значение.
    """


def _version_of(path, what):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise Unreadable("%s не прочитан: %s" % (what, error))
    except UnicodeDecodeError as error:
        raise Unreadable("%s не декодируется: %s" % (what, error))
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise Unreadable("%s не разобран: %s" % (what, error))
    if not isinstance(data, dict) or "version" not in data:
        raise Unreadable("в %s нет поля version" % what)
    value = data["version"]
    # Число вместо строки — не версия: сравнение с ним зелено по построению,
    # а `str(1)` был бы догадкой о написании, которого автор не писал.
    if not isinstance(value, str) or not value.strip():
        raise Unreadable("в %s поле version не строка или пусто" % what)
    return value.strip()


def plugin_version():
    """Версия пакета. `Unreadable`, если манифест не прочитан."""
    return _version_of(MANIFEST, "манифест плагина")


def instance_version(root):
    """Версия рецепта в дереве. `Unreadable`, если маркер не прочитан."""
    return _version_of(Path(root) / MARKER, "маркер рецепта")


def _parts(version):
    """Кортеж целых, если версия точечная, иначе `None`."""
    if not _NUMERIC.match(version):
        return None
    return tuple(int(part) for part in version.split("."))


def _order(instance, plugin):
    """Как эти две версии соотносятся, словами.

    Хвостовые нули добиваются, потому что `(1,)` и `(1, 0, 0)` — одна версия,
    записанная по-разному, а кортежное сравнение объявило бы первую младше.
    Совпавший номер при разошедшейся строке остаётся расхождением: маркер
    обязан нести версию манифеста, а не эквивалентную ей.
    """
    left, right = _parts(instance), _parts(plugin)
    if left is None or right is None:
        return "порядок не установлен"
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    if left < right:
        return "дерево старше пакета, это событие обновления"
    if left > right:
        return "инстанс новее плагина, чинить нечего"
    return "номер тот же, версии написаны по-разному"


def divergence(root):
    """Одна строка расхождения версий либо `None`, когда расхождения нет.

    Сообщение, а не блок (§21). Невосстановимое называется, а не молчит:
    §22 требует того же от битого маркера — файл есть, значит мы внутри
    контекстного репозитория, и обновление версии не запускается, потому
    что сравнивать не с чем.
    """
    try:
        plugin = plugin_version()
    except Unreadable as error:
        return "версия рецепта не сверена: %s: сравнивать не с чем" % error
    try:
        instance = instance_version(root)
    except Unreadable as error:
        return "версия рецепта не сверена: %s: сравнивать не с чем" % error
    if instance == plugin:
        return None
    return ("версии разошлись: в дереве %s, в пакете %s — %s"
            % (instance, plugin, _order(instance, plugin)))
