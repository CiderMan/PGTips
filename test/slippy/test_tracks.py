import unittest

from slippy.tracks import Track


class TrackTest(unittest.TestCase):
    def test_region_covers_all_points(self):
        t = Track([(50, -4), (51, -3), (50.5, -5)])
        r = t.get_region()
        self.assertEqual((r._nw.lat, r._nw.long), (51, -5))
        self.assertEqual((r._se.lat, r._se.long), (50, -3))

    def test_track_drops_consecutive_duplicate_pixels(self):
        # At zoom 0, these points are all within the same pixel
        t = Track([(50, -4), (50.0001, -4.0001), (50.0002, -4)])
        self.assertEqual(len(t.get_track(0)), 1)
        self.assertEqual(len(t.get_track(18)), 3)

    def test_track_is_cached(self):
        t = Track([(50, -4), (51, -3)])
        self.assertIs(t.get_track(10), t.get_track(10))


if __name__ == "__main__":
    unittest.main()
