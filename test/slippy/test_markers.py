import unittest

from test import HAVE_DISPLAY, get_wx_app


@unittest.skipUnless(HAVE_DISPLAY, "Needs a display")
class MarkerTest(unittest.TestCase):
    def setUp(self):
        get_wx_app()

    def test_default_images(self):
        from slippy.markers import Marker

        m = Marker("id", 50, -4)
        self.assertEqual(m.pin.hotspot, (15, 28))
        self.assertTrue(m.pin.bitmap.IsOk())
        self.assertTrue(m.shadow.bitmap.IsOk())

    def test_select(self):
        from slippy.markers import Marker

        m = Marker("id", 50, -4)
        unselected = m.pin
        m.select()
        self.assertIsNot(m.pin, unselected)
        m.select(False)
        self.assertIs(m.pin, unselected)

    def test_hit_test(self):
        from slippy.markers import Marker

        m = Marker("id", 50, -4)
        # Offsets are relative to the hotspot, so well outside the bitmap is a miss
        self.assertFalse(m.hit_test(100, 100))

    def test_compares_by_id(self):
        from slippy.markers import Marker

        self.assertEqual(Marker("a", 0, 0), "a")
        self.assertLess(Marker("a", 0, 0), Marker("b", 0, 0))


if __name__ == "__main__":
    unittest.main()
