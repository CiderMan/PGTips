import os, sys

# GUI tests need a display to create a wx.App; without one, wxGTK aborts the whole process
HAVE_DISPLAY = sys.platform != "linux" or bool(
    os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
)


_app = None


def get_wx_app():
    """
    Return the wx.App for the test run, creating it if necessary (wx only supports one per
    process). A reference is kept so that it isn't destroyed between tests
    """
    global _app
    import wx

    if _app is None:
        _app = wx.App(False)
    return _app
