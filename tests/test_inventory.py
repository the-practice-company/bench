"""Инвентарь чужого дерева: строка на каталог и ни одного имени файла."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import inventory
from tests.foreign import materialise
from tests.test_foreign_fixture import FILES

ROOT = Path(__file__).resolve().parent.parent

DIRS = (".", "archive", "archive/notion", "identity", "journal", "media",
        "notes", "pipeline", "projects", "vendor-lib")


def rows(text):
    """TSV в список словарей. Комментарий и заголовок отбрасываются."""
    lines = [l for l in text.split("\n") if l and not l.startswith("#")]
    header = lines[0].split("\t")
    return [dict(zip(header, l.split("\t"))) for l in lines[1:]]


class TestShape(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=True)
        self.text = inventory.render(self.root, today="2026-08-29")

    def test_one_line_per_directory_and_no_file_names(self):
        """Механизм «не втянуть дерево в контекст» проверяется буквально."""
        self.assertEqual([r["path"] for r in rows(self.text)], list(DIRS))
        names = [p.name for p in self.root.rglob("*")
                 if p.is_file() and ".git" not in p.parts]
        leaked = sorted({n for n in names if n in self.text})
        self.assertEqual(leaked, [])

    def test_the_directory_list_is_the_fixtures_own(self):
        """`DIRS` — литерал, и он обязан совпасть с составом фикстуры.

        Иначе это второй список тех же фактов, живущий своей жизнью: три
        разошедшиеся копии одной таблицы этому репозиторию уже стоили
        критерия выхода. Здесь копий две, и сверка стоит четыре строки.
        """
        expected = {"."}
        for name in FILES:
            parts = Path(name).parts[:-1]
            for depth in range(1, len(parts) + 1):
                expected.add("/".join(parts[:depth]))
        self.assertEqual(sorted(DIRS), sorted(expected))

    def test_the_header_carries_the_given_date_and_no_other(self):
        self.assertTrue(self.text.startswith("# scan-tree today=2026-08-29\n"))
        without = inventory.render(self.root)
        self.assertTrue(without.startswith("# scan-tree today=unset\n"))

    def test_the_columns_are_these_in_this_order(self):
        header = self.text.split("\n")[1]
        self.assertEqual(header.split("\t"), list(inventory.COLUMNS))
        self.assertEqual(
            list(inventory.COLUMNS),
            ["path", "files", "files_subtree", "bytes_subtree", "extensions",
             "frontmatter", "first_commit", "last_commit", "mark"])


class TestCells(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=True)
        self.rows = {r["path"]: r for r in rows(inventory.render(self.root))}

    def test_the_archive_is_inventoried(self):
        """§13 исключает архив из периметра гейта. Инвентарь — не гейт:
        не увидев архива, он не сможет положить его в план, а §18 обязывает."""
        self.assertEqual(self.rows["archive/notion"]["files"], "2")

    def test_a_journal_row_counts_its_own_files_and_extensions(self):
        row = self.rows["journal"]
        self.assertEqual((row["files"], row["files_subtree"]), ("2", "2"))
        self.assertEqual(row["extensions"], "md:2")

    def test_frontmatter_fields_are_counted_by_records(self):
        self.assertEqual(self.rows["journal"]["frontmatter"], "created:2,status:1")

    def test_a_directory_without_frontmatter_says_so(self):
        self.assertEqual(self.rows["pipeline"]["frontmatter"], "-")

    def test_extensions_sort_by_count_then_name(self):
        self.assertEqual(self.rows["pipeline"]["extensions"], "csv:1,json:1,py:1")

    def test_the_foreign_repository_is_marked_and_not_descended_into(self):
        """Четыре числа — прочерки, а не нули: внутрь не спускались, и ноль
        был бы неправдой про непрочитанное (незыблемое №4)."""
        row = self.rows["vendor-lib"]
        self.assertEqual(row["mark"], "foreign-repo")
        self.assertEqual([row["files"], row["files_subtree"],
                          row["bytes_subtree"], row["extensions"]],
                         ["-", "-", "-", "-"])

    def test_a_plain_directory_carries_no_mark(self):
        self.assertEqual(self.rows["journal"]["mark"], "-")

    def test_the_root_subtree_weight_is_the_sum_of_what_was_walked(self):
        """Число не вписывается литералом: оно обязано совпасть с деревом,
        а не с тем, что автор плана посчитал на бумаге."""
        walked = sum(p.stat().st_size for p in self.root.rglob("*")
                     if p.is_file() and ".git" not in p.parts
                     and "vendor-lib" not in p.parts)
        self.assertEqual(self.rows["."]["bytes_subtree"], str(walked))

    def test_without_git_both_date_columns_say_so(self):
        for row in self.rows.values():
            self.assertEqual((row["first_commit"], row["last_commit"]),
                             ("no-git", "no-git"), row["path"])


class TestUnreadableFrontmatter(unittest.TestCase):
    """Незыблемое №4 в колонке `frontmatter`.

    «Полей нет» и «полей не узнать» — разные факты. Первый честно даёт
    пустоту; второй, отданный той же пустотой, тихо утверждает за автора,
    что файл без frontmatter. Невосстановимое помечается синтетическим —
    полем `#unreadable`, которым настоящее поле стать не может: разбор
    frontmatter ключ с `#` в начале не принимает вовсе.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        weird = self.root / "weird"
        weird.mkdir()
        # Повторный ключ — отказ разбора, а не молчаливая победа последнего.
        (weird / "dup-key.md").write_text("---\na: 1\na: 2\n---\n",
                                          encoding="utf-8")
        # Выгрузка не в UTF-8: полей не узнать по той же причине.
        (weird / "cp1251.md").write_bytes(b"---\n\xff\xfe: 1\n---\n")
        (weird / "plain.md").write_text("---\nb: 1\n---\n", encoding="utf-8")
        self.rows = {r["path"]: r for r in rows(inventory.render(self.root))}

    def test_the_unreadable_records_are_counted_apart(self):
        self.assertEqual(self.rows["weird"]["frontmatter"],
                         "#unreadable:2,b:1")

    def test_a_file_genuinely_without_frontmatter_is_not_marked(self):
        """Контроль: помечается непрочитанное, а не отсутствующее."""
        (self.root / "weird" / "bare.md").write_text("просто текст\n",
                                                     encoding="utf-8")
        again = {r["path"]: r for r in rows(inventory.render(self.root))}
        self.assertEqual(again["weird"]["frontmatter"], "#unreadable:2,b:1")


class TestLongLists(unittest.TestCase):
    def test_a_long_list_is_cut_with_an_explicit_tail(self):
        """Списки обрезаются, строки каталогов — никогда. Хвост назван
        числом: молчаливое усечение прячет ровно то, ради чего смотрят."""
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp, git_root=False, nested=False)
            many = root / "many"
            many.mkdir()
            for i in range(1, 10):
                (many / ("file.e%d" % i)).write_text("x", encoding="utf-8")
            by_path = {r["path"]: r for r in rows(inventory.render(root))}
            self.assertEqual(
                by_path["many"]["extensions"],
                ",".join("e%d:1" % i for i in range(1, 9)) + ",+1")


class TestDates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_a_repository_without_commits_says_no_history(self):
        """Третий токен, а не второй: «репозитория нет» и «коммитов нет» —
        разные факты, и оба чинятся по-разному."""
        root = materialise(self.tmp.name, git_root=False, nested=False)
        subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
        by_path = {r["path"]: r for r in rows(inventory.render(root))}
        self.assertEqual(by_path["journal"]["first_commit"], "no-history")

    def test_committed_paths_carry_iso_dates(self):
        root = materialise(self.tmp.name, git_root=True, nested=False)
        by_path = {r["path"]: r for r in rows(inventory.render(root))}
        self.assertRegex(by_path["journal"]["first_commit"], r"\A\d{4}-\d{2}-\d{2}\Z")
        self.assertEqual(by_path["journal"]["first_commit"],
                         by_path["journal"]["last_commit"])

    def test_a_path_no_commit_touched_is_a_dash(self):
        """Четвёртый факт, и он не равен трём предыдущим: репозиторий есть,
        коммиты есть, а этой папки ни один не касался."""
        root = materialise(self.tmp.name, git_root=True, nested=False)
        (root / "fresh").mkdir()
        (root / "fresh" / "note.md").write_text("новое\n", encoding="utf-8")
        by_path = {r["path"]: r for r in rows(inventory.render(root))}
        self.assertEqual((by_path["fresh"]["first_commit"],
                          by_path["fresh"]["last_commit"]), ("-", "-"))


class TestIgnored(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)

    def test_gitignored_subtrees_do_not_appear(self):
        (self.root / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        (self.root / "node_modules" / "pkg").mkdir(parents=True)
        (self.root / "node_modules" / "pkg" / "a.js").write_text("x", encoding="utf-8")
        paths = [r["path"] for r in rows(inventory.render(self.root))]
        self.assertNotIn("node_modules", paths)

    def test_the_archive_is_not_taken_from_the_gate(self):
        """Обратная половина разделения периметров: `archive/` попадает в
        инвентарь именно потому, что тот зовёт разбор `.gitignore`, а не
        периметр гейта ссылок."""
        paths = [r["path"] for r in rows(inventory.render(self.root))]
        self.assertIn("archive", paths)
        self.assertIn("archive/notion", paths)


class TestReadOnly(unittest.TestCase):
    def test_the_command_changes_nothing(self):
        """Доказательство read-only — хеш дерева, тот же приём, что у гейтов."""
        with tempfile.TemporaryDirectory() as tmp:
            root = materialise(tmp, git_root=False, nested=True)
            before = _hash(root)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "adopt" / "inventory.py"),
                 str(root), "--today", "2026-08-29"],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(_hash(root), before)
            self.assertIn("# scan-tree today=2026-08-29", proc.stdout)


def _hash(root):
    import hashlib
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()
