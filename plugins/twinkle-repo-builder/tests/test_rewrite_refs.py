"""Критерий 2: число резолвящихся ссылок не меняется ни на одном шаге.

Путевой формы wikilink'а в чужой фикстуре нет ни одной — все её ссылки
голые, а голая ссылка переезда каталога не замечает по построению. Поэтому
тесты сажают путевую форму сами: без неё оба фальсификатора критерия 2
зелены не потому, что правка работает, а потому, что ломать нечего.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_links
from scripts.adopt import init_tree, move, refs, rewrite_refs, tree
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from scripts.maintain import field_map
from tests.foreign import committer, materialise
from tests.test_read_plan import TOTAL, write_plan

ROOT = Path(__file__).resolve().parent.parent

SHORTFALL = "ссылка ожидалась в таблице и её там нет, объяснения тоже"
AGREED = "notes -> areas/work/notes"


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)

# TOTAL не переименовывает ни одного файла, а голая форма ссылки правится
# только переименованием: переезд каталога basename не меняет, и ветка
# голой формы осталась бы без единого красного теста. Строка про `identity`
# заменяется целиком — вложенный источник рядом с накрывающим дал бы
# `overlapping-line`, то есть план, который не исполняется вовсе.
RENAMED = TOTAL.replace(
    "- [x] `identity` -> `stay`\n      Лежит правильно.",
    "- [x] `identity/how-we-work.md` -> `core/устав.md`\n"
    "      Переименование: basename меняется, голая ссылка его не переживёт.")

MOVED = TOTAL.replace(
    "- [x] `identity` -> `stay`\n      Лежит правильно.",
    "- [x] `identity` -> `core/identity`\n"
    "      Переезд каталога: basename тот же, где лежит — другое.")

# Единственная markdown-ссылка фикстуры ведёт в `journal/`, а в TOTAL эта
# строка несёт `?` и не исполняется ничем. Спрашивать про markdown-ссылки
# у отказавшей строки бессмысленно: отчёт до них не доходит.
JOURNAL = TOTAL.replace(
    "- [x] `journal` -> `areas/<?>/journal`\n      Область неизвестна, спрашиваю.",
    "- [x] `journal` -> `areas/work/journal`\n      Область выяснена.")

OUTSIDE = TOTAL.replace("- [x] `notes` -> `areas/work/notes`",
                        "- [x] `notes` -> `../соседний/notes`")


class Prepared(unittest.TestCase):
    """Дерево фикстуры, план и точка отката. Тестов своих не несёт."""

    PLAN = TOTAL

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        self.plan = write_plan(self.root, self.PLAN)
        report, code = init_tree.run(self.root)
        self.assertEqual(code, EXIT_OK, report)

    def R(self):
        return check_links.count_resolvable(self.root)

    def readme(self, text=None):
        path = self.root / "README.md"
        if text is not None:
            path.write_text(text, encoding="utf-8")
        return path.read_text(encoding="utf-8")

    def plant_path_form(self):
        """Ссылка с путём вместо голой. Точное место — строка 6 README."""
        self.readme(self.readme().replace("[[meeting]]", "[[notes/meeting]]"))


class TestChain(Prepared):
    PLAN = RENAMED

    def setUp(self):
        super().setUp()
        self.plant_path_form()

    def test_the_chain_preserves_R(self):
        """Обе формы за один прогон: переезд каталога и переименование файла.

        Вынутая ветка путевой формы роняет здесь R на первом шаге, вынутая
        ветка голой — на втором. Фальсификатор «правка, знающая только одну
        форму» этим и меряется, а не обещанием в докстроке.
        """
        before = self.R()
        self.assertGreater(before, 0)
        for source, target in (("notes", "areas/work/notes"),
                               ("identity/how-we-work.md", "core/устав.md")):
            report, code = rewrite_refs.run(self.root, source, target, self.plan)
            self.assertEqual(code, EXIT_OK, report)
            report, code = move.run(self.root, source, target, self.plan)
            self.assertEqual(code, EXIT_OK, report)
            self.assertEqual(self.R(), before, source)

    def test_move_without_rewrite_drops_R(self):
        """Первый фальсификатор. Без него равенство R ничего не доказывает."""
        before = self.R()
        report, code = move.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.R(), before - 1)

    def test_rewrite_without_move_drops_R(self):
        """Второй. Правка ссылок вперёд переезда ломает их ровно на один ход,
        и это окно названо в спеке волны."""
        before = self.R()
        report, code = rewrite_refs.run(self.root, "notes", "areas/work/notes",
                                        self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.R(), before - 1)

    def test_a_rewriter_blind_to_the_bare_form_drops_R(self):
        """Третий, и он не тот, что в спеке волны.

        Спека называет третьим фальсификатором правку, знающую только
        путевую форму, «при переезде, создающем коллизию basename».
        Коллизия R не двигает: неоднозначная ссылка считается одним
        вхождением по решению той же спеки. Двигает R переименование:
        голая ссылка на переименованный файл повисает, и правка, знающая
        только путевую форму, её не чинит. Здесь это и меряется — переезд
        без правки, то есть правка, для голой формы ничего не сделавшая.
        """
        before = self.R()
        report, code = move.run(self.root, "identity/how-we-work.md",
                                "core/устав.md", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.R(), before - 1)


class TestForms(Prepared):
    def test_the_path_form_gets_the_new_prefix(self):
        self.readme("[[notes/meeting#Итоги|встреча]]\n")
        rewrite_refs.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(self.readme(), "[[areas/work/notes/meeting#Итоги|встреча]]\n")

    def test_the_embed_form_keeps_its_exclamation(self):
        self.readme("![[notes/meeting]]\n")
        rewrite_refs.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(self.readme(), "![[areas/work/notes/meeting]]\n")

    def test_a_link_in_backticks_is_not_the_one_that_gets_rewritten(self):
        """Правка по подстроке чинила первое вхождение в строке — а первым
        стоит пример в backtick'ах, который гейт ссылкой не считает вовсе.
        Живая ссылка справа при этом оставалась старой: правка попадала
        ровно мимо того, ради чего заведена."""
        self.readme("Пишется `[[notes/meeting]]`, а ведёт [[notes/meeting]].\n")
        rewrite_refs.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(
            self.readme(),
            "Пишется `[[notes/meeting]]`, "
            "а ведёт [[areas/work/notes/meeting]].\n")

    def test_two_links_on_one_line_are_both_rewritten(self):
        self.readme("[[notes/meeting]] и снова [[notes/meeting]]\n")
        rewrite_refs.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(self.readme(),
                         "[[areas/work/notes/meeting]] и снова "
                         "[[areas/work/notes/meeting]]\n")


class TestBareForm(Prepared):
    PLAN = MOVED

    def test_a_bare_basename_that_still_leads_to_the_file_is_left_alone(self):
        """Переезда такая ссылка не замечает: пути в тексте нет вовсе."""
        self.readme("[[how-we-work]]\n")
        report, code = rewrite_refs.run(self.root, "identity", "core/identity",
                                        self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.readme(), "[[how-we-work]]\n")
        self.assertIn("голых ссылок оставлено: 1", report)

    def test_an_ambiguity_older_than_the_move_is_not_resolved_for_the_author(self):
        """`[[meeting]]` неоднозначна в фикстуре до всякого переезда, и
        переезд `notes` этого не меняет: basename по-прежнему ведёт к
        переехавшему файлу, просто не только к нему.

        Дописать сюда полный путь значило бы решить за автора, какую из
        двух встреч он имел в виду, — это содержимое, а не форма (линия
        ответственности). Гейт про такую ссылку говорит `ambiguous`, и
        чинит её автор.
        """
        before = self.readme()
        report, code = rewrite_refs.run(self.root, "notes", "areas/work/notes",
                                        self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.readme(), before)
        self.assertEqual(
            (self.root / "journal" / "2026-01-04.md").read_text(encoding="utf-8"),
            (Path(__file__).resolve().parent.parent / "fixtures" / "foreign"
             / "journal" / "2026-01-04.md").read_text(encoding="utf-8"))
        self.assertIn("голых ссылок оставлено: 2", report)


class TestRename(Prepared):
    PLAN = RENAMED

    def test_a_bare_basename_that_stops_leading_to_the_file_gets_the_full_path(self):
        """Переименование уносит basename, и голая ссылка после него ведёт
        в никуда. Тогда её надо доопределить, а не оставить."""
        self.readme("[[how-we-work]]\n")
        report, code = rewrite_refs.run(self.root, "identity/how-we-work.md",
                                        "core/устав.md", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.readme(), "[[core/устав]]\n")


class TestMarkdownLinks(Prepared):
    PLAN = JOURNAL

    def test_markdown_links_are_counted_and_not_touched(self):
        """R их не видит, значит переезд их ломает, а счётчик молчит. Число
        показывается вслух ровно поэтому."""
        report, code = rewrite_refs.run(self.root, "journal",
                                        "areas/work/journal", self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertIn("markdown-ссылок не тронуто: 1", report)
        self.assertIn("ссылок переписано: 0", report)
        self.assertIn("(journal/2026-01-04.md)", self.readme())


class TestTheTable(Prepared):
    """Критерий 5, первая половина: машинная таблица массовой мутации.

    Четыре счётчика отвечали на вопрос «сколько», а §20 спрашивает «что и во
    скольких файлах»: поимённо счётчик не называет ни одной правки, и
    сходимость до таблицы держал один инвариант «R до = R после».
    """

    TABLE = "tmp/ref-map-rewrite-refs-notes-areas-work-notes.tsv"

    def rewrite(self):
        return rewrite_refs.run(self.root, "notes", "areas/work/notes",
                                self.plan)

    def table(self):
        return (self.root / self.TABLE).read_text(encoding="utf-8")

    def test_the_table_lands_in_tmp_and_names_every_rewrite(self):
        self.readme("Встреча [[notes/meeting]], она же ![[notes/meeting#Итоги]].\n")
        report, code = self.rewrite()
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.table(), "\n".join([
            "\t".join(field_map.REF_COLUMNS),
            "README.md\t1\t![[notes/meeting#Итоги]]\t"
            "![[areas/work/notes/meeting#Итоги]]\t%s" % AGREED,
            "README.md\t1\t[[notes/meeting]]\t[[areas/work/notes/meeting]]\t%s"
            % AGREED,
        ]) + "\n")
        self.assertIn("таблица: %s" % self.TABLE, report)

    def test_the_name_of_the_table_carries_no_date(self):
        """Метка времени вернула бы часы и сломала побайтовую
        воспроизводимость: имя выводится из операции и её аргументов."""
        self.plant_path_form()
        self.rewrite()
        names = sorted(p.name for p in (self.root / "tmp").glob("*-map-*"))
        self.assertEqual(names, ["ref-map-rewrite-refs-notes-areas-work-notes.tsv"])

    def test_a_run_that_rewrote_nothing_still_leaves_a_table(self):
        """«Правок ноль» и «мутации не было» обязаны различаться на диске:
        таблица — запись о состоявшейся мутации, а не о непустой."""
        self.readme("Ничего про заметки тут нет.\n")
        report, code = self.rewrite()
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.table(), "\t".join(field_map.REF_COLUMNS) + "\n")

    def test_a_refused_run_leaves_no_table_at_all(self):
        """Отказ мутацией не является, и таблица про него солгала бы."""
        report, code = rewrite_refs.run(self.root, "state.md", "core/state.md",
                                        self.plan)
        self.assertEqual(code, EXIT_VIOLATION, report)
        self.assertEqual(sorted((self.root / "tmp").glob("*-map-*")), [])

    def test_two_identical_links_on_one_line_are_one_row_and_one_edit(self):
        """Правит их `_applied` одной инструкцией — словарём по тексту
        ссылки, — и различить их между собой нечем: колонки у вхождения нет.
        Вторая строка таблицы описывала бы ту же правку дважды."""
        self.readme("[[notes/meeting]] и снова [[notes/meeting]]\n")
        report, code = self.rewrite()
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.table(), "\n".join([
            "\t".join(field_map.REF_COLUMNS),
            "README.md\t1\t[[notes/meeting]]\t[[areas/work/notes/meeting]]\t%s"
            % AGREED,
        ]) + "\n")
        self.assertEqual(self.readme(),
                         "[[areas/work/notes/meeting]] и снова "
                         "[[areas/work/notes/meeting]]\n")


class TestTheCounterDiff(Prepared):
    """Критерий 5, вторая половина: дифф ожидаемого и фактического.

    Ожидаемое — то, что назвал резолвер гейта по дереву **до** мутации;
    фактическое — строки таблицы. Что это доказывает, а что нет, названо
    вслух: обе половины берут у одного резолвера, что считать ссылкой и куда
    она ведёт, и независимы ровно в одном — что цикл правки сделал с каждой
    из названных. Недостача обязана нести токен из закрытого списка.
    """

    def plant(self):
        """Три ссылки под источником, и ни одну правка не переписывает —
        каждую по своей причине: голая (после переезда ведёт туда же),
        markdown (§13 отдаёт её отдельной мутации), путь в backtick'ах
        (правятся только wikilink'и)."""
        self.readme("Встреча: [[meeting]].\n"
                    "Дневник: [встреча](notes/meeting.md).\n"
                    "Заметки лежат в `notes/meeting.md`.\n")

    def diff(self, explained=None):
        hits, _ = refs.find(self.root, "notes")
        rows, kept = rewrite_refs.plan_rewrites(
            hits, "notes", "areas/work/notes", AGREED)
        return rows, rewrite_refs.counter_diff(
            hits, rows.values(), kept if explained is None else explained)

    def test_two_enumerations_that_agree_say_nothing(self):
        self.plant_path_form()
        rows, findings = self.diff()
        self.assertEqual(sorted(rows), [("README.md", 6, "[[notes/meeting]]")])
        self.assertEqual(places(findings), [])

    def test_every_reference_the_rewriter_leaves_carries_a_token(self):
        self.plant()
        rows, findings = self.diff()
        self.assertEqual(sorted(rows), [])
        self.assertEqual(places(findings), [])

    def test_without_the_token_channel_each_of_them_is_named(self):
        """Фальсификатор третьего аргумента `reconcile` и он же
        анти-тавтология: ожидаемое, выведенное из цикла правки, знало бы ровно
        то же, что и таблица, — дифф зеленел бы по построению и не покраснел
        бы уже никогда. Здесь ожидаемое называет три ссылки, которых цикл не
        трогал вовсе, и без объяснения каждая — находка."""
        self.plant()
        _, findings = self.diff(explained={})
        self.assertEqual(places(findings), [
            ("README.md", 1, "unexplained-count", SHORTFALL),
            ("README.md", 2, "unexplained-count", SHORTFALL),
            ("README.md", 3, "unexplained-count", SHORTFALL),
            # Четвёртая — своя у фикстуры: `[[meeting]]` в дневнике, тоже
            # голая и тоже ведущая под `notes`.
            ("journal/2026-01-04.md", 5, "unexplained-count", SHORTFALL),
        ])

    def test_every_token_belongs_to_the_closed_list(self):
        self.plant()
        hits, _ = refs.find(self.root, "notes")
        _, kept = rewrite_refs.plan_rewrites(
            hits, "notes", "areas/work/notes", AGREED)
        self.assertEqual(
            sorted(set(kept.values()) - set(field_map.REF_TOKENS)), [])
        self.assertEqual(sorted(set(kept.values())),
                         ["bare-still-resolves", "md-link", "not-a-wikilink"])


class TestPathsThatAreNotWikilinks(Prepared):
    """Наблюдённая поломка, ради которой заведён токен `not-a-wikilink`."""

    def test_a_backtick_path_under_the_source_is_broken_by_the_move_and_named(self):
        """Путь в backtick'ах резолвится, R его считает, переезд его ломает —
        а правка wikilink'ов его не трогает. До таблицы отчёт не говорил про
        него ничего: ни счётчиком, ни строкой, и R уезжала молча."""
        self.readme("Заметки лежат в `notes/meeting.md`.\n")
        before = self.R()
        report, code = rewrite_refs.run(self.root, "notes", "areas/work/notes",
                                        self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertIn("не переписано: README.md:1 `notes/meeting.md` "
                      "(not-a-wikilink)", report)
        report, code = move.run(self.root, "notes", "areas/work/notes",
                                self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(self.R(), before - 1)


class TestJournal(Prepared):
    def test_touched_files_are_recorded_against_the_line(self):
        """Иначе `check-plan` объявит правку ссылок уходом с плана."""
        self.readme("[[notes/meeting]]\n")
        rewrite_refs.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(tree.read_touched(self.root), [("notes", "README.md")])

    def test_a_second_run_does_not_double_the_entry(self):
        """Цепочка повторно входима, и журнал обязан это переживать."""
        self.readme("[[notes/meeting]]\n")
        rewrite_refs.run(self.root, "notes", "areas/work/notes", self.plan)
        rewrite_refs.run(self.root, "notes", "areas/work/notes", self.plan)
        self.assertEqual(tree.read_touched(self.root), [("notes", "README.md")])

    def test_the_journal_holds_a_pair_once_and_keeps_the_earlier_ones(self):
        """Журнал — множество пар, а не лента событий: `check-plan` спрашивает
        у него «названа ли эта правка», и вторая такая же запись ответа не
        меняет, а запись про другой файл обязана лечь рядом.

        Пишется напрямую, потому что через `rewrite-refs` второй записи про
        тот же файл не получить: второй ход правит уже переписанное, то есть
        ничего. Проверка через команду была бы зелена от пустого хода.
        """
        tree.record_touched(self.root, "notes", ["README.md"])
        tree.record_touched(self.root, "notes", ["README.md"])
        tree.record_touched(self.root, "media", ["state.md"])
        self.assertEqual(tree.read_touched(self.root),
                         [("media", "state.md"), ("notes", "README.md")])

    def test_nothing_is_recorded_when_nothing_changed(self):
        """Ход, не тронувший ни файла, журнала не заводит. Код возврата
        проверяется здесь же: отказ тоже ничего не пишет, и без этой строки
        тест был бы зелен от отказа, а не от пустой правки."""
        plan = write_plan(self.root, JOURNAL)
        report, code = rewrite_refs.run(self.root, "journal",
                                        "areas/work/journal", plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertEqual(tree.read_touched(self.root), [])


class TestRefusals(Prepared):
    def test_an_unagreed_line_is_refused(self):
        report, code = rewrite_refs.run(self.root, "state.md", "core/state.md",
                                        self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("строка не согласована", report)

    def test_a_line_absent_from_the_plan_is_refused(self):
        report, code = rewrite_refs.run(self.root, "notes", "core/иное",
                                        self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("такой строки в плане нет", report)

    def test_an_unread_file_is_named_not_swallowed(self):
        """Недекодируемый файл может нести ссылку на переезжающий путь, и
        переписана она не будет. «Переписано 0» про такое дерево —
        невосстановимое значение, подставленное молча (незыблемое №4)."""
        # Кириллица обязательна: ASCII в cp1251 остаётся ASCII, и такой
        # файл прочитался бы как UTF-8, не дав отказа вовсе.
        (self.root / "notes" / "старое.md").write_bytes(
            "Старая заметка про [[notes/meeting]]\n".encode("cp1251"))
        report, code = rewrite_refs.run(self.root, "notes", "areas/work/notes",
                                        self.plan)
        self.assertEqual(code, EXIT_OK, report)
        self.assertIn("не прочитан: notes/старое.md", report)


class TestOutsideTheRoot(Prepared):
    PLAN = OUTSIDE

    def test_a_target_outside_the_root_is_refused(self):
        """Незыблемое №6. `move` такую строку отвергает, но `rewrite-refs`
        идёт **раньше** него: без своей проверки он успел бы вписать
        `[[../соседний/notes/meeting]]` в файлы автора."""
        self.plant_path_form()
        before = self.readme()
        report, code = rewrite_refs.run(self.root, "notes", "../соседний/notes",
                                        self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("вне корня", report)
        self.assertEqual(self.readme(), before)


class TestWithoutRollback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)
        self.plan = write_plan(self.root, TOTAL)

    def test_without_a_repository_nothing_is_rewritten(self):
        """Правка ссылок необратима иначе ничем: `move` останавливает сам
        git, а запись в файл проходит молча и вернуть её нечем."""
        path = self.root / "README.md"
        path.write_text("[[notes/meeting]]\n", encoding="utf-8")
        report, code = rewrite_refs.run(self.root, "notes", "areas/work/notes",
                                        self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("точки отката нет", report)
        self.assertEqual(path.read_text(encoding="utf-8"), "[[notes/meeting]]\n")

    def test_a_repository_without_the_base_commit_is_refused_too(self):
        """Случай, ради которого точка отката спрашивается именем, а не
        наличием `.git`: автор завёл репозиторий руками, коммита «как было»
        нет, и `revert` возвращать не к чему. Здесь ничто не падает само —
        снятая проверка переписала бы файл молча и с кодом 0.
        """
        subprocess.run(["git", "init", "-q"], cwd=str(self.root), check=True)
        path = self.root / "README.md"
        path.write_text("[[notes/meeting]]\n", encoding="utf-8")
        report, code = rewrite_refs.run(self.root, "notes", "areas/work/notes",
                                        self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertIn("точки отката нет", report)
        self.assertEqual(path.read_text(encoding="utf-8"), "[[notes/meeting]]\n")


class TestCommandLine(Prepared):
    def test_the_command_line_carries_the_rewrite_through(self):
        self.readme("[[notes/meeting]]\n")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "adopt" / "rewrite_refs.py"),
             str(self.root), "notes", "areas/work/notes", "--plan", str(self.plan)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
        self.assertIn("ссылок переписано: 1", proc.stdout)
        self.assertEqual(self.readme(), "[[areas/work/notes/meeting]]\n")

    def test_there_is_no_way_to_omit_the_plan(self):
        """`--plan` обязателен: мутация без плана — дверь мимо инварианта,
        и закрыта она разбором аргументов, а не дисциплиной."""
        before = self.readme()
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "adopt" / "rewrite_refs.py"),
             str(self.root), "notes", "areas/work/notes"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--plan", proc.stderr)
        self.assertEqual(self.readme(), before)
