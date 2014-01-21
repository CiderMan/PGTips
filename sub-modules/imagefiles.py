import os, sys, datetime, re
import xml.etree.cElementTree as ET
from subprocess import Popen, PIPE

_DEBUG = True

class ExiftoolException(Exception): pass

def _find_all_files(files, include, exclude):
    fList = []
    if isinstance(files, str) or isinstance(files, unicode):
        files = [files]
    if _DEBUG: print files

    for path in files:
        if os.path.isfile(path):
            f = path
            ext = os.path.splitext(f)[1].lower()
            if (include is None or ext in include) and (exclude is None or ext not in exclude):
                fList.append(f)
        else:
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    ext = os.path.splitext(f)[1].lower()
                    if (include is None or ext in include) and (exclude is None or ext not in exclude):
                        fList.append(os.path.join(dirpath, f))

    return fList

_popenKwds = {}

if sys.platform == "win32":
    import subprocess
    # Some messing to allow running of pipes without a window and without needing
    # to use a shell (which screws the ability to use UNC paths)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    _popenKwds["startupinfo"] = startupinfo
else:
    _popenKwds["shell"] = True

_exiftool_datetime = re.compile(
    "^"
    "(?P<year>[0-9]{4})"
    ":"
    "(?P<month>[0-9]{2})"
    ":"
    "(?P<day>[0-9]{2})"
    " "
    "(?P<hour>[0-9]{2})"
    ":"
    "(?P<minutes>[0-9]{2})"
    ":"
    "(?P<seconds>[0-9]{2})"
    "$")

_tz = re.compile(
    "^(?P<tzhours>[-+][0-9]{2})"
    ":?(?P<tzminutes>[0-9]{2})$")

class _exiftool_tzinfo(datetime.tzinfo):
    def __init__(self, hours = 0, minutes = 0, name = "UTC"):
        self._utcoffset = datetime.timedelta(hours = hours, minutes = minutes)
        self._name = name

    def utcoffset(self, dt):
        return self._utcoffset

    def dst(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return self.name

def _parse_exiftool_datetime(time, defaultTz):
    try:
        t, tz = time.split('Z', 1)
    except ValueError:
        try:
            t, tz = time.split('+', 1)
            tz = '+' + tz
        except ValueError:
            try:
                t, tz = time.split('-', 1)
                tz = '-' + tz
            except ValueError:
                # Naive time
                t = time
                tz = None

    if tz is not None:
        if tz == "":
            tz = _exiftool_tzinfo()
        else:
            m = _tz.match(tz)
            tz = _exiftool_tzinfo(m.group("tzhours"), m.group("tzminutes"), tz)
    else:
        tz = defaultTz

    m = _exiftool_datetime.match(t)

    args = map(int, [m.group("year"), m.group("month"), m.group("day"), m.group("hour"), m.group("minutes"), m.group("seconds")]) + [0, tz]
    dt = datetime.datetime(*args)

    return dt

class ExifFile(object):
    managedAttributes = [
            "dateTime",
            "geotag",
            ]

    def __init__(self, filename, exifDict, defaultTz, exiftool = "exiftool"):
        self._exiftool = exiftool
        self._filename = filename
        self._namespaces = exifDict
        self._defaultTz = defaultTz
        self._modified = False
        try:
            self._dateTime = _parse_exiftool_datetime(self["DateTimeOriginal"], defaultTz)
        except KeyError:
            self._dateTime = None
        try:
            try:
                alt = float(self["GPS", "GPSAltitude"])
                if int(self["GPS", "GPSAltitudeRef"]) == 1:
                    alt = -alt
            except:
                alt = None
            lat = float(self["GPS", "GPSLatitude"])
            if self["GPS", "GPSLatitudeRef"][0] == "S":
                lat = -lat
            lon = float(self["GPS", "GPSLongitude"])
            if self["GPS", "GPSLongitudeRef"][0] == "W":
                lon = -lon
            self._geotag = (lat, lon, alt)
        except:
            self._geotag = None

    def __getattr__(self, attr):
        if attr in self.managedAttributes:
            return getattr(self, '_' + attr)
        else:
            raise AttributeError("Class %s does not have attribute %s" % (self.__class__.__name__, attr))

    def __getitem__(self, index):
        if isinstance(index, str):
            # Need to search
            found = []
            for key in self._namespaces.keys():
                try:
                    found.append(self._namespaces[key][index])
                except KeyError:
                    pass # Not found in this namespace
            if len(found) == 0:
                raise KeyError("EXIF data for %s doesn't have key %s" % (self._filename, index))
            elif len(found) > 1:
                raise Exception("Key %s is not unique in EXIF data for %s" % (index, self._filename))
            else:
                return found[0]
        else:
            assert isinstance(index, tuple) and len(index) == 2, "Index must be a string or a tuple of 2 strings"
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
                exiftoolCmd = " -q -overwrite_original -gps:all= " + self._filename
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

                exiftoolCmd = " -q -n -overwrite_original "
                exiftoolCmd += "-GPSLatitude=%f -GPSLatitudeRef=%s " % (lat, latRef)
                exiftoolCmd += "-GPSLongitude=%f -GPSLongitudeRef=%s " % (lon, lonRef)
                if alt is not None:
                    exiftoolCmd += "-GPSAltitude=%f -GPSAltitudeRef=%d " % (alt, altRef)
                exiftoolCmd += self._filename

            pipe = Popen(self._exiftool + exiftoolCmd, stdin = PIPE, stdout = PIPE, **_popenKwds)
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

class _ExifContext(object):
    def __init__(self, defaultTz, exiftool):
        self._root = None
        self._namespaces = []
        self._defaultTz = defaultTz
        self._exiftool = exiftool

    def gen_exif_files(self, pipe):
        for exiffiles in self._gen_exiffile_objects(
                         self._gen_file_descriptions(
                         pipe), self._exiftool):
            yield exiffiles

    def _reverse_namespace(self, tag):
        if tag.startswith("{"):
            uri, shortTag = tag[1:].split('}')
            for shortForm, longForm in self._namespaces:
                if uri == longForm:
                    return shortForm, shortTag
            else:
                print "*** Could not match namespace", uri
                return "", item.tag
        else:
            return "", item.tag

    def _gen_file_descriptions(self, pipe):
        for event, item in ET.iterparse(pipe.stdout,
                                        events = ("start",
                                                  "end",
                                                  "start-ns",
                                                  "end-ns")):
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
                try:
                    exif[key[0]][key[1]] = item.text
                except KeyError:
                    exif[key[0]] = {}
                    exif[key[0]][key[1]] = item.text
            self._root.clear()
            yield ExifFile(about, exif, self._defaultTz, exiftool)

_tagsToExtract = "\n".join([
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
        ])

def gen_images_from_files(files,
                          include = None,
                          exclude = None,
                          exiftool = "exiftool",
                          defaultTzHours = 0,
                          defaultTzMinutes = 0):
    defaultTz = _exiftool_tzinfo(defaultTzHours, defaultTzMinutes)
    if include is not None: include = map(str.lower, include)
    if exclude is not None: exclude = map(str.lower, exclude)
    files = _find_all_files(files, include, exclude)
    files = "\n".join(files)
    if files == "":
        return
    pipe = Popen(exiftool + " -q -n -X -@ -",
                 stdin = PIPE, stdout = PIPE, **_popenKwds)
    pipe.stdin.write(_tagsToExtract + "\n")
    pipe.stdin.write(files)
    pipe.stdin.close()

    context = _ExifContext(defaultTz, exiftool)
    for v in context.gen_exif_files(pipe):
        yield v

if __name__ == "__main__":
    for i in gen_images_from_files("Images", [".jpg", ".mrw"]):
        print i[("System", "FileName")], i["FileType"], i["Model"]
        if i.has_embedded_image():
            print i.get_filename(), "has preview image"
        else:
            print i.get_filename(), "doesn't have preview image"
