"""`find-refs`: кто ссылается на путь. Резолвер — тот же, что у гейта.

Номера строк ниже сняты с файлов `fixtures/foreign/`, а не из плана волны:
план ставил markdown-ссылку на `journal/2026-01-04.md` в строку 6, а стоит
она в строке 5 — в шестой лежит `[[meeting]]`.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_links
from scripts.adopt import refs
from scripts.findings import EXIT_OK
from tests.foreign import materialise

ROOT = Path(__file__).resolve().parent.parent


class TestSingleResolver(unittest.TestCase):
    def test_refs_does_not_own_a_resolver(self):
        """Тот же приём, что у `tests/test_zones.py::TestSingleDefinition`:
        второй резолвер ловится тождеством, а не обещанием в докстроке."""
        self.assertIs(refs.occurrences, check_links.occurrences)


class TestFind(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)

    def test_it_finds_a_markdown_link_by_its_resolved_target(self):
        hits, unreadable = refs.find(self.root, "journal/2026-01-04.md")
        self.assertEqual(unreadable, [])
        self.assertEqual([(h.path, h.line, h.kind) for h in hits],
                         [("README.md", 5, "mdlink")])

    def test_a_directory_argument_matches_everything_under_it(self):
        """Переезжает каталог — искать надо ссылки на каждый файл в нём."""
        hits, _ = refs.find(self.root, "journal")
        self.assertEqual([(h.path, h.kind) for h in hits],
                         [("README.md", "mdlink")])

    def test_an_ambiguous_basename_is_found_from_both_files(self):
        hits, _ = refs.find(self.root, "notes/meeting.md")
        self.assertEqual(
            [(h.path, h.line, h.kind, h.raw) for h in hits],
            [("README.md", 6, "wikilink", "[[meeting]]"),
             ("journal/2026-01-04.md", 5, "wikilink", "[[meeting]]")])

    def test_the_archive_is_not_scanned_but_a_link_into_it_is_found(self):
        """Две половины исключения §13, и путать их нельзя.

        Архив гейт **не читает**: ссылка изнутри `archive/notion/index.md`
        вхождением не является и после переезда её цели никем не чинится.
        Ссылка **в** архив — обычное вхождение обычного файла: `archive/`
        по §18 из дерева уезжает, и молчать про такую ссылку значило бы
        показать автору ноль там, где переезд ломает ссылку.
        """
        into, _ = refs.find(self.root, "archive/notion/index.md")
        self.assertEqual([(h.path, h.line, h.kind) for h in into],
                         [("README.md", 9, "mdlink")])
        inside, _ = refs.find(self.root, "archive/notion/Page%20one.md")
        self.assertEqual(inside, [])


class TestRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)

    def test_the_header_shows_the_markdown_count_separately(self):
        """Число, которое инвариант R не видит, показывается автору явно:
        `rewrite-refs` эти ссылки не трогает, и переезд их сломает."""
        text = refs.render(self.root, "journal")
        self.assertEqual(
            text.split("\n")[0],
            "# find-refs journal: вхождений 1, из них markdown-ссылок 1")
        self.assertEqual(text.split("\n")[1], "file\tline\tkind\traw")

    def test_an_unread_file_is_named_not_swallowed(self):
        """Чужое дерево — ровно то место, где недекодируемые файлы живут.

        Их ссылки не прочитаны, и «вхождений 2» про такое дерево — половина
        правды: незыблемое №4 запрещает подставлять невосстановимое молча.
        Гейт про такой файл говорит `undecodable`; `find-refs` гейтом не
        является и говорит своими словами, но говорит.
        """
        # Кириллица обязательна: ASCII в cp1251 остаётся ASCII, и такой
        # файл прочитался бы как UTF-8, дав третье вхождение вместо отказа.
        (self.root / "notes" / "старое.md").write_bytes(
            "Старая заметка про [[meeting]]\n".encode("cp1251"))
        text = refs.render(self.root, "notes/meeting.md")
        self.assertEqual(
            text.split("\n")[0],
            "# find-refs notes/meeting.md: вхождений 2, из них markdown-ссылок 0")
        self.assertEqual(
            text.split("\n")[-2],
            "# не прочитан: notes/старое.md — ссылки в нём не проверены")


class TestReadOnly(unittest.TestCase):
    def test_the_command_changes_nothing(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp, git_root=False, nested=False)
            def digest():
                h = hashlib.sha256()
                for path in sorted(p for p in root.rglob("*") if p.is_file()):
                    h.update(path.relative_to(root).as_posix().encode("utf-8"))
                    h.update(path.read_bytes())
                return h.hexdigest()
            before = digest()
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "adopt" / "refs.py"),
                 str(root), "journal"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
            self.assertEqual(digest(), before)
