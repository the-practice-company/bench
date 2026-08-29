"""Скилл усыновления: он не вправе назвать разрушающую команду по имени.

Проверка пакета держит над ним `destructive-example` — двадцать веток
регулярки, запрещающих в файлах `skills/adopt*/` разрушающие команды. Значит
`revert` в тексте скилла нельзя объяснить через команду git, которую он
заворачивает, и это следствие правильное: скилл называет операции командными
токенами, а знание приходит от механизма, который его держит.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.check_package import DESTRUCTIVE, check
from scripts.frontmatter import parse as parse_frontmatter
from tests.test_create_skill import CYRILLIC, _eval_sections

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "adopt-context-repo"

# Командные токены ADOPT. Скилл называет их, а не команды, которые они
# заворачивают. Список закрытый: команда, которой в скилле нет, для агента не
# существует, а десятая заведена задачей 11 — `merge`.
TOKENS = ("scan-tree", "find-refs", "read-plan", "check-plan", "rewrite-refs",
          "move", "drop", "merge", "revert", "init-tree")


def _findings():
    """Находки проверки пакета о файлах скилла — её собственным кодом.

    Скилл копируется во временный корень: `check` на корне репозитория
    запускает весь набор тестов подпроцессом (`tests-touched-product`), то
    есть этот тест звал бы сам себя и стоил бы минуты. Копия — тот же код и
    те же пути в находках; на настоящем корне проверку целиком прогоняет
    `tests/test_check_package.py::TestThisPackage`.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(SKILL, root / "skills" / SKILL.name)
        return [(f.path, f.line, f.cls, f.detail) for f in check(root).findings]


class TestSkill(unittest.TestCase):
    def setUp(self):
        self.text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    def test_the_package_check_is_silent_about_it(self):
        self.assertEqual(_findings(), [])

    def test_no_line_names_a_destructive_command(self):
        """Разрушающий пример в инструкциях ADOPT рано или поздно исполнят
        буквально. Проверка та же, что у гейта, а не своя копия."""
        offending = [(n, l.strip()) for n, l in
                     enumerate(self.text.split("\n"), start=1)
                     if DESTRUCTIVE.search(l)]
        self.assertEqual(offending, [])

    def test_every_command_token_appears(self):
        missing = [t for t in TOKENS if "`%s`" % t not in self.text]
        self.assertEqual(missing, [])

    def test_every_script_call_goes_through_the_plugin_root(self):
        """Восемь скиллов у изученного аналога звали скрипт относительным
        путём: рабочим каталогом оказывался репозиторий пользователя."""
        calls = [l for l in self.text.split("\n") if "scripts/" in l]
        self.assertTrue(calls)
        self.assertEqual([l for l in calls if "${CLAUDE_PLUGIN_ROOT}" not in l],
                         [])

    def test_the_frontmatter_names_the_skill_after_its_directory(self):
        fields = parse_frontmatter(self.text)
        self.assertEqual(fields.get("name"), "adopt-context-repo")
        self.assertTrue(fields.get("description", "").strip())

    def test_the_description_is_english(self):
        """Описание грузится всегда и решает, поднимется ли скилл вообще;
        форма английская — секция 25."""
        fields = parse_frontmatter(self.text)
        self.assertIsNone(CYRILLIC.search(fields["description"]))

    def test_it_stays_within_the_form_budget(self):
        """70–180 строк, как у скилла создания: карта процедуры, не глубина."""
        self.assertLessEqual(len(self.text.split("\n")), 180)
        self.assertGreaterEqual(len(self.text.split("\n")), 70)

    def test_the_order_of_the_chain_is_stated_and_it_is_this_one(self):
        """Цепочка разведена намеренно: слипшись, она потеряла бы повторную
        входимость. Порядок держит скилл, и он записан."""
        position = [self.text.index("`%s`" % t)
                    for t in ("find-refs", "rewrite-refs", "move")]
        self.assertEqual(position, sorted(position))

    def test_it_names_the_rollback_point_before_the_inventory(self):
        """`init-tree` — первое действие: без точки отката необратимо всё
        остальное, а вес выгрузок показывается автору до коммита."""
        self.assertLess(self.text.index("`init-tree`"),
                        self.text.index("`scan-tree`"))

    def test_it_says_what_it_does_not_do(self):
        """Согласие с вопросом — это согласие с тем, что ответа нет, и
        аллоулист скилл не пишет: причины принадлежат автору."""
        self.assertIn("## What this skill does not do", self.text)
        for marker in ("`?`", ".link-allow"):
            self.assertIn(marker, self.text)

    def test_it_states_that_the_run_does_not_end_on_a_green_gate(self):
        """ADOPT заканчивается измеренным долгом: R не изменилась, число
        находок тяжести `error` не выросло. Зелёный гейт потребовал бы
        сгенерированного аллоулиста, то есть той самой гнили, против которой
        §13 аллоулист и обставляет условиями."""
        self.assertIn("not end with a green gate", self.text)

    def test_it_never_stages_everything(self):
        """`git add -A` кладёт вложенный чужой репозиторий gitlink'ом:
        коммит несёт указатель на объект, которого здесь нет."""
        self.assertEqual(
            [l for l in self.text.split("\n")
             if "add -A" in l or "add --all" in l or "add ." in l], [])


class TestTriggerEval(unittest.TestCase):
    def sections(self):
        return _eval_sections(SKILL)

    def test_triggers_are_written_in_both_languages(self):
        """Английское описание не ловит русскую просьбу — поломка
        наблюдённая, не гипотеза (секция 25)."""
        triggers = self.sections()["triggers"]
        russian = [p for p in triggers if CYRILLIC.search(p)]
        english = [p for p in triggers if not CYRILLIC.search(p)]
        self.assertGreaterEqual(len(russian), 5)
        self.assertGreaterEqual(len(english), 5)

    def test_neighbouring_phrases_that_must_not_raise_it_are_listed(self):
        """Половина эвала без соседних фраз доказывает только, что скилл
        поднимается на всё подряд."""
        self.assertGreaterEqual(len(self.sections()["non-triggers"]), 3)

    def test_the_non_triggers_name_the_two_neighbouring_modes(self):
        joined = " ".join(self.sections()["non-triggers"]).lower()
        self.assertIn("create", joined)
        self.assertIn("maintain", joined)
