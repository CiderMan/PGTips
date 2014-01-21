import wx
from subprocess import Popen, PIPE, STDOUT
import os.path

_TEXT_WIDTH = 500
_FILETYPES_TEXT = "PGTips handles individual files as being one of three types. Specify the file extensions that you want to be handled in that way.\n\nNote that specifying no filetypes in a box means that PGTips should attempt to handle all files that it encounters in that way."
_DIRECTORIES_TEXT = "Specify the directories to be used by PGTips."
_EXIFTOOL_TEXT = "EXIFtool is the de-facto standard tool for reading and writing EXIF data in images. At the time of writing, it supports the largest number of file formats (including most camera RAW formats) and provides the most complete support of tag types. It also supports two different structured interfaces (JSON and XML) to allow easy interfacing to other applications as well as its human interface. Hence, PGTips uses it to read information like the shooting date from your images and write back the geotagging infomation."
_JPEGTRAN_TEXT = "jpegtran is an application that supports lossless operations on JPEG images. In particular, it allows JPEGs to be losslessly rotated.\n\nWhile PGTips doesn't require jpegtran, if it is available, it can be used to losslessly rotate (either manually or automatically, if the companion application jpegexiforient is also available) JPEGs if required."

def _split_csl(csl, prefix = ""):
    l1 = [e.strip() for e in csl.split(",")]
    l2 = []
    for e in l1:
        if len(e) > 0:
            l2 += e.split()
    l = [prefix + e for e in l2]
    return l

class OptionsDialog(wx.Dialog):
    def _create_labelled_text_ctrl(self, parent, label, sizer, ctrlAttr, labelAttr = None, border = 3, multiline = False, tooltip = None):
        style = wx.TE_MULTILINE if multiline else 0
        label = wx.StaticText(parent, -1, label)
        label.Wrap(_TEXT_WIDTH/2)
        if labelAttr is not None:
            setattr(self, labelAttr, label)
        ctrl = wx.TextCtrl(parent, -1, "", style = style)
        if multiline:
            minSize = ctrl.GetMinSize()
            if minSize.height < (self._lineHeight + 2):
                minSize.SetHeight(self._lineHeight + 2)
                ctrl.SetMinSize(minSize)
        setattr(self, ctrlAttr, ctrl)
        if tooltip is not None:
            ctrl.SetToolTip(wx.ToolTip(tooltip))
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(label, 1, wx.ALIGN_RIGHT | wx.ALIGN_CENTRE_VERTICAL, 0)
        hSizer.Add(ctrl, 1, wx.EXPAND, 0)
        sizer.Add(hSizer, 1 if multiline else 0, wx.EXPAND | wx.TOP, border)

    def _create_filetypes_page(self):
        self.filetypesPage = wx.Panel(self.categoryNotebook, -1)
        explanation = wx.StaticText(self.filetypesPage, -1, _FILETYPES_TEXT)
        explanation.Wrap(_TEXT_WIDTH)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(explanation, 0, wx.TOP, 3)
        self._create_labelled_text_ctrl(
                self.filetypesPage,
                "Image file extensions:",
                vSizer,
                "_imageExtTextCtrl",
                tooltip = "Image files are the files that PGTips will import, attempt to Geotag and file",
                multiline = True)
        self._create_labelled_text_ctrl(
                self.filetypesPage,
                "GPS file extensions:",
                vSizer,
                "_gpsExtTextCtrl",
                border = 10,
                tooltip = "GPS files are the files that PGTips will use to determine where you were when a photo was taken and are used 'in place'",
                multiline = True)
        self._create_labelled_text_ctrl(
                self.filetypesPage,
                "Other file extensions:",
                vSizer,
                "_otherExtTextCtrl",
                border = 10,
                tooltip = "'Other' files are additional file types (e.g. Video files) that will be imported and filed but otherwise will not be processed",
                multiline = True)
        self.filetypesPage.SetSizer(vSizer)
        return self.filetypesPage

    def _populate_filetypes_options(self):
        self._imageExtTextCtrl.SetValue(", ".join([e.lstrip('.') for e in self.options["ImageExtensions"]]))
        self._gpsExtTextCtrl.SetValue(", ".join([e.lstrip('.') for e in self.options["GpsExtensions"]]))
        self._otherExtTextCtrl.SetValue(", ".join([e.lstrip('.') for e in self.options["OtherExtensions"]]))

    def _update_filetypes_options(self):
        v = str(self._imageExtTextCtrl.GetValue().lower())
        self.options["ImageExtensions"] = _split_csl(v, prefix = ".")
        v = str(self._gpsExtTextCtrl.GetValue().lower())
        self.options["GpsExtensions"] = _split_csl(v, prefix = ".")
        v = str(self._otherExtTextCtrl.GetValue().lower())
        self.options["OtherExtensions"] = _split_csl(v, prefix = ".")

    def _create_directories_page(self):
        self.directoriesPage = wx.Panel(self.categoryNotebook, -1)
        explanation = wx.StaticText(self.directoriesPage, -1, _DIRECTORIES_TEXT)
        explanation.Wrap(_TEXT_WIDTH)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(explanation, 0, wx.TOP, 3)
        self._create_labelled_text_ctrl(
                self.directoriesPage,
                "Working directory:",
                vSizer,
                "_workingDir",
                tooltip = "This is the directory into which PGTips will import files before working on (i.e. modifying) those files")
        self._create_labelled_text_ctrl(
                self.directoriesPage,
                "Filing directory:",
                vSizer,
                "_filingDir",
                border = 10,
                tooltip = "This is the base directory into which PGTips will move the files once it has finished working on those files")
        self._create_labelled_text_ctrl(
                self.directoriesPage,
                "Filing structure:",
                vSizer,
                "_filingStruct",
                border = 10,
                tooltip = "This is the directory structure to create underneath the filing directory above")
        self.directoriesPage.SetSizer(vSizer)
        return self.directoriesPage

    def _populate_directories_options(self):
        self._workingDir.SetValue(self.options["WorkingDir"])
        self._filingDir.SetValue(self.options["FilingDir"])
        self._filingStruct.SetValue(self.options["FilingStruct"])

    def _update_directories_options(self):
        self.options["WorkingDir"] = os.path.normpath(self._workingDir.GetValue())
        self.options["FilingDir"] = os.path.normpath(self._filingDir.GetValue())
        self.options["FilingStruct"] = os.path.normpath(self._filingStruct.GetValue())
        pass

    def _create_exiftool_page(self):
        self.exiftoolPage = wx.Panel(self.categoryNotebook, -1)
        explanation = wx.StaticText(self.exiftoolPage, -1, _EXIFTOOL_TEXT)
        explanation.Wrap(_TEXT_WIDTH)
        self._exiftoolCheckCfg = wx.Button(self.exiftoolPage, -1, "Check configuration")
        self.Bind(wx.EVT_BUTTON, self._check_exiftool_cfg, self._exiftoolCheckCfg)
        self._exiftoolCheckText = wx.TextCtrl(self.exiftoolPage, -1, "", style = wx.TE_MULTILINE)

        minSize = self._exiftoolCheckText.GetMinSize()
        if minSize.height < (5 * self._lineHeight + 2):
            minSize.SetHeight(5 * self._lineHeight + 2)
            self._exiftoolCheckText.SetMinSize(minSize)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(explanation, 0, wx.TOP, 3)
        self._create_labelled_text_ctrl(
                self.exiftoolPage,
                "Path to EXIFtool:",
                vSizer,
                "_exiftoolPath",
                tooltip = "If EXIFtool is in your path, simply leave this blank. Once you've completed the configuration, click 'Check Configuration' to see if PGTips is able to find the application",
                border = 6)
        vSizer.Add(self._exiftoolCheckCfg, 0, wx.TOP | wx.ALIGN_LEFT, 3)
        vSizer.Add(self._exiftoolCheckText, 1, wx.EXPAND | wx.TOP, 3)
        self.exiftoolPage.SetSizer(vSizer)
        return self.exiftoolPage

    def _populate_exiftool_options(self):
        self._exiftoolPath.SetValue(self.options["ExiftoolPath"])

    def _update_exiftool_options(self):
        self.options["ExiftoolPath"] = self._exiftoolPath.GetValue()

    def _check_exiftool_cfg(self, evt):
        path = self._exiftoolPath.GetValue()
        if path != "" and not os.path.isdir(path):
            self._exiftoolCheckText.SetValue("ERROR: '%s' is not a directory" % path)
            return
        exiftool = "exiftool"
        if path != "":
            exiftool = os.path.join(path, exiftool)
        try:
            p = Popen([exiftool, "-ver", "-listwf"], stdin = PIPE, stdout = PIPE, stderr = STDOUT)
            stdout, stderr = p.communicate()
        except OSError:
            self._exiftoolCheckText.SetValue("ERROR: Unable to execute '%s -ver -listwf'" % exiftool)
            return
        s = [x.strip() for x in stdout.splitlines()]
        ver = s[0]
        wf = " ".join(s[2:])

        self._exiftoolCheckText.SetValue("SUCCESS! You have version %s of EXIFtool\n\n" % ver + s[1] + "\n" + wf)

    def _create_jpegtran_page(self):
        self.jpegtranPage = wx.Panel(self.categoryNotebook, -1)
        explanation = wx.StaticText(self.jpegtranPage, -1, _JPEGTRAN_TEXT)
        explanation.Wrap(_TEXT_WIDTH)
        self._jpegtranEnable = wx.CheckBox(self.jpegtranPage, -1, "Enable jpegtran (and jpegexiforient)")
        self.Bind(wx.EVT_CHECKBOX, self._jpegtran_enabled, self._jpegtranEnable)
        self._jpegtranCheckCfg = wx.Button(self.jpegtranPage, -1, "Check configuration")
        self.Bind(wx.EVT_BUTTON, self._check_jpegtran_cfg, self._jpegtranCheckCfg)
        self._jpegtranCheckText = wx.TextCtrl(self.jpegtranPage, -1, "", style = wx.TE_MULTILINE)

        minSize = self._jpegtranCheckText.GetMinSize()
        if minSize.height < (5 * self._lineHeight + 2):
            minSize.SetHeight(5 * self._lineHeight + 2)
            self._jpegtranCheckText.SetMinSize(minSize)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(explanation, 0, wx.TOP, 3)
        vSizer.Add(self._jpegtranEnable, 0, wx.TOP, 6)
        self._create_labelled_text_ctrl(
                self.jpegtranPage,
                "Path to jpegtran/jpegexiforient:",
                vSizer,
                "_jpegtranPath",
                tooltip = "If jpegtran is in your path, simply leave this blank. Once you've completed the configuration, click 'Check Configuration' to see if PGTips is able to find the applications")
        vSizer.Add(self._jpegtranCheckCfg, 0, wx.TOP | wx.ALIGN_LEFT, 3)
        vSizer.Add(self._jpegtranCheckText, 1, wx.EXPAND | wx.TOP, 3)
        self.jpegtranPage.SetSizer(vSizer)
        return self.jpegtranPage

    def _populate_jpegtran_options(self):
        self._jpegtranEnable.SetValue(self.options["JpegtranEnabled"])
        self._jpegtranPath.SetValue(self.options["JpegtranPath"])
        self._jpegtran_enabled(None)

    def _update_jpegtran_options(self):
        self.options["JpegtranEnabled"] = self._jpegtranEnable.GetValue()
        self.options["JpegtranPath"] = self._jpegtranPath.GetValue()

    def _jpegtran_enabled(self, evt):
        enabled = self._jpegtranEnable.GetValue()
        self._jpegtranPath.Enable(enabled)
        self._jpegtranCheckCfg.Enable(enabled)
        self._jpegtranCheckText.Enable(enabled)

    def _check_jpegtran_cfg(self, evt):
        path = self._jpegtranPath.GetValue()
        if path != "" and not os.path.isdir(path):
            self._jpegtranCheckText.SetValue("ERROR: '%s' is not a directory" % path)
            return
        jpegtran = "jpegtran"
        jpegexiforient = "jpegexiforient"
        if path != "":
            jpegtran = os.path.join(path, jpegtran)
            jpegexiforient = os.path.join(path, jpegexiforient)
        try:
            p = Popen([jpegtran, "-v"], stdin = PIPE, stdout = PIPE, stderr = STDOUT)
            stdout, stderr = p.communicate()
        except OSError:
            self._jpegtranCheckText.SetValue("ERROR: Unable to execute '%s -v'" % jpegtran)
            return
        s = stdout.splitlines()[0:2]
        try:
            p = Popen([jpegexiforient, "--help"], stdin = PIPE, stdout = PIPE, stderr = STDOUT)
            stdout, stderr = p.communicate()
        except OSError:
            self._jpegtranCheckText.SetValue("Semi-success: jpegtran worked fine but unable to execute '%s --help'. You will only be able to rotate JPEGS manually.\n\n" % jpegexiforient + "\n".join(s))
            return
        s.append("")
        s += stdout.splitlines()[0:1]
        self._jpegtranCheckText.SetValue("SUCCESS! You can losslessly rotate JPEGs both automatically and manually.\n\n" + "\n".join(s))

    def __init__(self, *args, **kwds):
        try:
            self._optFile = kwds["optFile"]
            del kwds["optFile"]
            try:
                o = file(self._optFile).read()
            except IOError:
                o = "{}"
            readOpts = eval(o)
        except KeyError:
            self._optFile = None
            readOpts = {}

        # Set everything to the default values in the first case
        self.options = {
                "ImageExtensions" : [],
                "GpsExtensions" : [],
                "OtherExtensions" : [],
                "WorkingDir" : "",
                "FilingDir" : "",
                "FilingStruct" : "%Y/%Y_%m/%Y_%m_%d",
                "JpegtranEnabled": True,
                "JpegtranPath": "",
                "ExiftoolPath": "",
                }

        for k, v in readOpts.items():
            self.options[k] = v

        kwds["style"] = wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, *args, **kwds)

        dc = wx.ClientDC(self)
        self._lineHeight = dc.GetTextExtent("Tg\nTg")[1] - dc.GetTextExtent("Tg")[1]
        del dc

        if self._lineHeight == 0:
            print "Unable to determine line height; picking a number, any number..."
            self._lineHeight = 20

        self.SetTitle("Options...")

        self.categoryNotebook = wx.Notebook(self, -1, style=0)

        self._pages = [
                ("Filetypes", self._create_filetypes_page, self._populate_filetypes_options, self._update_filetypes_options),
                ("Directories", self._create_directories_page, self._populate_directories_options, self._update_directories_options),
                ("EXIFtool", self._create_exiftool_page, self._populate_exiftool_options, self._update_exiftool_options),
                ("jpegtran", self._create_jpegtran_page, self._populate_jpegtran_options, self._update_jpegtran_options),
                ]

        for name, addFn, popFn, updateFn in self._pages:
            panel = addFn()
            self.categoryNotebook.AddPage(panel, name)
            popFn()

        # Create the main sizer that has the notebook at the top and the OK/Cancel at the bottom
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        # Add the notebook
        mainSizer.Add(self.categoryNotebook, 1, wx.EXPAND, 0)

        # Now create and populate the button sizer
        buttonSizer = wx.StdDialogButtonSizer()

        okButton = wx.Button(self, wx.ID_OK)
        buttonSizer.AddButton(okButton)
        self.Bind(wx.EVT_BUTTON, self.OnOK, okButton)

        button = wx.Button(self, wx.ID_CANCEL)
        buttonSizer.AddButton(button)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, button)

        okButton.SetDefault()

        buttonSizer.Realize()

        # Add to the main sizer
        mainSizer.Add(buttonSizer, 0, wx.EXPAND|wx.ALIGN_RIGHT, 0)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)
        self.Layout()

    def OnOK(self, evt):
        map(lambda x: x[3](), self._pages)
        map(lambda x: x[2](), self._pages)
        if self._optFile is not None:
            with file(self._optFile, "w") as o:
                o.write(repr(self.options))
        evt.Skip()

    def OnCancel(self, evt):
        map(lambda x: x[2](), self._pages)
        evt.Skip()

if __name__ == "__main__":
    app = wx.PySimpleApp(0)
    wx.InitAllImageHandlers()
    optionsDialog = OptionsDialog(None, -1, "", optFile = "test.opt")
    app.SetTopWindow(optionsDialog)
    optionsDialog.Show()
    app.MainLoop()
