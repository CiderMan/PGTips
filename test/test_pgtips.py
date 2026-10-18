import base64
import contextlib
import datetime
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from test import HAVE_DISPLAY, get_wx_app
import pgtips

# Importing pgtips puts the sub-modules on the path
from imagefiles import read_orientation, set_orientation

HAVE_TOOLS = bool(shutil.which("exiftool") and shutil.which("jpegtran"))

UTC = datetime.timezone.utc

# A 32x16 pixel JPEG, red on the left and blue on the right. Note that it starts with a JFIF
# header (rather than EXIF), so any orientation flag added to it is not at the start of the file
_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwc"
    "KDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAQACADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcI"
    "CQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRol"
    "JicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ip"
    "qrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAA"
    "AAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLR"
    "ChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaX"
    "mJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEA"
    "PwDi6KKK+ZP3E5Ciiiv6XP57P//Z"
)

_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="50.0" lon="-4.0"><ele>10</ele><time>2010-09-02T10:00:00Z</time></trkpt>
    <trkpt lat="50.1" lon="-4.1"><ele>20</ele><time>2010-09-02T10:01:00Z</time></trkpt>
  </trkseg></trk>
</gpx>
"""


def _write_photo(path, orientation=None, dateTime="2010:09:02 10:00:30"):
    path.write_bytes(_JPEG)
    args = ["-DateTimeOriginal=" + dateTime]
    if orientation is not None:
        args.append("-Orientation#=%d" % orientation)
    subprocess.run(
        ["exiftool", "-q", "-overwrite_original"] + args + ["--", str(path)], check=True
    )
    return path


def _dimensions(path):
    out = subprocess.run(
        ["exiftool", "-s3", "-ImageWidth", "-ImageHeight", "--", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return tuple(int(v) for v in out.split())


def _colour(path, x, y):
    """Return the dominant colour component ("red" or "blue") of a pixel"""
    import wx

    get_wx_app()
    img = wx.Image(str(path), wx.BITMAP_TYPE_JPEG)
    return "red" if img.GetRed(x, y) > img.GetBlue(x, y) else "blue"


@unittest.skipUnless(HAVE_TOOLS, "Needs exiftool and jpegtran")
class LosslessRotateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def assertNoTempFiles(self):
        self.assertEqual([f.name for f in self.dir.iterdir()], ["photo.jpg"])

    def test_orientation_is_read_despite_jfif_header(self):
        photo = _write_photo(self.dir / "photo.jpg", 6)
        self.assertEqual(photo.read_bytes()[2:4], b"\xff\xe0")
        self.assertEqual(read_orientation(photo), 6)

    def test_rotate_90(self):
        photo = _write_photo(self.dir / "photo.jpg", 6)
        pgtips._lossless_rotate(photo, 6)
        self.assertEqual(_dimensions(photo), (16, 32))
        self.assertEqual(read_orientation(photo), 1)
        self.assertNoTempFiles()
        if HAVE_DISPLAY:
            # Rotating clockwise moves the left (red) half to the top
            self.assertEqual(_colour(photo, 8, 4), "red")
            self.assertEqual(_colour(photo, 8, 28), "blue")

    def test_rotate_180(self):
        photo = _write_photo(self.dir / "photo.jpg", 3)
        pgtips._lossless_rotate(photo, 3)
        self.assertEqual(_dimensions(photo), (32, 16))
        self.assertEqual(read_orientation(photo), 1)
        if HAVE_DISPLAY:
            self.assertEqual(_colour(photo, 4, 8), "blue")

    def test_metadata_is_kept(self):
        photo = _write_photo(self.dir / "photo.jpg", 8)
        pgtips._lossless_rotate(photo, 8)
        out = subprocess.run(
            ["exiftool", "-s3", "-DateTimeOriginal", str(photo)], capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual(out, "2010:09:02 10:00:30")

    def test_failure_leaves_file_untouched(self):
        photo = self.dir / "photo.jpg"
        photo.write_bytes(b"not a JPEG")
        with self.assertRaises(RuntimeError):
            pgtips._lossless_rotate(photo, 6)
        self.assertEqual(photo.read_bytes(), b"not a JPEG")
        self.assertNoTempFiles()


class _OfflineTileSource:
    """A tile source that never fetches anything, so that the tests don't use the network"""

    def get_full_name(self):
        return "tiles"

    def get_tile_url(self, xtile, ytile, zoom):
        return ""

    def get_attribution(self):
        return None


@unittest.skipUnless(HAVE_DISPLAY, "Needs a display")
@unittest.skipUnless(HAVE_TOOLS, "Needs exiftool and jpegtran")
class MyFrameTest(unittest.TestCase):
    def setUp(self):
        get_wx_app()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        # The options file and tile cache are relative to the current directory
        self.enterContext(contextlib.chdir(root))
        self.enterContext(
            mock.patch.object(pgtips.slippy, "OpenStreetMapTileSource", _OfflineTileSource)
        )
        self.card = root / "card"
        self.work = root / "work"
        self.filing = root / "filing"
        for d in (self.card, self.work, self.filing):
            d.mkdir()
        Path("pgtips.opt").write_text(
            json.dumps(
                {
                    "WorkingDir": str(self.work),
                    "FilingDir": str(self.filing),
                    "ImageExtensions": [".jpg"],
                    "OtherExtensions": [".mov"],
                }
            )
        )
        self.frame = pgtips.MyFrame(None)
        self.addCleanup(self.frame.OnClose, None)
        self.assertTrue(self.frame._exiftool_check())

    def pump(self, condition, timeout=20):
        """Run the event loop until the condition is true and the worker threads are idle"""
        import wx

        end = time.monotonic() + timeout
        while time.monotonic() < end:
            wx.Yield()
            time.sleep(0.02)
            if condition() and not self.frame._working and not self.frame._importing:
                return
        self.fail("Timed out")

    def images(self):
        return {img.get_filename().name: img for img in self.frame._images.iter_images()}

    def import_files(self, useJpegtran=True, emptyWorkingDir=False):
        self.frame._do_work(
            self.frame._import_files_work,
            self.card,
            self.work,
            useJpegtran,
            "jpegtran",
            emptyWorkingDir,
        )

    def test_import(self):
        _write_photo(self.card / "rotated.jpg", 6)
        (self.card / "sub").mkdir()
        _write_photo(self.card / "sub" / "upright.jpg", 1)
        (self.card / "clip.mov").write_bytes(b"video")
        (self.card / "notes.txt").write_text("ignored")
        self.import_files()
        self.pump(lambda: len(self.images()) == 2)

        self.assertEqual(
            sorted(f.name for f in self.work.iterdir()), ["clip.mov", "rotated.jpg", "upright.jpg"]
        )
        self.assertEqual(_dimensions(self.work / "rotated.jpg"), (16, 32))
        self.assertEqual(_dimensions(self.work / "upright.jpg"), (32, 16))
        self.assertEqual(self.images()["rotated.jpg"]["Orientation"], "1")
        self.assertEqual(
            self.images()["rotated.jpg"].dateTime,
            datetime.datetime(2010, 9, 2, 10, 0, 30, tzinfo=UTC),
        )
        # The originals are untouched
        self.assertEqual(read_orientation(self.card / "rotated.jpg"), 6)

    def test_import_without_jpegtran(self):
        _write_photo(self.card / "rotated.jpg", 6)
        self.import_files(useJpegtran=False)
        self.pump(lambda: len(self.images()) == 1)
        self.assertEqual(_dimensions(self.work / "rotated.jpg"), (32, 16))
        self.assertEqual(read_orientation(self.work / "rotated.jpg"), 6)

    def test_import_empties_working_dir(self):
        (self.work / "old.jpg").write_bytes(b"old")
        _write_photo(self.card / "new.jpg")
        self.import_files(emptyWorkingDir=True)
        self.pump(lambda: len(self.images()) == 1)
        self.assertEqual([f.name for f in self.work.iterdir()], ["new.jpg"])

    def test_load_gps_file(self):
        gpx = self.card / "track.gpx"
        gpx.write_text(_GPX)
        self.frame._do_work(self.frame._load_gps_files_work, gpx)
        tree = self.frame._gpxTree
        self.pump(lambda: tree.GetChildrenCount(self.frame._gpxRoot, False) == 1)
        item, cookie = tree.GetFirstChild(self.frame._gpxRoot)
        self.assertEqual(tree.GetItemText(item), "track.gpx")
        tree.SelectItem(item)
        self.pump(lambda: len(self.frame._tracks) == 1)
        self.assertEqual(self.frame._slipMap._tracks, self.frame._tracks)

    def test_geotag_and_export(self):
        gpx = self.card / "track.gpx"
        gpx.write_text(_GPX)
        _write_photo(self.card / "IMG 0001.jpg")
        self.frame._do_work(self.frame._load_gps_files_work, gpx)
        self.import_files()
        self.pump(lambda: len(self.images()) == 1)

        img = self.images()["IMG 0001.jpg"]
        self.frame.OnGeotagAll(None)
        self.pump(lambda: img.geotag is not None)
        lat, lon, alt = img.geotag
        self.assertAlmostEqual(lat, 50.05)
        self.assertAlmostEqual(lon, -4.05)
        self.assertAlmostEqual(alt, 15)
        row = self.frame._images.GetListCtrl()
        self.assertEqual(row.GetItemText(0, 2), "50.050, -4.050 (15m)")

        self.frame.OnExport(None)
        exported = self.filing / "2010" / "2010_09" / "2010_09_02" / "IMG 0001.jpg"
        self.pump(lambda: exported.exists() and len(self.images()) == 0)
        self.assertFalse((self.work / "IMG 0001.jpg").exists())
        out = subprocess.run(
            ["exiftool", "-n", "-s3", "-GPSLatitude", "-GPSLongitude", str(exported)],
            capture_output=True,
            text=True,
        ).stdout.split()
        self.assertEqual([round(float(v), 4) for v in out], [50.05, -4.05])


if __name__ == "__main__":
    unittest.main()
