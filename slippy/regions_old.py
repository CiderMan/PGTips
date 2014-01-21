from collections import namedtuple

Point = namedtuple("Point", ["lat", "long"])
        
class Region(object):
    def __init__(self, firstPoint, *args):
        self._nw = firstPoint
        self._se = firstPoint
        map(self.include_point, args)
        
    def northmost(self):
        return self._nw.lat

    def eastmost(self):
        return self._se.long

    def southmost(self):
        return self._se.lat

    def westmost(self):
        return self._nw.long

    def centre(self):
        return Point((self._nw.lat + self._se.lat) / 2, (self._nw.long + self._se.long) / 2)

    def contains_point(self, point):
        if self._nw.long <= self._se.long:
            # The "normal" case
            return (point.lat <= self._nw.lat and
                    point.lat >= self._se.lat and
                    point.long >= self._nw.long and
                    point.long <= self._se.long)
        else:
            raise Exception("Not implemented")

    def include_point(self, point):
        if self.contains_point(point):
            # Check whether there is any work to do
            return

        # First, the easy one. Figure out if we need to expand the
        # region in the latitude direction
        self._nw = Point(max(point.lat, self._nw.lat), self._nw.long)
        self._se = Point(min(point.lat, self._se.lat), self._se.long)

        if self.contains_point(point):
            # Nothing left to do
            return
            
        # Longitude is the trickier one
        # Normally the westward edge will be <= than the eastward, but
        # not it the region crosses the -180 line
        if self._nw.long <= self._se.long:
            # The "normal" case
            west = self._nw.long - point.long
            if west < 0:
                west += 360
            east = point.long - self._se.long
            if east < 0:
                east += 360
            if west < east:
                self._nw = Point(self._nw.lat, point.long)
            else:
                self._se = Point(self._se.lat, point.long)
        else:
            raise Exception("Not implemented")

