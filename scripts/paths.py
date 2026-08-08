"""Признак «токен — путь» и граница корня репозитория.

Секция 13: в backtick'ах лежит и путь, и имя команды. Без признака гейт
либо ругается на `grep`, либо молчит про `scripts/check_links.py`.
Признак синтаксический, потому что он нужен машине.
"""

import posixpath
import unicodedata

# Закрытый список, а не «есть точка»: 0.05 с и v1.2 файлами не являются.
PATH_EXTENSIONS = (".md", ".py", ".sh", ".json", ".base", ".yml", ".yaml", ".txt")

URL_SCHEMES = ("https:", "http:", "mailto:", "tel:")

# Голый маркер без содержимого: не путь, а сокращение в прозе.
_BARE_MARKERS = ("/", "~", "../")

# `:` и `?` — слэш-команды (`/baton:auto 1`) и API-роуты с параметрами
# (`/backlinks/:path`, `/bases/:name?view=`), не файловые пути.
_NON_PATH_CHARS = (":", "?")

# Метасимволы, по которым узнаётся `/regex/`, а не абсолютный путь.
_REGEX_META = set("^$*+()[]{}|\\")


def is_url(token):
    return token.startswith(URL_SCHEMES)


def is_path_token(token):
    token = token.strip()
    if not token or is_url(token):
        return False
    if any(ch.isspace() for ch in token):
        return False  # у путей в этом репозитории нет пробелов — а у команд есть
    if any(ch in token for ch in _NON_PATH_CHARS):
        return False
    if token in _BARE_MARKERS:
        return False
    if (token.startswith("/") and token.endswith("/") and len(token) > 1
            and any(ch in _REGEX_META for ch in token)):
        return False  # `/^[a-z]+$/` — регулярка, а не путь
    if token.startswith("/") or token.startswith("~"):
        return True
    if "/" in token:
        return True
    return token.endswith(PATH_EXTENSIONS)


def normalise(target, base=""):
    """Путь от корня репозитория, приведённый: NFC, POSIX, `..` схлопнуты.

    Возвращает строку, которая может начинаться с `..`, — это и есть сигнал
    выхода за корень.
    """
    target = unicodedata.normalize("NFC", str(target).replace("\\", "/"))
    if target.startswith("/") or target.startswith("~"):
        return target
    joined = posixpath.join(base, target) if base else target
    return posixpath.normpath(joined)


def escapes_root(target, base=""):
    """Выводит ли ссылка за корень репозитория.

    Абсолютный путь и `~` — выход всегда. Для `..` граница — сам корень
    репозитория, а не зона: `base` — путь ссылающегося файла, поэтому
    нормализация идёт от его каталога (`dirname(base)`), и уцелевший
    после неё `..` — это и есть сигнал выхода за корень (см. docstring
    `normalise`). Переход в соседнюю зону внутри репозитория выходом не
    считается — это отдельный класс находки (`link-to-transient` и
    т.п.), не `escapes-root`. URL не путь и потому не выходит никуда.
    """
    target = target.strip()
    if is_url(target) or target.startswith("#"):
        return False
    if target.startswith("/") or target.startswith("~"):
        return True
    normalised = normalise(target, posixpath.dirname(base) if base else base)
    return normalised == ".." or normalised.startswith("../")
