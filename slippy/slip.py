from math import *
from utils import *
from regions import Point, Region
import wx
import os.path

_DEFAULT_ZOOM = 15


def get_tile_number(zoom, lat, long):
    n = 2 ** zoom

    xtile = ((long + 180) / 360) * n
    xpixel, xtile = modf(xtile)
    xtile = int(xtile)
    xpixel = int(xpixel * 256)

    lat_radians = radians(lat)
    ytile = (1 - (log(tan(lat_radians) + 1 / cos(lat_radians)) / pi)) / 2 * n
    ypixel, ytile = modf(ytile)
    ytile = int(ytile)
    ypixel = int(ypixel * 256)

    return (xtile, xpixel, ytile, ypixel)

def get_lat_long(xtile, ytile, zoom):
    n = 2 ** zoom

    long = xtile / n * 360.0 - 180.0;
    lat = (atan(sinh(pi * (1 - 2 * ytile / n)))) * 180 / pi

    return (lat, long)

def lat_long_from_pixel(x, y, zoom):
    n = 2 ** zoom
    xtile = float(x)
    xtile /= _TILE_SIZE
    xtile %= n
    ytile = float(y)
    ytile /= _TILE_SIZE
    ytile %= n
    return get_lat_long(xtile, ytile, zoom)

class SlippyPanel(wx.Panel):
    def __init__(self, *args, **kwargs):
        try:
            self._cache = kwargs["cache"]
            del kwargs["cache"]
        except KeyError:
            raise Exception("No cache specified in SlippyPanel constructor")

        wx.Panel.__init__(self, *args, **kwargs)

        if "size" not in kwargs.keys():
            self.SetSize((2 * _TILE_SIZE, 2 * _TILE_SIZE))
        self._bitmapZoom = 0
        self._bitmaps = {}
        self._tiles = []
        self._size = self.GetSizeTuple()
        self._pollTimer = wx.Timer(self, -1)

        # start with the single zoom 0 tile centred on the panel
        self._zoom = 0
        res = _TILE_SIZE # Zoom = 0 so the world is a single tile
        # _tlx and _tly are the top-left co-ordinate in map space. However, the tlx value
        # is kept positive to allow wrapping
        self._tlx = _TILE_SIZE - self._size[0]
        self._tly = _TILE_SIZE - self._size[1]

        self._markers = []
        self._activeMarker = None

        self._tracks = []

        self._PopulateTiles()

        self._wheelDelta = 0
        self._oldFocus = None
        self._lastMove = (0, 0)

        # This is required to allow use of buffered DCs
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnEnterWindow)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)

    def get_coordinate(self, lat, long):
        n = 2 ** self._zoom

        xtile = ((long + 180) / 360) * n

        lat_radians = radians(lat)
        ytile = (1 - (log(tan(lat_radians) + 1 / cos(lat_radians)) / pi)) / 2 * n

        return (round(xtile * _TILE_SIZE), round(ytile * _TILE_SIZE))

    def OnTimer(self, evt):
        waiting = False
        moreAvail = False
        newTiles = []
        for tile, x, y in self._tiles:
            if type(tile) is str:
                # This is a filename that wasn't ther last time we checked
                if os.path.isfile(tile):
                    # There now
                    tile = wx.Image(tile, wx.BITMAP_TYPE_PNG).ConvertToBitmap()
                    moreAvail = True
                else:
                    waiting = True
                newTiles.append((tile, x, y))
            else:
                newTiles.append((tile, x, y))
        if not waiting:
            self._pollTimer.Stop()
        self._tiles = newTiles
        if moreAvail:
            self.Refresh()

    def _region_overlaps_viewport(self, a, b, c, d):
        # TODO
        return True

    def _PopulateTiles(self):
        self._cache.StartNewFetchBatch()
        # Ensure that the top-left X is not negative
        res = (2 ** self._zoom) * _TILE_SIZE
        while self._tlx < 0:
            self._tlx += res

        # Now work out the tile index for the top-left corner
        xtile, ytile = self._tlx / _TILE_SIZE, self._tly / _TILE_SIZE
        # Now work out where this tile should be drawn relative to the top-left
        xord, yord = -(self._tlx - xtile * _TILE_SIZE), -(self._tly - ytile * _TILE_SIZE)

        oldBitmaps = self._bitmaps
        if self._zoom != self._bitmapZoom:
            oldBitmaps = {}
            self._bitmapZoom = self._zoom
        self._bitmaps = {}
        self._tiles = []

        xnum = (self._size[0] - 1) / _TILE_SIZE + 1
        ynum = (self._size[1] - 1) / _TILE_SIZE + 1
        needToWait = False
        for x in range(xnum + 1):
            for y in range(ynum + 1):
                xindex = xtile + x
                yindex = ytile + y
                try:
                    tile = oldBitmaps[(xindex, yindex)]
                    self._tiles.append((tile, xord + x * _TILE_SIZE, yord + y * _TILE_SIZE))
                    self._bitmaps[(xindex, yindex)] = tile
                except:
                    fname = self._cache.GetTileFilename(xtile + x, ytile + y, self._zoom)
                    if fname is not None:
                        if os.path.isfile(fname):
                            tile = wx.Image(fname, wx.BITMAP_TYPE_PNG).ConvertToBitmap()
                            self._bitmaps[(xindex, yindex)] = tile
                        else:
                            # Not currently in the cache
                            tile = fname
                            needToWait = True
                        self._tiles.append((tile, xord + x * _TILE_SIZE, yord + y * _TILE_SIZE))
        if needToWait:
            self._pollTimer.Start(200)

        self._visibleTracks = []

        latWraps = self._size[1] >= (_TILE_SIZE * (2 ** self._zoom))
        longWraps = self._size[0] >= (_TILE_SIZE * (2 ** self._zoom))
        lat, long_ = lat_long_from_pixel(self._tlx, self._tly, self._zoom)
        tl = Point(90 if latWraps else lat, -180 if longWraps else long_)
        lat, long_ = lat_long_from_pixel(self._tlx + self._size[0],
                                         self._tly + self._size[1],
                                         self._zoom)
        br = Point(90 if latWraps else lat, 180 if longWraps else long_)
        viewport_region = Region(tl, br)

        for track in self._tracks:
            r = track.get_region()
            ttlx, ttly = self.get_coordinate(r._nw.lat, r._nw.long)
            tbrx, tbry = self.get_coordinate(r._se.lat, r._se.long)
            if r.intersects(viewport_region):
                self._visibleTracks.append(track)

        self._visibleMarkers = []
        for marker in self._markers:
            markerX, markerY = self.get_coordinate(marker.lat, marker.long)
            if self._region_overlaps_viewport(
                    markerX - marker.beforeHotspot,
                    markerY - marker.aboveHotspot,
                    markerX + marker.afterHotspot,
                    markerY + marker.belowHotspot):
                self._visibleMarkers.append((markerX - self._tlx, markerY - self._tly, marker))

    def OnPaint(self, evt):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush("WHITE"))
        dc.Clear()

        dc.SetPen(wx.Pen("BLUE", 3))

        for tile, x, y in self._tiles:
            if type(tile) is str:
                pass
            else:
                dc.DrawBitmap(tile, x, y, False)

        for track in self._visibleTracks:
            # Add an extra point a single pixel offset from the last point as the last pixel is not drawn
            extraX, extraY = track.get_track(self._zoom)[-1]
            extraPoint = extraX + 1, extraY
            dc.DrawLines([wx.Point(p[0] - self._tlx, p[1] - self._tly) for p in track.get_track(self._zoom)] +
                         [wx.Point(extraPoint[0] - self._tlx, extraPoint[1] - self._tly)])

        for markerX, markerY, marker in self._visibleMarkers:
            if marker.shadow is not None:
                hotspot = marker.shadow.hotspot
                dc.DrawBitmap(marker.shadow.bitmap, markerX - hotspot[0], markerY - hotspot[1], True)
            hotspot = marker.pin.hotspot
            dc.DrawBitmap(marker.pin.bitmap, markerX - hotspot[0], markerY - hotspot[1], True)

        if len(self._tiles) > 0:
            attribution = self._cache.source.get_attribution()
            if attribution is not None:
                dc.SetFont(wx.Font(8, wx.SWISS, wx.ITALIC, wx.NORMAL, False))
                dc.DrawText(attribution, 2, 2)

        dc.SetPen(wx.NullPen)

    def OnSize(self, evt):
        newSize = self.GetSizeTuple()
        self._tlx += (self._size[0] - newSize[0]) / 2
        self._tly += (self._size[1] - newSize[1]) / 2
        self._size = newSize
        self._PopulateTiles()
        self.Refresh()

    def OnEnterWindow(self, evt):
        self._oldFocus = wx.Window.FindFocus()
        self.SetFocus()

    def OnLeaveWindow(self, evt):
        if self._oldFocus is not None:
            self._oldFocus.SetFocus()
            self._oldFocus = None

    def OnMotion(self, evt):
        if evt.LeftIsDown():
            xdiff, ydiff = evt.GetPosition()
            xdiff -= self._lastMove[0]
            ydiff -= self._lastMove[1]
            if self._activeMarker is not None and self._activeMarker.movable:
                markerX, markerY = self._activeMarkerXy
                markerX += xdiff
                markerY += ydiff
                self._activeMarkerXy = (markerX, markerY)
                lat, long = get_lat_long(float(markerX + self._tlx) / _TILE_SIZE, float(markerY + self._tly) / _TILE_SIZE, self._zoom)
                self._activeMarker.lat = lat
                self._activeMarker.long = long
            else:
                self._tlx -= xdiff
                self._tly -= ydiff
            self._PopulateTiles()
            self.Refresh()
            self.Update()
        self._lastMove = evt.GetPosition()

    def OnMouseWheel(self, evt):
        # This needs reworking but works well enough for now
        delta = self._wheelDelta + evt.GetWheelRotation()
        isPositive = delta > 0
        if not isPositive:
            delta = - delta
        steps = delta / evt.GetWheelDelta()
        if steps == 0:
            self._wheelDelta += evt.GetWheelRotation()
        else:
            where = evt.GetPositionTuple()
            xord = where[0] + self._tlx
            yord = where[1] + self._tly
            lat, long = get_lat_long(float(xord) / _TILE_SIZE, float(yord) / _TILE_SIZE, self._zoom)

            self._wheelDelta = delta - steps * evt.GetWheelDelta()
            if isPositive:
                self._zoom += steps
                if self._zoom > 18:
                    self._zoom = 18
            else:
                self._wheelDelta = - self._wheelDelta
                self._zoom -= steps
                if self._zoom < 0:
                    self._zoom = 0

            self.CentreMap(lat, long, point = where)

    def OnLeftDown(self, evt):
        needRefresh = False
        evtPos = evt.GetPosition()
        p = None
        for x, y, marker in self._visibleMarkers:
            xOffset = evtPos[0] - x
            yOffset = evtPos[1] - y
            if marker.hit_test(xOffset, yOffset):
                p = marker
                pX = x
                pY = y
        if self._activeMarker is not None and self._activeMarker.selectable:
            self._activeMarker.select(False)
            needRefresh = True
        self._activeMarker = p
        if p:
            if p.selectable:
                p.select()
                needRefresh = True
            # print "Hit marker with ID", p.id
            self._activeMarkerXy = (pX, pY)
        if needRefresh:
            self._PopulateTiles()
            self.Refresh()
        evt.Skip()

    def AddMarker(self, marker):
        self._markers.append(marker)
        self._PopulateTiles()
        self.Refresh()

    def GetMarker(self, marker):
        try:
            return self._markers[self._markers.index(marker)]
        except ValueError:
            return None

    def GetSelectedMarker(self):
        if self._activeMarker is not None and self._activeMarker.selectable:
            return self._activeMarker
        else:
            return None

    def RemoveMarker(self, marker):
        if self._activeMarker == marker:
            if self._activeMarker.selectable:
                self._activeMarker.select(False)
            self._activeMarker = None
        try:
            while True:
                self._markers.remove(marker)
        except ValueError:
            pass
        finally:
            self._PopulateTiles()
            self.Refresh()

    def AddTrack(self, track):
        self._tracks.append(track)
        self._PopulateTiles()
        self.Refresh()

    def RemoveTrack(self, track):
        try:
            while True:
                self._tracks.remove(track)
        except ValueError:
            pass
        self._PopulateTiles()
        self.Refresh()

    def ShowRegion(self, region):
        def get_extent(zoom):
            # Note the latitude swap due to the opposite way round
            br = _get_coordinate(region._se.lat, region._se.long, zoom)
            tl = _get_coordinate(region._nw.lat, region._nw.long, zoom)
            return (br[0] - tl[0], br[1] - tl[1], zoom)

        def return_best_fit(x, y):
            if y[0] < self._size[0] and y[1] < self._size[1]:
                return y
            else:
                return x

        best = reduce(return_best_fit, map(get_extent, range(19)), None)
        c = region.get_centre()
        self.CentreMap(c.lat, c.long, best[2])

    def CentreMap(self, lat, long, zoom = None, point = None):
        if zoom is None:
            try:
                zoom = self._zoom
            except:
                zoom = _DEFAULT_ZOOM
        self._zoom = zoom
        if point is None:
            xsize, ysize = self._size
            xstart = xsize / 2
            ystart = ysize / 2
        else:
            xstart, ystart = point
        xtile, xpixel, ytile, ypixel = get_tile_number(zoom, lat, long)
        self._tlx = xtile * _TILE_SIZE + xpixel - xstart
        self._tly = ytile * _TILE_SIZE + ypixel - ystart
        self._PopulateTiles()
        self.Refresh()
