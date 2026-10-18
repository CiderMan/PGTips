import wx
import wx.lib.mixins.listctrl as listmix
import images


class _ImageListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """
    Create a sub-class of the ListCtrl class which includes the mix-in
    to handle automatically adjusting the width of the columns based on
    their contents.
    """

    def __init__(self, parent, ID, pos=wx.DefaultPosition, size=wx.DefaultSize, style=0):
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        listmix.ListCtrlAutoWidthMixin.__init__(self)


class ImageListCtrlPanel(wx.Panel, listmix.ColumnSorterMixin):
    """
    Define the panel that will hold the list of images
    """

    def __init__(self, parent):
        """
        Do all the set-up to create an empty control
        """
        wx.Panel.__init__(self, parent, -1, style=wx.WANTS_CHARS)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self._listCtrl = _ImageListCtrl(
            self,
            -1,
            style=wx.LC_REPORT
            # | wx.BORDER_SUNKEN
            | wx.BORDER_NONE | wx.LC_EDIT_LABELS | wx.LC_SORT_ASCENDING
            # | wx.LC_NO_HEADER
            | wx.LC_VRULES | wx.LC_HRULES,
            # | wx.LC_SINGLE_SEL
        )

        sizer.Add(self._listCtrl, 1, wx.EXPAND)

        self._itemDataMap = {}
        # The ColumnSorterMixin sorts using the column values held in itemDataMap
        self.itemDataMap = {}
        self._uuidCounter = 0
        listmix.ColumnSorterMixin.__init__(self, 3)
        # self.SortListItems(0, True)

        self._listCtrl.InsertColumn(0, "Filename")
        self._listCtrl.InsertColumn(1, "Date")
        self._listCtrl.InsertColumn(2, "Geotag")

        self.SetSizer(sizer)
        self.SetAutoLayout(True)

        # self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self._listCtrl)
        # self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self._listCtrl)
        # self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated, self._listCtrl)
        # self.Bind(wx.EVT_LIST_DELETE_ITEM, self.OnItemDelete, self._listCtrl)
        # self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick, self._listCtrl)
        # self.Bind(wx.EVT_LIST_COL_RIGHT_CLICK, self.OnColRightClick, self._listCtrl)
        # self.Bind(wx.EVT_LIST_COL_BEGIN_DRAG, self.OnColBeginDrag, self._listCtrl)
        # self.Bind(wx.EVT_LIST_COL_DRAGGING, self.OnColDragging, self._listCtrl)
        # self.Bind(wx.EVT_LIST_COL_END_DRAG, self.OnColEndDrag, self._listCtrl)
        # self.Bind(wx.EVT_LIST_BEGIN_LABEL_EDIT, self.OnBeginEdit, self._listCtrl)

        # self._listCtrl.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        # self._listCtrl.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)

        # for wxMSW
        # self._listCtrl.Bind(wx.EVT_COMMAND_RIGHT_CLICK, self.OnRightClick)

        # for wxGTK
        # self._listCtrl.Bind(wx.EVT_RIGHT_UP, self.OnRightClick)

        self._imageSelectNotifyList = []
        self._imageDeselectNotifyList = []

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnImageSelected, self._listCtrl)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnImageDeselected, self._listCtrl)

        self._il = wx.ImageList(16, 16)

        self._sm_up = self._il.Add(images.SmallUpArrow.GetBitmap())
        self._sm_dn = self._il.Add(images.SmallDnArrow.GetBitmap())
        self._listCtrl.SetImageList(self._il, wx.IMAGE_LIST_SMALL)

    # Used by the ColumnSorterMixin, see wx/lib/mixins/listctrl.py
    def GetListCtrl(self):
        return self._listCtrl

    # Used by the ColumnSorterMixin, see wx/lib/mixins/listctrl.py
    def GetSortImages(self):
        return (self._sm_dn, self._sm_up)

    def OnImageSelected(self, event):
        img = self._get_image_from_index(event.GetIndex())
        for notify in self._imageSelectNotifyList:
            notify(img)

    def OnImageDeselected(self, event):
        img = self._get_image_from_index(event.GetIndex())
        for notify in self._imageDeselectNotifyList:
            notify(img)

    def add_image_select_notify(self, notify):
        self._imageSelectNotifyList.append(notify)

    def add_image_deselect_notify(self, notify):
        self._imageDeselectNotifyList.append(notify)

    def _image_columns(self, img):
        """
        Return the text for each column of the list for the given image
        """
        a = img["FileName"]
        b = img.dateTime.isoformat(" ") if img.dateTime is not None else "-"
        c = img.geotag
        if c is None:
            c = "-"
        else:
            alt = c[2]
            c = "%.3f, %.3f" % (c[0], c[1])
            if alt is not None:
                c += " (%dm)" % alt
        return a, b, c

    def _autosize_columns(self):
        self._listCtrl.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        self._listCtrl.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        self._listCtrl.SetColumnWidth(2, wx.LIST_AUTOSIZE)

    def update_image(self, img):
        for ident, image in self._itemDataMap.items():
            if img is image:
                index = self._listCtrl.FindItem(-1, ident)
                columns = self._image_columns(img)
                for n, text in enumerate(columns):
                    self._listCtrl.SetItem(index, n, text)
                self.itemDataMap[ident] = columns
                self._autosize_columns()
                break

    def add_image(self, img):
        """
        Add an image to the control. It is assumed to be a object
        returned from gen_images_from_files()
        """
        assert img not in self._itemDataMap.values()
        a, b, c = columns = self._image_columns(img)
        while self._uuidCounter in self._itemDataMap:
            self._uuidCounter += 1
        ident = self._uuidCounter
        self._uuidCounter += 1
        self._itemDataMap[ident] = img
        self.itemDataMap[ident] = columns
        index = self._listCtrl.InsertItem(self._listCtrl.GetItemCount(), a)
        self._listCtrl.SetItem(index, 1, b)
        self._listCtrl.SetItem(index, 2, c)
        self._listCtrl.SetItemData(index, ident)

        self._autosize_columns()

    def iter_images(self):
        """
        Iterate over (a snapshot of) the images
        """
        for img in list(self._itemDataMap.values()):
            yield img

    def _get_image_from_index(self, index):
        """
        Given the item index, e.g. from event.GetIndex(), this
        returns the image object
        """
        ident = self._listCtrl.GetItemData(index)
        return self._itemDataMap[ident]

    def rm_image(self, img):
        for ident, image in self._itemDataMap.items():
            if img is image:
                index = self._listCtrl.FindItem(-1, ident)
                self._listCtrl.DeleteItem(index)
                del self._itemDataMap[ident]
                del self.itemDataMap[ident]
                break
