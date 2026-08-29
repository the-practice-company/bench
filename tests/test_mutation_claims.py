"""Утверждения о состязательной оснастке обязаны сходиться с самой оснасткой.

`docs/criteria-coverage.md` — документ, который заявляет, что критерии выхода
волны 1 доказаны: столько-то мутаций посажено, столько-то убито, вот какая
мутация атакует какой критерий. Заявление жило без единой проверки и разошлось
ровно так, как расходится всё непроверяемое: число мутаций отстало на одну,
словарь исходов — на два, а один критерий числился доказанным мутацией,
которую из его строки уже переподписали другой волной.

Мутации здесь **не гоняются**. Прогон копирует дерево на каждую мутацию и
стоит десятки секунд; `./check` обязан оставаться дешёвым настолько, чтобы его
гоняли постоянно. Читаются константы `dev/mutate.py` — они и есть то, с чем
документ обязан совпадать.

**Чего эта проверка не видит: прозу.** Строка может назвать верное имя мутации
и при этом неверно описать, что мутация делает и почему это доказательство.
Такое ловит только читатель. Назвать остаток честно дешевле, чем выдать сверку
имён и чисел за проверку документа целиком.
"""

import collections
import re
import unittest
from pathlib import Path

from dev import mutate

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "criteria-coverage.md"

# Числа записаны цифрами намеренно: их сверяет эта проверка, а прописью
# «семнадцать» она читать не умеет — и именно прописью число простояло
# устаревшим. Меняя формулировку, поменяйте и образец здесь.
CLAIMED_MUTATIONS = re.compile(r"Мутаций в таблице — (\d+)")
CLAIMED_OUTCOMES = re.compile(r"Исходов — (\d+)")
# Строка таблицы критериев: «| 3. The package check shall … | … | … |».
CRITERION_ROW = re.compile(r"^\|\s*(\d+)\.")
QUOTED = re.compile(r"`([^`]+)`")
# Мутации волны 1 подписаны «в1 К<номер>». Мутация, подписанная другой волной,
# в этом документе не числится вовсе: он про критерии выхода волны 1.
WAVE_ONE = re.compile(r"^в1 К(\d+)$")


def wave_one_mutations():
    """Имена мутаций волны 1 по номеру критерия."""
    out = collections.defaultdict(set)
    for mutation in mutate.MUTATIONS:
        match = WAVE_ONE.match(mutation.criterion)
        if match:
            out[match.group(1)].add(mutation.name)
    return out


def _cited(text):
    """Имена мутаций, названные строками таблицы, по номеру критерия."""
    out = collections.defaultdict(set)
    for line in text.split("\n"):
        match = CRITERION_ROW.match(line)
        if not match:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        out[match.group(1)].update(QUOTED.findall(cells[1]))
    return out


def _problems(text):
    """Расхождения документа с `dev/mutate.py`.

    Три сверки, и каждая закрывает утверждение, которое документ делает
    вслух: сколько мутаций посажено, какими словами называются исходы и
    какая мутация атакует какой критерий.
    """
    out = []

    claimed = CLAIMED_MUTATIONS.search(text)
    if claimed is None:
        out.append("нет числа мутаций в форме «Мутаций в таблице — N»")
    elif int(claimed.group(1)) != len(mutate.MUTATIONS):
        out.append("мутаций заявлено %s, в dev/mutate.py — %d"
                   % (claimed.group(1), len(mutate.MUTATIONS)))

    outcomes = CLAIMED_OUTCOMES.search(text)
    if outcomes is None:
        out.append("нет числа исходов в форме «Исходов — N»")
    elif int(outcomes.group(1)) != len(mutate.OUTCOMES):
        out.append("исходов заявлено %s, в dev/mutate.py — %d"
                   % (outcomes.group(1), len(mutate.OUTCOMES)))
    for outcome in mutate.OUTCOMES:
        if outcome not in text:
            out.append("исход «%s» не назван" % outcome)

    cited, real = _cited(text), wave_one_mutations()
    for number in sorted(set(cited) | set(real)):
        for name in sorted(real.get(number, set()) - cited.get(number, set())):
            out.append("критерий %s: мутация «%s» не названа" % (number, name))
        for name in sorted(cited.get(number, set()) - real.get(number, set())):
            out.append("критерий %s: мутации «%s» в dev/mutate.py под этим "
                       "критерием нет" % (number, name))
    return out


def _synthetic():
    """Документ, сходящийся с таблицей мутаций по построению.

    Собирается из тех же констант, чтобы фальсификации ниже проверяли
    проверку, а не устаревали вместе с записанным здесь текстом.
    """
    lines = ["Мутаций в таблице — %d." % len(mutate.MUTATIONS),
             "Исходов — %d: %s." % (len(mutate.OUTCOMES),
                                    ", ".join(mutate.OUTCOMES))]
    real = wave_one_mutations()
    for number in sorted(real):
        lines.append("| %s. критерий | %s | доказан |"
                     % (number, "; ".join("`%s`" % name
                                          for name in sorted(real[number]))))
    return "\n".join(lines)


class TestTheDocumentMatchesTheHarness(unittest.TestCase):
    def test_the_real_document_is_sound(self):
        self.assertEqual(_problems(DOC.read_text(encoding="utf-8")), [])


class TestTheDocumentCannotLie(unittest.TestCase):
    """Проверка, не краснеющая на посаженном расхождении, — не проверка."""

    def test_a_sound_document_has_no_problems(self):
        self.assertEqual(_problems(_synthetic()), [])

    def test_a_stale_mutation_count_is_caught(self):
        text = _synthetic().replace("Мутаций в таблице — %d" % len(mutate.MUTATIONS),
                                    "Мутаций в таблице — %d" % (len(mutate.MUTATIONS) - 1))
        self.assertEqual(len(_problems(text)), 1)

    def test_a_count_spelled_out_in_words_is_not_a_number(self):
        """Прописью — ровно та форма, в которой число и устарело."""
        text = _synthetic().replace("Мутаций в таблице — %d" % len(mutate.MUTATIONS),
                                    "Мутаций в таблице — восемнадцать")
        self.assertEqual(len(_problems(text)), 1)

    def test_a_stale_outcome_count_is_caught(self):
        text = _synthetic().replace("Исходов — %d" % len(mutate.OUTCOMES),
                                    "Исходов — 3")
        self.assertEqual(len(_problems(text)), 1)

    def test_an_unnamed_outcome_is_caught(self):
        text = _synthetic().replace(mutate.ELSEWHERE, "")
        problems = _problems(text)
        self.assertEqual(problems, ["исход «%s» не назван" % mutate.ELSEWHERE])

    def test_a_mutation_missing_from_its_criterion_row_is_caught(self):
        name = mutate.MUTATIONS[0].name
        text = _synthetic().replace("`%s`; " % name, "")
        self.assertEqual(len(_problems(text)), 1)

    def test_a_mutation_cited_under_the_wrong_criterion_is_caught(self):
        """Мутация, переподписанная другой волной, обязана уйти из строки.

        Ровно это и разъехалось: `глоб снова считается конкретным путём`
        числился доказательством критерия 1 волны 1, а доказывает критерий
        волны 3 — битую фикстуру он не меняет вовсе.
        """
        name = mutate.MUTATIONS[0].name
        text = _synthetic() + "\n| 9. чужой критерий | `%s` | доказан |" % name
        self.assertEqual(
            _problems(text),
            ["критерий 9: мутации «%s» в dev/mutate.py под этим критерием нет"
             % name])
