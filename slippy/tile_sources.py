# This Python file uses the following encoding: utf-8


class TileSource:
    def __init__(self, name, prefix, attribution="", minZoom=0, maxZoom=18):
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
        return "/".join([self._prefix, str(zoom), str(xtile), str(ytile) + ".png"])

    def get_full_name(self):
        return self._name

    def get_attribution(self):
        return self._attribution


class OpenStreetMapTileSource(TileSource):
    """
    The standard OpenStreetMap tiles. Note the tile usage policy at
    https://operations.osmfoundation.org/policies/tiles/ - in particular, bulk
    downloading is prohibited and requests must carry an identifying User-Agent
    """

    def __init__(self):
        TileSource.__init__(
            self,
            "openstreetmap.org",
            "https://tile.openstreetmap.org",
            "© OpenStreetMap contributors",
            maxZoom=19,
        )
