"""Утверждения о состязательной оснастке обязаны сходиться с самой оснасткой.

`docs/criteria-coverage.md` — документ, который заявляет, что критерии выхода
доказаны: столько-то мутаций посажено, столько-то убито, вот какая мутация
атакует какой критерий. Заявление жило без единой проверки и разошлось ровно
так, как расходится всё непроверяемое: число мутаций отстало на одну, словарь
исходов — на два, а один критерий числился доказанным мутацией, которую из его
строки уже переподписали другой волной.

За какие волны документ отвечает, он говорит сам — заголовками `## Волна N`.
Список волн внутри этой проверки был бы четвёртым местом, которое надо не
забыть дописать, и забылся бы первым: раздел волны пишет тот, кто закрывает
волну, а тест открывает другой человек и в другой день.

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
# Строка таблицы критериев: «| в1 К3. The package check shall … | … | … |».
# Метка — дословно поле `criterion` таблицы мутаций. Прежде строка начиналась
# просто с номера, и сверка держалась на негласной договорённости, что «3.»
# значит третий критерий волны 1: второй волне в такой форме места нет вовсе.
CRITERION_ROW = re.compile(r"^\|\s*(в\d+ К\d+)\.")
QUOTED = re.compile(r"`([^`]+)`")
# Заголовок раздела волны. Какие волны документ обязан покрывать, читается
# отсюда, а не из списка внутри этой проверки: список пришлось бы дописывать
# той же рукой, которая пишет раздел, и устаревал бы он так же, как устарело
# число мутаций. Мутация волны, у которой раздела нет, здесь не числится —
# ровно так и живёт `в3 К1`, заведённый до раздела своей волны.
SECTION = re.compile(r"^## Волна (\d+)")
WAVE_OF = re.compile(r"^в(\d+) К\d+$")


def _wave(criterion):
    """Номер волны из метки критерия, или None у метки чужой формы."""
    match = WAVE_OF.match(criterion)
    return match.group(1) if match else None


def covered_mutations(waves):
    """Имена мутаций перечисленных волн по метке критерия."""
    out = collections.defaultdict(set)
    for mutation in mutate.MUTATIONS:
        if _wave(mutation.criterion) in waves:
            out[mutation.criterion].add(mutation.name)
    return out


def _cited(text):
    """Имена мутаций, названные строками таблиц, по метке критерия."""
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


def _covered_waves(text, cited):
    """Волны, за которые документ отвечает: свои разделы плюс свои же строки.

    Строки учитываются наравне с разделами, иначе строка волны, у которой
    заголовка нет, читалась бы как выдумка про несуществующую мутацию, а не
    как забытый заголовок.
    """
    waves = {match.group(1) for match in
             (SECTION.match(line) for line in text.split("\n")) if match}
    return waves | {wave for wave in map(_wave, cited) if wave}


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

    cited = _cited(text)
    real = covered_mutations(_covered_waves(text, cited))
    for label in sorted(set(cited) | set(real)):
        for name in sorted(real.get(label, set()) - cited.get(label, set())):
            out.append("критерий %s: мутация «%s» не названа" % (label, name))
        for name in sorted(cited.get(label, set()) - real.get(label, set())):
            out.append("критерий %s: мутации «%s» в dev/mutate.py под этим "
                       "критерием нет" % (label, name))
    return out


def _synthetic():
    """Документ, сходящийся с таблицей мутаций по построению.

    Собирается из тех же констант, чтобы фальсификации ниже проверяли
    проверку, а не устаревали вместе с записанным здесь текстом.
    """
    lines = ["Мутаций в таблице — %d." % len(mutate.MUTATIONS),
             "Исходов — %d: %s." % (len(mutate.OUTCOMES),
                                    ", ".join(mutate.OUTCOMES))]
    every = {_wave(mutation.criterion) for mutation in mutate.MUTATIONS}
    real = covered_mutations(every - {None})
    for label in sorted(real):
        lines.append("| %s. критерий | %s | доказан |"
                     % (label, "; ".join("`%s`" % name
                                         for name in sorted(real[label]))))
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
        text = _synthetic() + "\n| в9 К9. чужой критерий | `%s` | доказан |" % name
        self.assertEqual(
            _problems(text),
            ["критерий в9 К9: мутации «%s» в dev/mutate.py под этим "
             "критерием нет" % name])

    def test_a_wave_without_a_section_is_not_demanded(self):
        """Документ отвечает за те волны, разделы которых в нём есть.

        Иначе мутация, заведённая раньше своего раздела, читалась бы как
        пропущенная строка — и единственным способом позеленеть было бы
        написать раздел про волну, которой ещё нет.
        """
        waves = {_wave(m.criterion) for m in mutate.MUTATIONS} - {None}
        self.assertGreater(len(waves), 1, "нечего исключать: волна одна")
        lonely = sorted(waves)[-1]
        text = "\n".join(line for line in _synthetic().split("\n")
                         if not line.startswith("| в%s К" % lonely))
        self.assertEqual(_problems(text), [])

    def test_a_wave_with_a_section_demands_its_rows(self):
        """Обратная сторона: заголовок раздела и есть взятое обязательство."""
        waves = {_wave(m.criterion) for m in mutate.MUTATIONS} - {None}
        lonely = sorted(waves)[-1]
        text = "\n".join(["## Волна %s" % lonely] +
                         [line for line in _synthetic().split("\n")
                          if not line.startswith("| в%s К" % lonely)])
        self.assertTrue(_problems(text), "снятая строка раздела не замечена")
        self.assertTrue(all("не названа" in problem for problem in _problems(text)),
                        _problems(text))
