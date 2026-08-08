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


def is_url(token):
    return token.startswith(URL_SCHEMES)


def is_path_token(token):
    token = token.strip()
    if not token or is_url(token):
        return False
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

    Абсолютный путь и `~` — выход всегда. Для `..` граница — вершина
    `base` (первый сегмент, обычно имя зоны): если после нормализации
    результат уходит из-под этого сегмента, ссылка покинула тот раздел
    репозитория, в котором лежит ссылающийся файл — даже если формально
    осталась где-то внутри репозитория целиком. Без `base` (файл сам в
    корне) граница — сам корень: любой уцелевший `..` и есть выход.
    URL не путь и потому не выходит никуда.
    """
    target = target.strip()
    if is_url(target) or target.startswith("#"):
        return False
    if target.startswith("/") or target.startswith("~"):
        return True
    normalised = normalise(target, base)
    if not base:
        return normalised == ".." or normalised.startswith("../")
    return normalised.split("/", 1)[0] != base.split("/", 1)[0]
