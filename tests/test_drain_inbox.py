"""Инвариант «элемент покидает inbox»: четыре исхода за один разбор.

Спека волны, секция `drain-inbox`, требует ровно этого: тест гоняет все
четыре исхода §6 на inbox из четырёх элементов и утверждает, что зона пуста.
Скилл волны был отгружен, а проверки за этим правилом не стояло — то есть
незыблемое №2 не считало его существующим вовсе.

**Зона спрашивается у дерева, а не у отчёта.** Команда, сказавшая
«перенесено», доказательством переноса не является: то же самое написано в
самом скилле. Поэтому пустота читается из файловой системы и из индекса git,
а вторая половина инварианта — «содержимое осталось в истории» — из коммита
«как было», который несёт все четыре захвата.

**Inbox здесь свой, а не общий.** В `fixtures/maintain/inbox/` лежит один
README, и четыре элемента, положенные туда, поехали бы по чужим
утверждениям: у слоя спроса зона перестала бы быть `declared-unused`
(`tests/test_demand.py`, строка зоны и находка), вместе с ней уехал бы
маркер в `CLAUDE.md` (`tests/test_maintain_run.py`), а список `EXTRA`
фикстуры пришлось бы дописывать (`tests/maintain_fixture.py`). Захваты
кладутся в развёрнутую копию, и то же самое доказывается без этой ряби.
Расхождение со спекой — она говорит «фикстурный inbox» — намеренное и
названо в отчёте задачи.

**План покрывает всё дерево, а не одну зону.** `plan.load` считает покрытие
от корня: план, назвавший только inbox, роняет `uncovered-path` на каждый
остальной путь верхнего уровня, и мутация по нему не идёт с кодом 2. Это не
догадка, а утверждение `TestThePlanCoversTheWholeTree` — и отсюда `stay` у
всего, что не разбирается.

**Растворение и отвержение исполняются одной командой, но разными
суждениями.** Механика у обоих — `drop`: элемент уходит из дерева и остаётся
в истории. Различает их то, что растворению предшествует правка существующей
записи, и она утверждается отдельно, — иначе два исхода из четырёх были бы
одним, записанным дважды.

Две правки в разборе принадлежат автору, а не команде, и помечены здесь
`# автор`: впитывание захвата в карточку человека и frontmatter у элемента,
ставшего записью. Открыть блок frontmatter в пакете нечем — `backfill`
дописывает ключ только в уже открытый.
"""

import os
import tempfile
import unittest
from pathlib import Path

from scripts.adopt import drop, init_tree, move, refs, rewrite_refs, tree
from scripts.adopt import plan as adopt_plan
from scripts.findings import EXIT_OK, EXIT_VIOLATION
from scripts.maintain import backfill, field_map
from tests.maintain_fixture import materialise

JOURNAL = "areas/work/journal"
PLAN = "tmp/drain-plan.md"

# Файл, из которого ссылаются на захват. Ссылка нужна не для украшения:
# скилл ставит `find-refs` и `rewrite-refs` **раньше** переноса, потому что
# переписчик читает дерево как оно есть, и уехавший путь он уже не найдёт.
LINKER = "%s/README.md" % JOURNAL
LINK = "[[inbox/2026-08-26-встреча]]"
LINK_LINE = "Захват про эту планёрку лежит в %s." % LINK
MOVED_LINK = "[[%s/items/2026-08-26-встреча]]" % JOURNAL
MOVED_LINK_LINE = "Захват про эту планёрку лежит в %s." % MOVED_LINK

# Четыре захвата — по одному на исход §6. Дата в имени у каждого: §6 её
# гарантирует, и на ней стоит восстановление `created`.
RECORD = "inbox/2026-08-26-встреча.md"
DISSOLVED = "inbox/2026-08-26-про-анну.md"
RAW = "inbox/2026-08-27-расшифровка.md"
REJECTED = "inbox/2026-08-27-черновик.md"

RECORD_TARGET = "%s/items/2026-08-26-встреча.md" % JOURNAL
RAW_TARGET = "sources/2026-08-27-расшифровка.md"

ITEMS = {
    RECORD: "Планёрка 26 августа: разобрали две сделки.\n",
    DISSOLVED: "Анна ушла в августе, в карточке этого ещё нет.\n",
    RAW: "Расшифровка созвона, как пришла.\n",
    REJECTED: "Черновик мысли, ничего за ним нет.\n",
}

ANNA = "core/people/items/anna.md"

# Правка автора, которой «растворилось» отличается от «отвергнуто».
ABSORBED = "Уход подтверждён захватом из inbox, сам захват ушёл в историю."

# Frontmatter записи, которой стал захват. `type` не пишет ни одна команда
# пакета: `backfill` дописывает ключ только в открытый блок, а архетип —
# суждение автора.
FRONTMATTER = "---\ntype: планёрка\n---\n"

# Всё, что не разбирается, несёт зарезервированную цель `stay`: покрытие
# считается от корня, и путь без строки объявил бы план неполным.
STAY = (
    (".claude", "Правила зон, а не элемент inbox."),
    (".gitignore", "Не элемент inbox."),
    (".twinkle-repo-builder", "Метка рецепта."),
    ("CLAUDE.md", "Не элемент inbox."),
    ("OPEN-THREADS.md", "Открытые нити, не элемент inbox."),
    ("areas", "Зона направлений, разбору не подлежит."),
    ("core", "Зона основы, разбору не подлежит."),
    ("decisions", "Зона решений, разбору не подлежит."),
    ("projects", "Зона проектов, разбору не подлежит."),
    ("sources", "Зона сырья, разбору не подлежит."),
    ("tmp", "Черновой каталог, в нём же лежит и сам план."),
    ("vault", "Выгрузки из старого хранилища."),
    ("inbox/README.md", "README зоны, а не элемент в ней."),
)

# Четыре строки разбора, по одной на исход. У растворившегося и отвергнутого
# цель одна — `git-history`; разводит их не она, а основание в теле строки.
TRIAGE = (
    (RECORD, RECORD_TARGET,
     "Стало записью журнала: событие, и дата стоит в имени."),
    (DISSOLVED, "git-history",
     "Растворилось: впитано в карточку Анны, сам захват уходит в историю."),
    (RAW, RAW_TARGET,
     "Сырьё: получено, а не написано."),
    (REJECTED, "git-history",
     "Отвергнуто автором: ценности нет, содержимое остаётся в истории."),
)

# Пути, которые план из одних строк разбора оставляет непокрытыми. Порядок —
# обхода: по имени на каждом уровне, со спуском там, где строка плана лежит
# внутри каталога.
UNCOVERED = (".claude", ".gitignore", ".twinkle-repo-builder", "CLAUDE.md",
             "OPEN-THREADS.md", "areas", "core", "decisions",
             "inbox/README.md", "projects", "sources", "tmp/README.md",
             "vault")


def places(findings):
    return [(f.path, f.line, f.cls, f.detail) for f in findings]


def hits(found):
    """Находки `find-refs` теми же четырьмя полями, что и находки гейтов."""
    return [(hit.path, hit.line, hit.kind, hit.raw) for hit in found]


def _entry(agreed, source, target, why):
    return "- [%s] `%s` -> `%s`\n\n  %s\n" % (
        "x" if agreed else " ", source, target, why)


def plan_text(triage=TRIAGE, stay=STAY):
    """План разбора: шапка, строки `stay`, строки разбора.

    Строка `stay` без крестика — как в скилле: её не исполняет ничто, и
    крестик на ней означал бы согласие на действие, которого нет.
    """
    out = ["# план разбора inbox, снят 2026-08-29\n", "## Что не разбирается\n"]
    out.extend(_entry(False, source, "stay", why) for source, why in stay)
    out.append("## Разбор\n")
    out.extend(_entry(True, source, target, why) for source, target, why in triage)
    return "\n".join(out)


def write_plan(root, text):
    path = Path(root) / PLAN
    path.write_text(text, encoding="utf-8")
    return path


def seed(root):
    """Четыре захвата, ссылка на один из них и коммит, который их несёт.

    Дата коммита пиннится по тому же доводу, что и вся история фикстуры:
    взятая из часов машины, она сделала бы `created`, восстановленный из git,
    зависящим от дня прогона.

    Возвращает номер строки, на которую легла ссылка: `find-refs` обязан
    назвать её, и сверять этот номер глазами с длиной чужого README — тот же
    протухающий номер строки, что уже подводил в CLAUDE.md.
    """
    root = Path(root)
    for rel, text in ITEMS.items():
        (root / rel).write_text(text, encoding="utf-8")
    readme = root / LINKER
    text = readme.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + LINK_LINE + "\n"
    readme.write_text(text, encoding="utf-8")

    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = "2026-08-28T12:00:00+00:00"
    tree.git(root, "add", "-A", "--", "inbox", LINKER)
    tree.git(root, "commit", "-q", "-m", "inbox: четыре захвата", env=env)
    return text.split("\n").index(LINK_LINE) + 1


class TestFourOutcomesOnOneInbox(unittest.TestCase):
    """Все четыре исхода за один разбор, и после него зона пуста.

    Разбор идёт в `setUpClass`, а не в `setUp`: это цепочка мутаций ценой в
    две секунды, а утверждения к ней — чтение. Свой разбор на каждое
    утверждение стоил бы набору лишних двадцати секунд и не разделил бы
    ничего: все они смотрят в один и тот же результат.

    Коды и отчёты шагов складываются в `steps` и утверждаются в тестах, а не
    в `setUpClass`. Отказ шага обязан краснеть в тесте про **свой** исход:
    падение в общей подготовке назвало бы поломкой весь класс сразу и не
    сказало бы, какой из исходов не дошёл.
    """

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.root = materialise(tmp.name)
        cls.link_line = seed(cls.root)

        # Точка отката. Скилл её не называет ни одним шагом, а `rewrite-refs`
        # без неё отказывает: правка ссылок идёт раньше переноса, то есть
        # первой необратимой была бы она. Расхождение вынесено в отчёт задачи.
        cls.init = init_tree.run(cls.root)
        cls.base = tree.read_base(cls.root)
        cls.plan = write_plan(cls.root, plan_text())

        # Ссылки спрашиваются про все четыре пути и **до** переезда: путь,
        # который уже уехал, переписчик не найдёт, а про уходящий в историю
        # ссылок не должно быть вовсе — переписывать их не во что.
        cls.pointing = {rel: hits(refs.find(cls.root, rel)[0])
                        for rel in (RECORD, DISSOLVED, RAW, REJECTED)}
        cls.steps = {}

        # Исход 1: стало записью.
        cls.steps["rewrite-record"] = rewrite_refs.run(
            cls.root, RECORD, RECORD_TARGET, cls.plan)
        cls.steps["move-record"] = move.run(
            cls.root, RECORD, RECORD_TARGET, cls.plan)
        # автор: архетип — его суждение, и блок frontmatter открывает он.
        # Условие спрашивает дерево, а не отчёт переноса, и стоит здесь не
        # ради аккуратности: без него не доехавший элемент валит подготовку
        # исключением, то есть красит весь класс разом вместо того теста,
        # ради которого мутация и посажена. Проверено мутацией.
        record = cls.root / RECORD_TARGET
        if record.exists():
            record.write_text(FRONTMATTER + record.read_text(encoding="utf-8"),
                              encoding="utf-8")
        cls.rows, cls.backfilled = backfill.run(cls.root, JOURNAL, "created")

        # Исход 2: растворилось. Впитывание — правка чужой записи, и делает
        # её автор в диалоге; командой пакета оно не делается ничем.
        anna = cls.root / ANNA
        cls.anna_before = anna.read_text(encoding="utf-8")
        anna.write_text(cls.anna_before.rstrip("\n") + "\n" + ABSORBED + "\n",
                        encoding="utf-8")   # автор
        cls.steps["drop-dissolved"] = drop.run(cls.root, DISSOLVED, cls.plan)

        # Исход 3: это было сырьё.
        cls.steps["rewrite-raw"] = rewrite_refs.run(
            cls.root, RAW, RAW_TARGET, cls.plan)
        cls.steps["move-raw"] = move.run(cls.root, RAW, RAW_TARGET, cls.plan)

        # Исход 4: отвергнуто.
        cls.steps["drop-rejected"] = drop.run(cls.root, REJECTED, cls.plan)

    def text(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def in_base(self, path):
        return tree.git_zlines(self.root, "ls-tree", "-r", "--name-only", "-z",
                               self.base, "--", path)

    def test_the_zone_holds_nothing_but_its_readme(self):
        """Инвариант спеки, и он же — единственная причина этого файла.

        Спрашивается дважды: у файловой системы и у индекса. Один git сказал
        бы «пусто» и про файл, который просто не добавили; одна файловая
        система — про путь, который уехал мимо индекса и оттого невозвратен.
        """
        self.assertEqual(
            sorted(path.relative_to(self.root).as_posix()
                   for path in (self.root / "inbox").rglob("*")),
            ["inbox/README.md"])
        self.assertEqual(
            tree.git_zlines(self.root, "ls-files", "-z", "--", "inbox"),
            ["inbox/README.md"])

    def test_every_triaged_item_stayed_in_the_history(self):
        """Вторая половина инварианта. Элемент, которого нет ни в дереве, ни
        в истории, — та потеря, ради невозможности которой и заведён порядок:
        `drop` отказывает пути, которого нет в `HEAD`."""
        self.assertEqual(sorted(self.in_base("inbox")),
                         [RECORD, DISSOLVED, RAW, REJECTED, "inbox/README.md"])

    def test_the_item_that_became_a_record_lies_in_the_collection(self):
        self.assertEqual(self.steps["move-record"],
                         ("перенесено: `%s` -> `%s`\n" % (RECORD, RECORD_TARGET),
                          EXIT_OK))
        self.assertFalse((self.root / RECORD).exists())
        self.assertEqual(self.text(RECORD_TARGET),
                         "---\ncreated: 2026-08-26\ntype: планёрка\n---\n"
                         + ITEMS[RECORD])

    def test_the_date_of_that_record_came_from_the_name_of_the_file(self):
        """§6 гарантирует дату в имени захвата, и `backfill` предпочитает её
        дате коммита, которым файл внесли: обратный порядок отдал бы записи,
        внесённой задним числом, дату внесения. Список точный и накрывает всю
        коллекцию: `backfill` идёт по ней целиком, а не по одной записи."""
        self.assertEqual(self.rows, [
            ("%s/items/2026-08-25.md" % JOURNAL, "created", "", "2026-08-25",
             "computed", "filename-date"),
            (RECORD_TARGET, "created", "", "2026-08-26",
             "computed", "filename-date"),
            ("%s/items/late-entry.md" % JOURNAL, "created", "", "2026-08-25",
             "computed", "git-first-commit"),
        ])
        self.assertEqual(self.backfilled, "")

    def test_the_item_that_dissolved_left_the_tree_and_its_content_did_not(self):
        """Растворение от отвержения отличает не команда, а то, что впитано:
        карточка Анны несёт фразу захвата, сам захват — в истории."""
        self.assertEqual(self.steps["drop-dissolved"],
                         ("убрано из дерева, осталось в истории: %s\n" % DISSOLVED,
                          EXIT_OK))
        self.assertFalse((self.root / DISSOLVED).exists())
        self.assertEqual(self.text(ANNA),
                         self.anna_before.rstrip("\n") + "\n" + ABSORBED + "\n")
        self.assertEqual(self.in_base(DISSOLVED), [DISSOLVED])

    def test_the_raw_material_lies_in_sources_byte_for_byte(self):
        """«Получено, а не написано»: у сырья меняется место и не меняется
        ни байта содержимого."""
        self.assertEqual(self.steps["move-raw"],
                         ("перенесено: `%s` -> `%s`\n" % (RAW, RAW_TARGET),
                          EXIT_OK))
        self.assertFalse((self.root / RAW).exists())
        self.assertEqual(self.text(RAW_TARGET), ITEMS[RAW])

    def test_the_rejected_item_left_the_tree_and_stayed_in_the_history(self):
        self.assertEqual(self.steps["drop-rejected"],
                         ("убрано из дерева, осталось в истории: %s\n" % REJECTED,
                          EXIT_OK))
        self.assertFalse((self.root / REJECTED).exists())
        self.assertEqual(self.in_base(REJECTED), [REJECTED])

    def test_the_reference_to_the_moved_item_followed_it(self):
        """Ссылки раньше пути. Спрошенные после переезда, они не нашлись бы
        вовсе, и «переписано 0» выглядело бы успехом."""
        self.assertEqual(self.pointing[RECORD],
                         [(LINKER, self.link_line, "wikilink", LINK)])
        table = field_map.name("rewrite-refs", (RECORD, RECORD_TARGET),
                               field_map.REFS)
        self.assertEqual(self.steps["rewrite-record"],
                         ("ссылок переписано: 1\nголых ссылок оставлено: 0\n"
                          "файлов затронуто: 1\nmarkdown-ссылок не тронуто: 0\n"
                          "таблица: %s\n" % table,
                          EXIT_OK))
        # Правка ссылок — массовая мутация и здесь, и таблица её называет
        # поимённо: счётчик «переписано 1» не говорит, что именно.
        self.assertEqual((self.root / table).read_text(encoding="utf-8"),
                         "\n".join([
                             "\t".join(field_map.REF_COLUMNS),
                             "%s\t%d\t%s\t%s\t%s -> %s"
                             % (LINKER, self.link_line, LINK, MOVED_LINK,
                                RECORD, RECORD_TARGET)]) + "\n")
        self.assertEqual(self.text(LINKER).split("\n")[self.link_line - 1],
                         MOVED_LINK_LINE)

    def test_nobody_pointed_at_the_two_items_that_left_for_the_history(self):
        """У ушедшего в историю пути ссылку переписать не во что: цели нет.
        Порядок «ссылки первыми» здесь и нужен — чтобы это было известно до
        удаления, а не после."""
        for rel in (DISSOLVED, REJECTED):
            with self.subTest(item=rel):
                self.assertEqual(self.pointing[rel], [])

    def test_the_rollback_point_stood_before_the_first_irreversible_step(self):
        """Первым необратимым шагом разбора идёт не перенос, а правка ссылок:
        запись в файл не спрашивает git и не возвращается ничем. Поэтому
        точка отката поставлена до неё, и отчёт `init-tree` утверждается
        целиком — «точка отката уже стоит» здесь значило бы, что её ставил
        кто-то другой и неизвестно когда."""
        self.assertEqual(self.init, ("точка отката: %s\n" % self.base, EXIT_OK))

    def test_the_plan_stays_complete_after_the_drain(self):
        """Покрытие считается от дерева, а дерево изменилось: цели
        исполненных переносов покрывают себя сами, иначе план объявлялся бы
        неполным ровно за то, что исполнен."""
        lines, found = adopt_plan.load(self.root, self.plan)
        self.assertEqual(places(found), [])
        self.assertEqual(len(lines), len(STAY) + len(TRIAGE))


class TestThePlanCoversTheWholeTree(unittest.TestCase):
    """Почему в плане разбора стоит дюжина строк про то, что не разбирается.

    Проверено живьём при отгрузке скилла и закреплено здесь: `plan.load`
    гоняет `coverage` по всему дереву, и план из одних строк inbox роняет
    `uncovered-path` на каждый остальной путь верхнего уровня.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)
        seed(self.root)
        self.plan = write_plan(self.root, plan_text(stay=()))

    def test_a_plan_that_names_only_the_inbox_leaves_the_rest_uncovered(self):
        _, found = adopt_plan.load(self.root, self.plan)
        self.assertEqual(places(found), [
            (PLAN, 1, "uncovered-path", "путь не покрыт ни одной строкой: %s" % path)
            for path in UNCOVERED])

    def test_the_move_refuses_to_run_on_such_a_plan(self):
        """Мутация не идёт по плану, который сама же называет сломанным: у
        `move`, `drop` и `rewrite-refs` вход в план один, `plan.load`."""
        report, code = move.run(self.root, RECORD, RECORD_TARGET, self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertEqual(
            sorted(line.rsplit(": ", 1)[1] for line in report.split("\n")
                   if "uncovered-path" in line),
            sorted(UNCOVERED))
        self.assertEqual(report.rstrip("\n").split("\n")[-1],
                         "план не разобран, мутация не идёт")
        self.assertTrue((self.root / RECORD).exists())


class TestTheChainNeedsARollbackPoint(unittest.TestCase):
    """Шаг, которого скилл `drain-inbox` не называет нигде.

    Порядок в скилле начинается с `find-refs` и `rewrite-refs`, а точка
    отката там не упомянута ни в порядке, ни в командах — при том что
    `revert` в командах стоит, а он без неё тоже не работает. Правка ссылок
    без отката отказывается идти, и процедура, записанная в скилле дословно,
    останавливается на втором шаге. Расхождение вынесено в отчёт задачи; тут
    оно закреплено проверкой, чтобы не оставаться словами.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name)
        self.link_line = seed(self.root)
        self.plan = write_plan(self.root, plan_text())

    def test_rewriting_references_refuses_until_the_rollback_point_is_set(self):
        self.assertIsNone(tree.read_base(self.root))
        report, code = rewrite_refs.run(self.root, RECORD, RECORD_TARGET,
                                        self.plan)
        self.assertEqual(code, EXIT_VIOLATION)
        self.assertEqual(report, "отказ: точки отката нет, правка ссылок не "
                                 "идёт: сначала `init-tree`\n")
        # Отказ ничего не написал: ссылка стоит как стояла.
        self.assertEqual(
            (self.root / LINKER).read_text(encoding="utf-8")
            .split("\n")[self.link_line - 1], LINK_LINE)


if __name__ == "__main__":
    unittest.main()
