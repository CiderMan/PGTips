import json
import tempfile
import unittest
from pathlib import Path

from test import HAVE_DISPLAY, get_wx_app


class SplitCslTest(unittest.TestCase):
    def test_split(self):
        from options import _split_csl

        self.assertEqual(_split_csl("jpg, mrw  dng,,", prefix="."), [".jpg", ".mrw", ".dng"])
        self.assertEqual(_split_csl(""), [])


class _Event:
    def Skip(self):
        pass


@unittest.skipUnless(HAVE_DISPLAY, "Needs a display")
class OptionsDialogTest(unittest.TestCase):
    def setUp(self):
        get_wx_app()
        self._tmp = tempfile.TemporaryDirectory()
        self.optFile = Path(self._tmp.name) / "pgtips.opt"

    def tearDown(self):
        self.dialog.Destroy()
        self._tmp.cleanup()

    def create(self):
        from options import OptionsDialog

        self.dialog = OptionsDialog(None, optFile=str(self.optFile))
        return self.dialog

    def test_defaults_without_file(self):
        d = self.create()
        self.assertEqual(d.options["FilingStruct"], "%Y/%Y_%m/%Y_%m_%d")
        self.assertTrue(d.options["JpegtranEnabled"])

    def test_reads_legacy_repr_file(self):
        # As written by the Python 2 version
        self.optFile.write_text("{'ImageExtensions': [u'.jpg'], 'WorkingDir': u'/tmp/work'}")
        d = self.create()
        self.assertEqual(d.options["ImageExtensions"], [".jpg"])
        self.assertEqual(d.options["WorkingDir"], "/tmp/work")

    def test_ok_saves_json(self):
        d = self.create()
        d._imageExtTextCtrl.SetValue("JPG, mrw")
        d._workingDir.SetValue("/tmp//work/")
        d.OnOK(_Event())
        saved = json.loads(self.optFile.read_text())
        self.assertEqual(saved["ImageExtensions"], [".jpg", ".mrw"])
        self.assertEqual(saved["WorkingDir"], "/tmp/work")
        self.assertEqual(self.create().options, saved)

    def test_cancel_reverts_controls(self):
        d = self.create()
        d._imageExtTextCtrl.SetValue("jpg")
        d.OnCancel(_Event())
        self.assertEqual(d._imageExtTextCtrl.GetValue(), "")
        self.assertEqual(d.options["ImageExtensions"], [])


if __name__ == "__main__":
    unittest.main()
