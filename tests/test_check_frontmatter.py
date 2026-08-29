import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_frontmatter import scan
from tests.test_fixtures import places

ROOT = Path(__file__).resolve().parent.parent
BROKEN = ROOT / "fixtures" / "broken"
GREEN = ROOT / "fixtures" / "green"


def view(folder, group_by_status=True):
    """Текст `views.base`: папка записей и, по желанию, группировка по статусу.

    Вид без `groupBy` нужен ровно затем, чтобы отделить требование архетипа
    от требования вида: пока `status` требовался только потому, что его
    называл вид, конвейерная коллекция с видом-карточками не требовала
    статуса вовсе.
    """
    out = ['filters:\n  and:\n    - file.inFolder("%s")\n' % folder,
           "    - 'type == \"decision\"'\n", "views:\n"]
    if group_by_status:
        out.append("  - type: table\n    groupBy: status\n")
    else:
        out.append("  - type: cards\n")
    return "".join(out)


DECLARATION = ("---\narchetype: pipeline\nvalues:\n  status:\n"
               "    - open\n    - decided\n    - revisited\n---\n# Решения\n")
WHOLE_RECORD = "---\ntype: decision\ncreated: 2026-07-01\nstatus: open\n---\nтело\n"
BARE_RECORD = "---\ntype: decision\n---\nни created, ни status\n"

# Коллекция папок: вид фильтрует зону целиком, записи — README проектов
# уровнем ниже. Единственная раскладка рецепта, где README и объявление,
# и запись лежат под одним фильтром (секция 4, исключение про `projects`).
PROJECTS_DECLARATION = ("---\narchetype: pipeline\nvalues:\n"
                        "  status: [active, paused, done]\n---\n# Проекты\n")
PROJECT_RECORD = ("---\ntype: project\ncreated: 2026-08-29\nstatus: active\n"
                  "description: одна строка\n---\n# alpha\n")


def tree(tmp, files):
    """Дерево из «относительный путь → содержимое». bytes пишутся как есть."""
    root = Path(tmp)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return root


class TestContract(unittest.TestCase):
    def test_green_sample_is_silent(self):
        self.assertEqual(scan(GREEN).counts(), {})

    def test_missing_required_field(self):
        """Три: status у no-status.md плюс created у обеих разобравшихся записей.

        `created` требует стартовый набор секции 2, а не вид, — поэтому
        находка появляется и там, где вид поле не упоминает.
        """
        self.assertEqual(scan(BROKEN).counts().get("missing-required"), 3)

    def test_value_outside_vocabulary(self):
        self.assertEqual(scan(BROKEN).counts().get("value-outside-vocabulary"), 1)

    def test_unparseable_with_consumer_reports_the_line(self):
        report = scan(BROKEN)
        self.assertEqual(report.counts().get("unparseable"), 1)
        line = [f for f in report.findings if f.cls == "unparseable"][0]
        self.assertEqual(line.line, 4)

    def test_perimeter_is_records_of_collections_only(self):
        """core, папки документов и вложения не проверяются вовсе."""
        report = scan(BROKEN)
        touched = {f.path for f in report.findings}
        self.assertTrue(all(p.startswith("decisions/items/") for p in touched), touched)

    def test_field_with_no_consumer_is_silence(self):
        from scripts.check_frontmatter import check_record
        from scripts.basefile import parse_base
        base = parse_base('filters:\n  - file.inFolder("x")\n')
        fields = {"type": "note", "created": "2026-07-01", "случайное": 1}
        self.assertEqual(check_record("x/a.md", fields, base, {}), [])


class TestDeclarationIsNotSwallowed(unittest.TestCase):
    """Отказ разбора README не имеет права стать пустым словарём.

    Блочный список под `values:` — форма панели Properties — ронял разбор,
    гейт ловил `FrontmatterError` и продолжал с `declaration = {}`. Словарь
    коллекции исчезал целиком, а с ним и класс `value-outside-vocabulary`:
    невосстановимое значение подменялось пустым молча (незыблемое №4).
    """

    def test_vocabulary_declared_by_a_block_list_still_judges_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "decisions/README.md": DECLARATION,
                "decisions/views.base": view("decisions/items"),
                "decisions/items/x.md":
                    "---\ntype: decision\ncreated: 2026-07-01\n"
                    "status: НЕТ-ТАКОГО\n---\n",
            })
            self.assertEqual(places(scan(root)), [
                ("decisions/items/x.md", 1, "value-outside-vocabulary",
                 "status='НЕТ-ТАКОГО' вне словаря ['open', 'decided', 'revisited']"),
            ])

    def test_unparseable_declaration_is_a_finding_not_an_empty_vocabulary(self):
        """Парсер расширен, но следующий кривой README всё равно найдётся."""
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "decisions/README.md":
                    "---\narchetype: pipeline\nvalues:\n  status: [open]\n"
                    "policy: |\n  многострочное\n---\n",
                "decisions/views.base": view("decisions/items"),
                "decisions/items/x.md": WHOLE_RECORD,
            })
            self.assertEqual(places(scan(root)), [
                ("decisions/README.md", 5, "unparseable",
                 "блочный скаляр не поддерживается (строка 5)"),
            ])


    def test_duplicate_key_in_a_record_reaches_the_report(self):
        """Побеждала последняя строка, и значение вне словаря исчезало.

        `status: НЕТ-ТАКОГО` перед `status: open` до гейта не доезжал вовсе:
        отчёт был пуст, а запись — «зелёной». Громкий отказ разбора здесь
        и есть починка: чинить строку в файле, а не догадываться за автора.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "decisions/README.md": DECLARATION,
                "decisions/views.base": view("decisions/items"),
                "decisions/items/x.md":
                    "---\ntype: decision\ncreated: 2026-07-01\n"
                    "status: НЕТ-ТАКОГО\nstatus: open\n---\n",
            })
            self.assertEqual(places(scan(root)), [
                ("decisions/items/x.md", 5, "unparseable",
                 "повторный ключ: status (строка 5)"),
            ])


class TestCollectionOwnReadme(unittest.TestCase):
    """README рядом с `views.base` — объявление коллекции, а не её запись.

    Секция 14 дословно: «frontmatter не делает его записью — он лежит уровнем
    выше записей и в виды не попадает». Не попадает, пока вид фильтрует
    `items/`; у коллекции папок фильтр берёт зону целиком, и перечисление
    `rglob` сметает README самой коллекции. Гейт требовал у него `type`,
    `created` и `status` — в каждом инстансе, на файле, который положил
    сам рецепт.

    Послабление ровно на один путь: README, лежащий рядом с тем самым
    `views.base`, чьё перечисление сейчас идёт. `projects/<имя>/README.md`
    остаётся записью — секция 4, единственное место, где README является
    записью: проект одна вещь, и разносить его карточку и его материалы
    по двум местам значит ломать его пополам.
    """

    FILES = {
        "projects/views.base": view("projects"),
        "projects/README.md": PROJECTS_DECLARATION,
        "projects/alpha/README.md": PROJECT_RECORD,
    }

    def _tree(self, tmp, extra=None):
        files = dict(self.FILES)
        files.update(extra or {})
        return tree(tmp, files)

    def test_the_collections_own_readme_is_not_a_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(places(scan(self._tree(tmp))), [])

    def test_a_project_readme_is_still_a_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(tmp, {
                "projects/alpha/README.md":
                    PROJECT_RECORD.replace("created: 2026-08-29\n", ""),
            })
            self.assertEqual(places(scan(root)), [
                ("projects/alpha/README.md", 1, "missing-required",
                 "стартовый набор: поле created"),
            ])

    def test_the_declaration_still_feeds_the_vocabulary(self):
        """Исключение снимает файл с перечисления, но не с чтения словаря."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(tmp, {
                "projects/alpha/README.md":
                    PROJECT_RECORD.replace("status: active", "status: живой"),
            })
            self.assertEqual(places(scan(root)), [
                ("projects/alpha/README.md", 1, "value-outside-vocabulary",
                 "status='живой' вне словаря ['active', 'paused', 'done']"),
            ])

    def test_a_nested_collection_does_not_excuse_the_project_record(self):
        """Послабление привязано к своему виду, а не к соседству с любым.

        Разводит два прочтения правила. «README рядом с каким-нибудь
        `views.base` — не запись» выглядит тем же самым, пока у проекта
        нет своей коллекции: заведи он её — и его карточка перестала бы
        проверяться вовсе, то есть исключение секции 4 отменялось бы
        появлением подпапки.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(tmp, {
                "projects/alpha/views.base": view("projects/alpha/items"),
                "projects/alpha/README.md":
                    PROJECT_RECORD.replace("created: 2026-08-29\n", ""),
            })
            self.assertEqual(places(scan(root)), [
                ("projects/alpha/README.md", 1, "missing-required",
                 "стартовый набор: поле created"),
            ])


class TestRequired(unittest.TestCase):
    def test_present_but_empty_required_field_is_missing(self):
        """Критерий 4 то же самое уже установил для пустой причины.

        `name not in fields or fields[name] is None` пропускал и `""`,
        и `"   "`: обязательное поле удовлетворялось пустотой.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "decisions/README.md": DECLARATION,
                "decisions/views.base": view("decisions/items"),
                "decisions/items/x.md":
                    '---\ntype: "   "\ncreated: ""\nstatus: open\n---\n',
            })
            self.assertEqual(places(scan(root)), [
                ("decisions/items/x.md", 1, "missing-required",
                 "стартовый набор: поле created"),
                ("decisions/items/x.md", 1, "missing-required",
                 "стартовый набор: поле type"),
            ])

    def test_emptied_multivalue_field_is_missing(self):
        """Стёртое свойство Obsidian пишет как `[]`, а не как отсутствие ключа."""
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "decisions/README.md": DECLARATION,
                "decisions/views.base": view("decisions/items"),
                "decisions/items/x.md":
                    "---\ntype: decision\ncreated: 2026-07-01\nstatus: []\n---\n",
            })
            self.assertEqual(places(scan(root)), [
                ("decisions/items/x.md", 1, "missing-required",
                 "стартовый набор: поле status у архетипа pipeline"),
            ])

    def test_pipeline_requires_status_with_no_view_reading_it(self):
        """Правило, записанное в комментарии модуля и не заведённое в коде.

        `status` был обязателен побочным эффектом: его называл `groupBy`.
        Конвейерная коллекция с видом-карточками требования статуса не имела.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "decisions/README.md": DECLARATION,
                "decisions/views.base": view("decisions/items",
                                             group_by_status=False),
                "decisions/items/x.md":
                    "---\ntype: decision\ncreated: 2026-07-01\n---\n",
            })
            self.assertEqual(places(scan(root)), [
                ("decisions/items/x.md", 1, "missing-required",
                 "стартовый набор: поле status у архетипа pipeline"),
            ])

    def test_journal_and_registry_do_not_require_status(self):
        """Секция 5: жизненного цикла у этих записей нет, требовать нечего."""
        for archetype in ("journal", "registry"):
            with self.subTest(archetype=archetype):
                with tempfile.TemporaryDirectory() as tmp:
                    root = tree(tmp, {
                        "journal/README.md": "---\narchetype: %s\n---\n" % archetype,
                        "journal/views.base": view("journal/items",
                                                   group_by_status=False),
                        "journal/items/x.md":
                            "---\ntype: decision\ncreated: 2026-07-01\n---\n",
                    })
                    self.assertEqual(places(scan(root)), [])

    def test_a_view_still_requires_what_it_reads(self):
        """Требование вида не растворилось в требовании архетипа.

        Журнальной коллекции статус не нужен, но вид, который по нему
        группирует, читает поле, — и это по-прежнему причина находки.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "journal/README.md": "---\narchetype: journal\n---\n",
                "journal/views.base": view("journal/items"),
                "journal/items/x.md":
                    "---\ntype: decision\ncreated: 2026-07-01\n---\n",
            })
            self.assertEqual(places(scan(root)), [
                ("journal/items/x.md", 1, "missing-required",
                 "поле status читает вид"),
            ])

    def test_one_field_gives_one_finding_when_both_sources_want_it(self):
        """Конвейер плюс `groupBy: status` — один факт, а не два."""
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "decisions/README.md": DECLARATION,
                "decisions/views.base": view("decisions/items"),
                "decisions/items/x.md": BARE_RECORD,
            })
            self.assertEqual(places(scan(root)), [
                ("decisions/items/x.md", 1, "missing-required",
                 "стартовый набор: поле created"),
                ("decisions/items/x.md", 1, "missing-required",
                 "стартовый набор: поле status у архетипа pipeline"),
            ])


class TestUndecodableFileIsAFinding(unittest.TestCase):
    """Тот же ложный вердикт, что у гейта ссылок, только в значении поля.

    Первый фикс читал с `errors="replace"`, чтобы один байт не уносил отчёт
    целиком (код возврата 1, которого контракт `findings.py` не знает).
    Крах он закрыл и завёл обвинение на пустом месте: `status: op\\xffen`
    доезжал сюда как `op?en`, и гейт объявлял вне словаря значение, которого
    автор не писал. Точно так же портится и `type`, и любое перечислимое
    поле — то есть врал класс, ради которого коллекция объявляет словарь.

    Незыблемое №4: нечитаемый файл уходит в отчёт целиком. Полей у него
    нет — не потому, что они пусты, а потому что читать их неоткуда.
    """

    def _tree(self, tmp):
        return tree(tmp, {
            "decisions/README.md": DECLARATION.encode("utf-8") + b"\xff\n",
            "decisions/views.base": view("decisions/items").encode("utf-8") + b"\xff\n",
            "decisions/items/x.md":
                b"---\ntype: decision\ncreated: 2026-07-01\nstatus: op\xffen\n---\n",
        })

    def test_every_unreadable_file_is_named_and_none_is_judged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(tmp)
            self.assertEqual(places(scan(root)), [
                ("decisions/views.base", 1, "undecodable",
                 "не читается как UTF-8: байт 0xff в позиции 125, "
                 "записи коллекции не проверены"),
            ])

    def test_an_unreadable_record_is_named_under_a_readable_view(self):
        """Вид и объявление целы — тогда видно и запись, и её причину."""
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "decisions/README.md": DECLARATION,
                "decisions/views.base": view("decisions/items"),
                "decisions/items/x.md":
                    b"---\ntype: decision\ncreated: 2026-07-01\nstatus: op\xffen\n---\n",
            })
            self.assertEqual(places(scan(root)), [
                ("decisions/items/x.md", 1, "undecodable",
                 "не читается как UTF-8: байт 0xff в позиции 49, "
                 "поля записи не проверены"),
            ])

    def test_an_unreadable_declaration_leaves_the_records_checked(self):
        """Словаря нет и он назван вслух; обязательные поля судятся дальше."""
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, {
                "decisions/README.md": DECLARATION.encode("utf-8") + b"\xff\n",
                "decisions/views.base": view("decisions/items"),
                "decisions/items/x.md": BARE_RECORD,
            })
            self.assertEqual(places(scan(root)), [
                ("decisions/README.md", 1, "undecodable",
                 "не читается как UTF-8: байт 0xff в позиции 104, "
                 "объявление коллекции не прочитано"),
                ("decisions/items/x.md", 1, "missing-required",
                 "поле status читает вид"),
                ("decisions/items/x.md", 1, "missing-required",
                 "стартовый набор: поле created"),
            ])

    def test_exit_code_stays_within_the_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(tmp)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check_frontmatter.py"),
                 str(root)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("undecodable", result.stdout)


class TestPerimeter(unittest.TestCase):
    """Периметр — тот же, что у гейта ссылок, и импортированный оттуда же.

    `scan` звал `rglob` без единого фильтра, и два гейта расходились в том,
    что считать репозиторием: архив, ради которого исключение и заведено,
    давал стену находок на первом же прогоне ADOPT.
    """

    FILES = {
        "decisions/README.md": DECLARATION,
        "decisions/views.base": view("decisions/items"),
        "decisions/items/x.md": WHOLE_RECORD,
    }

    def _outside(self, prefix, extra=None):
        files = dict(self.FILES)
        files.update({
            prefix + "/decisions/README.md": DECLARATION,
            prefix + "/decisions/views.base": view(prefix + "/decisions/items"),
            prefix + "/decisions/items/old.md": BARE_RECORD,
        })
        files.update(extra or {})
        return files

    def test_archive_is_outside_the_perimeter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, self._outside("archive"))
            self.assertEqual(places(scan(root)), [])

    def test_a_gitignored_subtree_is_outside_the_perimeter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, self._outside("vendor", {".gitignore": "vendor/\n"}))
            self.assertEqual(places(scan(root)), [])

    def test_a_negation_returns_the_subtree_to_the_perimeter(self):
        """Отрицание `.gitignore` сильнее префикса — как в гейте ссылок.

        Отличает импорт периметра от второго `startswith`, написанного здесь.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp, self._outside(
                "vendor", {".gitignore": "vendor/\n!vendor/decisions\n"}))
            self.assertEqual(places(scan(root)), [
                ("vendor/decisions/items/old.md", 1, "missing-required",
                 "стартовый набор: поле created"),
                ("vendor/decisions/items/old.md", 1, "missing-required",
                 "стартовый набор: поле status у архетипа pipeline"),
            ])


if __name__ == "__main__":
    unittest.main()
