import unittest

from slippy.tile_sources import OpenStreetMapTileSource, TileSource


class TileSourceTest(unittest.TestCase):
    def test_url(self):
        s = TileSource("example.com_tiles", "https://example.com/tiles", maxZoom=5)
        self.assertEqual(s.get_tile_url(1, 2, 3), "https://example.com/tiles/3/1/2.png")

    def test_out_of_range_zoom(self):
        s = TileSource("example.com_tiles", "https://example.com/tiles", minZoom=2, maxZoom=5)
        self.assertEqual(s.get_tile_url(0, 0, 1), "")
        self.assertEqual(s.get_tile_url(0, 0, 6), "")

    def test_default_attribution(self):
        s = TileSource("example.com_tiles", "https://example.com/tiles")
        self.assertEqual(s.get_attribution(), "Tiles from example.com")


class OpenStreetMapTileSourceTest(unittest.TestCase):
    def test_url(self):
        s = OpenStreetMapTileSource()
        self.assertEqual(
            s.get_tile_url(16000, 10000, 15), "https://tile.openstreetmap.org/15/16000/10000.png"
        )

    def test_attribution(self):
        self.assertIn("OpenStreetMap contributors", OpenStreetMapTileSource().get_attribution())


if __name__ == "__main__":
    unittest.main()
