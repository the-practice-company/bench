"""`created` из git, и токен вместо молчаливой подстановки."""

import os
import subprocess
import tempfile
import unittest

from scripts import check_frontmatter
from scripts.adopt import dates, init_tree, tree
from tests.foreign import committer, git, materialise


def _commit(root, message, when):
    """Коммит с назначенной датой.

    Дата назначается, а не берётся у часов: тест на «первый коммит файла»,
    сверяющий сегодняшнее число, утверждал бы ровно ту дату прогона, против
    которой написан модуль, и прошёл бы зелёным на реализации, которая
    ничего у git не спрашивает.
    """
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=str(root),
                   check=True, env=env)


class TestCreated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        committer(self)

    def test_without_history_the_token_is_unknown_not_today(self):
        """Ловушка измерена: 235 файлов необратимо несут дату прогона
        миграции. Подставленная дата от настоящей неотличима."""
        root = materialise(self.tmp.name, git_root=False, nested=False)
        self.assertEqual(dates.created(root, "state.md"), dates.UNKNOWN)

    def test_a_fresh_repository_still_says_unknown(self):
        """git завели только что — истории до усыновления нет, и коммит
        «как было» её не создаёт: он датирован сегодня."""
        root = materialise(self.tmp.name, git_root=False, nested=False)
        init_tree.run(root)
        self.assertEqual(dates.created(root, "state.md"), dates.UNKNOWN)

    def test_a_root_commit_base_is_a_named_branch_not_a_swallowed_failure(self):
        """`base^` у корневого коммита git не разрешает: код 128 при пустом
        выводе. `unknown` отсюда — верный ответ, но приходить он обязан по
        названной причине. Молчаливое падение `subprocess` дало бы тот же
        токен и на сломанном репозитории, где история есть.
        """
        root = materialise(self.tmp.name, git_root=False, nested=False)
        init_tree.run(root)
        base = tree.read_base(root)
        probe = tree.git(root, "rev-parse", "--verify", "-q", "%s^" % base)
        self.assertNotEqual(probe.returncode, 0)
        self.assertEqual(probe.stdout.strip(), "")
        self.assertIsNone(dates.history_before(root, base))

    def test_real_history_gives_the_first_commit_not_the_last(self):
        root = materialise(self.tmp.name, git_root=False, nested=False)
        git(root, "init", "-q")
        _commit(root, "первый", "2019-03-04T10:00:00 +0000")
        (root / "state.md").write_text("правка\n", encoding="utf-8")
        _commit(root, "второй", "2024-07-08T10:00:00 +0000")
        self.assertEqual(dates.created(root, "state.md"), "2019-03-04")

    def test_the_adoption_commit_is_not_history(self):
        """Коммит «как было» сделал ADOPT сегодня, и датой создания записи
        его дата не является. Отличает его от настоящей истории только точка
        отката, поэтому она и читается: файл, появившийся в дереве до git, но
        попавший в первый же коммит ADOPT, восстановимой даты не имеет.
        """
        root = materialise(self.tmp.name, git_root=False, nested=False)
        git(root, "init", "-q")
        _commit(root, "своя история", "2019-03-04T10:00:00 +0000")
        (root / "новое.md").write_text("без истории\n", encoding="utf-8")
        init_tree.run(root)
        self.assertEqual(dates.created(root, "README.md"), "2019-03-04")
        self.assertEqual(dates.created(root, "новое.md"), dates.UNKNOWN)

    def test_a_wildcard_in_a_filename_is_matched_literally(self):
        """Измерено: `git log -- 'журнал-*.md'` — это шаблон, а не путь, и он
        подбирает соседа постарше. Ответ тогда настоящая дата, но от другого
        файла — ровно тот правдоподобно-неверный ответ, против которого
        заведён класс.
        """
        root = materialise(self.tmp.name, git_root=False, nested=False)
        git(root, "init", "-q")
        (root / "журнал-2019.md").write_text("сосед\n", encoding="utf-8")
        _commit(root, "сосед", "2019-03-04T10:00:00 +0000")
        (root / "журнал-*.md").write_text("звёздочка\n", encoding="utf-8")
        _commit(root, "звёздочка", "2024-07-08T10:00:00 +0000")
        self.assertEqual(dates.created(root, "журнал-*.md"), "2024-07-08")

    def test_the_token_is_not_a_date_and_never_becomes_one(self):
        self.assertNotRegex(dates.UNKNOWN, r"\d")

    def test_the_token_satisfies_the_frontmatter_gate_and_emptiness_does_not(self):
        """Ради этого расхождение с §18 и заведено: `created: ""` гейт считает
        тем же `missing-required`, что и отсутствующее поле, и дерево после
        усыновления несёт N красных, неотличимых от небрежности автора."""
        self.assertTrue(check_frontmatter._filled(dates.UNKNOWN))
        self.assertFalse(check_frontmatter._filled(""))


class TestReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = materialise(self.tmp.name, git_root=False, nested=False)

    def test_every_unrecoverable_record_is_named(self):
        """Поимённо, а не одним числом: имя грепается, число — нет."""
        findings = dates.unrecoverable(self.root, ["state.md", "README.md"])
        self.assertEqual(sorted((f.path, f.cls, f.detail) for f in findings), [
            ("README.md", "created-unrecoverable",
             "дата создания невосстановима: истории до усыновления нет"),
            ("state.md", "created-unrecoverable",
             "дата создания невосстановима: истории до усыновления нет")])

    def test_a_recoverable_date_produces_no_finding(self):
        root = materialise(self.tmp.name, name="second", git_root=True,
                           nested=False)
        self.assertEqual(dates.unrecoverable(root, ["state.md"]), [])
