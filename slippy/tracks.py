from math import *
from regions import *
from utils import *

class Track(object):
    def __init__(self, points):
        self._points = [Point(x[0], x[1]) for x in points]
        self._cache = {}

    def get_region(self):
        try:
            return self._region
        except AttributeError:
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
            self._cache[zoom] = [x for x in gen_coords(self._points)]
            return self._cache[zoom]

