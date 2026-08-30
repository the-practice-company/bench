"""Разворачивание фикстуры MAINTAIN с пиннингом дат коммитов.

Даты — свойство истории, а не файловой системы. `st_mtime` переставляется
чекаутом, и порог в 30 дней, посчитанный по нему, зависел бы от того, когда
гоняли набор, — это буквально мутация, пережившая проверку волны 1. Пиннинг
через `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`; приём тот же, которым волна 2
собирает временный репозиторий подпроцессом, а волна 4 — чужое дерево
(`tests/foreign.py`).

**Порядок коммитов важнее их дат.** Последний коммит, затронувший путь, —
последний **в порядке исполнения**: `git log` идёт от `HEAD` по цепочке
родителей, и дата на этот обход не влияет никак. Поэтому коммита, ловящего
всё разом (`git add -A` в конце), здесь нет ни с какой датой: он стал бы
последним касанием для каждого пути, который подобрал, и ослепил бы слой
спроса ровно там, ради чего фикстура заведена. Забытый файл ловится не им,
а проверкой чистоты дерева в наборе.

В пакете лежат просто файлы — конечное состояние. Промежуточные состояния
(статус, который переехал между коммитами) собираются здесь подстановкой и
обязаны сойтись обратно: `test_the_materialised_tree_matches_the_package`.
"""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "maintain"
SCAFFOLD = ROOT / "scaffold"

# Документация фикстуры, а не её часть: разворачивание её удаляет.
DOC = "ЧТО-ПОСАЖЕНО.md"

# Файлы каркаса, которые в фикстуре правлены руками. Список закрыт: всё
# остальное обязано совпадать с `scaffold/` побайтово, иначе волна завела бы
# второе определение формы, сама того не заметив.
EDITED = (
    "CLAUDE.md",
    "areas/README.md",
    ".claude/rules/areas.md",
    ".gitignore",
)

# Файлы каркаса, которых в фикстуре нет. `knowledge/README.md` — посаженное
# наблюдение; `settings-fragment.json` рецепт не копирует, а сливает в
# `.claude/settings.json`, поэтому в развёрнутом репозитории его не бывает.
ABSENT = (
    "knowledge/README.md",
    ".claude/settings-fragment.json",
)

# Всё, чего в каркасе нет: посаженное плюс то, что дописал сам рецепт.
EXTRA = (
    DOC,
    ".claude/settings.json",
    "areas/hiring/README.md",
    "areas/work/README.md",
    "areas/work/journal/README.md",
    "areas/work/journal/items/2026-08-25.md",
    "areas/work/journal/items/late-entry.md",
    "areas/work/journal/views.base",
    "areas/work/reviews/README.md",
    "areas/work/reviews/drafts/.gitkeep",
    "areas/work/reviews/items/2026-06-10-q2.md",
    "areas/work/reviews/views.base",
    "core/people/README.md",
    "core/people/items/anna.md",
    "core/people/items/boris.md",
    "core/people/views.base",
    "projects/deals/README.md",
    "projects/deals/items/one.md",
    "projects/deals/items/two.md",
    "projects/deals/views.base",
    "projects/fresh/README.md",
    "projects/fresh/items/.gitkeep",
    "projects/fresh/views.base",
    "projects/stale/README.md",
    "projects/stale/items/.gitkeep",
    "projects/stale/views.base",
    "sources/2026-08-15-созвон.md",
    "sources/dump.bin",
    "vault/README.md",
)

# История: `(дата, сообщение, пути, подстановки)`. Порядок — порядок коммитов.
# Пути называются точно, а не поддеревом целиком: `areas/work` в коммите про
# обзоры забрал бы заодно и журнал, и журнальному коммиту трёх месяцев спустя
# нечего было бы фиксировать.
#
# Подстановка собирает состояние **до** правки: в пакете лежит конечное, и
# без неё вторая правка того же файла не отличалась бы от первой ничем.
HISTORY = (
    ("2026-05-01", "рецепт: каркас", (
        ".claude", ".gitignore", ".twinkle-repo-builder", "CLAUDE.md",
        "OPEN-THREADS.md", "areas/README.md", "core/README.md",
        "decisions/README.md", "inbox/README.md", "projects/README.md",
        "sources/README.md", "tmp/README.md",
    ), {}),
    ("2026-05-20", "vault: выгрузки из старого хранилища",
     ("vault",), {}),
    ("2026-06-10", "работа: направление и квартальные обзоры",
     ("areas/work/README.md", "areas/work/reviews"), {}),
    ("2026-06-20", "найм: направление заведено", ("areas/hiring",), {}),
    ("2026-07-01", "stale: коллекция заведена", ("projects/stale",), {}),
    ("2026-08-15", "созвон: расшифровка как пришла", ("sources",), {}),
    ("2026-08-18", "люди: реестр студии", ("core/people",),
     {"core/people/items/anna.md": ("status: alumni", "status: active")}),
    ("2026-08-20", "люди: Анна ушла", ("core/people/items/anna.md",),
     {"core/people/items/anna.md": ("status: active", "status: alumni")}),
    ("2026-08-25", "журнал: планёрка и запись задним числом",
     ("areas/work/journal",), {}),
    ("2026-08-27", "сделки: две записи", ("projects/deals",), {}),
    ("2026-08-28", "fresh: коллекция заведена", ("projects/fresh",), {}),
)

# Путь -> дата его **последнего** коммита. Не производная от `HISTORY`, а
# независимое утверждение о том, что скажет git: пути вложены друг в друга,
# и вывести одно из другого значило бы проверять словарь самим собой.
TOUCHED = {
    "CLAUDE.md": "2026-05-01",
    ".claude/rules/areas.md": "2026-05-01",
    "vault": "2026-05-20",
    "areas/work/reviews": "2026-06-10",
    "areas/hiring": "2026-06-20",
    "projects/stale": "2026-07-01",
    "sources": "2026-08-15",
    "core/people/items/boris.md": "2026-08-18",
    "core/people": "2026-08-20",
    "areas/work/journal": "2026-08-25",
    "areas/work": "2026-08-25",
    "projects/deals": "2026-08-27",
    "projects/fresh": "2026-08-28",
}


def _git(root, *args, date=None):
    env = dict(os.environ)
    if date is not None:
        stamp = "%sT12:00:00+00:00" % date
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
    return subprocess.run(["git", *args], cwd=str(root), env=env,
                          capture_output=True, text=True, check=True)


def _stage(root, edits):
    """Промежуточное состояние файла. Несовпавшая подстановка — отказ.

    `str.replace` на отсутствующей подстроке молчит и возвращает текст как
    есть: история собралась бы без правки, а коммит про переезд статуса
    остался бы пустым по содержанию и зелёным на вид.
    """
    for rel, (before, after) in edits.items():
        path = Path(root) / rel
        text = path.read_text(encoding="utf-8")
        if before not in text:
            raise ValueError("состояние не собрано: в %s нет %r" % (rel, before))
        path.write_text(text.replace(before, after), encoding="utf-8")


def materialise(base, name="maintain"):
    """Копия фикстуры в `base/name` с историей, где у каждого пути своя дата."""
    root = Path(base) / name
    shutil.copytree(FIXTURE, root)
    (root / DOC).unlink()
    _git(root, "init", "-q")
    # Личность коммиттера — в конфиг репозитория, а не в среду: глобальный
    # `user.email` на машине прогона может быть не настроен. Тот же довод,
    # что у `tests/foreign.py`.
    _git(root, "config", "user.email", "maintain@example.invalid")
    _git(root, "config", "user.name", "maintain")
    for date, message, paths, edits in HISTORY:
        _stage(root, edits)
        _git(root, "add", "-A", "--", *paths)
        _git(root, "commit", "-q", "-m", message, date=date)
    return root
