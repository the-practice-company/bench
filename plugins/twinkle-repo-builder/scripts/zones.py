"""Единственное определение зон рецепта.

Волны 2 и 3 импортируют отсюда и не заводят своих копий: тест
tests/test_zones.py::TestSingleDefinition падает, если копия появилась.
Секция 1 спеки — источник значений.
"""

from pathlib import PurePosixPath

# Семантическая ось: про что оно.
SEMANTIC = ("core", "areas", "projects", "knowledge")
# Конвейерная ось: в каком состоянии обработки оно находится.
PIPELINE = ("inbox", "sources", "tmp", "decisions")
ZONES = SEMANTIC + PIPELINE

# Содержимое исчезает по построению, поэтому ссылка сюда из долгоживущей
# зоны — отложенная поломка, а не риск (класс link-to-transient).
TRANSIENT = frozenset({"tmp", "inbox"})
LONG_LIVED = frozenset(SEMANTIC)

# Только добавление: правка существующего — предупреждение или блок (секция 15).
ADD_ONLY = frozenset({"inbox", "sources", "decisions"})
# Чужие git-сабмодули: не пишем вообще.
READ_ONLY = frozenset({"knowledge"})

# Зоны, в которых лежат материалы собственной разработки этого репозитория.
# Он удваивается под контекст-репозиторий своей же разработки: в `inbox/` и
# `sources/` лежат чужие цитаты и черновики исследования, а не содержимое
# пакета. Абсолютный путь внутри них — свойство цитаты, а не находка о
# пакете, поэтому проверка пакета туда не заходит (`check_package.SKIP_AT_ROOT`
# читает имена отсюда). Имя — про смысл: две зоны, где живёт разработка, а не
# «две зоны, которые пропускает такая-то проверка».
SELF_DEVELOPMENT = frozenset({"inbox", "sources"})

# Статически закрывается в settings.json целевого репозитория.
DENY_PATTERNS = ("knowledge/*/**",)


def zone_of(path):
    """Зона, которой принадлежит путь, или None.

    Смотрит только на первый сегмент: зоны живут в корне и нигде больше.
    """
    parts = PurePosixPath(str(path).replace("\\", "/")).parts
    if not parts:
        return None
    return parts[0] if parts[0] in ZONES else None
