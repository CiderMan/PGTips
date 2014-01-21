from urllib import URLopener
import os.path
from threading import Thread
from Queue import Queue, Empty
import shutil

class SlippyCache(object):
    """This is a basic map tile cache used by the SlippyPanel class
    to retrieve and store locally the images that form the map"""
    def __init__(self, source, proxy = ""):
        self.source = source
        if len(proxy) > 0:
            self._opener = URLopener({"http": proxy})
        else:
            self._opener = URLopener()
        self._fetchQueue = Queue(0)
        self._fetchThread = Thread(target = self._FetchTile)
        self._fetchThread.setDaemon(True)
        self._fetchThread.start()

    def _FetchTile(self):
        task = ""
        while task is not None:
            task = self._fetchQueue.get()
            url, fname = task
            if not os.path.isfile(fname):
                print "Getting", fname
                try:
                    self._opener.retrieve(url, "tmp.png")
                    shutil.move("tmp.png", fname)
                except IOError:
                    pass
            self._fetchQueue.task_done()

    def StartNewFetchBatch(self):
        try:
            while True:
                item = self._fetchQueue.get(False)
                self._fetchQueue.task_done()
        except Empty:
            pass

    def GetTileFilename(self, xtile, ytile, zoom):
        numTiles = 2 ** zoom
        while xtile >= numTiles:
            xtile -= numTiles
        if xtile < 0 or ytile < 0 or ytile >= numTiles:
            # Indicate that this is not a valid tile
            return None
        else:
            fname = "/".join([self.source.get_full_name(), str(zoom), str(xtile), str(ytile) + ".png"])
            if not os.path.isfile(fname):
                url = self.source.get_tile_url(xtile, ytile, zoom)
                # Ensure that the directory exists
                dname = os.path.dirname(fname)
                if not os.path.isdir(dname):
                    os.makedirs(dname)
                self._fetchQueue.put((url, fname))
            # Valid tile, though may not be present in the cache
            return fname
