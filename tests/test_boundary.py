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

    def test_search_stops_at_git_root(self):
        """Не выше git-корня: git обязателен, значит корень рецепта не может
        лежать выше него."""
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            (outer / ".twinkle-repo-builder").write_text("{}", encoding="utf-8")
            inner = outer / "repo"
            (inner / "areas").mkdir(parents=True)
            (inner / ".git").mkdir()
            self.assertIsNone(boundary.find_root(inner / "areas"))

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
