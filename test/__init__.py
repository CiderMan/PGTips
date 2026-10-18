import functools
import os
import shutil
import sys
import tempfile
from pathlib import Path

import wx

# GUI tests need a display to create a wx.App; without one, wxGTK aborts the whole process
HAVE_DISPLAY = sys.platform != "linux" or bool(
    os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
)


@functools.cache
def get_wx_app():
    """
    Return the wx.App for the test run, creating it if necessary (wx only supports one per
    process). The cache keeps a reference so that it isn't destroyed between tests
    """
    return wx.App(False)


def temp_dir(testCase):
    """
    Return a new temporary directory that is removed when the test case finishes
    """
    path = Path(tempfile.mkdtemp())
    testCase.addCleanup(shutil.rmtree, path)
    return path
