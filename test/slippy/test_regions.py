import unittest

from slippy.regions import Point, Region


class PointTest(unittest.TestCase):
    def test_members(self):
        p = Point(50, -4)
        self.assertEqual((p.lat, p.long), (50, -4))

    def test_clipping(self):
        p = Point(100, -200)
        self.assertEqual((p.lat, p.long), (90, -180))

    def test_read_only(self):
        p = Point(50, -4)
        with self.assertRaises(AttributeError):
            p.lat = 51


class RegionTest(unittest.TestCase):
    def assertRegion(self, region, n, w, s, e):
        self.assertAlmostEqual(region._nw.lat, n)
        self.assertAlmostEqual(region._nw.long, w)
        self.assertAlmostEqual(region._se.lat, s)
        self.assertAlmostEqual(region._se.long, e)

    def test_empty_region_contains_nothing(self):
        self.assertNotIn(Point(0, 0), Region())

    def test_add_point_to_empty_region(self):
        r = Region() + Point(50, -4)
        self.assertRegion(r, 50, -4, 50, -4)
        self.assertIn(Point(50, -4), r)

    def test_add_point_expands_region(self):
        r = Region(Point(50, -4)) + Point(50.5, 4.01)
        self.assertRegion(r, 50.5, -4, 50, 4.01)
        self.assertIn(Point(50.25, 0), r)
        self.assertNotIn(Point(50.25, 5), r)

    def test_add_overlapping_regions(self):
        r = Region(Point(51, -4), Point(50, -3)) + Region(Point(51.5, -3.5), Point(50.5, -2.5))
        self.assertRegion(r, 51.5, -4, 50, -2.5)

    def test_add_point_across_antimeridian(self):
        # The shortest way to include 179 from -179 is across the +/-180 line
        r = Region(Point(50, -179)) + Point(51, 179)
        self.assertRegion(r, 51, 179, 50, -179)
        self.assertIn(Point(50.5, 180), r)
        self.assertIn(Point(50.5, -179.5), r)
        self.assertNotIn(Point(50.5, 0), r)

    def test_add_region_across_antimeridian(self):
        r = Region(Point(51, 179), Point(50, -179)) + Region(Point(51.5, 178), Point(50.5, -179.5))
        self.assertRegion(r, 51.5, 178, 50, -179)

    def test_centre(self):
        c = Region(Point(52, -4), Point(50, 2)).get_centre()
        self.assertAlmostEqual(c.lat, 51)
        self.assertAlmostEqual(c.long, -1)

    def test_centre_across_antimeridian(self):
        c = Region(Point(52, 178), Point(50, -176)).get_centre()
        self.assertAlmostEqual(c.lat, 51)
        self.assertAlmostEqual(c.long, -179)

    def test_add_unknown_type(self):
        with self.assertRaises(TypeError):
            _ = Region(Point(50, -4)) + 1


if __name__ == "__main__":
    unittest.main()
