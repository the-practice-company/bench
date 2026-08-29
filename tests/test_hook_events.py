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
        """Наблюдённая поломка, а не гипотеза: `check_links.scan` читает всякий
        `*.md` как utf-8 и падает `UnicodeDecodeError` на файле в cp1251.

        Один такой файл где угодно в дереве иначе гасил бы `PostToolUse` на
        каждой записи, а причиной в stderr значился бы код возврата hook.py.
        Провалившийся гейт называет себя, второй досчитывает.
        """
        (self.root / "areas" / "cp1251.md").write_bytes("привет".encode("cp1251"))
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
