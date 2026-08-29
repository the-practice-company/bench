"""Слой «форма механически»: что чинится, что уходит в отчёт."""

import tempfile
import unittest
from pathlib import Path

from scripts.adopt import tree
from scripts.maintain import content_diff, mechanical, surface
from tests.maintain_fixture import materialise

SCAFFOLD = Path(__file__).resolve().parent.parent / "scaffold"

# Пути фикстуры, на которых стоят утверждения этого набора. Названы здесь,
# а не по месту: переименование образца обязано ронять набор целиком, а не
# одну строку в середине.
RULE = ".claude/rules/areas.md"
RECORD = "areas/work/journal/items/late-entry.md"
DEAL = "projects/deals/items/one.md"


def places(findings):
    return sorted((f.path, f.line, f.cls, f.detail) for f in findings)


def commit(root, *paths):
    """Правка теста, ставшая частью истории.

    Без коммита путь остаётся незакоммиченным, а незакоммиченного MAINTAIN
    не трогает вовсе — тест на «что уцелело после починки» прошёл бы,
    ничего не проверив: уцелело бы всё, включая то, что чиниться обязано.
    """
    tree.git(root, "add", "--", *paths)
    tree.git(root, "commit", "-q", "-m", "правка теста")


class TestWhatIsFixed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_rule_file_is_returned_to_the_scaffold_byte_for_byte(self):
        """Правило рецепта принадлежит плагину целиком. Чинится не ссылка,
        а файл: эталон один — `scaffold/`."""
        fixed, _, _ = mechanical.run(self.root)
        self.assertIn(RULE, fixed)
        self.assertEqual((self.root / RULE).read_bytes(),
                         (SCAFFOLD / RULE).read_bytes())

    def test_the_repaired_link_leaves_the_report_and_the_others_stay(self):
        """Находки снимаются **после** починок, а не до. Иначе отчёт назвал
        бы автору то, что MAINTAIN только что починил сам, и не покраснел бы
        оттого, что починка не состоялась."""
        _, findings, _ = mechanical.run(self.root)
        self.assertEqual(
            [f for f in places(findings) if f[2] == "unresolved"],
            [("areas/README.md", 17, "unresolved", "`knowledge/`"),
             ("tmp/README.md", 14, "unresolved", "`knowledge/`")])

    def test_a_hand_edited_form_section_of_claude_md_is_restored(self):
        fixed, _, _ = mechanical.run(self.root)
        self.assertIn("CLAUDE.md", fixed)
        text = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        reference = (SCAFFOLD / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(surface.section(text, "Zone map"),
                         surface.section(reference, "Zone map"))

    def test_prose_outside_the_form_sections_survives_the_restore(self):
        """Секция целиком — это секция, а не файл. Авторская проза рядом
        с формой остаётся."""
        path = self.root / "CLAUDE.md"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n## Мой раздел\n\nАвторский текст.\n", encoding="utf-8")
        commit(self.root, "CLAUDE.md")
        fixed, _, _ = mechanical.run(self.root)
        self.assertIn("CLAUDE.md", fixed)
        self.assertIn("Авторский текст.", path.read_text(encoding="utf-8"))

    def test_the_domain_description_is_not_taken_from_the_scaffold(self):
        """Первый абзац `CLAUDE.md` — содержимое. Заменить его каркасным
        значило бы переписать за автора описание домена."""
        mechanical.run(self.root)
        self.assertIn("Домен: работа студии",
                      (self.root / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_the_restore_of_claude_md_is_not_read_as_content_modified(self):
        """Долг, названный в `content_diff`: гранулярность тоньше файла.
        Без неё само-проверка волны откатывала бы каждый прогон."""
        before = content_diff.snapshot(self.root)
        mechanical.run(self.root)
        self.assertEqual(
            places(content_diff.compare(before,
                                        content_diff.snapshot(self.root))), [])

    def test_a_second_run_fixes_nothing(self):
        """Инвариант 2 волны на этом слое: починенное второй раз не чинится."""
        mechanical.run(self.root)
        after = (self.root / "CLAUDE.md").read_bytes()
        fixed, _, skipped = mechanical.run(self.root)
        self.assertEqual((fixed, skipped), ([], []))
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), after)


class TestWhatIsReported(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_an_unresolved_link_in_a_record_body_is_reported_not_guessed(self):
        """Неверная догадка здесь тиха: ссылка начинает резолвиться, гейт
        зеленеет, а указывает она не туда, куда автор писал."""
        path = self.root / RECORD
        path.write_text(path.read_text(encoding="utf-8") +
                        "См. [[несуществующая-цель]].\n", encoding="utf-8")
        commit(self.root, RECORD)
        fixed, findings, _ = mechanical.run(self.root)
        self.assertNotIn(RECORD, fixed)
        self.assertIn((RECORD, 8, "unresolved", "[[несуществующая-цель]]"),
                      places(findings))
        self.assertIn("[[несуществующая-цель]]",
                      path.read_text(encoding="utf-8"))

    def test_a_value_outside_the_vocabulary_is_always_a_report(self):
        """И значение, и словарь авторские."""
        path = self.root / DEAL
        path.write_text(path.read_text(encoding="utf-8")
                        .replace("status: new", "status: придумал"),
                        encoding="utf-8")
        commit(self.root, DEAL)
        fixed, findings, _ = mechanical.run(self.root)
        self.assertNotIn(DEAL, fixed)
        self.assertIn(
            (DEAL, 1, "value-outside-vocabulary",
             "status='придумал' вне словаря ['new', 'won', 'lost']"),
            places(findings))
        self.assertIn("status: придумал", path.read_text(encoding="utf-8"))

    def test_missing_required_is_reported_and_no_field_is_written(self):
        """Backfill — отдельная задача волны со своей таблицей `field-map`.
        Здесь дыра только называется: подставить молча нечего."""
        before = {rel: shot.bytes
                  for rel, shot in content_diff.snapshot(self.root).items()}
        _, findings, _ = mechanical.run(self.root)
        self.assertEqual(
            [f for f in places(findings) if f[2] == "missing-required"],
            [("areas/work/journal/items/2026-08-25.md", 1, "missing-required",
              "стартовый набор: поле created"),
             ("areas/work/journal/items/late-entry.md", 1, "missing-required",
              "стартовый набор: поле created"),
             ("projects/deals/items/two.md", 1, "missing-required",
              "стартовый набор: поле status у архетипа pipeline")])
        for rel in ("areas/work/journal/items/2026-08-25.md",
                    "areas/work/journal/items/late-entry.md",
                    "projects/deals/items/two.md"):
            self.assertEqual((self.root / rel).read_bytes(), before[rel], rel)

    def test_the_allowlist_is_never_written(self):
        (self.root / ".link-allow").write_text(
            "черновики/*  # временно\n", encoding="utf-8")
        before = (self.root / ".link-allow").read_bytes()
        mechanical.run(self.root)
        self.assertEqual((self.root / ".link-allow").read_bytes(), before)


class TestDirtyPaths(unittest.TestCase):
    """Незакоммиченное — след человека (§8), и второго механизма под это
    волна не заводит."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def test_a_path_with_uncommitted_changes_is_not_touched(self):
        """Иначе собственный откат снёс бы работу человека."""
        path = self.root / RULE
        path.write_text("правка человека\n", encoding="utf-8")
        fixed, _, skipped = mechanical.run(self.root)
        self.assertNotIn(RULE, fixed)
        self.assertEqual(path.read_text(encoding="utf-8"), "правка человека\n")
        self.assertEqual(skipped, [RULE])

    def test_an_uncommitted_claude_md_keeps_its_hand_written_form_section(self):
        """Форм-секция принадлежит плагину, но не тогда, когда файл прямо
        сейчас в работе у человека."""
        path = self.root / "CLAUDE.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nхвост\n",
                        encoding="utf-8")
        fixed, _, skipped = mechanical.run(self.root)
        self.assertNotIn("CLAUDE.md", fixed)
        self.assertIn("CLAUDE.md", skipped)
        self.assertIn("верстак, всё временное",
                      path.read_text(encoding="utf-8"))

    def test_a_clean_form_file_is_not_called_skipped(self):
        """Пропущенное — то, что чинилось бы, да нельзя. Файл, которому
        чинить нечего, в этой строке отчёта не значится."""
        _, _, skipped = mechanical.run(self.root)
        self.assertEqual(skipped, [])

    def test_an_untracked_form_file_inside_an_untracked_folder_counts(self):
        """Без `-uall` git возвращает неотслеженное поддерево одной строкой
        каталога, и файл внутри не совпал бы ни с одним ключом: MAINTAIN
        переписал бы то, чего git ещё не видел."""
        tree.git(self.root, "rm", "-r", "-q", "--cached", "--", ".claude/rules")
        tree.git(self.root, "commit", "-q", "-m", "правила ушли из индекса")
        fixed, _, skipped = mechanical.run(self.root)
        self.assertNotIn(RULE, fixed)
        self.assertEqual(skipped, [RULE])
        self.assertIn("areas/hiring/items/",
                      (self.root / RULE).read_text(encoding="utf-8"))

    def test_a_non_ascii_path_comes_back_as_it_is_on_disk(self):
        """Без `-z` git обрамляет не-ASCII путь кавычками и экранирует его
        восьмеричными последовательностями: `sources/дубль.md` вернулся бы
        именем, которого в дереве нет, — грязный путь прочитался бы чистым."""
        (self.root / "sources" / "дубль.md").write_text("x\n", encoding="utf-8")
        self.assertIn("sources/дубль.md", mechanical._dirty(self.root))

    def test_a_renamed_path_names_both_of_its_sides(self):
        """У переименования две записи подряд, и вторая приходит голой, без
        префикса состояния. Прочитанная как обычная, она теряет три первых
        знака имени."""
        tree.git(self.root, "mv", "core/people/items/anna.md",
                 "core/people/items/anna2.md")
        self.assertLessEqual(
            {"core/people/items/anna.md", "core/people/items/anna2.md"},
            mechanical._dirty(self.root))

    def test_a_tree_without_git_refuses_instead_of_rewriting_itself(self):
        """Пустое множество грязных путей здесь значило бы «всё чисто» —
        молчаливая заглушка, за которой MAINTAIN переписал бы форму дерева,
        о котором ничего не знает (незыблемое №4)."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                mechanical._dirty(tmp)


class TestSurfaceIsTheOnlyDefinitionOfForm(unittest.TestCase):
    """Второго перечисления формы волна не заводит: тот, кто чинит, и тот,
    кто доказывает «содержимое не тронуто», читают одну строку."""

    def test_the_files_restored_whole_are_exactly_those_the_surface_covers(self):
        self.assertEqual(
            [rel for rel, _ in mechanical._whole_files()],
            sorted(path.relative_to(SCAFFOLD).as_posix()
                   for path in (SCAFFOLD / ".claude" / "rules").glob("*.md")))

    def test_the_restored_sections_are_named_by_the_surface(self):
        self.assertEqual(surface.names("CLAUDE.md", "section"),
                         ("Zone map", "Placement rule"))

    def test_a_record_names_no_sections(self):
        self.assertEqual(surface.names(RECORD, "section"), ())


class TestSections(unittest.TestCase):
    TEXT = ("# Заголовок\n\nпролог\n\n## Один\n\nтело один\n\n"
            "### Вложенный\n\nещё\n\n## Два\n\nтело два\n")

    def test_a_section_runs_to_the_next_second_level_heading(self):
        self.assertEqual(
            surface.section(self.TEXT, "Один"),
            "## Один\n\nтело один\n\n### Вложенный\n\nещё\n\n")

    def test_the_last_section_runs_to_the_end_of_the_file(self):
        self.assertEqual(surface.section(self.TEXT, "Два"),
                         "## Два\n\nтело два\n")

    def test_an_absent_section_is_empty_and_not_an_error(self):
        self.assertEqual(surface.section(self.TEXT, "Нет такой"), "")

    def test_the_remainder_holds_everything_the_sections_do_not(self):
        self.assertEqual(surface.without_sections(self.TEXT, ("Один", "Два")),
                         "# Заголовок\n\nпролог\n\n")

    def test_removing_two_sections_does_not_shift_the_second_span(self):
        """Вырезание по индексам идёт с конца: вырезав первую секцию, спан
        второй сдвинулся бы, и из файла ушёл бы кусок чужого текста."""
        self.assertEqual(surface.without_sections(self.TEXT, ("Два", "Один")),
                         "# Заголовок\n\nпролог\n\n")

    def test_a_section_is_replaced_in_place(self):
        self.assertEqual(surface.replace_section(self.TEXT, "Один", "## Один\n"),
                         "# Заголовок\n\nпролог\n\n## Один\n## Два\n\nтело два\n")


class TestClaudeMdDiff(unittest.TestCase):
    """Гранулярность секции в `content_diff`: форм-секция прощается, всё
    остальное в том же файле — нет."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)
        self.before = content_diff.snapshot(self.root)
        self.path = self.root / "CLAUDE.md"

    def _diff(self):
        return places(content_diff.compare(self.before,
                                           content_diff.snapshot(self.root)))

    def _rewrite(self, old, new):
        self.path.write_text(
            self.path.read_text(encoding="utf-8").replace(old, new),
            encoding="utf-8")

    def test_a_change_inside_a_form_section_is_forgiven(self):
        self._rewrite("верстак, всё временное", "workbench")
        self.assertEqual(self._diff(), [])

    def test_a_change_outside_the_form_sections_still_reddens(self):
        self._rewrite("Домен: работа студии", "Домен: переписан за автора")
        self.assertEqual(self._diff(), [
            ("CLAUDE.md", 1, "content-modified", "тело markdown-файла изменилось")])

    def test_a_legal_change_does_not_blind_the_diff_to_an_illegal_one(self):
        """Вырезание форм-секций обязано оставить остальное под сравнением:
        иначе одна законная починка прощала бы правку прозы рядом с ней."""
        self._rewrite("верстак, всё временное", "workbench")
        self._rewrite("Домен: работа студии", "Домен: переписан за автора")
        self.assertEqual(self._diff(), [
            ("CLAUDE.md", 1, "content-modified", "тело markdown-файла изменилось")])

    def test_a_section_of_another_file_is_not_forgiven(self):
        """Секционная гранулярность названа для `CLAUDE.md` и только для
        него: `## Zone map`, дописанный в README зоны, — содержимое."""
        path = self.root / "areas" / "README.md"
        # Дописано впритык к последней строке: останься между ними лишний
        # перевод строки, остаток файла разошёлся бы и без разбора секций,
        # и тест краснел бы не тем, чем утверждает.
        path.write_text(path.read_text(encoding="utf-8") +
                        "## Zone map\n\nчужая карта\n", encoding="utf-8")
        self.assertEqual(self._diff(), [
            ("areas/README.md", 1, "content-modified",
             "тело markdown-файла изменилось")])


if __name__ == "__main__":
    unittest.main()
