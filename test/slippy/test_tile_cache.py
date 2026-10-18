import unittest

from test import temp_dir
from slippy.tile_cache import SlippyCache


class _OfflineSource:
    """A tile source whose URLs are all empty, so that the cache never fetches anything"""

    def __init__(self, root):
        self._root = root

    def get_full_name(self):
        return str(self._root)

    def get_tile_url(self, _xtile, _ytile, _zoom):
        return ""


class SlippyCacheTest(unittest.TestCase):
    def setUp(self):
        self.root = temp_dir(self)
        self.cache = SlippyCache(_OfflineSource(self.root))

    def tearDown(self):
        self.cache._fetchQueue.join()

    def test_filename(self):
        fname = self.cache.GetTileFilename(3, 5, 4)
        self.assertEqual(fname, self.root / "4" / "3" / "5.png")
        # The directory is created ready for the tile to be fetched into
        self.assertTrue(fname.parent.is_dir())

    def test_x_wraps(self):
        self.assertEqual(self.cache.GetTileFilename(17, 5, 4), self.root / "4" / "1" / "5.png")

    def test_invalid_tiles(self):
        self.assertIsNone(self.cache.GetTileFilename(-1, 0, 4))
        self.assertIsNone(self.cache.GetTileFilename(0, -1, 4))
        self.assertIsNone(self.cache.GetTileFilename(0, 16, 4))

    def test_cached_tile_is_not_fetched(self):
        tile = self.root / "4" / "3" / "5.png"
        tile.parent.mkdir(parents=True)
        tile.write_bytes(b"")
        self.assertEqual(self.cache.GetTileFilename(3, 5, 4), tile)
        self.assertTrue(self.cache._fetchQueue.empty())


if __name__ == "__main__":
    unittest.main()
