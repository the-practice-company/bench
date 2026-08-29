import tempfile
import unittest
from pathlib import Path

from hooks import boundary


class TestFindRoot(unittest.TestCase):
    """Корень — место маркера, не поле в конфиге: искать корень по конфигу,
    который лежит в корне, — круг (секция 22)."""

    def test_marker_found_upwards(self):
        with tempfile.TemporaryDirectory() as tmp:
            # `.resolve()` на временном каталоге обязателен: на macOS
            # `tempfile` отдаёт `/var/...`, а `/var` — симлинк на `/private/var`.
            # `find_root` нормализует путь (иначе граница не сойдётся с
            # `outside`), и ждать от неё ненормализованный корень — значит
            # проверять симлинк файловой системы, а не поиск маркера.
            root = Path(tmp).resolve() / "repo"
            (root / "areas" / "hiring").mkdir(parents=True)
            (root / ".git").mkdir()
            (root / ".twinkle-repo-builder").write_text('{"version": "1"}',
                                                        encoding="utf-8")
            self.assertEqual(boundary.find_root(root / "areas" / "hiring"), root)

    def test_a_marker_outside_any_git_repo_is_not_a_root(self):
        """Git обязателен (секция 8): без него не будет ни истории, ни
        чекпоинтов, ни списка файлов хода.

        `.git` здесь лежит **ниже** маркера, то есть в другом репозитории,
        и корнем маркер не делает.
        """
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            (outer / ".twinkle-repo-builder").write_text("{}", encoding="utf-8")
            inner = outer / "repo"
            (inner / "areas").mkdir(parents=True)
            (inner / ".git").mkdir()
            self.assertIsNone(boundary.find_root(inner / "areas"))

    def test_a_context_repo_inside_a_code_repo_is_a_root(self):
        """Контекстный репозиторий законно живёт подкаталогом кодового, и
        тогда `.git` лежит выше маркера. Требовать `.git` рядом с маркером
        значило бы не найти корня в этой конфигурации — а на разъехавшиеся
        корни у `SessionStart` заведена своя ветка, и она бы умерла."""
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp).resolve()
            (outer / ".git").mkdir()
            context = outer / "context"
            (context / "areas").mkdir(parents=True)
            (context / ".twinkle-repo-builder").write_text("{}",
                                                           encoding="utf-8")
            self.assertEqual(boundary.find_root(context / "areas"), context)

    def test_a_nested_git_repo_does_not_end_the_search(self):
        """`knowledge/` держит чужие сабмодули **по построению**.

        Остановка на первом встреченном `.git` означала, что любой ход,
        чей `cwd` оказался внутри сабмодуля, не находил корня вовсе — и
        незыблемое №6 не проверялось ни для одной цели, а не только для
        целей внутри `knowledge`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / "repo"
            vendor = root / "knowledge" / "vendor"
            vendor.mkdir(parents=True)
            (root / ".git").mkdir()
            (root / ".twinkle-repo-builder").write_text("{}", encoding="utf-8")
            (vendor / ".git").mkdir()
            self.assertEqual(boundary.find_root(vendor), root)

    def test_a_git_file_counts_as_a_git_root(self):
        """У сабмодуля и у рабочего дерева git `.git` — файл-указатель, а не
        каталог. Контекстный репозиторий бывает и тем и другим, и требовать
        от него каталога значит не найти корня там, где он есть."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / "repo"
            (root / "areas").mkdir(parents=True)
            (root / ".git").write_text("gitdir: ../real/.git\n", encoding="utf-8")
            (root / ".twinkle-repo-builder").write_text("{}", encoding="utf-8")
            self.assertEqual(boundary.find_root(root / "areas"), root)

    def test_no_marker_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(boundary.find_root(Path(tmp)))


class TestOutside(unittest.TestCase):
    """Нормализация до сравнения: `..`, симлинк и абсолютный путь дают один
    и тот же ответ. Сравнение по префиксу строки ловится собственным `..`."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        (self.root / "areas").mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def test_inside_is_inside(self):
        self.assertFalse(boundary.outside(self.root / "areas" / "x.md", self.root))

    def test_dotdot_above_root_is_outside(self):
        self.assertTrue(boundary.outside(self.root / "areas" / ".." / ".." / "x",
                                         self.root))

    def test_dotdot_between_zones_is_inside(self):
        self.assertFalse(boundary.outside(self.root / "areas" / ".." / "core" / "x",
                                          self.root))

    def test_absolute_elsewhere_is_outside(self):
        self.assertTrue(boundary.outside(Path("/etc/passwd"), self.root))

    def test_symlink_out_is_outside(self):
        target = Path(self._tmp.name) / "outside"
        target.mkdir()
        link = self.root / "escape"
        link.symlink_to(target)
        self.assertTrue(boundary.outside(link / "x.md", self.root))

    def test_prefix_match_alone_is_not_enough(self):
        """`repo-neighbour` начинается на `repo`, но лежит снаружи."""
        sibling = Path(self._tmp.name) / "repo-neighbour"
        sibling.mkdir()
        self.assertTrue(boundary.outside(sibling / "x.md", self.root))
