# This Python file uses the following encoding: utf-8

class TileSource(object):
    def __init__(self, name, prefix, attribution = "", minZoom = 0, maxZoom = 18):
        self._name = name
        self._prefix = prefix
        if attribution == "":
            self._attribution = "Tiles from " + self._name.split("_")[0]
        else:
            self._attribution = attribution
        self._zoomRange = (minZoom, maxZoom)

    def get_tile_url(self, xtile, ytile, zoom):
        if zoom < self._zoomRange[0] or zoom > self._zoomRange[1]:
            return ""
        else:
            return "/".join([self._prefix, str(zoom), str(xtile), str(ytile) + ".png"])

    def get_full_name(self):
        return self._name

    def get_attribution(self):
        return self._attribution

class CloudmadeTileSource(TileSource):
    def __init__(self, apiKey):
        from datetime import date
        year = str(date.today().year)
        TileSource.__init__(
                self,
                "cloudmade.com_style1",
                "http://tile.cloudmade.com/" + apiKey + "/1/256",
                u"\u00a9 " + year + u" CloudMade  Map data CCBYSA " + year + " OpenStreetMap.org contributors")
