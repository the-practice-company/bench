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
