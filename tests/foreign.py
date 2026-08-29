"""Разворачивание чужой фикстуры во временном каталоге.

Два свойства §16 в пакете не хранятся и собираются здесь:

* **нет git вообще** — достигается тем, что в `fixtures/foreign/` нет `.git`;
* **вложенный чужой репозиторий** — внутри своего репозитория он был бы
  сабмодулем, то есть указателем на объект, которого здесь нет.

Приём тот же, которым волна 2 собирает временный репозиторий через
`subprocess`; ни одного нового механизма.
"""

import os
import shutil
import subprocess
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
FOREIGN = ROOT / "fixtures" / "foreign"

# Каталог, который в развёрнутой фикстуре становится чужим репозиторием.
NESTED = "vendor-lib"

_EXCLUDE_HEADER = "# вложенные репозитории, исключены ADOPT"

# Личность коммиттера для тех тестов, где репозиторий заводит не фикстура,
# а `init-tree`: настроить его конфиг до себя самого некому, а глобальный
# `user.email` в среде прогона может быть не настроен — тот же довод, что у
# `tests/test_hook_events.commit_all`. Переменные среды старше конфига,
# поэтому тест на отказ без личности снимает их сам, `no_committer`.
COMMITTER = {
    "GIT_AUTHOR_NAME": "adopt",
    "GIT_AUTHOR_EMAIL": "adopt@example.invalid",
    "GIT_COMMITTER_NAME": "adopt",
    "GIT_COMMITTER_EMAIL": "adopt@example.invalid",
}


def committer(case):
    """Личность коммиттера в среде на время одного теста."""
    patcher = mock.patch.dict(os.environ, COMMITTER)
    patcher.start()
    case.addCleanup(patcher.stop)


def no_committer(case):
    """Ни личности в среде, ни следа от неё после теста."""
    patcher = mock.patch.dict(os.environ)
    patcher.start()
    case.addCleanup(patcher.stop)
    for name in COMMITTER:
        os.environ.pop(name, None)


def git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root),
                          capture_output=True, text=True, check=True)


def _identity(root, who):
    git(root, "config", "user.email", "%s@example.invalid" % who)
    git(root, "config", "user.name", who)


def materialise(base, name="foreign", git_root=False, nested=True):
    """Копия фикстуры в `base/name`.

    `git_root` — завести ли git в корне и сделать коммит «как было».
    `nested` — собрать ли вложенный чужой репозиторий.

    Имя параметра — `git_root`, а не `git`: модульная функция `git` уже
    занята, и совпадение имён внутри этой функции затенило бы её.
    """
    root = Path(base) / name
    shutil.copytree(FOREIGN, root)
    if nested:
        git(root / NESTED, "init", "-q")
        _identity(root / NESTED, "vendor")
        git(root / NESTED, "add", "-A")
        git(root / NESTED, "commit", "-q", "-m", "vendor")
    if git_root:
        git(root, "init", "-q")
        _identity(root, "adopt")
        exclude = root / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        if nested:
            exclude.write_text("%s\n%s/\n" % (_EXCLUDE_HEADER, NESTED),
                               encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "как было")
    return root
