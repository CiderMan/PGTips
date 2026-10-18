import datetime
import unittest
from test import HAVE_DISPLAY, get_wx_app

import wx

from imagelist import ImageListCtrlPanel


class _Image:
    """Enough of an ExifFile for the list control"""

    def __init__(self, name, dateTime, geotag=None):
        self._exif = {"FileName": name}
        self.dateTime = dateTime
        self.geotag = geotag

    def __getitem__(self, key):
        return self._exif[key]


@unittest.skipUnless(HAVE_DISPLAY, "Needs a display")
class ImageListCtrlPanelTest(unittest.TestCase):
    def setUp(self):
        get_wx_app()
        self.frame = wx.Frame(None)
        self.panel = ImageListCtrlPanel(self.frame)
        self.list = self.panel.GetListCtrl()

    def tearDown(self):
        self.frame.Destroy()

    def row(self, index):
        return [self.list.GetItemText(index, col) for col in range(3)]

    def test_add_image(self):
        img = _Image("b.jpg", datetime.datetime(2010, 9, 2, 16, 29, 47), (50.12345, -4.5, 12.7))
        self.panel.add_image(img)
        self.assertEqual(self.list.GetItemCount(), 1)
        self.assertEqual(self.row(0), ["b.jpg", "2010-09-02 16:29:47", "50.123, -4.500 (12m)"])
        self.assertEqual(list(self.panel.iter_images()), [img])

    def test_image_without_date_or_geotag(self):
        self.panel.add_image(_Image("a.jpg", None))
        self.assertEqual(self.row(0), ["a.jpg", "-", "-"])

    def test_update_image(self):
        img = _Image("a.jpg", datetime.datetime(2010, 9, 2))
        self.panel.add_image(img)
        img.geotag = (1, 2, None)
        self.panel.update_image(img)
        self.assertEqual(self.row(0)[2], "1.000, 2.000")

    def test_rm_image(self):
        a = _Image("a.jpg", None)
        b = _Image("b.jpg", None)
        self.panel.add_image(a)
        self.panel.add_image(b)
        self.panel.rm_image(a)
        self.assertEqual(self.list.GetItemCount(), 1)
        self.assertEqual(self.row(0)[0], "b.jpg")
        self.assertEqual(list(self.panel.iter_images()), [b])

    def test_sort_by_column(self):
        self.panel.add_image(_Image("a.jpg", datetime.datetime(2012, 1, 1)))
        self.panel.add_image(_Image("b.jpg", datetime.datetime(2011, 1, 1)))
        self.panel.SortListItems(1, True)
        self.assertEqual([self.row(i)[0] for i in range(2)], ["b.jpg", "a.jpg"])
        self.panel.SortListItems(0, False)
        self.assertEqual([self.row(i)[0] for i in range(2)], ["b.jpg", "a.jpg"])

    def test_selection_notifies(self):
        a = _Image("a.jpg", None)
        self.panel.add_image(a)
        selected = []
        self.panel.add_image_select_notify(selected.append)
        self.list.SetItemState(0, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
        wx.Yield()
        self.assertEqual(selected, [a])


if __name__ == "__main__":
    unittest.main()
