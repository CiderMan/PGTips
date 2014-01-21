import wx
import os.path

_thisDir = os.path.dirname(__file__)
_pinBitmap = os.path.join(_thisDir, "pin.png")
_selectedBitmap = os.path.join(_thisDir, "selected_pin.png")
_shadowBitmap = os.path.join(_thisDir, "pin_shadow.png")
_selectedShadowBitmap = os.path.join(_thisDir, "selected_pin_shadow.png")

class MarkerImage(object):
    def __init__(self, imageName, xOffset, yOffset):
        self._image = wx.Image(imageName, wx.BITMAP_TYPE_PNG)
        self.bitmap = self._image.ConvertToBitmap()
        self.hotspot = (xOffset, yOffset)

    def hit_test(self, x, y):
        # Where x and y are within the image
        if not self._image.HasAlpha() or self._image.GetAlpha(x, y) > 127:
            return True
        else:
            return False

class Marker(object):
    _defaultPinImage = None
    _defaultShadowImage = None
    _defaultSelectedImage = None
    _defaultSelectedShadowImage = None

    def __init__(self,
                 markerId,
                 lat,
                 long,
                 markerValue = None,
                 movable = True,
                 selectable = True,
                 **kwargs):
        self.id = markerId
        self.lat = lat
        self.long = long
        self.value = markerValue
        self.movable = movable
        self.selectable = selectable
        self._selected = False

        try:
            self._pin = kwargs["pinImage"]
        except:
            if self._defaultPinImage is None:
                Marker._defaultPinImage = MarkerImage(_pinBitmap, 15, 28)
            self._pin = self._defaultPinImage

        try:
            self._selectedPin = kwargs["selectedImage"]
        except:
            if kwargs.has_key("pinImage"):
                self._selectedPin = self._pin
            else:
                if self._defaultSelectedImage is None:
                    Marker._defaultSelectedImage = MarkerImage(_selectedBitmap, 15, 28)
                self._selectedPin = self._defaultSelectedImage

        try:
            self._shadow = kwargs["shadowImage"] # May be None for no shadow
        except:
            if self._defaultShadowImage is None:
                Marker._defaultShadowImage = MarkerImage(_shadowBitmap, 4, 28)
            self._shadow = self._defaultShadowImage

        try:
            self._selectedShadow = kwargs["selectedShadowImage"]
        except:
            if kwargs.has_key("shadowImage"):
                self._selectedShadow = self._shadow
            else:
                if self._defaultSelectedShadowImage is None:
                    Marker._defaultSelectedShadowImage = MarkerImage(_selectedShadowBitmap, 4, 28)
                self._selectedShadow = self._defaultSelectedShadowImage

        self.pin = self._pin
        self.shadow = self._shadow

        self.aboveHotspot = max(self.pin.hotspot[1], self.shadow.hotspot[1])
        self.belowHotspot = max(self.pin.bitmap.GetHeight() - self.pin.hotspot[1],
                                self.shadow.bitmap.GetHeight() - self.shadow.hotspot[1])
        self.beforeHotspot = max(self.pin.hotspot[0], self.shadow.hotspot[0])
        self.afterHotspot = max(self.pin.bitmap.GetWidth() - self.pin.hotspot[0],
                                self.shadow.bitmap.GetWidth() - self.shadow.hotspot[0])

    def __lt__(self, other):
        try:
            return self.id < other.id
        except AttributeError:
            return self.id < other

    def __le__(self, other):
        try:
            return self.id <= other.id
        except AttributeError:
            return self.id <= other

    def __eq__(self, other):
        try:
            return self.id == other.id
        except AttributeError:
            return self.id == other

    def __ne__(self, other):
        try:
            return self.id != other.id
        except AttributeError:
            return self.id != other

    def __gt__(self, other):
        try:
            return self.id > other.id
        except AttributeError:
            return self.id > other

    def __ge__(self, other):
        try:
            return self.id >= other.id
        except AttributeError:
            return self.id >= other

    def hit_test(self, xOffset, yOffset):
        # Note: Offset is relative to the hotspot - convert to TL relative
        xOffset += self.pin.hotspot[0]
        yOffset += self.pin.hotspot[1]
        if (xOffset >= 0 and xOffset < self.pin.bitmap.GetWidth() and
            yOffset >= 0 and yOffset < self.pin.bitmap.GetHeight()):
            return self.pin.hit_test(xOffset, yOffset)
        else:
            return False

    def select(self, selected = True):
        assert self.selectable, "Attempt to select an unselectable marker"
        if selected:
            self.pin = self._selectedPin
            self.shadow = self._selectedShadow
            self._selected = True
        else:
            self.pin = self._pin
            self.shadow = self._shadow
            self._selected = False
