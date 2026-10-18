import sys, datetime, re
from pathlib import Path, PurePath
import subprocess
import xml.etree.ElementTree as ET
from subprocess import Popen, PIPE

_DEBUG = True


class ExiftoolException(Exception):
    pass


def _find_all_files(files, include, exclude):
    def wanted(f):
        ext = f.suffix.lower()
        return (include is None or ext in include) and (exclude is None or ext not in exclude)

    fList = []
    if isinstance(files, (str, PurePath)):
        files = [files]
    if _DEBUG:
        print(files)

    for path in map(Path, files):
        if path.is_file():
            if wanted(path):
                fList.append(path)
        else:
            for dirpath, dirnames, filenames in path.walk():
                fList += [dirpath / f for f in filenames if wanted(dirpath / f)]

    return fList


_popenKwds = {}

if sys.platform == "win32":
    # Run the pipes without popping up a console window
    _popenKwds["creationflags"] = subprocess.CREATE_NO_WINDOW

# Ensure that exiftool interprets (and reports) file names as UTF-8. This matters on
# Windows, where it would otherwise use the system code page
_exiftoolCharsetArgs = ["-charset", "filename=utf8"]

_exiftool_date = re.compile(
    "^(?P<year>[0-9]{4}):(?P<month>[0-9]{2}):(?P<day>[0-9]{2})(?P<rest>.*)$"
)


def _parse_exiftool_datetime(time, defaultTz):
    # EXIF date/times look like "2010:09:02 16:29:47", optionally followed by
    # sub-seconds and/or a time zone. Convert the date separators so that it
    # can be parsed as an ISO 8601 date/time
    m = _exiftool_date.match(time.strip())
    if m is None:
        raise ValueError("Unrecognised exiftool date/time: %r" % time)
    dt = datetime.datetime.fromisoformat(
        "%s-%s-%s%s" % (m.group("year"), m.group("month"), m.group("day"), m.group("rest"))
    )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=defaultTz)
    return dt


class ExifFile:
    managedAttributes = [
        "dateTime",
        "geotag",
    ]

    def __init__(self, filename, exifDict, defaultTz, exiftool="exiftool"):
        self._exiftool = exiftool
        self._filename = Path(filename)
        self._namespaces = exifDict
        self._defaultTz = defaultTz
        self._modified = False
        try:
            self._dateTime = _parse_exiftool_datetime(self["DateTimeOriginal"], defaultTz)
        except (KeyError, ValueError):
            # Missing or unset (e.g. "0000:00:00 00:00:00")
            self._dateTime = None
        try:
            try:
                alt = float(self["GPS", "GPSAltitude"])
                if int(self["GPS", "GPSAltitudeRef"]) == 1:
                    alt = -alt
            except (KeyError, TypeError, ValueError):
                alt = None
            lat = float(self["GPS", "GPSLatitude"])
            if self["GPS", "GPSLatitudeRef"][0] == "S":
                lat = -lat
            lon = float(self["GPS", "GPSLongitude"])
            if self["GPS", "GPSLongitudeRef"][0] == "W":
                lon = -lon
            self._geotag = (lat, lon, alt)
        except (KeyError, TypeError, ValueError, IndexError):
            self._geotag = None

    def __getattr__(self, attr):
        if attr in self.managedAttributes:
            return getattr(self, "_" + attr)
        else:
            raise AttributeError(
                "Class %s does not have attribute %s" % (self.__class__.__name__, attr)
            )

    def __getitem__(self, index):
        if isinstance(index, str):
            # Need to search
            found = []
            for namespace in self._namespaces.values():
                try:
                    found.append(namespace[index])
                except KeyError:
                    pass  # Not found in this namespace
            if len(found) == 0:
                raise KeyError("EXIF data for %s doesn't have key %s" % (self._filename, index))
            elif len(found) > 1:
                raise Exception(
                    "Key %s is not unique in EXIF data for %s" % (index, self._filename)
                )
            else:
                return found[0]
        else:
            assert (
                isinstance(index, tuple) and len(index) == 2
            ), "Index must be a string or a tuple of 2 strings"
            return self._namespaces[index[0]][index[1]]

    def get_filename(self):
        return self._filename

    def set_geotag(self, geotag):
        assert geotag is None or len(geotag) == 3, "geotag must be (lat, lon, alt) or None"
        self._geotag = geotag
        self._modified = True

    def save_changes(self):
        if self._modified:
            if self._geotag is None:
                # Remove geotag
                exiftoolArgs = ["-q", "-overwrite_original", "-gps:all="]
            else:
                lat, lon, alt = self._geotag
                latRef, lonRef, altRef = "N", "E", 0

                if lat < 0:
                    lat = -lat
                    latRef = "S"

                if lon < 0:
                    lon = -lon
                    lonRef = "W"

                if alt is not None and alt < 0:
                    alt = -alt
                    altRef = 1

                exiftoolArgs = ["-q", "-n", "-overwrite_original"]
                exiftoolArgs += ["-GPSLatitude=%f" % lat, "-GPSLatitudeRef=%s" % latRef]
                exiftoolArgs += ["-GPSLongitude=%f" % lon, "-GPSLongitudeRef=%s" % lonRef]
                if alt is not None:
                    exiftoolArgs += ["-GPSAltitude=%f" % alt, "-GPSAltitudeRef=%d" % altRef]

            pipe = Popen(
                [self._exiftool] + _exiftoolCharsetArgs + exiftoolArgs + ["--", self._filename],
                stdin=PIPE,
                stdout=PIPE,
                **_popenKwds,
            )
            pipe.communicate()
            if pipe.returncode != 0:
                raise ExiftoolException()
            self._modified = False

    def has_embedded_image(self):
        try:
            self["PreviewImage"]
            return True
        except KeyError:
            try:
                self["JpgFromRaw"]
                return True
            except KeyError:
                return False


def read_orientation(filename, exiftool="exiftool"):
    """
    Return the EXIF orientation (1-8) of the file, or None if it doesn't have one
    """
    p = subprocess.run(
        [exiftool] + _exiftoolCharsetArgs + ["-n", "-s3", "-Orientation", "--", str(filename)],
        stdin=PIPE,
        capture_output=True,
        text=True,
        **_popenKwds,
    )
    if p.returncode != 0:
        raise ExiftoolException(p.stderr.strip())
    try:
        return int(p.stdout)
    except ValueError:
        return None


def set_orientation(filename, orientation, exiftool="exiftool"):
    """
    Set the EXIF orientation (1-8) of the file
    """
    p = subprocess.run(
        [exiftool]
        + _exiftoolCharsetArgs
        + [
            "-q",
            "-n",
            "-overwrite_original",
            "-Orientation=%d" % orientation,
            "--",
            str(filename),
        ],
        stdin=PIPE,
        capture_output=True,
        text=True,
        **_popenKwds,
    )
    if p.returncode != 0:
        raise ExiftoolException(p.stderr.strip())


class _ExifContext:
    def __init__(self, defaultTz, exiftool):
        self._root = None
        self._namespaces = []
        self._defaultTz = defaultTz
        self._exiftool = exiftool

    def gen_exif_files(self, pipe):
        for exiffiles in self._gen_exiffile_objects(
            self._gen_file_descriptions(pipe), self._exiftool
        ):
            yield exiffiles

    def _reverse_namespace(self, tag):
        if tag.startswith("{"):
            uri, shortTag = tag[1:].split("}")
            for shortForm, longForm in self._namespaces:
                if uri == longForm:
                    return shortForm, shortTag
            else:
                print("*** Could not match namespace", uri)
                return "", tag
        else:
            return "", tag

    def _gen_file_descriptions(self, pipe):
        for event, item in ET.iterparse(
            pipe.stdout, events=("start", "end", "start-ns", "end-ns")
        ):
            if event == "start-ns":
                self._namespaces.append(item)
            elif event == "end-ns":
                self._namespaces.pop(-1)
            elif event == "start":
                if self._root is None:
                    self._root = item
            else:
                if self._reverse_namespace(item.tag) == ("rdf", "Description"):
                    yield item

    def _gen_exiffile_objects(self, fileDescriptions, exiftool):
        for description in fileDescriptions:
            about = None
            for key in description.keys():
                if self._reverse_namespace(key) == ("rdf", "about"):
                    about = description.get(key)
            exif = {}
            for item in description:
                key = self._reverse_namespace(item.tag)
                exif.setdefault(key[0], {})[key[1]] = item.text
            self._root.clear()
            yield ExifFile(about, exif, self._defaultTz, exiftool)


_tagsToExtract = [
    "-PreviewImage",
    "-JpgFromRaw",
    "-FileType",
    "-FileName",
    "-Directory",
    "-Manufacturer",
    "-Model",
    "-DateTimeOriginal",
    "-GPSLatitude",
    "-GPSLatitudeRef",
    "-GPSLongitude",
    "-GPSLongitudeRef",
    "-GPSAltitude",
    "-GPSAltitudeRef",
    "-Orientation",
]


def gen_images_from_files(
    files, include=None, exclude=None, exiftool="exiftool", defaultTzHours=0, defaultTzMinutes=0
):
    defaultTz = datetime.timezone(
        datetime.timedelta(hours=defaultTzHours, minutes=defaultTzMinutes)
    )
    if include is not None:
        include = [e.lower() for e in include]
    if exclude is not None:
        exclude = [e.lower() for e in exclude]
    files = _find_all_files(files, include, exclude)
    if len(files) == 0:
        return
    # The tags and file names are passed to exiftool as an argument file on stdin,
    # one argument per line
    argFile = "\n".join(_tagsToExtract + [str(f) for f in files]) + "\n"
    pipe = Popen(
        [exiftool] + _exiftoolCharsetArgs + ["-q", "-n", "-X", "-@", "-"],
        stdin=PIPE,
        stdout=PIPE,
        **_popenKwds,
    )
    pipe.stdin.write(argFile.encode("utf-8", "surrogateescape"))
    pipe.stdin.close()

    context = _ExifContext(defaultTz, exiftool)
    try:
        for v in context.gen_exif_files(pipe):
            yield v
    finally:
        pipe.stdout.close()
        pipe.wait()


if __name__ == "__main__":
    for i in gen_images_from_files("Images", [".jpg", ".mrw"]):
        print(i[("System", "FileName")], i["FileType"], i["Model"])
        if i.has_embedded_image():
            print(i.get_filename(), "has preview image")
        else:
            print(i.get_filename(), "doesn't have preview image")
