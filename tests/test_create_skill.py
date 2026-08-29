"""Форма скилла CREATE и его эвал на срабатывание.

Проверка пакета уже требует непустого описания, совпадения имени с папкой и
непустого `eval.txt`. Здесь — то, чего она не проверяет: двуязычность фраз
(секция 25, поломка наблюдённая), порядок процедуры и запрет сочинять. Имя
папки повторено намеренно и единственным дублем: на нём держится путь
`SKILL`, по которому читают файлы все остальные тесты набора.
"""

import re
import unittest
from pathlib import Path

from scripts.frontmatter import parse as parse_frontmatter

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "create-context-repo"
CYRILLIC = re.compile(r"[а-яё]", re.I)
# Взять всё разом: `-A`, `--all` и точка как **весь** аргумент. Подстрока
# `"git add ."` красила бы законное: каркас кладёт `.gitignore`,
# `.claude/settings.json` и `.twinkle-repo-builder`, то есть коммит по
# названным путям начинается с точки и содержит запрещённую подстроку
# целиком. Запрет — на аргумент, а не на первый знак пути.
STAGES_EVERYTHING = re.compile(r"git\s+add\s+(?:-A|--all|\.)(?![\w-])")


def _eval_sections():
    """Фразы, по которым скилл обязан подняться, и соседние, по которым нет."""
    sections = {"triggers": [], "non-triggers": []}
    current = None
    for line in (SKILL / "eval.txt").read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            current = line.lstrip("# ").strip()
            continue
        if current in sections:
            sections[current].append(line)
    return sections


class TestSkillForm(unittest.TestCase):
    def setUp(self):
        self.text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.fields = parse_frontmatter(self.text)

    def test_the_name_matches_the_directory(self):
        self.assertEqual(self.fields["name"], SKILL.name)

    def test_the_description_is_english(self):
        """Описание грузится всегда и решает, поднимется ли скилл вообще;
        форма английская — секция 25."""
        self.assertIsNone(CYRILLIC.search(self.fields["description"]))

    def test_it_stays_within_the_form_budget(self):
        """70–180 строк: карта процедуры, не глубина. Схождение измерено
        на трёх репозиториях владельца."""
        self.assertLessEqual(len(self.text.split("\n")), 180)
        self.assertGreaterEqual(len(self.text.split("\n")), 70)

    def test_it_calls_the_installer_through_the_plugin_root(self):
        """Относительный путь разрешится от репозитория пользователя.
        У изученного аналога так молча не работали восемь скиллов."""
        calls = [line for line in self.text.split("\n")
                 if "install_scaffold.py" in line]
        self.assertTrue(calls)
        for line in calls:
            self.assertIn("${CLAUDE_PLUGIN_ROOT}", line)

    def test_it_never_stages_everything(self):
        """`git add -A` заберёт сдвиги сабмодулей knowledge и параллельные
        правки человека в Obsidian. Коммит идёт по названным путям."""
        self.assertEqual(STAGES_EVERYTHING.findall(self.text), [])

    def test_it_puts_git_init_before_the_first_write(self):
        self.assertLess(self.text.index("git init"),
                        self.text.index("install_scaffold.py"))

    def test_it_names_the_three_questions_and_no_more(self):
        """Анкета по восьми зонам отвергнута: она даёт заполненный
        репозиторий, в котором автор не отличает своё от продиктованного."""
        questions = re.findall(r"^\| \d\. (.+?) \|", self.text, re.M)
        self.assertEqual(len(questions), 3)

    def test_it_forbids_generating_the_plausible(self):
        for marker in ("Never generate", "Example Person"):
            self.assertIn(marker, self.text)

    def test_it_sends_what_was_not_obtained_to_open_threads(self):
        """Не в отчёт, исчезающий вместе с сессией."""
        self.assertIn("OPEN-THREADS.md", self.text)

    def test_it_says_what_it_does_not_do(self):
        self.assertIn("## Out of scope", self.text)

    def test_it_states_the_headless_result_as_a_result(self):
        """Форма без брифа — правильный исход, а не отказ."""
        self.assertIn("not a refusal", self.text)


class TestTriggerEval(unittest.TestCase):
    def test_triggers_are_written_in_both_languages(self):
        """Английское описание не ловит русскую просьбу — поломка
        наблюдённая, не гипотеза (секция 25)."""
        triggers = _eval_sections()["triggers"]
        russian = [p for p in triggers if CYRILLIC.search(p)]
        english = [p for p in triggers if not CYRILLIC.search(p)]
        self.assertGreaterEqual(len(russian), 5)
        self.assertGreaterEqual(len(english), 5)

    def test_neighbouring_phrases_that_must_not_raise_it_are_listed(self):
        """Половина эвала без соседних фраз доказывает только, что скилл
        поднимается на всё подряд."""
        self.assertGreaterEqual(len(_eval_sections()["non-triggers"]), 3)

    def test_the_non_triggers_name_the_two_neighbouring_modes(self):
        joined = " ".join(_eval_sections()["non-triggers"]).lower()
        self.assertIn("adopt", joined)
        self.assertIn("maintain", joined)
