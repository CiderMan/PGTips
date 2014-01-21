class ManagedMembers(object):
    def __setattr__(self, key, value):
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            raise AttributeError("Unable to set %s" % key)

    def __getattribute__(self, key):
        if key.startswith("_"):
            return object.__getattribute__(self, key)
        elif key in self._ACCESSIBLE_MEMBERS:
            return object.__getattribute__(self, "_" + key)
        else:
            raise AttributeError("Unable to get %s" % key)

class Point(ManagedMembers):
    _ACCESSIBLE_MEMBERS = [
            "lat",
            "long",
            ]

    def __init__(self, lat, long_):
        # Clip to maximum and minimum values
        # TODO: should this wrap (at least for longitude)?
        self._lat = max(min(lat, 90), -90)
        self._long = max(min(long_, 180), -180)

    def __repr__(self):
        return "Point(%+g, %+g)" % (self._lat, self._long)

class Region(object):
    def __init__(self, nw = None, se = None):
        if nw is not None:
            self._nw = Point(nw.lat, nw.long)
        else:
            self._nw = None
        if se is not None:
            self._se = Point(se.lat, se.long)
        else:
            self._se = self._nw

    def intersects(self, other):
        return True

    def _is_type1(self):
        """Type 1 is a region not spanning the wrap point at +/- 180 degrees
           Type 2 does span that wrap"""
        return self._nw.long <= self._se.long

    def __add__(self, other):
        accu = Region(self._nw, self._se)
        if other not in self:
            accu._add_something(other)
        return accu

    def _add_something(self, other):
        addPoint = False
        addRegion = False
        try:
            # Now handle the case where we are adding a point
            other.lat, other.long
            addPoint = True
        except AttributeError:
            try:
                # Handle adding a region
                other._nw, other._se
                addRegion = True
            except AttributeError:
                raise TypeError("Don't know how to add a %s to a Region" % other.__class__.__name__)

        if addPoint:
            self._add_point(other)
        elif addRegion:
            self._add_region(other)

    def _add_point(self, point):
        if not point in self:
            if self._nw is None:
                self._nw = Point(point.lat, point.long)
                self._se = self._nw
            else:
                n = self._nw.lat
                w = self._nw.long
                s = self._se.lat
                e = self._se.long

                # Expand N-S if necessary
                n = max(n, point.lat)
                s = min(s, point.lat)

                # Now consider E-W
                if self._is_type1():
                    # Type 1 region
                    needChange = point.long < w or point.long > e
                else:
                    # Type 2 region
                    needChange = point.long < w and point.long > e

                if needChange:
                    eDiff = point.long - e
                    if eDiff < 0: eDiff += 360
                    wDiff = w - point.long
                    if wDiff < 0: wDiff += 360
                    if eDiff < wDiff:
                        e = point.long
                    else:
                        w = point.long
                    # Shouldn't need the following check but added in case rounding
                    # errors cause it to trigger
                    if e == w:
                        # This region has expanded to go right around the globe so indicate that
                        e = 180
                        w = -180

                self._nw = Point(n, w)
                self._se = Point(s, e)

    def _add_region(self, region):
        if self._nw is None:
            self._nw = region._nw
            self._se = region._se
        else:
            n = self._nw.lat
            w = self._nw.long
            s = self._se.lat
            e = self._se.long

            # Expand N-S if necessary
            n = max(n, region._nw.lat)
            s = min(s, region._se.lat)

            # Update these so can use other methods later
            self._nw = Point(n, w)
            self._se = Point(s, e)

            # Create a modified version of the region we are adding with the same N-S size as we have
            r = Region(Point(n, region._nw.long), Point(s, region._se.long))

            # Now consider E-W
            if r in self:
                return
            if self in r:
                self._nw = r._nw
                self._se = r._se
                return

            count = 0
            if r._nw not in self:
                count += 1
            if r._se not in self:
                count += 2

            # count is now either:
            #  0 (nothing to do),
            #  1/2 (overlapping regions) or
            #  3 (disjoint regions)
            if count == 3:
                eDiff = r._se.long - e
                if eDiff < 0: eDiff += 360
                wDiff = w - r._nw.long
                if wDiff < 0: wDiff += 360
                if eDiff < wDiff:
                    count = 2
                else:
                    count = 1

            # Now count has been refined, if necessary, from 3 to be either 1 or 2
            if self._is_type1() != r._is_type1():
                # OK, non-matching region types, so there is a chance that the two regions
                # wrap the globe
                if count == 0:
                    # Note a sub-region so must be completing a wrap of the globe
                    e = 180
                    w = -180
                    self._nw = Point(n, w)
                    self._se = Point(s, e)

            # OK, it just remains to expand the region on the longitude 
            if count == 1:
                self._add_point(region._nw)
            elif count == 2:
                self._add_point(region._se)

    def __repr__(self):
        return "Region(nw = %s, se = %s)" % (str(self._nw), str(self._se))

    def __contains__(self, item):
        try:
            # Try for a Point style object
            return self.crosses_lat(item.lat) and self.crosses_long(item.long)
        except AttributeError:
            try:
                # Try for a Region style object
                # The NW and SE points must both be in this region but neither of this region's
                # NW nor SE may be in the other's
                return (item._nw in self and
                        item._se in self and
                        self._nw not in item and
                        self._se not in item) or (item._nw == self._nw and item._se == self._se)
            except AttributeError:
                raise TypeError("Don't know how to test for a %s in a Region" % item.__class__.__name__)

    def crosses_lat(self, lat):
        if self._nw is None:
            return False
        return lat <= self._nw.lat and lat >= self._se.lat

    def crosses_long(self, long_):
        if self._nw is None:
            return False
        if self._is_type1():
            # Type 1 region
            return long_ >= self._nw.long and long_ <= self._se.long
        else:
            # Type 2 region
            return long_ >= self._nw.long or long_ <= self._se.long
    
    def get_centre(self):
        lat = (self._nw.lat + self._se.lat) / 2
        long_ = (self._nw.long + self._se.long) / 2
        if not self._is_type1():
            long_ -= 180
            if long_ < -180:
                long_ += 360
        return Point(lat, long_)

if __name__ == "__main__":
    def test(cmd, prefix = None):
        if prefix is not None:
            print prefix,
        print cmd, "=>",
        retval = eval(cmd)
        print retval
        return retval
    r = test("Region()", "r =")
    p = test("Point(50, -4)", "p =")
    r = test("r + p", "r =")
    r2 = test("Region() + r", "r2 =")
    p2 = test("Point(50.5, 4.01)", "p2 =")
    test("r2 + p2")
    test("Region(p) + Region(p2)")
    test("Region(Point(51, -4), Point(50, -3)) + Region(Point(51.5, -3.5), Point(50.5, -2.5))")
    test("Region(Point(51, 179), Point(50, -179)) + Region(Point(51.5, 178), Point(50.5, -179.5))")
    test("Region(Point(51, 179), Point(50, -179)) + Region(Point(51.5, 179.5), Point(50.5, 178))")
    test("Region(Point(51, 100), Point(50, -100)) + Region(Point(51.5, -120), Point(50.5, 120))")

