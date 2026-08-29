"""Чужая фикстура: восемь свойств §16, шесть в пакете и два собираемых.

Список, а не счёт. Пять задач волны 4 ниже по плану опираются на эту фикстуру
целиком: инвентарь считает её каталоги, `find-refs` — её ссылки, `revert`
доказывает побайтовое восстановление её содержимого. Свойство, тихо пропавшее
здесь, не роняет ничего — оно просто перестаёт проверяться там.

Восемь свойств и то, чем каждое здесь утверждается:

| свойство §16 | чем утверждено |
|---|---|
| нет git вообще | `test_the_package_carries_no_git_of_its_own` плюс `test_without_git_the_tree_has_no_repository` |
| папка с `.git` внутри | `test_the_nested_repository_is_assembled_here` |
| `archive/` с percent-encoding | `test_the_archive_carries_percent_encoding` |
| markdown-ссылки вместо wikilinks | `test_the_fixture_carries_both_link_spellings` |
| два файла с одним basename | `test_two_files_share_a_basename` |
| скрипт + вход + выход | состав `pipeline/` в `FILES` |
| бинарь рядом с текстом | `test_the_binary_is_not_decodable_as_text` |
| папка «core или areas — не скажешь» | состав `identity/` в `FILES` |

Два последних свойства держатся точным списком файлов и больше ничем: они про
раскладку, а не про содержимое, и `FILES` — единственное место, где их можно
утверждать, не пересказывая своими словами то, что задача 2 будет считать.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_links import extract_links
from tests.foreign import FOREIGN, NESTED, materialise

# Точный состав. Список, а не счёт: фикстура, потерявшая свойство, обязана
# уронить набор здесь, а не тихо ослабить пять задач ниже по плану.
FILES = (
    "README.md",
    "archive/notion/Page%20one.md",
    "archive/notion/index.md",
    "identity/how-we-work.md",
    "journal/2026-01-04.md",
    "journal/2026-01-05.md",
    "media/README.md",
    "media/clip.bin",
    "notes/meeting.md",
    "pipeline/build.py",
    "pipeline/input.csv",
    "pipeline/output.json",
    "projects/meeting.md",
    "state.md",
    "vendor-lib/README.md",
    "vendor-lib/lib.py",
)


class TestStoredFixture(unittest.TestCase):
    def test_the_package_carries_exactly_these_files(self):
        found = sorted(p.relative_to(FOREIGN).as_posix()
                       for p in FOREIGN.rglob("*") if p.is_file())
        self.assertEqual(found, sorted(FILES))

    def test_the_package_carries_no_git_of_its_own(self):
        """Свойство «нет git вообще» достигается отсутствием, а не файлом."""
        self.assertEqual([p.relative_to(FOREIGN).as_posix()
                          for p in FOREIGN.rglob(".git")], [])

    def test_the_binary_is_not_decodable_as_text(self):
        """«Бинарь рядом с текстом» — свойство, а не украшение: инвентарь
        обязан считать его байты, не пытаясь прочитать."""
        with self.assertRaises(UnicodeDecodeError):
            (FOREIGN / "media" / "clip.bin").read_text(encoding="utf-8")

    def test_two_files_share_a_basename(self):
        """Читается дерево, а не `FILES`.

        Версия, спрашивавшая про одноимённые файлы саму константу, была
        тавтологией: она утверждала, что список содержит две свои строки, и
        оставалась зелёной на любой правке фикстуры. Свойство §16 — про
        дерево, поэтому и спрашивается дерево.
        """
        found = sorted(p.relative_to(FOREIGN).as_posix()
                       for p in FOREIGN.rglob("*")
                       if p.is_file() and p.stem == "meeting")
        self.assertEqual(found, ["notes/meeting.md", "projects/meeting.md"])

    def test_the_archive_carries_percent_encoding(self):
        text = (FOREIGN / "archive" / "notion" / "index.md").read_text(encoding="utf-8")
        self.assertIn("(Page%20one.md)", text)

    def test_the_fixture_carries_both_link_spellings(self):
        """Все ссылки фикстуры поимённо, обоими написаниями.

        §16 требует «markdown-ссылок на локальные файлы вместо wikilinks», и
        wikilinks рядом с ними: `find-refs` и `rewrite-refs` (задачи 5 и 8)
        обязаны считать оба написания, а `md-link-to-file` — оставаться
        находкой §13 при любом переезде. Перевод фикстуры на одно написание
        не меняет ни состава файлов, ни их числа — и без этого списка не
        роняет ничего.

        Ссылки читаются `extract_links` из гейта: второго читателя ссылок в
        этом репозитории нет и заводить его волна 4 не будет.
        """
        found = []
        for path in FOREIGN.rglob("*.md"):
            rel = path.relative_to(FOREIGN).as_posix()
            for link in extract_links(path.read_text(encoding="utf-8")):
                found.append((rel, link.line, link.kind, link.target))
        self.assertEqual(sorted(found), [
            ("README.md", 5, "mdlink", "journal/2026-01-04.md"),
            ("README.md", 6, "wikilink", "meeting"),
            ("README.md", 8, "wikilink", "how-we-work"),
            ("README.md", 9, "mdlink", "archive/notion/index.md"),
            ("archive/notion/Page%20one.md", 3, "mdlink", "index.md"),
            ("archive/notion/index.md", 3, "mdlink", "Page%20one.md"),
            ("archive/notion/index.md", 4, "mdlink", "Page%20two.md"),
            ("journal/2026-01-04.md", 5, "wikilink", "meeting"),
        ])


class TestMaterialised(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_without_git_the_tree_has_no_repository(self):
        root = materialise(self.tmp.name, git_root=False, nested=False)
        self.assertFalse((root / ".git").exists())

    def test_the_nested_repository_is_assembled_here(self):
        """Свойство §16 «папка с `.git` внутри». В пакете оно невыразимо."""
        root = materialise(self.tmp.name, git_root=False, nested=True)
        self.assertTrue((root / NESTED / ".git").is_dir())
        self.assertFalse((root / ".git").exists())

    def test_with_git_the_root_has_a_commit_and_the_nested_one_is_excluded(self):
        """Вложенный репозиторий уходит в `.git/info/exclude` до коммита:
        иначе `git add -A` кладёт его gitlink'ом, и клон теряет содержимое.

        Спрашивается `ls-tree HEAD`, а не `ls-files`: последний читает индекс,
        который наполняет `git add`, и на фикстуре без коммита остался бы
        зелёным — то есть проверял бы не то, что заявлено именем.
        """
        root = materialise(self.tmp.name, git_root=True, nested=True)
        tracked = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"],
                                 cwd=str(root), capture_output=True, text=True,
                                 check=True)
        names = sorted(l for l in tracked.stdout.split("\n") if l)
        self.assertEqual(names, sorted(f for f in FILES
                                       if not f.startswith(NESTED + "/")))

    def test_the_copy_is_byte_for_byte(self):
        root = materialise(self.tmp.name, git_root=False, nested=False)
        for name in FILES:
            self.assertEqual((root / name).read_bytes(),
                             (FOREIGN / name).read_bytes(), name)
