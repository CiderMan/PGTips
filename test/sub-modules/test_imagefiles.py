import base64
import datetime
import shutil
import subprocess
import unittest
from pathlib import Path

from test import temp_dir
import imagefiles
from imagefiles import (
    AmbiguousKeyError,
    ExifFile,
    ExiftoolException,
    _parse_exiftool_datetime,
    gen_images_from_files,
    read_orientation,
    set_orientation,
)

UTC = datetime.timezone.utc

# An 8x8 pixel JPEG with no EXIF data
_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwc"
    "KDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjL/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL"
    "/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJico"
    "KSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKz"
    "tLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAEC"
    "AwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYk"
    "NOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJma"
    "oqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5"
    "/ooooA//2Q=="
)


class ParseExiftoolDatetimeTest(unittest.TestCase):
    def test_default_timezone(self):
        tz = datetime.timezone(datetime.timedelta(hours=2))
        self.assertEqual(
            _parse_exiftool_datetime("2010:09:02 16:29:47", tz),
            datetime.datetime(2010, 9, 2, 16, 29, 47, tzinfo=tz),
        )

    def test_explicit_timezone(self):
        self.assertEqual(
            _parse_exiftool_datetime("2011:01:22 17:51:36-05:00", UTC),
            datetime.datetime(2011, 1, 22, 22, 51, 36, tzinfo=UTC),
        )

    def test_subseconds(self):
        self.assertEqual(
            _parse_exiftool_datetime("2011:01:22 17:51:36.5", UTC).microsecond, 500000
        )

    def test_unset(self):
        with self.assertRaises(ValueError):
            _parse_exiftool_datetime("0000:00:00 00:00:00", UTC)

    def test_garbage(self):
        with self.assertRaises(ValueError):
            _parse_exiftool_datetime("yesterday", UTC)


class ExifFileTest(unittest.TestCase):
    def exif(self, **namespaces):
        return ExifFile("photo.jpg", namespaces, UTC)

    def test_lookup(self):
        f = self.exif(System={"FileName": "photo.jpg"}, IFD0={"Model": "X"})
        self.assertEqual(f["Model"], "X")
        self.assertEqual(f["System", "FileName"], "photo.jpg")
        self.assertEqual(f.get_filename(), Path("photo.jpg"))
        with self.assertRaises(KeyError):
            _ = f["Missing"]

    def test_ambiguous_lookup(self):
        f = self.exif(A={"Model": "X"}, B={"Model": "Y"})
        with self.assertRaises(AmbiguousKeyError):
            _ = f["Model"]

    def test_embedded_image(self):
        self.assertTrue(self.exif(Preview={"PreviewImage": "(Binary data)"}).has_embedded_image())
        self.assertTrue(self.exif(MakerNotes={"JpgFromRaw": "(Binary data)"}).has_embedded_image())
        self.assertFalse(self.exif(System={"FileName": "photo.jpg"}).has_embedded_image())

    def test_no_date_or_geotag(self):
        f = self.exif(System={})
        self.assertIsNone(f.dateTime)
        self.assertIsNone(f.geotag)

    def test_unset_date(self):
        self.assertIsNone(self.exif(ExifIFD={"DateTimeOriginal": "0000:00:00 00:00:00"}).dateTime)

    def test_geotag(self):
        gps = {
            "GPSLatitude": "50.5",
            "GPSLatitudeRef": "S",
            "GPSLongitude": "4.25",
            "GPSLongitudeRef": "W",
            "GPSAltitude": "12",
            "GPSAltitudeRef": "1",
        }
        self.assertEqual(self.exif(GPS=gps).geotag, (-50.5, -4.25, -12.0))

    def test_geotag_without_altitude(self):
        gps = {
            "GPSLatitude": "50.5",
            "GPSLatitudeRef": "N",
            "GPSLongitude": "4.25",
            "GPSLongitudeRef": "E",
        }
        self.assertEqual(self.exif(GPS=gps).geotag, (50.5, 4.25, None))


@unittest.skipUnless(shutil.which("exiftool"), "Needs exiftool")
class ExiftoolTest(unittest.TestCase):
    def setUp(self):
        imagefiles._DEBUG = False
        self.dir = temp_dir(self)
        # A name that would be mangled by a shell, and that isn't ASCII
        self.path = self.dir / "café photo's $HOME.jpg"
        self.path.write_bytes(_JPEG)
        subprocess.run(
            [
                "exiftool",
                "-q",
                "-overwrite_original",
                "-DateTimeOriginal=2010:09:02 16:29:47",
                "-Orientation#=6",
                "--",
                str(self.path),
            ],
            check=True,
        )

    def load(self, files=None, **kwargs):
        return list(gen_images_from_files(self.path if files is None else files, **kwargs))

    def test_read(self):
        (img,) = self.load()
        self.assertEqual(img.get_filename(), self.path)
        self.assertEqual(img["FileName"], self.path.name)
        self.assertEqual(img["FileType"], "JPEG")
        self.assertEqual(img["Orientation"], "6")
        self.assertEqual(img.dateTime, datetime.datetime(2010, 9, 2, 16, 29, 47, tzinfo=UTC))
        self.assertIsNone(img.geotag)

    def test_default_timezone(self):
        (img,) = self.load(defaultTzHours=1)
        self.assertEqual(img.dateTime, datetime.datetime(2010, 9, 2, 15, 29, 47, tzinfo=UTC))

    def test_write_geotag(self):
        (img,) = self.load()
        img.set_geotag((-50.5, -4.25, 12.5))
        img.save_changes()
        (img,) = self.load()
        lat, lon, alt = img.geotag
        self.assertAlmostEqual(lat, -50.5)
        self.assertAlmostEqual(lon, -4.25)
        self.assertAlmostEqual(alt, 12.5)

    def test_remove_geotag(self):
        (img,) = self.load()
        img.set_geotag((50.5, 4.25, None))
        img.save_changes()
        (img,) = self.load()
        self.assertIsNotNone(img.geotag)
        img.set_geotag(None)
        img.save_changes()
        (img,) = self.load()
        self.assertIsNone(img.geotag)

    def test_directory_with_filter(self):
        (self.dir / "notes.txt").write_text("not an image")
        (self.dir / "sub").mkdir()
        shutil.copy(self.path, self.dir / "sub" / "second.JPG")
        images = self.load(self.dir, include=[".jpg"])
        self.assertEqual(
            sorted(i.get_filename().name for i in images), sorted(["second.JPG", self.path.name])
        )

    def test_read_orientation(self):
        self.assertEqual(read_orientation(self.path), 6)

    def test_set_orientation(self):
        set_orientation(self.path, 1)
        self.assertEqual(read_orientation(self.path), 1)
        (img,) = self.load()
        self.assertEqual(img.dateTime, datetime.datetime(2010, 9, 2, 16, 29, 47, tzinfo=UTC))

    def test_no_orientation(self):
        plain = self.dir / "plain.jpg"
        plain.write_bytes(_JPEG)
        self.assertIsNone(read_orientation(plain))

    def test_orientation_of_missing_file(self):
        with self.assertRaises(ExiftoolException):
            read_orientation(self.dir / "missing.jpg")

    def test_no_files(self):
        self.assertEqual(self.load(self.dir, include=[".mrw"]), [])


if __name__ == "__main__":
    unittest.main()
