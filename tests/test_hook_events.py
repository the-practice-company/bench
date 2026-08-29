import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIM = ROOT / "hooks" / "hook.sh"


def make_repo(base):
    """Настоящий git-репозиторий с восемью зонами и маркером рецепта.

    Фикстура собирается, а не лежит в дереве: восемь пустых каталогов git
    всё равно не хранит, а `git init` подпроцессом не приносит зависимостей.
    """
    root = Path(base) / "repo"
    for zone in ("core", "areas", "projects", "knowledge",
                 "inbox", "sources", "tmp", "decisions"):
        (root / zone).mkdir(parents=True)
    (root / ".twinkle-repo-builder").write_text('{"version": "1"}',
                                                encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    return root


def commit_all(root):
    """Довести фикстуру до чистого дерева.

    Свежий `git init` чистым деревом не является: маркер рецепта лежит
    неотслеженным, и `git status --porcelain` непуст ещё до того, как хук
    что-нибудь сделал. Проверять на такой фикстуре «запись не пачкает дерево»
    нечем — она не отличит «не пачкает» от «уже грязно».

    Личность коммиттера передаётся флагами: глобальный `user.email` в среде
    прогона может быть не настроен, и тогда `git commit` падает не по делу.
    """
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "-m", "фикстура"], cwd=str(root), check=True)


def call(event, payload, cwd):
    """Хук всегда прогоняется настоящим подпроцессом.

    Вызов обработчика напрямую не проверяет ни шим, ни код возврата, ни
    разбор stdin — то есть ровно то, что ломается на практике.
    """
    return subprocess.run([str(SHIM), event], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=str(cwd))


class TestPreToolUseWrite(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _payload(self, path, field="file_path"):
        return {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                "tool_name": "Write", "tool_input": {field: str(path)}}

    def test_write_outside_root_is_blocked_and_names_the_boundary(self):
        outside = Path(self._tmp.name) / "elsewhere.md"
        result = call("PreToolUse", self._payload(outside), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("граница", result.stderr)
        self.assertIn(str(outside), result.stderr)

    def test_write_inside_root_passes_silently(self):
        result = call("PreToolUse", self._payload(self.root / "core" / "me.md"),
                      self.root)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr.strip(), "")

    def test_rewrite_in_core_warns_but_does_not_block(self):
        """Долгоживущий слой: предупреждение, не блок. Записи в `core` —
        содержимое, и автор в нём хозяин (линия ответственности)."""
        target = self.root / "core" / "me.md"
        target.write_text("уже есть\n", encoding="utf-8")
        result = call("PreToolUse", self._payload(target), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("core", result.stderr)

    def test_rewrite_in_add_only_zone_warns(self):
        """`inbox` и `decisions` — только для добавления, но у автора может
        быть причина. Предупреждение, а не блок: строка таблицы секции 15,
        отличная от строки про `sources`."""
        target = self.root / "inbox" / "note.md"
        target.write_text("уже есть\n", encoding="utf-8")
        result = call("PreToolUse", self._payload(target), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("inbox", result.stderr)

    def test_rewrite_in_sources_is_blocked(self):
        """Неизменяемость `sources` держит доказуемость всего производного:
        поправленный задним числом транскрипт делает недоказуемым каждый
        вывод, который на него ссылается. Это поломка, а не конвенция."""
        target = self.root / "sources" / "call.md"
        target.write_text("как получено\n", encoding="utf-8")
        result = call("PreToolUse", self._payload(target), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("sources", result.stderr)

    def test_new_file_in_sources_is_allowed(self):
        """Зона только для добавления: запрещена правка, не появление."""
        result = call("PreToolUse",
                      self._payload(self.root / "sources" / "new.md"), self.root)
        self.assertEqual(result.returncode, 0)

    def test_unparsed_tool_input_is_visible_and_not_a_block(self):
        """Имена полей `tool_input` не документированы. Не нашёлся путь —
        видимая строка и код 0: блокировать по собственной слепоте нельзя,
        молча пропускать тоже (незыблемое №4)."""
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                   "tool_name": "Write", "tool_input": {"неизвестно": 1}}
        result = call("PreToolUse", payload, self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("путь не разобран", result.stderr)

    def test_notebook_field_is_read_from_the_same_closed_list(self):
        """Матчер везёт `NotebookEdit`, а поле пути у него своё. Закрытый
        список кандидатов существует ровно ради этого случая: имя поля не
        угадывается по одному образцу."""
        target = self.root / "sources" / "call.ipynb"
        target.write_text("{}\n", encoding="utf-8")
        result = call("PreToolUse",
                      self._payload(target, field="notebook_path"), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("sources", result.stderr)


class TestPreToolUsePathTricks(unittest.TestCase):
    """Пути, на которых наивная проверка границы даёт неверный ответ.

    Каждый случай — не гипотеза о вводе, а способ, которым проверка,
    сравнивающая строки или доверяющая своему рабочему каталогу, промахивается
    мимо реального нарушения либо блокирует законную запись.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _payload(self, path):
        return {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                "tool_name": "Write", "tool_input": {"file_path": str(path)}}

    def test_symlink_out_of_root_is_blocked(self):
        """Симлинк наружу — дыра в границе размером с файловую систему.
        Модуль границы её закрывает; тест доказывает, что обработчик зовёт
        именно его, а не своё сравнение."""
        target = Path(self._tmp.name) / "outside"
        target.mkdir()
        (self.root / "escape").symlink_to(target)
        result = call("PreToolUse",
                      self._payload(self.root / "escape" / "x.md"), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("граница", result.stderr)

    def test_dotdot_detour_into_sources_is_still_sources(self):
        """Зона считается после нормализации: `areas/../sources/call.md` —
        это `sources`. Иначе обход неизменяемости стоит четырёх символов."""
        target = self.root / "sources" / "call.md"
        target.write_text("как получено\n", encoding="utf-8")
        detour = self.root / "areas" / ".." / "sources" / "call.md"
        result = call("PreToolUse", self._payload(detour), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("неизменяема", result.stderr)

    def test_relative_path_is_resolved_against_the_event_cwd(self):
        """Рабочий каталог процесса хука не документирован.

        Относительный путь в `tool_input` осмыслен только относительно `cwd`
        события — каталога, в котором работает агент. Разрешать его средствами
        процесса значит вернуть `os.getcwd()` через чёрный ход: подпроцесс здесь
        запущен снаружи репозитория, и наивная нормализация объявит законную
        запись в `core` выходом за границу.
        """
        result = call("PreToolUse", self._payload("core/me.md"),
                      cwd=self._tmp.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.strip(), "")

    def test_tilde_is_read_as_the_home_directory(self):
        """`~/...` — не относительный путь, а домашний каталог.

        Приклеенный к корню, он даёт несуществующее `<корень>/~/...`, лежащее
        внутри границы, — и запись в домашний каталог проходит молча. Дыра
        в незыблемом №6 ценой одного символа; инструменты, раскрывающие
        тильду, пишут именно домой.
        """
        result = call("PreToolUse", self._payload("~/.ssh/authorized_keys"),
                      self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("граница", result.stderr)

    def test_relative_path_escaping_the_root_is_still_blocked(self):
        """Обратная сторона того же: относительный путь наружу — нарушение,
        и считается оно от `cwd` события, а не от каталога процесса."""
        result = call("PreToolUse", self._payload("../elsewhere.md"),
                      cwd=self._tmp.name)
        self.assertEqual(result.returncode, 2)
        self.assertIn("граница", result.stderr)

    def test_relative_path_into_sources_is_blocked_as_sources(self):
        """Причина отказа обязана называть настоящую поломку. Относительный
        путь, посчитанный от чужого каталога, даёт «граница» вместо
        «неизменяемый источник» — верный код при неверном объяснении, а
        имя зоны в тексте приходит из самого пути и потому ничего не
        подтверждает."""
        (self.root / "sources" / "call.md").write_text("как получено\n",
                                                       encoding="utf-8")
        result = call("PreToolUse", self._payload("sources/call.md"),
                      cwd=self._tmp.name)
        self.assertEqual(result.returncode, 2)
        self.assertIn("неизменяема", result.stderr)
        self.assertNotIn("граница", result.stderr)


class TestPreToolUseDegradation(unittest.TestCase):
    """Случаи, где хук не может судить. Все они обязаны быть кодом 0 плюс
    видимой строкой: «не смог» никогда не выглядит ни запретом, ни разрешением."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_repo_without_marker_is_visible_and_not_a_block(self):
        """Маркера нет — корень неизвестен, и подставлять вместо него рабочую
        папку нельзя (незыблемое №4). Ни блока, ни тишины."""
        (self.root / ".twinkle-repo-builder").unlink()
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                   "tool_name": "Write",
                   "tool_input": {"file_path": str(self.root / "core" / "me.md")}}
        result = call("PreToolUse", payload, self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("корень", result.stderr)

    def test_tool_input_of_the_wrong_shape_is_visible_and_not_a_block(self):
        """Не документировано и имя поля, и форма самого `tool_input`.

        Пришло не отображение — судить не о чем, и сказать об этом обязана та
        же строка, что и о ненайденном поле. Обвал с трассировкой контракт
        не нарушает (шим переводит его в код 0 с причиной), но говорит про
        строку hook.py вместо того, что случилось со входом.
        """
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                   "tool_name": "Write", "tool_input": ["core/me.md"]}
        result = call("PreToolUse", payload, self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("путь не разобран", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_write_in_knowledge_is_not_judged_here(self):
        """`knowledge/*/**` закрыт раньше и статически, через `permissions.deny`
        целевого репозитория. Дублировать статику динамикой — заводить второй
        источник истины, который разойдётся с первым."""
        target = self.root / "knowledge" / "foreign" / "README.md"
        target.parent.mkdir()
        target.write_text("чужой сабмодуль\n", encoding="utf-8")
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                   "tool_name": "Write", "tool_input": {"file_path": str(target)}}
        result = call("PreToolUse", payload, self.root)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr.strip(), "")

    def test_project_dir_env_is_the_fallback_for_a_missing_cwd(self):
        """`cwd` приходит в нагрузке, но полагаться на его наличие нечем:
        запасной источник корня — переменная окружения, а не рабочий каталог
        процесса."""
        environ = dict(os.environ)
        environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Write",
                   "tool_input": {"file_path": str(Path(self._tmp.name) / "x.md")}}
        result = subprocess.run([str(SHIM), "PreToolUse"],
                                input=json.dumps(payload), capture_output=True,
                                text=True, cwd=str(self.root), env=environ)
        self.assertEqual(result.returncode, 2)
        self.assertIn("граница", result.stderr)


class TestPreToolUseBash(unittest.TestCase):
    """Ветка Bash: `hooks.json` возит на неё матчер `Bash` отдельным событием.

    Пока в диспетчере не было такой записи, весь сканер команд был мёртвым
    кодом: событие приезжало, не находило обработчика и получало «не
    обслуживается» с кодом 0 — то есть голый `mv` проходил, а строка отказа
    рассказывала про диспетчер, а не про перемещение.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _payload(self, command, **extra):
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                   "tool_name": "Bash", "tool_input": {"command": command}}
        payload.update(extra)
        return payload

    def test_a_bare_mv_is_blocked_and_names_the_right_path(self):
        result = call("PreToolUseBash", self._payload("mv core/me.md core/other.md"),
                      self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("перемещение", result.stderr)
        self.assertIn("find-refs", result.stderr)

    def test_a_write_into_the_tree_by_redirect_is_blocked(self):
        """Сканер судит не только о `mv`: перенаправление в дерево контента
        идёт мимо гейтов и мимо списка файлов хода."""
        result = call("PreToolUseBash", self._payload("echo x > core/me.md"),
                      self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("мимо гейтов", result.stderr)

    def test_a_harmless_command_passes_silently(self):
        result = call("PreToolUseBash", self._payload("ls core"), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr.strip(), "")

    def test_a_missing_command_field_is_visible_and_not_a_block(self):
        """Поля нет — судить не о чем. Блок по неразобранному вводу был бы
        блоком по собственной слепоте (незыблемое №4)."""
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                   "tool_name": "Bash", "tool_input": {"неизвестно": 1}}
        result = call("PreToolUseBash", payload, self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("команда не разобрана", result.stderr)

    def test_a_command_that_is_not_a_string_is_visible_and_not_a_block(self):
        result = call("PreToolUseBash", self._payload(["mv", "a", "b"]), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("команда не разобрана", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class TestZoneCase(unittest.TestCase):
    """Зона выводится из первого сегмента пути, и регистр этот вывод ломал.

    `realpath` на macOS регистр не приводит: `SOURCES/x.md` пишет тот же
    inode, что `sources/x.md`, но зоной не считался — обработчик уходил
    в молчаливую ветку «вне зон». Тем же движением портился список файлов
    хода: git индексирует `sources/x.md`, а записано было `SOURCES/x.md`,
    и `Stop` считал бы правку агента чужой.

    На файловой системе, различающей регистр, тот же путь — действительно
    другой файл, и утверждение здесь другое: тест проверяет обе развилки,
    а не пропускает себя.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _blind_to_case(self):
        return (self.root / "SOURCES").exists()

    def test_an_immutable_zone_reached_in_another_case_is_still_blocked(self):
        (self.root / "sources" / "x.md").write_text("как получено\n",
                                                    encoding="utf-8")
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                   "tool_name": "Write",
                   "tool_input": {"file_path": str(self.root / "SOURCES" / "x.md")}}
        result = call("PreToolUse", payload, self.root)
        if self._blind_to_case():
            self.assertEqual(result.returncode, 2)
            self.assertIn("неизменяема", result.stderr)
        else:
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr.strip(), "")

    def test_a_long_lived_zone_in_another_case_still_warns(self):
        (self.root / "core" / "me.md").write_text("уже есть\n", encoding="utf-8")
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                   "tool_name": "Write",
                   "tool_input": {"file_path": str(self.root / "CORE" / "me.md")}}
        result = call("PreToolUse", payload, self.root)
        self.assertEqual(result.returncode, 0)
        if self._blind_to_case():
            self.assertIn("core", result.stderr)
        else:
            self.assertEqual(result.stderr.strip(), "")

    def test_the_recorded_path_is_spelled_the_way_git_indexes_it(self):
        from hooks import turnfiles
        (self.root / "areas" / "a.md").write_text("текст\n", encoding="utf-8")
        payload = {"hook_event_name": "PostToolUse", "cwd": str(self.root),
                   "session_id": "s1", "tool_name": "Write",
                   "tool_input": {"file_path": str(self.root / "AREAS" / "a.md")}}
        call("PostToolUse", payload, self.root)
        expected = "areas/a.md" if self._blind_to_case() else "AREAS/a.md"
        self.assertEqual(turnfiles.listing(self.root, "s1"), [expected])


class TestNestedRepoBoundary(unittest.TestCase):
    """`knowledge/` держит чужие репозитории по построению, и ход, чей `cwd`
    оказался внутри одного из них, не имеет права терять границу."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        self.vendor = self.root / "knowledge" / "vendor"
        self.vendor.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(self.vendor), check=True)
        self.addCleanup(self._tmp.cleanup)

    def test_a_write_outside_the_root_is_blocked_from_inside_a_submodule(self):
        outside = Path(self._tmp.name) / "elsewhere.md"
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.vendor),
                   "tool_name": "Write", "tool_input": {"file_path": str(outside)}}
        result = call("PreToolUse", payload, self.vendor)
        self.assertEqual(result.returncode, 2)
        self.assertIn("граница", result.stderr)


class TestResidualRisks(unittest.TestCase):
    """Названный остаточный риск — то, чем бэкстоп отличается от притворной
    песочницы. Регистр взят у `bashscan.UNCATCHABLE`, и проверяется он так же:
    запись обязана быть на месте, иначе следующий читатель сочтёт дыру
    недосмотром."""

    def test_a_hard_link_out_of_sources_is_named(self):
        """`realpath` разворачивает символические ссылки и не видит жёстких:
        два имени ведут в один inode, и правка `core/alias.md` пишет inode
        источника, получая обычное предупреждение `core`. Механизма против
        этого нет намеренно — искать второе имя inode значит обходить дерево
        на каждой записи."""
        from hooks import hook
        self.assertIn("жёсткая ссылка", hook.on_pre_tool_use.__doc__)

    def test_the_cost_of_filtering_findings_is_named(self):
        """Фильтр по записанному файлу выбрасывает ровно тот файл, который
        находку вызвал: новый `areas/dup.md` делает неоднозначным `[[dup]]`
        в `core/me.md`, и об этом не будет сказано. Решение оставлено, цена
        записана."""
        from hooks import hook
        self.assertIn("вызвавший", hook.on_post_tool_use.__doc__)


class TestTurnFiles(unittest.TestCase):
    """Список файлов хода не имеет права делать дерево грязным: незакоммиченное
    по решению секции 8 означает «здесь работал человек», и `SessionStart`
    с `Stop` оба стоят на этой разводке."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_recorded_path_survives_between_calls(self):
        from hooks import turnfiles
        turnfiles.record(self.root, "s1", "areas/a.md")
        turnfiles.record(self.root, "s1", "areas/b.md")
        self.assertEqual(turnfiles.listing(self.root, "s1"),
                         ["areas/a.md", "areas/b.md"])

    def test_sessions_do_not_mix(self):
        from hooks import turnfiles
        turnfiles.record(self.root, "s1", "areas/a.md")
        self.assertEqual(turnfiles.listing(self.root, "s2"), [])

    def test_recording_does_not_dirty_the_tree(self):
        from hooks import turnfiles
        commit_all(self.root)
        turnfiles.record(self.root, "s1", "areas/a.md")
        status = subprocess.run(["git", "status", "--porcelain"],
                                cwd=str(self.root), capture_output=True, text=True)
        self.assertEqual(status.stdout.strip(), "")

    def test_missing_list_degrades_to_empty_not_to_error(self):
        """Потеря файла ослабляет Stop до «считать все файлы чужими» —
        то есть до сообщения вместо блока. Ослабление, а не поломка."""
        from hooks import turnfiles
        self.assertEqual(turnfiles.listing(self.root, "не было такой"), [])

    def test_the_same_path_twice_is_listed_once(self):
        """Ход из Write и двух Edit по одному файлу — обычный ход, а не
        исключение. Список хода отвечает на вопрос «какие файлы тронуты»,
        и повтор в нём умножил бы и `git add` чекпоинта, и сообщения `Stop`
        на число правок."""
        from hooks import turnfiles
        turnfiles.record(self.root, "s1", "areas/a.md")
        turnfiles.record(self.root, "s1", "areas/b.md")
        turnfiles.record(self.root, "s1", "areas/a.md")
        self.assertEqual(turnfiles.listing(self.root, "s1"),
                         ["areas/a.md", "areas/b.md"])

    def test_session_id_with_separators_stays_one_file_inside_git(self):
        """`session_id` приходит снаружи и в имя файла попадает целиком.
        Разделитель пути в нём увёл бы запись из `.git/` — то есть за
        границу, которую держит незыблемое №6."""
        from hooks import turnfiles
        turnfiles.record(self.root, "../../s1", "areas/a.md")
        written = [p.name for p in (self.root / ".git").iterdir()
                   if p.name.startswith("twinkle-turn")]
        self.assertEqual(len(written), 1, written)
        self.assertEqual(turnfiles.listing(self.root, "../../s1"), ["areas/a.md"])

    def test_recording_without_git_reports_instead_of_returning_silently(self):
        """`.git/` может не быть. Молча не записать — заглушка (незыблемое
        №4): `Stop` тогда сочтёт чужим всё, что агент только что написал,
        и не скажет почему."""
        from hooks import turnfiles
        import shutil
        shutil.rmtree(self.root / ".git")
        self.assertFalse(turnfiles.record(self.root, "s1", "areas/a.md"))

    def test_a_git_file_pointer_is_followed(self):
        """У сабмодуля и у рабочего дерева git `.git` — файл со строкой
        `gitdir:`, а не каталог.

        Проверка «родитель цели существует» на таком файле истинна, и запись
        падала `NotADirectoryError` — то есть весь `PostToolUse` умирал вместе
        с отчётом гейтов по только что записанному файлу.
        """
        from hooks import turnfiles
        import shutil
        real = Path(self._tmp.name) / "real"
        shutil.move(str(self.root / ".git"), str(real))
        (self.root / ".git").write_text("gitdir: ../real\n", encoding="utf-8")
        self.assertTrue(turnfiles.record(self.root, "s1", "areas/a.md"))
        self.assertEqual(turnfiles.listing(self.root, "s1"), ["areas/a.md"])
        written = [p.name for p in real.iterdir()
                   if p.name.startswith("twinkle-turn")]
        self.assertEqual(len(written), 1, written)

    def test_an_absolute_git_pointer_is_followed(self):
        """Рабочее дерево git пишет указатель абсолютным путём, сабмодуль —
        относительным. Обе формы обязаны читаться."""
        from hooks import turnfiles
        import shutil
        real = Path(self._tmp.name) / "real"
        shutil.move(str(self.root / ".git"), str(real))
        (self.root / ".git").write_text("gitdir: %s\n" % real, encoding="utf-8")
        self.assertTrue(turnfiles.record(self.root, "s1", "areas/a.md"))

    def test_a_broken_git_pointer_degrades_instead_of_crashing(self):
        """Указатель, который никуда не ведёт, — это уже описанное ослабление,
        а не обвал: `False`, названная строка и отчёт гейтов на месте."""
        from hooks import turnfiles
        import shutil
        shutil.rmtree(self.root / ".git")
        (self.root / ".git").write_text("gitdir: ../нет-такого\n",
                                        encoding="utf-8")
        self.assertFalse(turnfiles.record(self.root, "s1", "areas/a.md"))
        self.assertEqual(turnfiles.listing(self.root, "s1"), [])


class TestPostToolUse(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _payload(self, path, **extra):
        payload = {"hook_event_name": "PostToolUse", "cwd": str(self.root),
                   "session_id": "s1", "tool_name": "Write",
                   "tool_input": {"file_path": str(path)}}
        payload.update(extra)
        return payload

    def _broken(self, name="broken.md"):
        target = self.root / "areas" / name
        target.write_text("[[нет такой цели]]\n", encoding="utf-8")
        return target

    def test_findings_are_limited_to_the_written_file(self):
        """Индекс строится по всему дереву, иначе unresolved неотличим от
        «цель есть, но её не просканировали». В отчёт идёт только записанный."""
        (self.root / "areas" / "broken.md").write_text(
            "[[нет такой цели]]\n", encoding="utf-8")
        (self.root / "areas" / "other.md").write_text(
            "[[и такой нет]]\n", encoding="utf-8")
        payload = {"hook_event_name": "PostToolUse", "cwd": str(self.root),
                   "session_id": "s1", "tool_name": "Write",
                   "tool_input": {"file_path": str(self.root / "areas" / "broken.md")}}
        result = call("PostToolUse", payload, self.root)
        self.assertIn("areas/broken.md", result.stderr)
        self.assertNotIn("areas/other.md", result.stderr)

    def test_a_link_to_a_file_elsewhere_in_the_tree_resolves(self):
        """Обратная сторона того же решения, и она несущая.

        Фильтр стоит после разбора, а не вместо него: индекс ссылок строится
        по всему дереву. Сузить сам разбор до записанного файла — сделать
        `unresolved` неотличимым от «цель есть, но её не просканировали»,
        и тогда каждая законная ссылка наружу файла становится находкой.
        """
        (self.root / "core" / "me.md").write_text("я\n", encoding="utf-8")
        target = self.root / "areas" / "uses-core.md"
        target.write_text("[[me]]\n", encoding="utf-8")
        result = call("PostToolUse", self._payload(target), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr.strip(), "")

    def test_findings_do_not_block(self):
        """`PostToolUse` сообщает, а не запрещает: файл уже записан, и код 2
        после факта был бы театром. Блокирует `Stop`."""
        result = call("PostToolUse", self._payload(self._broken()), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("unresolved", result.stderr)

    def test_a_clean_file_says_nothing(self):
        target = self.root / "areas" / "clean.md"
        target.write_text("просто текст\n", encoding="utf-8")
        result = call("PostToolUse", self._payload(target), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr.strip(), "")

    def test_the_written_path_is_recorded_relative_to_the_root(self):
        """Список хода переживает вызов инструмента, потому что лежит на диске.
        Записанный путь относителен корню: `Stop` сверяет его с выводом
        `git status`, а тот абсолютных путей не печатает."""
        from hooks import turnfiles
        call("PostToolUse", self._payload(self._broken()), self.root)
        self.assertEqual(turnfiles.listing(self.root, "s1"), ["areas/broken.md"])

    def test_the_same_file_written_twice_is_recorded_once(self):
        from hooks import turnfiles
        target = self._broken()
        call("PostToolUse", self._payload(target), self.root)
        call("PostToolUse", self._payload(target), self.root)
        self.assertEqual(turnfiles.listing(self.root, "s1"), ["areas/broken.md"])

    def test_relative_tool_path_is_resolved_against_the_event_cwd(self):
        """Рабочий каталог процесса хука не документирован.

        Относительный путь в `tool_input` осмыслен только относительно `cwd`
        события. Нормализация средствами процесса вернула бы `os.getcwd()`
        через чёрный ход: подпроцесс здесь запущен снаружи репозитория, и
        записанным в список хода оказался бы путь, которого в репозитории нет,
        а находки по файлу не нашлись бы вовсе.
        """
        from hooks import turnfiles
        self._broken()
        result = subprocess.run(
            [str(SHIM), "PostToolUse"],
            input=json.dumps(self._payload("areas/broken.md")),
            capture_output=True, text=True, cwd=self._tmp.name)
        self.assertEqual(result.returncode, 0)
        self.assertIn("areas/broken.md", result.stderr)
        self.assertEqual(turnfiles.listing(self.root, "s1"), ["areas/broken.md"])

    def test_path_outside_the_root_is_named_and_not_recorded(self):
        """Записать наружный путь в список хода — зарядить чекпоинт `Stop`
        на `git add` за границей корня (незыблемое №6). Судить о нём нечем:
        гейты сканируют репозиторий, а файл лежит не в нём."""
        from hooks import turnfiles
        outside = Path(self._tmp.name) / "elsewhere.md"
        outside.write_text("[[нет такой цели]]\n", encoding="utf-8")
        result = call("PostToolUse", self._payload(outside), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("вне корня", result.stderr)
        self.assertEqual(turnfiles.listing(self.root, "s1"), [])

    def test_missing_root_is_visible_and_not_a_block(self):
        (self.root / ".twinkle-repo-builder").unlink()
        result = call("PostToolUse", self._payload(self._broken()), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("корень", result.stderr)

    def test_unparsed_path_is_visible_and_not_a_block(self):
        payload = {"hook_event_name": "PostToolUse", "cwd": str(self.root),
                   "session_id": "s1", "tool_name": "Write",
                   "tool_input": {"неизвестно": 1}}
        result = call("PostToolUse", payload, self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("путь не разобран", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_gate_that_fails_names_itself_and_lets_the_other_run(self):
        """Утверждение здесь — контракт, а не способ его нарушить.

        Гейт, который не смог выполниться, называет себя видимой строкой,
        обработчик возвращает 0, и второй гейт досчитывает своё: «не смог» —
        это не «запретил» и не «разрешил», и различие несёт текст. Один
        сломанный гейт иначе гасил бы `PostToolUse` на каждой записи, а
        причиной в stderr значился бы код возврата hook.py.

        Ломает прогон каталог с именем на `.md`: `check_links.scan` обходит
        `*.md` и читает каждое совпадение как файл, получая
        `IsADirectoryError`. Такой каталог заводится одним движением мыши
        в Obsidian.

        Провокацию выбирали не из вкуса, и «упростить» её обратно нельзя:

        - файл в cp1251 стоял здесь раньше и перестал что-либо ломать
          в `cc3c7ea`, где чтение стало `errors="replace"`. Это сделано
          нарочно: одного нечитаемого байта хватало, чтобы гейт не выдал
          отчёта вовсе;
        - режим `000` роняет чтение `PermissionError`, но под root биты
          режима не значат ничего, а под root ходят половина образов CI.

        Каталог лежит в `projects/`, а коллекция вида — в `areas/`, и это
        не случайность: у гейтов разные периметры, `check_frontmatter`
        обходит только папки своего `views.base`. Положи каталог в `areas/` —
        упадут оба, и утверждать «второй досчитал» станет нечем.
        """
        (self.root / "projects" / "каталог.md").mkdir()
        (self.root / "areas" / "views.base").write_text(
            'filters:\n  and:\n    - file.inFolder("areas")\n'
            '    - status != "closed"\n', encoding="utf-8")
        result = call("PostToolUse", self._payload(self._broken()), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("гейт не выполнился", result.stderr)
        self.assertIn("check_links", result.stderr)
        self.assertIn("IsADirectoryError", result.stderr)
        self.assertIn("areas/broken.md:1 missing-required", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_broken_git_pointer_says_the_turn_list_was_not_written(self):
        """Корень найден, а писать список хода некуда: `.git` есть, но это
        файл-указатель в никуда. `Stop` тогда сочтёт чужим всё, что агент
        написал, — и это обязано быть сказано вслух.

        Отсюда же держится и вторая половина контракта: `PostToolUse` при
        этом досчитывает гейты. Раньше на этой фикстуре обработчик падал
        `NotADirectoryError`, и отчёт по только что записанному файлу
        исчезал целиком.

        Указатель в никуда выбран не для красоты: в отдельно стоящем
        репозитории без `.git` корня больше не находят вовсе
        (tests/test_boundary.py::test_a_marker_outside_any_git_repo_is_not_a_root),
        и до этой строки дело не доходит.
        """
        import shutil
        target = self._broken()
        shutil.rmtree(self.root / ".git")
        (self.root / ".git").write_text("gitdir: ../нет-такого\n",
                                        encoding="utf-8")
        result = call("PostToolUse", self._payload(target), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("список файлов хода", result.stderr)
        self.assertIn("areas/broken.md:1 unresolved", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


def git(root, *args, **kwargs):
    """Личность коммиттера — флагами, а не глобальным конфигом среды прогона."""
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=str(root), capture_output=True, text=True, **kwargs)


def status_of(root):
    """`git status` теста — с `-uall`, и это не украшение.

    Без `-uall` git схлопывает целиком неотслеженный каталог в одну строку
    `?? areas/`: файла внутри не видит ни тест, ни хук. Проверка «красное
    не закоммичено», написанная на схлопнутом выводе, зелена и при
    реализации, которая красное коммитит.
    """
    return git(root, "status", "--porcelain", "-uall").stdout


def tree_of(root):
    """Слепок дерева мимо `.git`: сводка не имеет права ничего туда положить."""
    return sorted(p.relative_to(root).as_posix()
                  for p in Path(root).rglob("*")
                  if ".git" not in p.relative_to(root).parts)


class TestSessionStart(unittest.TestCase):
    """Сводка старта: печатается в контекст, на диск не ложится, чекпоинтом
    забирает только зелёное."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        commit_all(self.root)
        self.addCleanup(self._tmp.cleanup)

    def _payload(self, **extra):
        payload = {"hook_event_name": "SessionStart", "cwd": str(self.root),
                   "session_id": "s1", "source": "startup"}
        payload.update(extra)
        return payload

    def test_summary_goes_to_stdout(self):
        """stdout попадает в контекст только у `SessionStart` — сводка идёт
        туда. В stderr она была бы видна лишь в отладочном выводе."""
        result = call("SessionStart", self._payload(), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("inbox", result.stdout)

    def test_clean_tree_says_nothing_uncommitted(self):
        result = call("SessionStart", self._payload(), self.root)
        self.assertIn("незакоммиченного: нет", result.stdout)

    def test_summary_writes_no_file(self):
        """Хук, перезаписывающий файл на каждом старте, делает дерево грязным,
        а грязное дерево означает «здесь работал человек», — и ветка
        «пусто → тишина» не наступила бы уже никогда. Вычисляемое не обязано
        лежать на диске: оно вычисляется."""
        before_status, before_tree = status_of(self.root), tree_of(self.root)
        call("SessionStart", self._payload(), self.root)
        self.assertEqual(status_of(self.root), before_status)
        self.assertEqual(tree_of(self.root), before_tree)

    def test_summary_names_the_last_checkpoint_and_its_size(self):
        """Строка сводки — из секции 1 спеки дословно: дата и объём.

        Число в единственном числе пишется единственным: «1 файл», не
        «1 файлов». Сводку читает человек, и грамматический мусор в ней —
        такой же шум, как неверная дата.
        """
        result = call("SessionStart", self._payload(), self.root)
        date = git(self.root, "log", "-1", "--format=%ad",
                   "--date=short").stdout.strip()
        self.assertIn("последний чекпоинт: %s, 1 файл\n" % date, result.stdout)

    def test_inbox_age_comes_from_git_not_from_the_clock(self):
        """Обе даты приходят из git, поэтому отчёт воспроизводим: он не зависит
        ни от часов машины, ни от дня прогона."""
        (self.root / "inbox" / "old.md").write_text("старое\n", encoding="utf-8")
        git(self.root, "add", "--", "inbox/old.md")
        git(self.root, "commit", "-qm", "инбокс", "--date=2026-08-01T10:00:00")
        (self.root / "areas" / "later.md").write_text("позже\n", encoding="utf-8")
        git(self.root, "add", "--", "areas/later.md")
        git(self.root, "commit", "-qm", "позже", "--date=2026-08-10T10:00:00")
        result = call("SessionStart", self._payload(), self.root)
        self.assertIn("inbox: 1, старшему 9 дней", result.stdout)

    def test_an_inbox_item_outside_git_is_named_not_dated_silently(self):
        """Возраст файла, которого в git нет, невосстановим. Подставить ему
        ноль дней — молчаливая заглушка (незыблемое №4): сводка соврала бы,
        что элемент свежий, ровно про тот элемент, который дольше всех лежит
        неучтённым."""
        (self.root / "inbox" / "old.md").write_text("старое\n", encoding="utf-8")
        git(self.root, "add", "--", "inbox/old.md")
        git(self.root, "commit", "-qm", "инбокс", "--date=2026-08-01T10:00:00")
        (self.root / "areas" / "later.md").write_text("позже\n", encoding="utf-8")
        git(self.root, "add", "--", "areas/later.md")
        git(self.root, "commit", "-qm", "позже", "--date=2026-08-10T10:00:00")
        (self.root / "inbox" / "новое.md").write_text("ещё не в git\n",
                                                      encoding="utf-8")
        result = call("SessionStart", self._payload(), self.root)
        self.assertIn("inbox: 2, старшему 9 дней (1 ещё не в git)", result.stdout)

    def test_green_uncommitted_work_is_checkpointed(self):
        """Незакоммиченное на старте — по определению чужое: сессия только что
        началась. Зелёное сохраняется, чтобы работа человека не потерялась."""
        (self.root / "areas" / "ok.md").write_text("# ок\n", encoding="utf-8")
        result = call("SessionStart", self._payload(), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(status_of(self.root).strip(), "")

    def test_red_uncommitted_work_is_shown_and_not_committed(self):
        """Красное показывается и не коммитится. Показывается в stdout:
        у `SessionStart` только он доходит до агента."""
        (self.root / "areas" / "bad.md").write_text("[[нет цели]]\n",
                                                    encoding="utf-8")
        result = call("SessionStart", self._payload(), self.root)
        self.assertIn("areas/bad.md", status_of(self.root))
        self.assertIn("areas/bad.md", result.stdout)

    def test_a_red_file_alone_in_an_untracked_directory_is_still_seen(self):
        """Тот же случай, но написанный так, чтобы поймать `git status` без
        `-uall`, — и он ловит.

        Git схлопывает целиком неотслеженный каталог в одну строку `?? areas/`.
        Находка гейта приходит на `areas/bad.md`, в списке незакоммиченного
        лежит `areas/`, они не совпадают ни одним символом — и красное молча
        уезжает в чекпоинт. Здесь у каталога нет ни одного отслеженного файла,
        то есть схлопывание гарантировано.
        """
        (self.root / "projects" / "bad.md").write_text("[[нет цели]]\n",
                                                       encoding="utf-8")
        head = git(self.root, "rev-parse", "HEAD").stdout.strip()
        result = call("SessionStart", self._payload(), self.root)
        self.assertEqual(git(self.root, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertIn("projects/bad.md", result.stdout)

    def test_a_non_ascii_path_is_checkpointed(self):
        """Кириллица в имени — обычный случай, а не край: репозиторий ведут
        по-русски. `git status --porcelain` без `-z` отдаёт такой путь
        закавыченным и в octal-escape'ах, и `git add` по этой строке
        не находит ничего."""
        (self.root / "areas" / "заметка.md").write_text("текст\n",
                                                        encoding="utf-8")
        call("SessionStart", self._payload(), self.root)
        self.assertEqual(status_of(self.root).strip(), "")

    def test_silent_git_never_reads_as_a_clean_tree(self):
        """Корень найден, а git не отвечает: `.git` есть, но это указатель
        в никуда — форма, в которой приезжают сабмодуль и рабочее дерево.
        Пустой ответ от неспросившего git неотличим от чистого дерева, и
        сводка соврала бы «незакоммиченного: нет» ровно там, где не знает
        ничего (незыблемое №4)."""
        import shutil
        shutil.rmtree(self.root / ".git")
        (self.root / ".git").write_text("gitdir: ../нет-такого\n",
                                        encoding="utf-8")
        result = call("SessionStart", self._payload(), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("незакоммиченного: нет", result.stdout)
        self.assertIn("неизвестно", result.stdout)
        self.assertIn("гейт не выполнился", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_an_unfinished_merge_is_not_checkpointed(self):
        """Конфликт в дереве — незавершённая работа человека. `git add` по
        такому файлу помечает конфликт разрешённым и коммитит текст вместе
        с маркерами `<<<<<<<`: плагин выдал бы за решение то, чего не решал.
        Гейты этого не поймают — маркеры конфликта не ссылка и не frontmatter.
        """
        ours = git(self.root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        (self.root / "areas" / "x.md").write_text("наше\n", encoding="utf-8")
        git(self.root, "add", "--", "areas/x.md")
        git(self.root, "commit", "-qm", "наше")
        git(self.root, "checkout", "-q", "-b", "их", "HEAD~1")
        # Уходя на коммит без единого отслеженного файла в `areas/`, git
        # уносит и сам каталог: он не хранит пустых каталогов.
        (self.root / "areas").mkdir(exist_ok=True)
        (self.root / "areas" / "x.md").write_text("их\n", encoding="utf-8")
        git(self.root, "add", "--", "areas/x.md")
        git(self.root, "commit", "-qm", "их")
        merged = git(self.root, "merge", "--no-edit", ours)
        self.assertNotEqual(merged.returncode, 0, "слияние обязано конфликтовать")
        head = git(self.root, "rev-parse", "HEAD").stdout.strip()
        result = call("SessionStart", self._payload(), self.root)
        self.assertEqual(git(self.root, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertIn("слияние", result.stdout)

    def test_a_gate_that_could_not_run_stops_the_checkpoint(self):
        """Коммит на власти прогона, который не состоялся, — подпись под
        непроверенным.

        Та же наблюдённая поломка, что и у `PostToolUse`: каталог с именем
        на `.md` роняет `check_links.scan`. Там она стоила отчёта, здесь
        стоила бы чекпоинта дерева, которое никто не смотрел.
        """
        (self.root / "areas" / "каталог.md").mkdir()
        (self.root / "areas" / "ok.md").write_text("# ок\n", encoding="utf-8")
        head = git(self.root, "rev-parse", "HEAD").stdout.strip()
        result = call("SessionStart", self._payload(), self.root)
        self.assertEqual(git(self.root, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertIn("check_links", result.stderr)
        self.assertIn("чекпоинт не сделан", result.stdout)
        self.assertIn("areas/ok.md", status_of(self.root))

    def test_a_root_below_the_git_root_is_not_checkpointed(self):
        """Пути `--porcelain` считаются от корня git, пути гейтов — от корня
        рецепта. Контекстный репозиторий подкаталогом кодового разводит эти
        корни на приставку, и списки перестают совпадать целиком: находка
        не найдёт своего файла, и красное уедет в чекпоинт молча."""
        outer = Path(self._tmp.name) / "outer"
        (outer / "context").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(outer), check=True)
        for zone in ("areas", "inbox"):
            (outer / "context" / zone).mkdir()
        (outer / "context" / ".twinkle-repo-builder").write_text(
            '{"version": "1"}', encoding="utf-8")
        (outer / "context" / "areas" / "ok.md").write_text("# ок\n",
                                                           encoding="utf-8")
        commit_all(outer)
        (outer / "context" / "areas" / "later.md").write_text("# ещё\n",
                                                              encoding="utf-8")
        payload = {"hook_event_name": "SessionStart", "session_id": "s1",
                   "cwd": str(outer / "context"), "source": "startup"}
        result = call("SessionStart", payload, outer / "context")
        self.assertIn("не совпадает с корнем git", result.stdout)
        self.assertIn("context/areas/later.md", status_of(outer))

    def test_a_missing_root_is_visible_and_not_a_crash(self):
        (self.root / ".twinkle-repo-builder").unlink()
        result = call("SessionStart", self._payload(), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("корень", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_checkpoint_never_uses_add_all(self):
        """`git add -A` заберёт сдвиги указателей сабмодулей `knowledge/`
        и параллельные правки человека в Obsidian."""
        source = (ROOT / "hooks" / "summary.py").read_text(encoding="utf-8")
        self.assertNotIn('"-A"', source)
        self.assertNotIn("'-A'", source)
        self.assertNotIn("--all", source)


class TestCheckpointArithmetic(unittest.TestCase):
    """Две развилки чекпоинта, у которых нет наблюдаемого следа в дереве:
    что считается красным и что вообще можно ставить в индекс."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_only_errors_block_the_checkpoint(self):
        """Красное — это ошибка, а не всякая находка.

        `orphan` — тяжесть `report`, `ambiguous` — `warning`; ни одна не делает
        `./check` красным. Считать красной всякую находку значит запретить
        чекпоинт репозиторию, где просто есть файл, на который никто не
        сослался, — то есть запретить навсегда: ветка «зелёное сохраняется»
        не наступит уже никогда.
        """
        from hooks import summary
        from scripts.findings import Finding
        soft = [Finding("orphan", "areas/a.md", 1, "на файл никто не сослался"),
                Finding("ambiguous", "areas/a.md", 2, "две цели")]
        self.assertEqual(summary.errors(soft), [])
        red = Finding("unresolved", "areas/a.md", 3, "нет такой цели")
        self.assertEqual(summary.errors(soft + [red]), [red])

    def test_a_dirty_directory_is_never_staged(self):
        """Сдвинутый указатель сабмодуля приходит в `git status` одной строкой
        с путём каталога. Назвать его поимённо не лучше, чем забрать `-A`:
        спека запрещает `-A` именно потому, что он уносит указатели
        `knowledge/`, а чужой репозиторий двигает его владелец, не плагин.
        """
        from hooks import summary
        (self.root / "knowledge" / "чужой").mkdir()
        (self.root / "areas" / "a.md").write_text("текст\n", encoding="utf-8")
        staged, skipped = summary.committable(
            self.root, ["areas/a.md", "knowledge/чужой"])
        self.assertEqual(staged, ["areas/a.md"])
        self.assertEqual(skipped, ["knowledge/чужой"])


class TestStop(unittest.TestCase):
    """Красный ход не заканчивается — но только по файлам, сломанным в этом ходе.

    Список файлов хода и есть всё различие между «агент сломал только что» и
    «человек сломал в Obsidian»: без него правка в Obsidian, оборвавшая ссылку,
    заблокировала бы агенту работу — и снимать блок пришлось бы человеку,
    который блокировать не собирался.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        commit_all(self.root)
        self.addCleanup(self._tmp.cleanup)

    def _payload(self, active=False, session="s1", **extra):
        payload = {"hook_event_name": "Stop", "cwd": str(self.root),
                   "session_id": session, "stop_hook_active": active}
        payload.update(extra)
        return payload

    def _broken(self, name="bad.md", zone="areas"):
        target = self.root / zone / name
        target.write_text("[[нет цели]]\n", encoding="utf-8")
        return target

    def _write_of_this_turn(self, target, session="s1"):
        """Файл попадает в список хода тем же путём, что в бою, — через хук.

        Звать `turnfiles.record` из теста значило бы проверять `Stop` на
        списке, который собрал тест, а не `PostToolUse`: форма пути в этих
        двух списках разная ровно тогда, когда есть что ловить.
        """
        payload = {"hook_event_name": "PostToolUse", "cwd": str(self.root),
                   "session_id": session, "tool_name": "Write",
                   "tool_input": {"file_path": str(target)}}
        return call("PostToolUse", payload, self.root)

    def test_broken_file_of_this_turn_blocks(self):
        target = self._broken()
        self._write_of_this_turn(target)
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("areas/bad.md", result.stderr)
        self.assertIn("unresolved", result.stderr)

    def test_broken_file_touched_by_a_human_only_reports(self):
        """Человек, сломавший ссылку в Obsidian, не вправе заблокировать
        работу агента: снимать такой блок пришлось бы ему же."""
        self._broken("human.md")
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("areas/human.md", result.stdout)
        self.assertIn("вне сессии", result.stdout)

    def test_both_halves_are_reported_and_only_one_blocks(self):
        """Находки считаются по всему незакоммиченному и делятся по
        происхождению. Обе половины называются, блокирует одна."""
        self._write_of_this_turn(self._broken("mine.md"))
        self._broken("human.md")
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("areas/mine.md", result.stderr)
        self.assertNotIn("areas/human.md", result.stderr)
        self.assertIn("areas/human.md", result.stdout)

    def test_stop_hook_active_gives_up_out_loud(self):
        """Второй заход подряд не блокируем: иначе ход не заканчивается никогда.

        Сдача обязана быть слышной. Молчаливая — это заглушка (незыблемое №4):
        правило «красный ход не может закончиться» перестало действовать,
        и никто об этом не узнал.
        """
        self._write_of_this_turn(self._broken())
        result = call("Stop", self._payload(active=True), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("второй заход", result.stdout + result.stderr)
        self.assertIn("areas/bad.md", result.stdout + result.stderr)

    def test_clean_turn_is_silent(self):
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr.strip(), "")
        self.assertEqual(result.stdout.strip(), "")

    def test_a_file_of_another_session_is_not_ours(self):
        """Список хода умирает вместе с сессией. Чужой ход — чужие файлы:
        имя файла списка несёт `session_id` именно ради этого."""
        self._write_of_this_turn(self._broken(), session="s1")
        result = call("Stop", self._payload(session="s2"), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("areas/bad.md", result.stdout)

    def test_a_soft_finding_of_this_turn_does_not_block(self):
        """Блокирует красное, а не всякая находка.

        `ambiguous` — тяжесть `warning`, `orphan` — `report`; ни одна не делает
        `./check` красным, и `summary.errors` заведён ровно на это различие.
        Блокировать ход на предупреждении значит запретить его конец там, где
        `./check` зелен, — и об этой находке уже сказал `PostToolUse`.
        """
        (self.root / "areas" / "dup.md").write_text("один\n", encoding="utf-8")
        (self.root / "projects" / "dup.md").write_text("другой\n",
                                                       encoding="utf-8")
        target = self.root / "areas" / "note.md"
        target.write_text("[[dup]]\n", encoding="utf-8")
        self._write_of_this_turn(target)
        probe = call("PostToolUse",
                     {"hook_event_name": "PostToolUse", "cwd": str(self.root),
                      "session_id": "s1", "tool_name": "Write",
                      "tool_input": {"file_path": str(target)}}, self.root)
        self.assertIn("ambiguous", probe.stderr, "фикстура обязана быть жёлтой")
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("ambiguous", result.stderr)
        # Вторая половина обязательна: утверждение «жёлтое не блокирует»
        # ничего не стоит, пока на той же фикстуре не показано, что красное
        # блокирует. Без неё тест зелен и при `Stop`, который не работает.
        self._write_of_this_turn(self._broken("red.md"))
        self.assertEqual(call("Stop", self._payload(), self.root).returncode, 2)

    def test_a_gate_that_fails_names_itself_and_the_other_still_blocks(self):
        """«Не смог» не имеет права выглядеть как «разрешил» — и не имеет права
        уносить с собой второй гейт.

        Провокация та же, что у `PostToolUse`: каталог с именем на `.md` роняет
        `check_links.scan` (`IsADirectoryError`), и заводится он одним движением
        мыши в Obsidian. Останься `Stop` без обработки — упавший гейт означал бы
        ход, который заканчивается зелёным, ни разу не проверенный.
        """
        (self.root / "projects" / "каталог.md").mkdir()
        (self.root / "areas" / "views.base").write_text(
            'filters:\n  and:\n    - file.inFolder("areas")\n'
            '    - status != "closed"\n', encoding="utf-8")
        self._write_of_this_turn(self._broken())
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("гейт не выполнился", result.stderr)
        self.assertIn("check_links", result.stderr)
        self.assertIn("areas/bad.md:1 missing-required", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_missing_root_is_visible_and_not_a_block(self):
        (self.root / ".twinkle-repo-builder").unlink()
        self._broken()
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("корень", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_silent_git_never_reads_as_a_finished_turn(self):
        """git не ответил — состояние дерева неизвестно. Пустой ответ
        неотличим от чистого дерева, и `Stop` закончил бы ход, не увидев
        ничего (незыблемое №4)."""
        import shutil
        self._broken()
        shutil.rmtree(self.root / ".git")
        (self.root / ".git").write_text("gitdir: ../нет-такого\n",
                                        encoding="utf-8")
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("гейт не выполнился", result.stderr)
        self.assertIn("состояние дерева", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class TestStopCannotBeSlippedPast(unittest.TestCase):
    """Ход, который обязан быть заблокирован, но не блокируется.

    Каждый случай здесь — построенная нагрузка, а не гипотеза: во всех трёх
    `Stop` возвращал ноль с зелёным видом, ни на что не пожаловавшись. Так
    выглядит ослабление блокирующего правила, которое незыблемое №4 запрещает
    делать молча, — и находится оно только тем, что его пробуют построить.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self._tmp.name)
        commit_all(self.root)
        self.addCleanup(self._tmp.cleanup)

    def _payload(self, **extra):
        payload = {"hook_event_name": "Stop", "cwd": str(self.root),
                   "session_id": "s1", "stop_hook_active": False}
        payload.update(extra)
        return payload

    def _record(self, target, root=None, session="s1"):
        root = self.root if root is None else root
        payload = {"hook_event_name": "PostToolUse", "cwd": str(root),
                   "session_id": session, "tool_name": "Write",
                   "tool_input": {"file_path": str(target)}}
        return call("PostToolUse", payload, root)

    def test_the_three_path_forms_are_one_form(self):
        """Три источника путей, и совпадать они обязаны побайтово.

        Список хода собирает `PostToolUse` из `tool_input`, незакоммиченное
        печатает `git status`, находки собирают гейты обходом дерева. Разойдись
        любые два — пересечение множеств пусто, `ours` пуст всегда, и `Stop`
        не блокирует уже ничего, оставаясь при этом зелёным и молчаливым.
        Утверждается равенство, а не «что-то нашлось», потому что промах здесь
        не виден ни по коду возврата, ни по тексту.
        """
        from hooks import turnfiles
        from scripts import check_links
        target = self.root / "areas" / "bad.md"
        target.write_text("[[нет цели]]\n", encoding="utf-8")
        self._record(target)
        fields = git(self.root, "status", "--porcelain", "-z",
                     "-uall").stdout.split("\0")
        from_git = sorted(entry[3:] for entry in fields if len(entry) >= 4)
        from_gate = sorted({f.path for f in check_links.scan(self.root).findings})
        self.assertEqual(from_git, ["areas/bad.md"])
        self.assertEqual(from_gate, ["areas/bad.md"])
        self.assertEqual(turnfiles.listing(self.root, "s1"), ["areas/bad.md"])

    def test_a_file_committed_inside_the_turn_still_blocks(self):
        """Коммит внутри хода уводил файл из-под `Stop` целиком.

        Незакоммиченное — не определение авторства, а способ отсечь красное,
        которое лежало в репозитории до этого хода. Файл из списка хода
        написан агентом сейчас, и от того, что агент его закоммитил, красным
        быть он не перестал: `git commit` — обычная команда, `bashscan` её не
        держит и держать не должен.
        """
        target = self.root / "areas" / "bad.md"
        target.write_text("[[нет цели]]\n", encoding="utf-8")
        self._record(target)
        git(self.root, "add", "--", "areas/bad.md")
        git(self.root, "commit", "-qm", "агент закоммитил своё")
        self.assertEqual(status_of(self.root).strip(), "")
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("areas/bad.md", result.stderr)

    def test_a_root_below_the_git_root_still_matches_paths(self):
        """Контекстный репозиторий подкаталогом кодового — не край, а
        описанная секцией 22 конфигурация.

        `--porcelain` печатает пути от корня git (`context/areas/bad.md`),
        гейты — от корня рецепта (`areas/bad.md`). Несведённые, они не
        совпадают ни одним символом: `Stop` не сказал бы ни слова ни про чужое,
        ни про своё. Список хода в этой конфигурации не ведётся вовсе —
        `context/.git` нет, — и это ослабление обязано быть названо вслух,
        а не выглядеть как зелёный ход.
        """
        outer = Path(self._tmp.name) / "outer"
        context = outer / "context"
        for zone in ("core", "areas", "projects", "inbox"):
            (context / zone).mkdir(parents=True)
        (context / ".twinkle-repo-builder").write_text('{"version": "1"}',
                                                       encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=str(outer), check=True)
        commit_all(outer)
        (context / "areas" / "bad.md").write_text("[[нет цели]]\n",
                                                  encoding="utf-8")
        payload = {"hook_event_name": "Stop", "cwd": str(context),
                   "session_id": "s1", "stop_hook_active": False}
        result = call("Stop", payload, context)
        self.assertEqual(result.returncode, 0)
        self.assertIn("вне сессии", result.stdout)
        self.assertIn("areas/bad.md", result.stdout)
        self.assertIn("список файлов хода", result.stderr)

    def test_an_unreadable_stop_hook_active_gives_up_by_its_own_name(self):
        """`stop_hook_active` строкой отменял блок на первом же заходе.

        `"false"` — истина в питоне, и `Stop` уходил в ветку сдачи, объявляя
        второй заход подряд там, где был первый. Читается поле защитно, тем же
        правилом, каким `read_event` проверяет `cwd` и `session_id`: сдача
        остаётся (блокировать по непрочитанному вводу нельзя), но причиной
        названа своя, а не выдуманная.
        """
        target = self.root / "areas" / "bad.md"
        target.write_text("[[нет цели]]\n", encoding="utf-8")
        self._record(target)
        result = call("Stop", self._payload(stop_hook_active="false"), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("stop_hook_active пришёл как str", result.stderr)
        self.assertNotIn("второй заход", result.stdout + result.stderr)
        self.assertIn("areas/bad.md", result.stderr)

    def test_the_blast_radius_beyond_the_turn_files_is_named(self):
        """Дыра, которую этот обработчик не закрывает, обязана быть названа.

        Агент пишет один законный `areas/views.base` — и все файлы `areas/`
        без frontmatter краснеют, не будучи тронутыми ни ходом, ни человеком.
        Фильтр по файлам хода выбрасывает их все: код 0, пустой stdout, пустой
        stderr, и прогон гейтов по репозиторию при этом красный. Названный
        риск — то, чем бэкстоп отличается от притворной песочницы; регистр
        взят у `bashscan.UNCATCHABLE` и проверяется так же.
        """
        from hooks import hook
        self.assertIn("не на тот файл", hook.on_stop.__doc__)
        self.assertIn("views.base", hook.on_stop.__doc__)

    def test_a_precomposed_path_over_a_decomposed_file_still_blocks(self):
        """Кириллица приезжает в двух формах Unicode, и они не равны как строки.

        Файл, созданный в NFD (так пишет macOS до APFS, так приезжает архив),
        обходом дерева и от git приходит в NFD, а `realpath` пути из
        `tool_input` возвращает форму, в которой путь пришёл, — NFC. Список
        хода тогда не пересекается с находками ни в одном символе, и правка
        агента в русском файле не блокирует ход никогда. Русские имена здесь
        норма, а не край: репозиторий ведут по-русски.
        """
        import unicodedata
        nfd = unicodedata.normalize("NFD", "ёлка.md")
        nfc = unicodedata.normalize("NFC", "ёлка.md")
        self.assertNotEqual(nfd, nfc)
        (self.root / "areas" / nfd).write_text("[[нет цели]]\n",
                                               encoding="utf-8")
        if not (self.root / "areas" / nfc).exists():
            # Файловая система формы различает: NFC-путь — другой файл, и
            # случая, о котором тест, на ней не существует. Ветка не
            # пропускается, а утверждает второй исход: два разных файла,
            # и сломан тот, который агент и написал.
            (self.root / "areas" / nfc).write_text("[[нет цели]]\n",
                                                   encoding="utf-8")
        self._record(self.root / "areas" / nfc)
        result = call("Stop", self._payload(), self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unresolved", result.stderr)
