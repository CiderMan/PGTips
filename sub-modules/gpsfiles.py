import xml.etree.ElementTree as ET
import datetime
from pathlib import Path, PurePath
from functools import reduce

_DEBUG = True


def _parse_xsd_datetime(time):
    # Python 3.11+ handles the full range of xsd:dateTime forms used by GPS
    # files, including a trailing 'Z', numeric offsets and fractional seconds
    return datetime.datetime.fromisoformat(time.strip())


def _gen_tracks_from_gpx_file(e):
    """
    Parse a GPX file (should be compatible with version 1.0 and 1.1)
    TODO: is a bit sunny day at the moment (except for altitude). Should
    be a little more robust
    """
    r = e.getroot()
    assert r.tag.startswith("{"), "No name space"
    t = r.tag.split("}")
    assert len(t) == 2 and t[1] == "gpx", "Not a GPX file"
    uri = t[0][1:]
    trkTag = "{%s}trk" % uri
    trksegTag = "{%s}trkseg" % uri
    trkptTag = "{%s}trkpt" % uri
    eleTag = "{%s}ele" % uri
    timeTag = "{%s}time" % uri
    for trkseg in r.iter(trksegTag):
        s = []
        for trkpt in trkseg.findall(trkptTag):
            try:
                ele = float(trkpt.find(eleTag).text)
            except (AttributeError, TypeError, ValueError):
                ele = None
            time = trkpt.find(timeTag)
            s.append(
                (
                    _parse_xsd_datetime(time.text),
                    float(trkpt.get("lat")),
                    float(trkpt.get("lon")),
                    ele,
                )
            )
        yield s


def _gen_tracks_from_tcx_file(e):
    """
    Parse a TCX file (should be compatible with version 1 and 2)
    TODO: is a bit sunny day at the moment (except for altitude). Should
    be a little more robust
    """
    r = e.getroot()
    assert r.tag.startswith("{"), "No name space"
    t = r.tag.split("}")
    assert len(t) == 2 and t[1] == "TrainingCenterDatabase", "Not a TCX file"
    uri = t[0][1:]
    trkTag = "{%s}Track" % uri
    trkptTag = "{%s}Trackpoint" % uri
    posTag = "{%s}Position" % uri
    latTag = "{%s}LatitudeDegrees" % uri
    longTag = "{%s}LongitudeDegrees" % uri
    altTag = "{%s}AltitudeMeters" % uri
    timeTag = "{%s}Time" % uri
    for trk in r.iter(trkTag):
        s = []
        for trkpt in trk.findall(trkptTag):
            time = trkpt.find(timeTag)
            pos = trkpt.find(posTag)
            latitude = pos.find(latTag)
            longitude = pos.find(longTag)
            try:
                # Note that, in TCX, the altitude is a sibling of the position
                altitude = float(trkpt.find(altTag).text)
            except AttributeError:
                # No altitude element
                altitude = None
            s.append(
                (
                    _parse_xsd_datetime(time.text),
                    float(latitude.text),
                    float(longitude.text),
                    altitude,
                )
            )
        yield s


def _nul(nul):
    """
    Define a "parser" for files that are unknown. It ignores its parameter
    and returns None to indicate that this is not a valid file
    """
    return None


# This is a dictionary that maps the root element of an XML file onto a tuple of
# the filetype and the parser for that file type
schemaMapping = {
    "{http://www.topografix.com/GPX/1/0}gpx": ("GPX File", _gen_tracks_from_gpx_file),
    "{http://www.topografix.com/GPX/1/1}gpx": ("GPX File", _gen_tracks_from_gpx_file),
    "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}TrainingCenterDatabase": (
        "TCX File",
        _gen_tracks_from_tcx_file,
    ),
    "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v1}TrainingCenterDatabase": (
        "TCX File",
        _gen_tracks_from_tcx_file,
    ),
}


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


def _track_from_file(f):
    # OK, this should be a file. We'll start by looking to see if it is one of the XML formats
    try:
        e = ET.parse(f)
        r = e.getroot()
        try:
            source = schemaMapping[r.tag], e
        except KeyError:
            if _DEBUG:
                print(f, "Unknown XML file type:", r.tag)
            source = ("Unknown XML file type", _nul), None
    except ET.ParseError:
        # Unknown file type
        source = ("Unknown file type", _nul), None
    except OSError:
        # File doesn't exist
        source = ("Non-existent file", _nul), None
    return _Tracks(f, source[0][0], source[0][1](source[1]))


def gen_tracks_from_files(files, include=None, exclude=None, returnEmpty=False, pool=None):
    if include is not None:
        include = [e.lower() for e in include]
    if exclude is not None:
        exclude = [e.lower() for e in exclude]
    files = _find_all_files(files, include, exclude)
    if pool is None:
        iterator = map(_track_from_file, files)
    else:
        iterator = pool.imap_unordered(_track_from_file, files)

    for track in iterator:
        if len(track) > 0 or returnEmpty:
            yield track
        elif _DEBUG:
            print(track._filename, "No tracks - ignoring")


def _gen_split_tracks(filename, tracks, splitTrackGap):
    for t in tracks:
        if splitTrackGap is None:
            yield t
        else:
            if len(t) > 1:
                splitPoints = []
                for i in range(len(t) - 1):
                    diff = (t[i + 1][0] - t[i][0]).total_seconds()
                    assert diff >= 0
                    if diff >= splitTrackGap:
                        if _DEBUG:
                            print(filename, "Splitting track at gap of %d seconds" % diff)
                        splitPoints.append(i + 1)
                if len(splitPoints) > 0:
                    i = 0
                    for pt in splitPoints:
                        yield t[i:pt]
                        i = pt
                    yield t[i:]
                    t = None
            if t is not None:
                yield t


def _gen_interpolate_alt(filename, tracks):
    for t in tracks:
        noAlt, missingAlt = reduce(
            lambda x, y: (y[3] is None and x[0], y[3] is None or x[1]), t, (True, False)
        )
        if noAlt:
            if _DEBUG:
                print(filename, "Track contains no altitude data")
            # TODO: Should we set the altitude data to a default value here?
        elif missingAlt:
            if _DEBUG:
                print(filename, "Track contains missing altitude data")
            # TODO: Interpolate
        yield t


def _gen_join_tracks(filename, tracks, joinTrackGap):
    lastTrack = None
    for t in tracks:
        # Note that this generator assumes that the tracks are in time order
        # This is probably a reasonable assumption an the worst that can happen
        # is that tracks that otherwise would be joined are not joined
        if lastTrack is not None:
            diff = (t[0][0] - lastTrack[-1][0]).total_seconds()
            if 0 <= diff <= joinTrackGap:
                lastTrack = lastTrack + t
                if _DEBUG:
                    print(filename, "Joining tracks separated by %d seconds" % diff)
            else:
                yield lastTrack
                lastTrack = t
        else:
            lastTrack = t
    # Make sure that we yield the final track too
    if lastTrack is not None:
        yield lastTrack


def _gen_remove_short_tracks(filename, tracks, minPointsPerTrack):
    for t in tracks:
        if len(t) < minPointsPerTrack:
            if _DEBUG:
                print(filename, "Discarding track with %d points" % len(t))
        else:
            yield t


class _Tracks:
    def __init__(
        self,
        filename,
        filetype,
        tracks,
        minPointsPerTrack=2,
        splitTrackGap=None,
        joinTrackGap=10,
    ):
        self._filename = filename
        self._filetype = filetype
        if tracks is None:
            self._tracks = []
            self._valid = False
            return
        # OK, this is a valid file so process the tracks
        self._valid = True
        # First split the track if we're requested to
        splitTracks = _gen_split_tracks(filename, tracks, splitTrackGap)
        # Now check if any of the tracks contains undefined altitudes
        interpolatedTracks = _gen_interpolate_alt(filename, splitTracks)
        joinedTracks = _gen_join_tracks(filename, interpolatedTracks, joinTrackGap)
        finalTracks = _gen_remove_short_tracks(filename, joinedTracks, minPointsPerTrack)
        self._tracks = list(finalTracks)

    def __len__(self):
        return len(self._tracks)

    def __getitem__(self, i):
        return _TrackProxy(self._tracks[i])

    def __str__(self):
        s = [
            str(self._filename)
            + ": "
            + self._filetype
            + " containing %d tracks" % len(self._tracks)
        ]
        for t in self._tracks:
            duration = t[-1][0] - t[0][0]
            s.append(
                " - %d points from %s to %s (%d days, %d seconds)"
                % (len(t), str(t[0][0]), str(t[-1][0]), duration.days, duration.seconds)
            )
        return "\n".join(s)

    def get_filename(self):
        return self._filename

    def match_time(self, dateTime, endTolerance=300, utcOffsetHours=None, utcOffsetMinutes=0):
        matches = []
        if dateTime.tzinfo is None and utcOffsetHours is not None:
            dateTime = dateTime.replace(
                tzinfo=datetime.timezone(
                    datetime.timedelta(hours=utcOffsetHours, minutes=utcOffsetMinutes)
                )
            )
        for t in self._tracks:
            if dateTime < t[0][0]:
                before = (t[0][0] - dateTime).total_seconds()
                if before <= endTolerance:
                    matches.append((t[0], t[0]))
            elif dateTime >= t[-1][0]:
                after = (dateTime - t[-1][0]).total_seconds()
                if after <= endTolerance:
                    matches.append((t[-1], t[-1]))
            else:
                last = t[0]
                for pt in t[1:]:
                    if dateTime >= last[0] and dateTime < pt[0]:
                        # Check for minimum proximity?
                        matches.append((last, pt))
                        break
                    last = pt
                else:
                    assert False, "Shouldn't get here!"
        if len(matches) == 0:
            # Nothing found
            return None
        else:
            # TODO Figure out which is best if there are more than one
            t1, t2 = matches[0]
            if t1 is t2:
                lat, lon, alt = t1[1:]
            else:
                ratio = (dateTime - t1[0]).total_seconds() / (t2[0] - t1[0]).total_seconds()
                lat1, lon1, alt1 = t1[1:]
                lat2, lon2, alt2 = t2[1:]
                lat = lat1 + (lat2 - lat1) * ratio
                lon = lon1 + (lon2 - lon1) * ratio
                if alt1 is None or alt2 is None:
                    alt = alt1 if alt2 is None else alt2
                else:
                    alt = alt1 + (alt2 - alt1) * ratio

            return lat, lon, alt


class _TrackProxy:
    """
    A class that provides read-only access (and possibly managed modification in the future,
    if required) to the underlying array.
    """

    def __init__(self, track):
        self._track = track

    def __len__(self):
        return len(self._track)

    def __getitem__(self, i):
        return self._track[i]

    def __str__(self):
        duration = self._track[-1][0] - self._track[0][0]
        return "Track with %d points from %s to %s (%d days, %d seconds)" % (
            len(self._track),
            str(self._track[0][0]),
            str(self._track[-1][0]),
            duration.days,
            duration.seconds,
        )


if __name__ == "__main__":
    # Note that the pool stuff is commented out as, on my netbook, using 2 pools
    # maxed out both threads but ran at less than half the speed of the single
    # threaded approach. Hence, it is (was) tested but make you get a benefit if
    # you turn it on!
    # import multiprocessing

    # pool = multiprocessing.Pool()
    files = gen_tracks_from_files(["GPSTracks", "missing.gpx"])  # , pool = pool)

    dt = datetime.datetime(2010, 9, 2, 10, 0, 0)
    for g in files:
        print(g._filename)
        print(g.match_time(dt, utcOffsetHours=0))

    # pool.close()
    # pool.join()
