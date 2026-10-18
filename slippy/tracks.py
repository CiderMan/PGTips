from .regions import Point, Region
from .utils import _get_coordinate


class Track:
    def __init__(self, points):
        self._points = [Point(x[0], x[1]) for x in points]
        self._cache = {}
        self._region = None

    def get_region(self):
        if self._region is None:
            self._region = Region()
            for p in self._points:
                self._region += p
        return self._region

    def get_track(self, zoom):
        try:
            return self._cache[zoom]
        except KeyError:

            def gen_coords(pts):
                last = None
                for p in pts:
                    n = _get_coordinate(p.lat, p.long, zoom)
                    if n != last:
                        yield n
                    last = n

            self._cache[zoom] = list(gen_coords(self._points))
            return self._cache[zoom]
