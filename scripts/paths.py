"""Признак «токен — путь» и граница корня репозитория.

Секция 13: в backtick'ах лежит и путь, и имя команды. Без признака гейт
либо ругается на `grep`, либо молчит про `scripts/check_links.py`.
Признак синтаксический, потому что он нужен машине.
"""

import posixpath
import re
import unicodedata

# Закрытый список, а не «есть точка»: 0.05 с и v1.2 файлами не являются.
PATH_EXTENSIONS = (".md", ".py", ".sh", ".json", ".base")

URL_SCHEMES = ("https:", "http:", "mailto:", "tel:")

# Класс символов `[...]` требует закрывающей скобки: одинокая `[` в имени
# файла классом не является, и превращать такое имя в шаблон значило бы
# перестать спрашивать о его существовании.
_GLOB_CLASS = re.compile(r"\[[^\]]*\]")

# Правило разрешений целиком: имя инструмента, скобка, аргумент, скобка.
# Форма «целиком» существенна — `scripts/move(1).py` остаётся именем файла.
_TOOL_RULE = re.compile(r"[A-Za-z][A-Za-z0-9_]*\((.*)\)\Z")


def is_url(token):
    return token.startswith(URL_SCHEMES)


def is_pattern(token):
    """Токен называет множество файлов, а не файл: внутри глоб-метасимвол.

    Первая строка таблицы секции 13. Спрашивать, существует ли
    `**/knowledge/**`, — ошибка категории, и до этого правила гейт
    спрашивал: каркас, предписанный спекой (`claudeMdExcludes` и
    `permissions.deny` — секция 4, `paths:` коллекций и видов — секция 9),
    не проходил гейт, предписанный той же спекой. На этом упиралась
    волна 3.

    Предикат отдельный, а не строка внутри `is_path_token`, намеренно.
    Отсеянный входным фильтром токен не проверяется вообще — и шаблон
    получил бы право уйти за корень репозитория, которого нет
    у конкретного пути. Глоб снимает ровно один вопрос: «есть ли такой
    файл». Границу корня он не снимает.
    """
    token = token.strip()
    return "*" in token or "?" in token or bool(_GLOB_CLASS.search(token))


def unwrap_tool(token):
    """Аргумент правила разрешений `Инструмент(...)`, иначе токен как есть.

    Второе разворачивание секции 13. `Edit(./knowledge/*/**)` в
    `.claude/settings*.json` — правило разрешений, а не путь: гейт видел
    в нём несуществующий файл с именем `Edit(...)`. Вынутый аргумент
    судится сам по себе и, будучи глобом, дальше идёт как шаблон.
    """
    match = _TOOL_RULE.fullmatch(token.strip())
    return match.group(1).strip() if match else token


def is_path_token(token):
    """Таблица «Что backtick-токен считается путём» дословно, плюс пробел.

    Порядок строк таблицы: есть `/` — путь; закрытое расширение — путь;
    ведущий `/` или `~` — путь и сразу ошибка; всё остальное — не путь.
    Первая строка таблицы — про глоб — здесь не живёт: она различает
    шаблон и конкретный путь среди уже отобранных токенов, а не отсеивает
    (см. `is_pattern`).
    Ни `:`, ни `?`, ни форма регулярки, ни голый маркер строкой таблицы
    не являются: ужатие DEC-0003 откатано, слэш-команды и маршруты API
    в backtick'ах гейт называет `escapes-root` — вопрос предъявлен автору,
    правится спека, а не признак (незыблемое №7).

    Единственное исключение — токен с пробелом: его обосновывает сама
    мотивировка спеки («Без признака гейт либо ругается на `grep`»),
    потому что `grep -rn "x" areas/` отличается от пути только пробелами.
    """
    token = token.strip()
    if not token or is_url(token):
        return False
    if any(ch.isspace() for ch in token):
        return False  # командная строка, а не путь: у путей здесь пробелов нет
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
