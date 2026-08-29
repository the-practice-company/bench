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
        """`.git/` может не быть: маркер рецепта ищется раньше него. Молча
        не записать — заглушка (незыблемое №4): `Stop` тогда сочтёт чужим всё,
        что агент только что написал, и не скажет почему."""
        from hooks import turnfiles
        import shutil
        shutil.rmtree(self.root / ".git")
        self.assertFalse(turnfiles.record(self.root, "s1", "areas/a.md"))


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
        """Наблюдённая поломка, а не гипотеза: `check_links.scan` обходит
        `*.md` и читает каждое совпадение как файл, а каталог с таким именем
        даёт `IsADirectoryError`. Заводится он одним движением мыши в Obsidian.

        Прежним образцом здесь был файл в cp1251; он перестал ломать гейт
        в `cc3c7ea`, где чтение стало `errors="replace"`. Проверка ветки
        осталась — сама ветка никуда не делась.

        Один такой каталог где угодно в дереве иначе гасил бы `PostToolUse`
        на каждой записи, а причиной в stderr значился бы код возврата
        hook.py. Провалившийся гейт называет себя, второй досчитывает.
        """
        (self.root / "areas" / "каталог.md").mkdir()
        result = call("PostToolUse", self._payload(self._broken()), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("check_links", result.stderr)
        self.assertIn("не выполнился", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_repo_without_git_says_the_turn_list_was_not_written(self):
        """Маркер рецепта ищется раньше `.git`, так что корень может найтись
        там, где писать список хода некуда. `Stop` тогда сочтёт чужим всё,
        что агент написал, — и это обязано быть сказано вслух."""
        import shutil
        shutil.rmtree(self.root / ".git")
        result = call("PostToolUse", self._payload(self._broken()), self.root)
        self.assertEqual(result.returncode, 0)
        self.assertIn("список файлов хода", result.stderr)


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

    def test_missing_git_never_reads_as_a_clean_tree(self):
        """Маркер рецепта ищется раньше `.git`, поэтому корень может найтись
        там, где git не ответит. Пустой ответ от неспросившего git
        неотличим от чистого дерева — и сводка соврала бы «незакоммиченного:
        нет» ровно там, где не знает ничего (незыблемое №4)."""
        import shutil
        shutil.rmtree(self.root / ".git")
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
