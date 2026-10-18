import urllib.request
import os
import tempfile
from pathlib import Path
from threading import Thread
from queue import Queue, Empty
import shutil

_USER_AGENT = "PGTips/0.1 (+https://github.com/CiderMan/PGTips)"


class SlippyCache:
    """This is a basic map tile cache used by the SlippyPanel class
    to retrieve and store locally the images that form the map"""

    def __init__(self, source, proxy=""):
        self.source = source
        handlers = []
        if len(proxy) > 0:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        self._opener = urllib.request.build_opener(*handlers)
        self._opener.addheaders = [("User-Agent", _USER_AGENT)]
        self._fetchQueue = Queue(0)
        self._fetchThread = Thread(target=self._FetchTile, daemon=True)
        self._fetchThread.start()

    def _FetchTile(self):
        task = ""
        while task is not None:
            task = self._fetchQueue.get()
            url, fname = task
            if url and not fname.is_file():
                print("Getting", fname)
                try:
                    # Download alongside the final file so that the tile only appears
                    # in the cache once it is complete
                    fd, tmpName = tempfile.mkstemp(suffix=".png", dir=fname.parent)
                    tmpFile = Path(tmpName)
                    try:
                        with os.fdopen(fd, "wb") as f, self._opener.open(url, timeout=30) as r:
                            shutil.copyfileobj(r, f)
                        tmpFile.replace(fname)
                    except BaseException:
                        tmpFile.unlink()
                        raise
                except (OSError, ValueError) as e:
                    print("Failed to get", url, "-", e)
            self._fetchQueue.task_done()

    def StartNewFetchBatch(self):
        try:
            while True:
                self._fetchQueue.get(False)
                self._fetchQueue.task_done()
        except Empty:
            pass

    def GetTileFilename(self, xtile, ytile, zoom):
        numTiles = 2**zoom
        while xtile >= numTiles:
            xtile -= numTiles
        if xtile < 0 or ytile < 0 or ytile >= numTiles:
            # Indicate that this is not a valid tile
            return None
        fname = Path(self.source.get_full_name(), str(zoom), str(xtile), str(ytile) + ".png")
        if not fname.is_file():
            url = self.source.get_tile_url(xtile, ytile, zoom)
            # Ensure that the directory exists
            fname.parent.mkdir(parents=True, exist_ok=True)
            self._fetchQueue.put((url, fname))
        # Valid tile, though may not be present in the cache
        return fname
