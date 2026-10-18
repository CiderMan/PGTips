import datetime
import tempfile
import unittest
from pathlib import Path

import gpsfiles
from gpsfiles import _parse_xsd_datetime, gen_tracks_from_files

UTC = datetime.timezone.utc

_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <trkseg>
      <trkpt lat="50.0" lon="-4.0"><ele>10</ele><time>2010-09-02T10:00:00Z</time></trkpt>
      <trkpt lat="50.1" lon="-4.1"><ele>20</ele><time>2010-09-02T10:01:00Z</time></trkpt>
      <trkpt lat="50.2" lon="-4.2"><ele>30</ele><time>2010-09-02T10:02:00Z</time></trkpt>
    </trkseg>
    <trkseg>
      <trkpt lat="51.0" lon="-3.0"><time>2010-09-02T12:00:00Z</time></trkpt>
      <trkpt lat="51.1" lon="-3.1"><time>2010-09-02T12:10:00Z</time></trkpt>
    </trkseg>
  </trk>
</gpx>
"""

_TCX = """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities><Activity Sport="Running"><Lap StartTime="2010-09-02T10:00:00Z"><Track>
    <Trackpoint>
      <Time>2010-09-02T10:00:00Z</Time>
      <Position><LatitudeDegrees>50.0</LatitudeDegrees><LongitudeDegrees>-4.0</LongitudeDegrees></Position>
      <AltitudeMeters>100.0</AltitudeMeters>
    </Trackpoint>
    <Trackpoint>
      <Time>2010-09-02T10:00:10Z</Time>
      <Position><LatitudeDegrees>50.001</LatitudeDegrees><LongitudeDegrees>-4.001</LongitudeDegrees></Position>
      <AltitudeMeters>101.0</AltitudeMeters>
    </Trackpoint>
  </Track></Lap></Activity></Activities>
</TrainingCenterDatabase>
"""


class ParseXsdDatetimeTest(unittest.TestCase):
    def test_utc(self):
        self.assertEqual(
            _parse_xsd_datetime("2009-08-28T19:11:37Z"),
            datetime.datetime(2009, 8, 28, 19, 11, 37, tzinfo=UTC),
        )

    def test_offset(self):
        dt = _parse_xsd_datetime("2009-08-28T20:11:37+01:00")
        self.assertEqual(dt, datetime.datetime(2009, 8, 28, 19, 11, 37, tzinfo=UTC))

    def test_negative_offset(self):
        dt = _parse_xsd_datetime("2009-08-28T14:11:37-05:00")
        self.assertEqual(dt, datetime.datetime(2009, 8, 28, 19, 11, 37, tzinfo=UTC))

    def test_fractional_seconds(self):
        dt = _parse_xsd_datetime("2009-08-28T19:11:37.250Z")
        self.assertEqual(dt.microsecond, 250000)

    def test_naive(self):
        self.assertIsNone(_parse_xsd_datetime("2009-08-28T19:11:37").tzinfo)


class GpsFilesTestCase(unittest.TestCase):
    def setUp(self):
        gpsfiles._DEBUG = False
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, content):
        path = self.dir / name
        path.write_text(content, encoding="utf-8")
        return path


class GpxTest(GpsFilesTestCase):
    def setUp(self):
        super().setUp()
        self.path = self.write("track.gpx", _GPX)
        (self.gpx,) = gen_tracks_from_files(self.path)

    def test_segments_become_tracks(self):
        self.assertEqual(len(self.gpx), 2)
        self.assertEqual(len(self.gpx[0]), 3)
        self.assertEqual(len(self.gpx[1]), 2)

    def test_points(self):
        when, lat, lon, ele = self.gpx[0][1]
        self.assertEqual(when, datetime.datetime(2010, 9, 2, 10, 1, tzinfo=UTC))
        self.assertEqual((lat, lon, ele), (50.1, -4.1, 20.0))
        self.assertIsNone(self.gpx[1][0][3])

    def test_filename(self):
        self.assertEqual(self.gpx.get_filename(), self.path)
        self.assertIn("track.gpx", str(self.gpx))

    def test_match_interpolates(self):
        lat, lon, alt = self.gpx.match_time(datetime.datetime(2010, 9, 2, 10, 0, 30, tzinfo=UTC))
        self.assertAlmostEqual(lat, 50.05)
        self.assertAlmostEqual(lon, -4.05)
        self.assertAlmostEqual(alt, 15)

    def test_match_later_segment_of_track(self):
        lat, lon, alt = self.gpx.match_time(datetime.datetime(2010, 9, 2, 10, 1, 30, tzinfo=UTC))
        self.assertAlmostEqual(lat, 50.15)
        self.assertAlmostEqual(alt, 25)

    def test_match_without_altitude(self):
        lat, lon, alt = self.gpx.match_time(datetime.datetime(2010, 9, 2, 12, 5, tzinfo=UTC))
        self.assertAlmostEqual(lat, 51.05)
        self.assertIsNone(alt)

    def test_match_within_end_tolerance(self):
        match = self.gpx.match_time(datetime.datetime(2010, 9, 2, 9, 58, tzinfo=UTC))
        self.assertEqual(match, (50.0, -4.0, 10.0))

    def test_no_match(self):
        self.assertIsNone(self.gpx.match_time(datetime.datetime(2010, 9, 2, 11, tzinfo=UTC)))
        self.assertIsNone(self.gpx.match_time(datetime.datetime(2010, 9, 3, 10, tzinfo=UTC)))

    def test_match_naive_time_with_offset(self):
        match = self.gpx.match_time(datetime.datetime(2010, 9, 2, 11, 0, 30), utcOffsetHours=1)
        self.assertAlmostEqual(match[0], 50.05)


class TcxTest(GpsFilesTestCase):
    def test_parse(self):
        (tcx,) = gen_tracks_from_files(self.write("run.tcx", _TCX))
        self.assertEqual(len(tcx), 1)
        self.assertEqual(tcx[0][0][1:], (50.0, -4.0, 100.0))
        self.assertEqual(tcx[0][1][3], 101.0)


class TrackProcessingTest(GpsFilesTestCase):
    def test_close_tracks_are_joined(self):
        gpx = _GPX.replace("2010-09-02T12:00:00Z", "2010-09-02T10:02:05Z").replace(
            "2010-09-02T12:10:00Z", "2010-09-02T10:03:00Z"
        )
        (tracks,) = gen_tracks_from_files(self.write("track.gpx", gpx))
        self.assertEqual(len(tracks), 1)
        self.assertEqual(len(tracks[0]), 5)

    def test_short_tracks_are_discarded(self):
        gpx = _GPX.replace(
            '<trkpt lat="51.1" lon="-3.1"><time>2010-09-02T12:10:00Z</time></trkpt>', ""
        )
        (tracks,) = gen_tracks_from_files(self.write("track.gpx", gpx))
        self.assertEqual(len(tracks), 1)

    def test_split_tracks(self):
        t = [(datetime.datetime(2010, 1, 1, 0, 0, s, tzinfo=UTC),) for s in (0, 1, 30, 31)]
        split = list(gpsfiles._gen_split_tracks("x", [t], 10))
        self.assertEqual(split, [t[:2], t[2:]])


class FindFilesTest(GpsFilesTestCase):
    def test_include_filter_applies_to_every_file(self):
        self.write("a.gpx", _GPX)
        self.write("b.GPX", _GPX)
        self.write("c.tcx", _TCX)
        names = sorted(t.get_filename().name for t in gen_tracks_from_files(self.dir, [".GPX"]))
        self.assertEqual(names, ["a.gpx", "b.GPX"])

    def test_walks_subdirectories(self):
        (self.dir / "sub").mkdir()
        self.write("sub/a.gpx", _GPX)
        self.assertEqual(len(list(gen_tracks_from_files([str(self.dir)]))), 1)

    def test_unknown_and_missing_files(self):
        self.write("other.xml", "<root/>")
        self.write("text.gpx", "not xml")
        files = [self.dir / "other.xml", self.dir / "text.gpx", self.dir / "missing.gpx"]
        self.assertEqual(list(gen_tracks_from_files(files)), [])
        self.assertEqual(len(list(gen_tracks_from_files(files, returnEmpty=True))), 2)


if __name__ == "__main__":
    unittest.main()
