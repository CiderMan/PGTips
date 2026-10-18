import unittest
from test import HAVE_DISPLAY, get_wx_app

import wx

from slippy.regions import Point, Region
from slippy.slip import SlippyPanel, get_lat_long, get_tile_number
from slippy.tracks import Track


class TileMathsTest(unittest.TestCase):
    def test_tile_number(self):
        self.assertEqual(get_tile_number(1, 0, 0), (1, 0, 1, 0))
        xtile, xpixel, ytile, ypixel = get_tile_number(15, 50.1, -4.2)
        for v in (xtile, xpixel, ytile, ypixel):
            self.assertIsInstance(v, int)

    def test_round_trip(self):
        zoom = 12
        xtile, xpixel, ytile, ypixel = get_tile_number(zoom, 50.1, -4.2)
        lat, long = get_lat_long(xtile + xpixel / 256, ytile + ypixel / 256, zoom)
        self.assertAlmostEqual(lat, 50.1, places=3)
        self.assertAlmostEqual(long, -4.2, places=3)


class _Source:
    def get_attribution(self):
        return None


class _RecordingCache:
    """A tile cache that records which tiles are requested but never has any"""

    source = _Source()

    def __init__(self):
        self.requests = []

    def StartNewFetchBatch(self):
        self.requests = []

    def GetTileFilename(self, xtile, ytile, zoom):
        self.requests.append((xtile, ytile, zoom))


@unittest.skipUnless(HAVE_DISPLAY, "Needs a display")
class SlippyPanelTest(unittest.TestCase):
    def setUp(self):
        get_wx_app()
        self.frame = wx.Frame(None)
        self.cache = _RecordingCache()
        self.panel = SlippyPanel(self.frame, -1, cache=self.cache, size=(600, 400))

    def tearDown(self):
        self.frame.Destroy()

    def assertIntegerTiles(self):
        self.assertGreater(len(self.cache.requests), 0)
        for request in self.cache.requests:
            for v in request:
                self.assertIsInstance(v, int)

    def test_centre_map(self):
        self.panel.CentreMap(50.1, -4.2, zoom=10)
        self.assertIsInstance(self.panel._tlx, int)
        self.assertIsInstance(self.panel._tly, int)
        self.assertIntegerTiles()
        self.assertTrue(all(zoom == 10 for x, y, zoom in self.cache.requests))

    def test_show_region(self):
        self.panel.ShowRegion(Region(Point(50.5, -4.5), Point(50, -4)))
        self.assertIntegerTiles()
        # The region should fit within the panel at the chosen zoom, but not at the next one
        self.assertEqual(self.panel._zoom, 9)

    def test_add_and_remove_track(self):
        t = Track([(50, -4), (50.5, -4.5)])
        self.panel.AddTrack(t)
        self.assertIn(t, self.panel._visibleTracks)
        self.panel.RemoveTrack(t)
        self.assertNotIn(t, self.panel._visibleTracks)


if __name__ == "__main__":
    unittest.main()
