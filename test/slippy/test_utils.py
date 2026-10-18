import unittest

from slippy.utils import _TILE_SIZE, _get_coordinate


class GetCoordinateTest(unittest.TestCase):
    def test_origin_is_centre_of_world(self):
        self.assertEqual(_get_coordinate(0, 0, 0), (_TILE_SIZE // 2, _TILE_SIZE // 2))
        self.assertEqual(_get_coordinate(0, 0, 1), (_TILE_SIZE, _TILE_SIZE))

    def test_west_edge(self):
        x, _y = _get_coordinate(0, -180, 3)
        self.assertEqual(x, 0)

    def test_web_mercator_limit_is_top_edge(self):
        _x, y = _get_coordinate(85.0511287798, 0, 0)
        self.assertEqual(y, 0)

    def test_returns_ints(self):
        for c in _get_coordinate(50.1, -4.2, 15):
            self.assertIsInstance(c, int)


if __name__ == "__main__":
    unittest.main()
