"""Фикстура MAINTAIN: двенадцать посаженных наблюдений и пиннинг дат.

Список, а не счёт. Одиннадцать задач волны 5 ниже по плану опираются на эту
фикстуру целиком: слой спроса меряет её даты, `content_diff` сверяет её байты,
`backfill` считает её поля. Свойство, тихо пропавшее здесь, не роняет ничего —
оно просто перестаёт проверяться там. Тот же довод, что у
`tests/test_foreign_fixture.py`.

Скелет фикстуры — **копия каркаса**, а не третье определение формы: что именно
разошлось с `scaffold/`, утверждается пофайлово и побайтово, и всякая правка
каркаса, не доехавшая до фикстуры, роняет набор здесь.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import dates
from tests.maintain_fixture import (ABSENT, BINARY, BINARY_BYTES, EDITED,
                                    EXTRA, FIXTURE, DOC, ROOT, SCAFFOLD,
                                    TOUCHED, materialise)
from tests.test_fixtures import tracked

# Точный состав посаженного. Потерянное свойство обязано уронить набор здесь,
# а не тихо ослабить одиннадцать задач ниже. Сверяется с `ЧТО-ПОСАЖЕНО.md`
# по тексту до первого двоеточия: заголовок раздела там — эта же фраза.
PLANTED = (
    "зона из карты без папки: knowledge/",
    "папка верхнего уровня вне карты: vault/",
    "направление без строки в areas/README.md: areas/hiring",
    "коллекция registry, чьи записи двигают status: core/people",
    "две пустые коллекции по разные стороны порога: "
    "projects/stale и projects/fresh",
    "вид на пустую папку: areas/work/reviews/views.base",
    "запись без created, восстановимого из git: "
    "areas/work/journal/items/2026-08-25.md",
    "запись без created, невосстановимого правилом имени: "
    "areas/work/journal/items/late-entry.md",
    "поле со словарём и дырой: projects/deals/items/two.md",
    "игнорируемый бинарь без ссылающейся записи: sources/dump.bin",
    "правило со ссылкой на переименованную папку: .claude/rules/areas.md",
    "форм-секция CLAUDE.md, правленная руками",
)

# Фраза, которой фикстура называет свою дыру вслух. Незыблемое №4 в приложении
# к самой фикстуре: образца, которого в ней нет, не изображают похожим.
GAP = "невосстановимого из git образца здесь нет"

JOURNAL = "areas/work/journal/items"


class TestStored(unittest.TestCase):
    def test_the_planted_list_is_documented_in_the_fixture(self):
        """Список посаженного лежит рядом с фикстурой, а не только в тесте:
        иначе через месяц никто не знает, что здесь намеренно, а что сломалось."""
        text = (FIXTURE / DOC).read_text(encoding="utf-8")
        missing = [p for p in PLANTED if p.split(":")[0] not in text]
        self.assertEqual(missing, [])

    def test_the_missing_sample_is_named_out_loud(self):
        """`created`, невосстановимого из git, в фикстуре нет, и это сказано
        вслух: у отслеживаемого файла с чистым деревом первый коммит есть
        всегда. Молчаливой заглушки на его месте не будет."""
        text = (FIXTURE / DOC).read_text(encoding="utf-8")
        self.assertIn(GAP, text)

    def test_the_map_names_eight_zones_and_one_of_them_has_no_folder(self):
        present = sorted(p.name for p in FIXTURE.iterdir() if p.is_dir()
                         and not p.name.startswith("."))
        self.assertIn("vault", present)
        self.assertNotIn("knowledge", present)
        self.assertIn("knowledge/", (FIXTURE / "CLAUDE.md").read_text(
            encoding="utf-8"))

    def test_the_skeleton_is_the_scaffold_byte_for_byte_apart_from_the_named(self):
        """Эталон формы один — `scaffold/`. Здесь утверждается, что фикстура
        именно его копия: расходятся ровно названные файлы, и ни одним больше.
        Правка каркаса, не доехавшая до фикстуры, роняет набор здесь."""
        same, differ, absent = [], [], []
        for source in sorted(SCAFFOLD.rglob("*")):
            if not source.is_file():
                continue
            rel = source.relative_to(SCAFFOLD).as_posix()
            target = FIXTURE / rel
            if not target.exists():
                absent.append(rel)
            elif target.read_bytes() == source.read_bytes():
                same.append(rel)
            else:
                differ.append(rel)
        self.assertEqual(sorted(differ), sorted(EDITED))
        self.assertEqual(sorted(absent), sorted(ABSENT))
        self.assertNotEqual(same, [])

    def test_the_package_carries_exactly_these_files_beyond_the_scaffold(self):
        """Второй половине фикстуры — посаженному — тоже нужен точный список.

        Список сверяется с `git ls-files`, а не с рабочим деревом. Пока
        мерили деревом, `EXTRA` заявляла `sources/dump.bin`, которого в
        пакете не было ни дня: файл подпадает под `sources/*.bin` в
        `.gitignore` фикстуры, git его не берёт, и свежий клон терял шесть
        тестов. Дерево — то, что лежит у автора; пакет — то, что уезжает.
        """
        from_scaffold = {p.relative_to(SCAFFOLD).as_posix()
                         for p in SCAFFOLD.rglob("*") if p.is_file()}
        prefix = FIXTURE.relative_to(ROOT).as_posix() + "/"
        found = sorted(rel for rel in (name[len(prefix):]
                                       for name in tracked(FIXTURE))
                       if rel not in from_scaffold)
        self.assertEqual(found, sorted(EXTRA))

    def test_the_binary_is_not_decodable_as_text(self):
        """«Игнорируемый бинарь» — свойство, а не украшение: слой формы обязан
        назвать его, не пытаясь прочитать.

        Утверждается о константе, а не о файле на диске: файла в пакете нет,
        и чтение его отсюда и было тем, что делало набор незелёным в клоне.
        """
        with self.assertRaises(UnicodeDecodeError):
            BINARY_BYTES.decode("utf-8")

    def test_the_package_does_not_carry_the_generated_binary(self):
        """Обратная сторона `BINARY`: файл собирается, значит в пакете его
        нет. Сторожит от `git add -f` — единственного хода, которым ловушку
        можно вернуть: у того, кто его сделает, всё зелено, а клон снова
        теряет шесть тестов. Тогда краснеет здесь."""
        self.assertEqual(
            [rel for rel in tracked(FIXTURE) if rel.endswith(".bin")], [])
        self.assertFalse((FIXTURE / BINARY).exists())


class TestMaterialised(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=str(self.root),
                              capture_output=True, text=True, check=True)

    def test_every_pinned_path_carries_the_date_it_was_given(self):
        """Даты приходят из git, а не из файловой системы: чекаут переставляет
        `st_mtime`, и результат начал бы зависеть от того, когда гоняли набор.
        Это буквально мутация, пережившая проверку волны 1."""
        for rel, date in TOUCHED.items():
            out = self.git("log", "-1", "--format=%cs", "--", rel)
            self.assertEqual(out.stdout.strip(), date, rel)

    def test_the_two_empty_collections_sit_on_opposite_sides_of_the_threshold(self):
        self.assertEqual(TOUCHED["projects/stale"], "2026-07-01")
        self.assertEqual(TOUCHED["projects/fresh"], "2026-08-28")
        for rel in ("projects/stale/items", "projects/fresh/items"):
            records = sorted(p.name for p in (self.root / rel).glob("*.md"))
            self.assertEqual(records, [], rel)

    def test_the_ignored_binary_is_ignored_and_present(self):
        """Оба свойства сразу: файл в дереве есть, а git его не несёт. Без
        первого нечего предъявить `unreferenced-ignored-binary`, без второго
        предикат не срабатывает вовсе."""
        out = subprocess.run(["git", "check-ignore", BINARY],
                             cwd=str(self.root), capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertEqual((self.root / BINARY).read_bytes(), BINARY_BYTES)

    def test_the_tree_has_a_history_not_a_single_commit(self):
        """Слой спроса меряет последним коммитом, затронувшим путь. Один
        коммит на всё сделал бы фикстуру слепой к тому, ради чего заведена."""
        out = self.git("rev-list", "--count", "HEAD")
        self.assertGreater(int(out.stdout.strip()), 3)

    def test_nothing_is_left_uncommitted(self):
        """Грязное дерево MAINTAIN читает как след человека и путь не трогает.
        Оставленный без коммита файл фикстуры поэтому не «мелочь»: он снимает
        себя с проверки молча — и снимает вместе с собой то, ради чего положен.

        Проверкой вместо ловящего всё `git add -A` в конце истории: тот
        подобрал бы забытый файл, но стал бы **последним касанием** для его
        пути, а последнее касание — это ровно то, что меряет слой спроса.
        """
        self.assertEqual(self.git("status", "--porcelain").stdout, "")

    def test_the_materialised_tree_matches_the_package_byte_for_byte(self):
        """История собирается через промежуточные состояния (статус Анны до
        и после). Конечное состояние обязано совпасть с тем, что лежит в
        пакете, — иначе фикстура и её история говорят разное."""
        for source in sorted(FIXTURE.rglob("*")):
            if not source.is_file():
                continue
            rel = source.relative_to(FIXTURE).as_posix()
            if rel == DOC:
                self.assertFalse((self.root / rel).exists(), rel)
                continue
            self.assertEqual((self.root / rel).read_bytes(),
                             source.read_bytes(), rel)

    def test_the_registry_record_moved_its_status_between_commits(self):
        """Расхождение архетипа и поведения вычислимо только по двум коммитам:
        `registry` против записи, у которой статус ездил."""
        out = self.git("log", "--format=%H", "--",
                       "core/people/items/anna.md")
        commits = [line for line in out.stdout.split("\n") if line]
        self.assertEqual(len(commits), 2)
        values = []
        for sha in commits:
            blob = self.git("show", "%s:core/people/items/anna.md" % sha)
            values.append([line for line in blob.stdout.split("\n")
                           if line.startswith("status:")][0])
        self.assertEqual(values, ["status: alumni", "status: active"])

    def test_neither_record_without_created_is_unrecoverable_from_git(self):
        """Утверждается дыра, а не свойство. У отслеживаемого файла в дереве
        с чистым `git status` первый коммит есть всегда, поэтому образца
        «created невосстановим из git» здесь нет и быть не может. Тест держит
        это заявление честным: появится такой образец — набор покраснеет,
        и `ЧТО-ПОСАЖЕНО.md` придётся править вместе с ним.
        """
        for name in ("2026-08-25.md", "late-entry.md"):
            rel = "%s/%s" % (JOURNAL, name)
            self.assertNotIn("created:",
                             (self.root / rel).read_text(encoding="utf-8"))
            self.assertNotEqual(dates.created(self.root, rel), dates.UNKNOWN,
                                rel)
