"""MAINTAIN целиком: три слоя, само-проверка, откат, отдельный коммит."""

import contextlib
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.adopt import tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from scripts.maintain import run as maintain
from scripts.maintain import mechanical, structural
from tests.maintain_fixture import materialise

# Пути фикстуры, на которых стоят утверждения набора. Названы здесь, а не по
# месту: переименование образца обязано ронять набор целиком.
RECORD = "areas/work/journal/items/late-entry.md"
STAGED = "sources/2026-08-15-созвон.md"
UNTRACKED = "core/черновик.md"
THREADS = "OPEN-THREADS.md"


def digest(root):
    """Хеш дерева без `.git/`. Ходы git его меняют, включая коммит MAINTAIN."""
    h = hashlib.sha256()
    for path in sorted(p for p in Path(root).rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        h.update(rel.encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()


def subject(root):
    return tree.git(root, "log", "-1", "--format=%s").stdout.strip()


def committed(root):
    """Пути последнего коммита. `-z`: без него не-ASCII имя приезжает в
    C-кавычках, и утверждение «этого пути в коммите нет» проходит зелёным на
    коммите, где он есть."""
    return tree.git_zlines(root, "show", "--name-only", "-z", "--format=",
                           "HEAD")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)


class TestRun(Fixture):
    def test_it_commits_its_own_fixes_separately(self):
        """Иначе `SessionStart` следующей сессии прочитает их как работу
        человека, а `Stop` увидит незакоммиченное."""
        before = tree.head(self.root)
        report, code = maintain.run(self.root, today="2026-08-29")
        self.assertEqual(code, EXIT_OK, report)
        self.assertNotEqual(tree.head(self.root), before)
        self.assertIn("MAINTAIN", subject(self.root))
        self.assertEqual(
            sorted(committed(self.root)),
            [".claude/rules/areas.md", "CLAUDE.md", THREADS,
             "knowledge/README.md", "projects/stale/README.md",
             "projects/stale/items/.gitkeep", "projects/stale/views.base"])

    def test_the_commit_names_only_the_paths_maintain_wrote(self):
        """`git add -A` подобрал бы чужое незакоммиченное. Правило волны 2.

        Утверждений три, и разводят они разные ошибки.

        Заиндексированный файл в коммите ловит коммит из индекса: `git commit`
        без списка путей забирает **весь** индекс, включая то, что человек
        приготовил себе.

        Состояние индекса ловит `git add -A`, и только оно: коммит по путям
        чужого из индекса не возьмёт, поэтому по составу коммита `-A`
        неотличим от честного `add`. Измерено — посаженный `-A` состав
        коммита не менял. Меняет он другое: неотслеженный черновик человека
        оказывается заиндексированным, то есть плагин распорядился индексом,
        который ему не принадлежит.
        """
        (self.root / UNTRACKED).write_text("моё\n", encoding="utf-8")
        staged = self.root / STAGED
        staged.write_text(staged.read_text(encoding="utf-8") + "моё\n",
                          encoding="utf-8")
        tree.git(self.root, "add", "--", STAGED)

        maintain.run(self.root, today="2026-08-29")
        touched = committed(self.root)
        self.assertNotIn(UNTRACKED, touched)
        self.assertNotIn(STAGED, touched)
        self.assertIn("моё\n", staged.read_text(encoding="utf-8"))
        self.assertIn(
            "?? " + UNTRACKED,
            tree.git_zlines(self.root, "status", "--porcelain", "-z", "-uall"))

    def test_the_tree_is_clean_of_maintain_after_the_run(self):
        maintain.run(self.root, today="2026-08-29")
        self.assertEqual(sorted(mechanical.dirty(self.root)), [])

    def test_a_second_run_changes_not_one_byte(self):
        """Инвариант 2 волны. Отчёт, дописывающийся при каждом запуске, и
        починка, переставляющая ключи, проходят «содержимое не тронуто» и
        при этом делают дерево грязным на каждом ходе."""
        maintain.run(self.root, today="2026-08-29")
        before = digest(self.root)
        head = tree.head(self.root)
        report, code = maintain.run(self.root, today="2026-08-29")
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(digest(self.root), before)
        self.assertEqual(tree.head(self.root), head)

    def test_open_threads_is_appended_idempotently(self):
        """Дописанное утверждается, а не только совпадение двух прогонов:
        не дописывающий ничего второе утверждение проходит даром."""
        path = self.root / THREADS
        was = path.read_text(encoding="utf-8")
        maintain.run(self.root, today="2026-08-29")
        first = path.read_bytes()
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(was), "дописывание переписало старое")
        self.assertIn("<!-- maintain:declared-unused inbox -->", text)
        self.assertIn("<!-- maintain:map-tree-divergence vault -->", text)
        maintain.run(self.root, today="2026-08-29")
        self.assertEqual(path.read_bytes(), first)

    def test_the_report_has_three_sections(self):
        report, _ = maintain.run(self.root, today="2026-08-29")
        for title in ("Форма механически", "Форма содержательно", "Спрос"):
            self.assertIn(title, report)

    def test_the_report_carries_no_absolute_path(self):
        report, _ = maintain.run(self.root, today="2026-08-29")
        self.assertNotIn(str(self.root), report)
        self.assertNotIn(str(self.tmp.name), report)

    def test_its_own_commit_is_dated_by_today_and_not_by_the_clock(self):
        """Дата коммита — данные хода, а не показание часов.

        Иначе часы возвращаются в режим с чёрного хода: слой спроса читает
        дату **последнего коммита, затронувшего путь**, и после первого же
        прогона этим коммитом становится коммит самого MAINTAIN. Отчёт
        второго прогона начал бы зависеть от того, когда его гоняли, — ровно
        та поломка, из-за которой запрещён `st_mtime`.
        """
        maintain.run(self.root, today="2026-09-01")
        self.assertEqual(
            tree.git(self.root, "log", "-1", "--date=short",
                     "--format=%cd").stdout.strip(), "2026-09-01")
        self.assertEqual(
            tree.git(self.root, "log", "-1", "--date=short",
                     "--format=%ad").stdout.strip(), "2026-09-01")
        report, _ = maintain.run(self.root, today="2026-09-01")
        self.assertIn("зона knowledge: материала 0, последнее касание "
                      "2026-09-01, дней 0", report)

    def test_a_write_no_layer_reported_is_named_in_the_report(self):
        """Полное множество изменённых путей берётся из `git status`, а не из
        намерений модуля. Созданный файл `content_diff` не ловит — правил
        сравнения на появление файла нет, — и стоит эта проверка один вызов
        git.
        """
        honest = structural.run

        def extra(root):
            created, findings = honest(root)
            (Path(root) / "decisions" / "лишний.md").write_text(
                "мимо отчёта\n", encoding="utf-8")
            return created, findings

        with mock.patch.object(maintain.structural, "run", extra):
            report, code = maintain.run(self.root, today="2026-08-29")
        self.assertEqual(code, EXIT_OK, report)
        self.assertIn("незакоммиченное после прогона: decisions/лишний.md",
                      report)
        self.assertNotIn("decisions/лишний.md", committed(self.root))


    def test_a_rewritten_open_threads_is_not_forgiven_as_appending(self):
        """Поверхность разрешает этому файлу дописывание, а не перенабор.

        Гранулярность `append` снята вместе с дописыванием, которое её
        производит, и проверяется префиксом байтов. Прощай она файл целиком —
        прощала бы и переставленные местами нити, то есть правку уже
        записанного, о которой строка поверхности говорит «не изменяются».
        """
        honest = maintain._append_threads

        def rewrite(root, suggestions):
            added = honest(root, suggestions)
            path = Path(root) / THREADS
            path.write_text(
                "\n".join(sorted(path.read_text(encoding="utf-8").split("\n"))),
                encoding="utf-8")
            return added

        with mock.patch.object(maintain, "_append_threads", rewrite):
            report, code = maintain.run(self.root, today="2026-08-29")
        self.assertEqual(code, EXIT_VIOLATION, report)
        self.assertIn("OPEN-THREADS.md:1 content-modified", report)


class TestSelfCheck(Fixture):
    """Само-проверка в бою. Продукт не несёт ни одного крючка ради теста:
    портит содержимое подменённый слой, а не флаг в сигнатуре."""

    def sabotage(self, rel=RECORD):
        def layer(root):
            path = Path(root) / rel
            path.write_text(path.read_text(encoding="utf-8") + "\nдописано\n",
                            encoding="utf-8")
            return [rel], [], []
        return layer

    def test_a_run_that_touches_content_rolls_itself_back_and_refuses(self):
        """Тесты доказывают поведение на фикстуре, а режим работает без
        присмотра на репозитории, полном авторской работы. Проверка, которой
        там нет, там и не работает."""
        before = digest(self.root)
        head = tree.head(self.root)
        with mock.patch.object(maintain.mechanical, "run", self.sabotage()):
            report, code = maintain.run(self.root, today="2026-08-29")
        self.assertEqual(code, EXIT_VIOLATION, report)
        self.assertIn("content-modified", report)
        self.assertIn("откатил себя", report)
        self.assertEqual(digest(self.root), before)
        self.assertEqual(tree.head(self.root), head)

    def test_the_rollback_reaches_what_no_layer_reported(self):
        """Откат берёт пути из `git status`, а не из отчёта слоя. Слой,
        совравший о том, что он записал, — это и есть случай, ради которого
        само-проверка заведена: верить его списку значит откатывать не то.
        """
        def liar(root):
            path = Path(root) / RECORD
            path.write_text(path.read_text(encoding="utf-8") + "\nдописано\n",
                            encoding="utf-8")
            return [], [], []

        before = digest(self.root)
        with mock.patch.object(maintain.mechanical, "run", liar):
            report, code = maintain.run(self.root, today="2026-08-29")
        self.assertEqual(code, EXIT_VIOLATION, report)
        self.assertEqual(digest(self.root), before)

    def test_the_rollback_does_not_wipe_work_left_uncommitted_by_a_human(self):
        """Откат возвращает путь в `HEAD`, и на грязном пути это потеря
        несохранённой работы — то самое, ради чего MAINTAIN грязного пути и
        не трогает. Слой, тронувший его вопреки правилу, сам по себе не
        случается, и ровно поэтому собран здесь: цена ошибки тут не находка,
        а чужой текст.

        Обойдённое называется в отчёте. Молчание было бы худшим из двух
        исходов сразу: правка MAINTAIN осталась бы в файле, а прогон
        отчитался бы, что откатил себя целиком.
        """
        path = self.root / RECORD
        path.write_text(path.read_text(encoding="utf-8") + "черновик\n",
                        encoding="utf-8")
        with mock.patch.object(maintain.mechanical, "run", self.sabotage()):
            report, code = maintain.run(self.root, today="2026-08-29")
        self.assertEqual(code, EXIT_VIOLATION, report)
        self.assertIn("черновик\n", path.read_text(encoding="utf-8"))
        self.assertIn("не откачено, путь был грязным до прогона: %s" % RECORD,
                      report)


class TestTodayIsMandatory(Fixture):
    """У гейтов волны 1 `--today` необязателен; там его отсутствие меняет
    текст отчёта, здесь — удаляет папку."""

    def test_the_call_refuses_without_today(self):
        with self.assertRaises(TypeError):
            maintain.run(self.root)

    def test_the_command_refuses_without_today(self):
        with io.StringIO() as noise, contextlib.redirect_stderr(noise):
            with self.assertRaises(SystemExit):
                maintain.main([str(self.root)])
        self.assertTrue((self.root / "projects" / "stale").is_dir())

    def test_the_command_line_carries_the_run_through(self):
        with io.StringIO() as out, contextlib.redirect_stdout(out):
            code = maintain.main([str(self.root), "--today", "2026-08-29"])
            printed = out.getvalue()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("## Спрос", printed)
        self.assertIn("MAINTAIN", subject(self.root))


if __name__ == "__main__":
    unittest.main()
