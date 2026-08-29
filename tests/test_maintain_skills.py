"""Три скилла волны 5: форма, эвал и периметр разрушающих примеров.

Проверка пакета уже требует непустого описания, совпадения имени с папкой и
живого `eval.txt`. Здесь — то, чего она не проверяет: двуязычность фраз
(секция 25, поломка наблюдённая), английский текст самого скилла (та же
секция: форма — плагин, значит английский) и утверждения, ради которых
каждый из трёх заведён.

Периметр `destructive-example` расширен волной 5 на все мутирующие скиллы,
и следствие для этих трёх ровно то же, что у волны 4: операции называются
командными токенами, а не командами git, которые они заворачивают.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.check_package import DESTRUCTIVE, check
from scripts.frontmatter import parse as parse_frontmatter
from tests.test_create_skill import CYRILLIC, _eval_sections

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

# Три каталога волны. Список закрыт и повторён здесь единственным дублем:
# на нём держатся все проверки набора, а периметр проверки пакета сверяется
# с деревом отдельно (`tests/test_check_package.py`).
NAMES = ("maintain-context-repo", "extend-structure", "drain-inbox")


def _findings(name):
    """Находки проверки пакета о файлах скилла — её собственным кодом.

    Скилл копируется во временный корень: `check` на корне репозитория
    запускает весь набор тестов подпроцессом (`tests-touched-product`), то
    есть этот тест звал бы сам себя и стоил бы минуты.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(SKILLS / name, root / "skills" / name)
        return [(f.path, f.line, f.cls, f.detail) for f in check(root).findings]


def _text(name):
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


class TestEveryOneOfTheThree(unittest.TestCase):
    def test_the_package_check_is_silent_about_each(self):
        for name in NAMES:
            with self.subTest(skill=name):
                self.assertEqual(_findings(name), [])

    def test_no_line_names_a_destructive_command(self):
        """Разрушающий пример в инструкции рано или поздно исполнят
        буквально. Проверка та же, что у гейта, а не своя копия."""
        for name in NAMES:
            with self.subTest(skill=name):
                offending = [(n, line.strip()) for n, line in
                             enumerate(_text(name).split("\n"), start=1)
                             if DESTRUCTIVE.search(line)]
                self.assertEqual(offending, [])

    def test_every_script_call_goes_through_the_plugin_root(self):
        """Восемь скиллов у изученного аналога звали скрипт относительным
        путём: рабочим каталогом оказывался репозиторий пользователя."""
        for name in NAMES:
            with self.subTest(skill=name):
                calls = [line for line in _text(name).split("\n")
                         if "scripts/" in line]
                self.assertTrue(calls, name)
                self.assertEqual(
                    [line for line in calls if "${CLAUDE_PLUGIN_ROOT}" not in line],
                    [])

    def test_the_frontmatter_names_the_skill_after_its_directory(self):
        for name in NAMES:
            with self.subTest(skill=name):
                fields = parse_frontmatter(_text(name))
                self.assertEqual(fields.get("name"), name)
                self.assertTrue(fields.get("description", "").strip())

    def test_the_description_is_english(self):
        """Описание грузится всегда и решает, поднимется ли скилл вообще;
        форма английская — секция 25."""
        for name in NAMES:
            with self.subTest(skill=name):
                fields = parse_frontmatter(_text(name))
                self.assertIsNone(CYRILLIC.search(fields["description"]))

    def test_the_body_is_english_too(self):
        """Секция 25 режет по линии ответственности: форма — плагин, значит
        английский. `SKILL.md` — форма, которую везёт пакет, и два уже
        отгруженных скилла написаны так же. Русским остаётся ровно то, что
        секция называет исключением, — фразы срабатывания."""
        for name in NAMES:
            with self.subTest(skill=name):
                cyrillic = [line.strip() for line in _text(name).split("\n")
                            if CYRILLIC.search(line)]
                self.assertEqual(cyrillic, [])

    def test_each_stays_within_the_form_budget(self):
        """70–180 строк, как у скиллов создания и усыновления: карта
        процедуры, не глубина."""
        for name in NAMES:
            with self.subTest(skill=name):
                lines = _text(name).split("\n")
                self.assertLessEqual(len(lines), 180)
                self.assertGreaterEqual(len(lines), 70)

    def test_each_says_what_it_does_not_do(self):
        for name in NAMES:
            with self.subTest(skill=name):
                self.assertIn("## What this skill does not do", _text(name))

    def test_each_names_the_line_of_responsibility_or_the_author(self):
        """Скилл, не назвавший, где кончаются его права, их не имеет."""
        for name in NAMES:
            with self.subTest(skill=name):
                self.assertIn("author", _text(name))


class TestMaintain(unittest.TestCase):
    def setUp(self):
        self.text = _text("maintain-context-repo")

    def test_it_names_the_mandatory_date(self):
        """Пропущенная в инструкции, она пропущена и в вызове."""
        self.assertIn("--today", self.text)

    def test_it_says_the_date_decides_a_deletion_and_not_the_text(self):
        """Умолчание из системных часов вернуло бы в мутирующий режим
        зависимость, которую волна 1 выкорчёвывала дважды."""
        self.assertIn("system clock", self.text)

    def test_it_states_the_rollback_and_what_the_rollback_spares(self):
        """Откат, забирающий чужую несохранённую правку, — та самая потеря,
        ради предотвращения которой он и заведён."""
        self.assertIn("content-modified", self.text)
        self.assertIn("dirty before the run", self.text)

    def test_it_states_that_it_never_calls_drain_inbox(self):
        """MAINTAIN идёт без присмотра, а разбор inbox — суждение о
        содержимом."""
        self.assertIn("never calls `drain-inbox`", self.text)

    def test_it_refuses_the_three_fixes_that_would_cross_the_line(self):
        for marker in ("unresolved link", "archetype", "`.link-allow`"):
            self.assertIn(marker, self.text)


class TestExtend(unittest.TestCase):
    def setUp(self):
        self.text = _text("extend-structure")

    def test_it_states_the_order_record_before_unit(self):
        """Единственный способ, которым инвариант выполняется механически, —
        не создавать до того."""
        self.assertIn("record first, unit second", self.text.lower())

    def test_it_names_all_four_commands(self):
        for token in ("add-collection", "add-area", "add-view", "backfill"):
            self.assertIn("`%s`" % token, self.text)

    def test_it_names_the_three_outcomes_of_backfill_and_no_fourth(self):
        """Второе перечисление исходов разошлось бы с тем, по которому
        таблица роняет строку."""
        for outcome in ("computed", "synthetic", "deferred"):
            self.assertIn(outcome, self.text)
        self.assertIn("no fourth", self.text)

    def test_it_says_a_refusal_has_written_nothing(self):
        self.assertIn("a refusal has written", self.text)

    def test_it_forbids_inventing_the_first_record(self):
        """Ровно тот запрет, что и у скилла создания: синтетическая запись
        хуже пустой папки, потому что пустая папка честна."""
        self.assertIn("Example Person", self.text)


class TestDrain(unittest.TestCase):
    def setUp(self):
        self.text = _text("drain-inbox")

    def test_it_names_all_four_outcomes(self):
        for outcome in ("became a record", "dissolved", "raw material",
                        "rejected"):
            self.assertIn(outcome, self.text)

    def test_it_states_that_two_of_the_four_need_the_author(self):
        """Без собеседника исполняются два исхода из четырёх, и элемент
        остаётся в inbox. Инвариант §6 этим не нарушен."""
        self.assertIn("two of the four are executed", self.text)
        self.assertIn("stays in the inbox", self.text)

    def test_it_states_the_invariant_as_two_halves_checked_on_the_tree(self):
        """«Элемент покидает inbox» проверяется, а не декларируется: файла
        нет в дереве и он есть в истории."""
        self.assertIn("not in the tree, and it is in\nthe history", self.text)

    def test_the_plan_covers_the_whole_tree_and_the_skill_says_so(self):
        """Разбор плана считает покрытие от корня, а не от разбираемой зоны:
        частичный план роняет `uncovered-path`, и мутация не идёт. Скилл,
        умолчавший об этом, обещал бы процедуру, которая отказывает."""
        self.assertIn("whole tree", self.text)
        self.assertIn("`stay`", self.text)

    def test_it_names_the_order_references_before_the_path(self):
        """Цепочка разведена намеренно: переписчик читает дерево как оно
        есть, и путь, который уже уехал, он больше не найдёт. Порядок
        ищется в разделе порядка, а не по всему тексту: в таблице исходов
        `move` стоит раньше по другой причине — там перечислены механизмы,
        а не шаги."""
        order = self.text[self.text.index("## Order per item"):]
        position = [order.index("`%s`" % token)
                    for token in ("find-refs", "rewrite-refs", "move")]
        self.assertEqual(position, sorted(position))

    def test_it_never_names_the_git_commands_the_tokens_wrap(self):
        """Знание приходит от механизма, который держит скилл: периметр
        разрушающих примеров теперь накрывает и этот каталог."""
        for forbidden in ("git rm", "git mv"):
            self.assertNotIn(forbidden, self.text)


class TestTriggerEval(unittest.TestCase):
    def sections(self, name):
        return _eval_sections(SKILLS / name)

    def test_triggers_are_written_in_both_languages(self):
        """Английское описание не ловит русскую просьбу — поломка
        наблюдённая, не гипотеза (секция 25)."""
        for name in NAMES:
            with self.subTest(skill=name):
                triggers = self.sections(name)["triggers"]
                russian = [p for p in triggers if CYRILLIC.search(p)]
                english = [p for p in triggers if not CYRILLIC.search(p)]
                self.assertGreaterEqual(len(russian), 5)
                self.assertGreaterEqual(len(english), 5)

    def test_neighbouring_phrases_that_must_not_raise_it_are_listed(self):
        """Половина эвала без соседних фраз доказывает только, что скилл
        поднимается на всё подряд."""
        for name in NAMES:
            with self.subTest(skill=name):
                self.assertGreaterEqual(
                    len(self.sections(name)["non-triggers"]), 3)

    def test_the_non_triggers_of_each_name_the_neighbouring_skills(self):
        """Соседи у всех трёх одни и те же, и путают их именно между собой."""
        for name in NAMES:
            with self.subTest(skill=name):
                joined = " ".join(self.sections(name)["non-triggers"]).lower()
                for neighbour in ("create", "adopt"):
                    self.assertIn(neighbour, joined)

    def test_no_skill_lists_a_phrase_that_raises_another_one_of_the_three(self):
        """Фраза, стоящая у одного в триггерах, а у другого — там же,
        доказывает не срабатывание, а спор двух скиллов за один запрос."""
        triggers = {name: {p.lower() for p in self.sections(name)["triggers"]}
                    for name in NAMES}
        for name in NAMES:
            others = set().union(*(triggers[other] for other in NAMES
                                   if other != name))
            self.assertEqual(sorted(triggers[name] & others), [], name)


if __name__ == "__main__":
    unittest.main()
