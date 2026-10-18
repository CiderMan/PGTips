import unittest
from pathlib import Path

from test import temp_dir
from findfiles import find_all_files


class FindAllFilesTest(unittest.TestCase):
    def setUp(self):
        self.dir = temp_dir(self)
        for name in ("a.jpg", "b.JPG", "c.mov", "sub/d.jpg", "sub/deeper/e.txt"):
            path = self.dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"")

    def names(self, files):
        return sorted(f.relative_to(self.dir).as_posix() for f in files)

    def test_walks_directories(self):
        self.assertEqual(
            self.names(find_all_files(self.dir)),
            ["a.jpg", "b.JPG", "c.mov", "sub/d.jpg", "sub/deeper/e.txt"],
        )

    def test_include_is_case_insensitive(self):
        self.assertEqual(
            self.names(find_all_files(self.dir, include=[".JPG"])), ["a.jpg", "b.JPG", "sub/d.jpg"]
        )

    def test_exclude(self):
        self.assertEqual(self.names(find_all_files(self.dir, exclude=[".jpg", ".txt"])), ["c.mov"])

    def test_files_and_directories(self):
        files = [str(self.dir / "c.mov"), self.dir / "sub", self.dir / "missing.jpg"]
        self.assertEqual(
            self.names(find_all_files(files)), ["c.mov", "sub/d.jpg", "sub/deeper/e.txt"]
        )

    def test_single_file_is_filtered(self):
        self.assertEqual(find_all_files(self.dir / "c.mov", include=[".jpg"]), [])

    def test_returns_paths(self):
        for f in find_all_files(str(self.dir)):
            self.assertIsInstance(f, Path)


if __name__ == "__main__":
    unittest.main()
