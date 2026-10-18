#!/usr/bin/env python3
import wx, sys, shutil
from pathlib import Path

# Include the sub-directory containing the sub-modules when looking for imports
sys.path.append(str(Path(__file__).resolve().parent / "sub-modules"))

import wx.lib.agw.aui as aui
import wx.lib.mixins.listctrl as listmix
import datetime
from functools import reduce
import images
from threading import Thread
import queue
from subprocess import Popen, PIPE, STDOUT
import slippy
from gpsfiles import gen_tracks_from_files
from imagefiles import gen_images_from_files, read_orientation, set_orientation
from options import OptionsDialog
from imagelist import ImageListCtrlPanel

_DEFAULT_STATUS_TEXT = "PGTips v0.1"

# Define the jpegtran command-line options to losslessly correct
# the possible orientations for an image
_jpegtranOptions = [
    None,  # 0 - not present
    [],  # 1 - no translation
    ["-flip", "horizontal"],  # 2 - Shouldn't get this with a photo?
    ["-rotate", "180"],  # 3 - Camera was upside down!
    ["-flip", "vertical"],  # 4 - Shouldn't get this with a photo?
    ["-transpose"],  # 5 - Shouldn't get this with a photo?
    ["-rotate", "90"],  # 6 - Camera was on its side
    ["-transverse"],  # 7 - Shouldn't get this with a photo?
    ["-rotate", "270"],  # 8 - Camera was on its other side
]


def _lossless_rotate(jpegFile, orientation, jpegtran="jpegtran", exiftool="exiftool"):
    """
    Losslessly transform a JPEG to correct the given EXIF orientation, then reset the
    file's orientation flag to say that no further correction is needed
    """
    tmpFile = jpegFile.with_name(jpegFile.name + ".pgtips~.jpg")
    try:
        p = Popen(
            [jpegtran, "-copy", "all"]
            + _jpegtranOptions[orientation]
            + ["-outfile", tmpFile, jpegFile],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
        )
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            raise RuntimeError("jpegtran failed: " + stderr)
        set_orientation(tmpFile, 1, exiftool)
        tmpFile.replace(jpegFile)
    finally:
        tmpFile.unlink(missing_ok=True)


class GpsFileCache(object):
    """
    This class implements a wrapper of the objects returned by the gpsfiles module
    It holds the inner object in its gpsFile member and the slippy track for each
    GPS track are retreived by a method, which will generate it if required or simply
    return the already generated one if it has already been requested previously
    """

    def __init__(self, inner):
        self.gpsFile = inner
        self._tracks = [None for n in range(len(inner))]

    def get_track(self, n):
        if self._tracks[n] is None:
            self._tracks[n] = slippy.Track(((x[1], x[2]) for x in self.gpsFile[n]))
        return self._tracks[n]


class CustomStatusBar(wx.StatusBar):
    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, -1)

        # This status bar has two fields
        self.SetFieldsCount(3)

        self.sizeChanged = False
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_IDLE, self.OnIdle)

        # Sets the three fields to be relative widths to each other.
        self.SetStatusWidths([-1, 100, 50])

        # Field 0 ... just text
        self.SetStatusText(_DEFAULT_STATUS_TEXT, 0)

        # This will fall into field 1 (the second field)
        self.progress = wx.Gauge(self, 100)
        self.progress.SetValue(0)

        # Now set the initial position of the progress bar
        self.Reposition()

    def OnSize(self, evt):
        self.Reposition()  # for normal size events

        # Set a flag so the idle time handler will also do the repositioning.
        # It is done this way to get around a buglet where GetFieldRect is not
        # accurate during the EVT_SIZE resulting from a frame maximize.
        self.sizeChanged = True

    def OnIdle(self, evt):
        if self.sizeChanged:
            self.Reposition()

    # reposition the checkbox
    def Reposition(self):
        rect = self.GetFieldRect(1)
        self.progress.SetPosition((rect.x + 2, rect.y + 2))
        self.progress.SetSize((rect.width - 4, rect.height - 4))
        self.sizeChanged = False


class MyFrame(wx.Frame):
    def __init__(
        self,
        parent,
        id=-1,
        title=_DEFAULT_STATUS_TEXT,
        pos=wx.DefaultPosition,
        size=(800, 500),
        style=wx.DEFAULT_FRAME_STYLE,
    ):
        wx.Frame.__init__(self, parent, id, title, pos, size, style)

        self._statusBar = CustomStatusBar(self)

        self.SetStatusBar(self._statusBar)

        self._optionsDialog = OptionsDialog(self, optFile="pgtips.opt")

        self._closing = False

        self._exiftoolChecked = ""

        self._mgr = aui.AuiManager(
            self,
            aui.AUI_MGR_ALLOW_FLOATING
            | aui.AUI_MGR_TRANSPARENT_DRAG
            | aui.AUI_MGR_VENETIAN_BLINDS_HINT
            | aui.AUI_MGR_NO_VENETIAN_BLINDS_FADE
            | aui.AUI_MGR_LIVE_RESIZE
            | aui.AUI_MGR_SMOOTH_DOCKING
            | aui.AUI_MGR_ANIMATE_FRAMES,
        )

        # Sort out the menu
        menuDef = [
            (
                "&File",
                [
                    ("Load GPS Files...\tCtrl-G", self.OnLoadGpsFiles),
                    ("Load image Files...\tCtrl-L", self.OnLoadImages),
                    ("", None),
                    ("Import files\tCtrl-I", self.OnImport),
                    ("Export files\tCtrl-E", self.OnExport),
                    ("", None),
                    ("Exit\tCtrl-Q", self.OnClose),
                ],
            ),
            (
                "&Geotag",
                [
                    ("Geotag all images\tCtrl-T", self.OnGeotagAll),
                ],
            ),
            (
                "&Tools",
                [
                    ("Toggle full screen mode\tF11", self.OnToggleFullScreen),
                    ("Options...", self.OnOptions),
                ],
            ),
        ]

        def create_menu(definition):
            menu = wx.Menu()
            for name, content in definition:
                if content is None:
                    menu.AppendSeparator()
                elif isinstance(content, list):
                    m = create_menu(content)
                    menu.AppendSubMenu(m, name)
                else:
                    item = menu.Append(-1, name)
                    self.Bind(wx.EVT_MENU, content, item)
            return menu

        mb = wx.MenuBar()
        for title, menu in menuDef:
            mb.Append(create_menu(menu), title)

        self.SetMenuBar(mb)

        self._fullscreen = True
        # self.Maximise(True)
        # Removed as is problematic on Windows. Workaround for this at the bottom of the file
        # self.ShowFullScreen(self._fullscreen, wx.FULLSCREEN_NOBORDER | wx.FULLSCREEN_NOCAPTION)

        # create several text controls
        source = slippy.OpenStreetMapTileSource()
        tileCache = slippy.SlippyCache(source)  # , proxy = "http://80.254.147.83:8080")

        self._slipMap = slippy.SlippyPanel(self, -1, cache=tileCache, size=(300, 300))
        self._tracks = []
        self._markers = {}

        self._gpxTree = wx.TreeCtrl(
            self,
            -1,
            wx.DefaultPosition,
            wx.Size(-1, -1),
            wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT,
        )
        self._gpxRoot = self._gpxTree.AddRoot("GPS Files")

        self._images = ImageListCtrlPanel(self)

        # add the panes to the manager
        self._mgr.AddPane(self._slipMap, wx.TOP, "Mapping pane")
        # self._mgr.AddPane(text1, wx.TOP, 'Preview pane')
        self._mgr.AddPane(self._gpxTree, wx.TOP, "GPS fle pane")
        self._mgr.AddPane(self._images, wx.CENTER)

        # tell the manager to 'commit' all the changes just made
        self._mgr.Update()

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self._gpxTree.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnNewTrack)

        # Create the worker thread
        self._working = False
        self._workerQueue = queue.Queue()
        self._workerThread = Thread(target=self._WorkerThread)
        self._workerThread.start()

        self._importing = False
        self._importQueue = queue.Queue()
        self._importThread = Thread(target=self._ImportThread)
        self._importThread.start()

        self._checkQueue = queue.Queue()

        self._images.add_image_select_notify(self.OnImageSelected)
        self._images.add_image_deselect_notify(self.OnImageDeselected)

        self._PulseProgress()

    # This method is the one called in the worker thread and dispatches
    # the tasks that are passed to it
    def _WorkerThread(self):
        while not self._closing:
            fn, args, kwargs = self._workerQueue.get()
            self._working = True
            while self._working:
                if fn is not None:
                    fn(*args, **kwargs)
                try:
                    fn, args, kwargs = self._workerQueue.get_nowait()
                except queue.Empty:
                    self._working = False

    # Method to pass work to the worker thread using the same pattern as
    # wx.CallAfter()
    def _do_work(self, fn, *args, **kwargs):
        self._workerQueue.put((fn, args, kwargs))

    def _do_check(self, fn, *args, **kwargs):
        self._checkQueue.put((fn, args, kwargs))

    # This method polls whether the working thread is busy and pulses the
    # status bar progress indicator while that it true
    def _PulseProgress(self):
        if self._closing:
            # The frame is being destroyed so stop polling
            return
        while not self._closing:
            try:
                fn, args, kwargs = self._checkQueue.get_nowait()
                fn(*args, **kwargs)
            except queue.Empty:
                break

        if self._working or self._importing:
            self._statusBar.progress.Pulse()
            wx.CallLater(100, self._PulseProgress)
        else:
            self._statusBar.SetStatusText(_DEFAULT_STATUS_TEXT)
            self._statusBar.progress.SetValue(0)
            wx.CallLater(500, self._PulseProgress)

    def _exiftool_check(self):
        exiftool = "exiftool"
        path = self._optionsDialog.options["ExiftoolPath"]
        if path != "":
            exiftool = str(Path(path, exiftool))
        if self._exiftoolChecked != exiftool:
            error = False
            try:
                p = Popen([exiftool, "-ver"], stdin=PIPE, stdout=PIPE, stderr=STDOUT)
                stdout, stderr = p.communicate()
            except OSError:
                error = True
            if error:
                response = wx.MessageDialog(
                    self,
                    "PGTips is uses EXIFtool to read the metadata in your photographs\n"
                    "and set the geotags in them. However, it has not been possible\n"
                    "to run exiftool. Please ensure that you have EXIFtool on this PC\n"
                    "and that the configuration (e.g. path in Tools->Options) is correct",
                    "Configuration problem",
                    style=wx.OK | wx.ICON_ERROR,
                ).ShowModal()
                return False
            self._exiftoolChecked = exiftool

        return True

    ################################################################################
    ####
    #### Load GPS files
    ####
    ################################################################################

    def _add_gps_file(self, gpsFile):
        text = Path(gpsFile.get_filename()).name
        item, cookie = self._gpxTree.GetFirstChild(self._gpxRoot)
        n = 0
        while item.IsOk() and text <= self._gpxTree.GetItemText(item):
            item, cookie = self._gpxTree.GetNextChild(self._gpxRoot, cookie)
            n += 1
        if item.IsOk():
            item = self._gpxTree.InsertItemBefore(self._gpxRoot, n, text)
        else:
            item = self._gpxTree.AppendItem(self._gpxRoot, text)
        wrappedGpsFile = GpsFileCache(gpsFile)
        # Note that the item data is:
        # 1: The object for the whole file
        # 2: The indices of the sub-tracks to which this element corresponds
        # 3: A placeholder for the cached track array
        # 4: A placeholder for the cached region
        self._gpxTree.SetItemData(item, (wrappedGpsFile, list(range(len(gpsFile)))))
        for n, t in enumerate(gpsFile):
            subitem = self._gpxTree.AppendItem(item, "%s - %s" % (str(t[0][0]), str(t[-1][0])))
            self._gpxTree.SetItemData(subitem, (wrappedGpsFile, [n]))

        # TODO: Now check whether there are any images to geotag

    def _load_gps_files_work(self, path):
        for t in gen_tracks_from_files(path):
            wx.CallAfter(self._add_gps_file, t)

    def OnLoadGpsFiles(self, event):
        dlg = wx.DirDialog(self, style=wx.DD_DIR_MUST_EXIST, defaultPath="/home/steve/GPSTracks/")
        if dlg.ShowModal() == wx.ID_OK:
            self._do_work(self._load_gps_files_work, dlg.GetPath())

    # End the "load GPS files" operation

    ################################################################################
    ####
    #### Load images
    ####
    ################################################################################

    def _add_image(self, img):
        if img["FileType"] == "JPG" and img["Orientation"] != "1":
            print(img.get_filename(), "is not orientation 1")

        # TODO: Check whether this image is geotagged by any of the GPS files
        self._images.add_image(img)

    def _load_file_work(self, path):
        wx.CallAfter(self._statusBar.SetStatusText, "Loading files from " + path)
        include = self._optionsDialog.options["ImageExtensions"]
        if len(include) == 0:
            include = None
        for i in gen_images_from_files(path, include=include, exiftool=self._exiftoolChecked):
            wx.CallAfter(self._statusBar.SetStatusText, "Loading " + i["FileName"])
            wx.CallAfter(self._add_image, i)

    def OnLoadImages(self, event):
        if not self._exiftool_check():
            return
        dlg = wx.DirDialog(self, style=wx.DD_DIR_MUST_EXIST, defaultPath="/home/steve/Master/")
        if dlg.ShowModal() == wx.ID_OK:
            self._do_work(self._load_file_work, dlg.GetPath())

    # End the "load images" operation

    ################################################################################
    ####
    #### Import files
    ####
    ################################################################################

    # This function is run as a seperate thread to automatically batch the files
    # to exiftool to improve performance
    def _ImportThread(self):
        while not self._closing:
            files = []
            try:
                filename = self._importQueue.get_nowait()
            except queue.Empty:
                self._importing = False
                filename = self._importQueue.get()
            self._importing = True
            if filename is not None:
                files.append(filename)
                try:
                    timeout = 0.5
                    while True:
                        filename = self._importQueue.get(block=timeout > 0, timeout=timeout)
                        if filename is not None:
                            files.append(filename)
                            timeout -= 0.1
                        else:
                            break
                except queue.Empty:
                    for i in gen_images_from_files(files, exiftool=self._exiftoolChecked):
                        wx.CallAfter(self._statusBar.SetStatusText, "Loading " + i["FileName"])
                        wx.CallAfter(self._add_image, i)

    def _copy_file_work(self, f, dirpath, workingDir, ext, process, useJpegtran, jpegtran):
        wx.CallAfter(self._statusBar.SetStatusText, "Importing " + f)
        srcFile = dirpath / f
        destFile = workingDir / f
        if destFile.exists():
            # User must have OK'd this so delete the destination file then copy the new one into place
            destFile.unlink()
        shutil.copy(srcFile, workingDir)
        if process and ext in [".jpg", ".jpeg"] and useJpegtran:
            # losslessly rotate
            orient = read_orientation(destFile, self._exiftoolChecked)
            # No (or an invalid) orientation flag means that there is nothing to correct
            if orient is not None and 1 < orient < len(_jpegtranOptions):
                wx.CallAfter(
                    self._statusBar.SetStatusText, "Importing %s (losslessly rotating)" % f
                )
                print(destFile, "- using option:", _jpegtranOptions[orient])
                _lossless_rotate(destFile, orient, jpegtran, self._exiftoolChecked)

        if process:
            # Now that the file is where it needs to be, load the file
            # TODO: Could optimize by batching files together?
            if 1:
                self._importQueue.put(destFile)
            else:
                wx.CallAfter(self._statusBar.SetStatusText, "Loading " + f)
                for i in gen_images_from_files(destFile, exiftool=self._exiftoolChecked):
                    wx.CallAfter(self._add_image, i)

    def _copy_file_overwrite_check(
        self, f, dirpath, workingDir, ext, process, useJpegtran, jpegtran
    ):
        if (
            wx.MessageBox(
                "%s already exists in %s; overwrite?" % (f, workingDir),
                "File exists",
                wx.YES_NO,
                self,
            )
            == wx.YES
        ):
            self._do_work(
                self._copy_file_work,
                f,
                dirpath,
                workingDir,
                ext,
                process,
                useJpegtran,
                jpegtran,
            )

    def _import_files_work(self, fromDir, workingDir, useJpegtran, jpegtran, emptyWorkingDir):
        if emptyWorkingDir:
            wx.CallAfter(self._statusBar.SetStatusText, "Deleting files in %s" % workingDir)
            for f in list(workingDir.iterdir()):
                print("Deleting", f)
                f.unlink()

        other = self._optionsDialog.options["OtherExtensions"]
        image = self._optionsDialog.options["ImageExtensions"]

        wx.CallAfter(self._statusBar.SetStatusText, "Searching for files to import...")

        # Walk and copy files to working dir
        for dirpath, dirnames, filenames in fromDir.walk():
            for f in filenames:
                ext = Path(f).suffix.lower()
                copy = False
                process = False
                if ext in other or len(other) == 0:
                    copy = True
                if ext in image or len(image) == 0:
                    copy = True
                    process = True
                if copy:
                    destFile = workingDir / f
                    if destFile.exists():
                        self._do_check(
                            self._copy_file_overwrite_check,
                            f,
                            dirpath,
                            workingDir,
                            ext,
                            process,
                            useJpegtran,
                            jpegtran,
                        )
                    else:
                        self._do_work(
                            self._copy_file_work,
                            f,
                            dirpath,
                            workingDir,
                            ext,
                            process,
                            useJpegtran,
                            jpegtran,
                        )

    def OnImport(self, event):
        if not self._exiftool_check():
            return
        useJpegtran = self._optionsDialog.options["JpegtranEnabled"]
        jpegtran = "jpegtran"
        if useJpegtran:
            error = False
            path = self._optionsDialog.options["JpegtranPath"]
            if path != "":
                jpegtran = str(Path(path, jpegtran))
            try:
                p = Popen([jpegtran, "-v"], stdin=PIPE, stdout=PIPE, stderr=STDOUT)
                stdout, stderr = p.communicate()
            except OSError:
                error = True
            if error:
                response = wx.MessageDialog(
                    self,
                    "PGTips is configured to use jpegtran but it was not able to\n"
                    "execute it. This means that it will not be possible to\n"
                    "automatically rotate any JPEG files during import\n\n"
                    "Do you want to continue importing?",
                    "Configuration problem",
                    style=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
                ).ShowModal()
                if response == wx.ID_NO:
                    return
                else:
                    useJpegtran = False

        dlg = wx.DirDialog(self, style=wx.DD_DIR_MUST_EXIST, defaultPath="/home/steve/Master/")
        if dlg.ShowModal() == wx.ID_OK:
            workingDir = Path(self._optionsDialog.options["WorkingDir"])
            emptyWorkingDir = False
            if not workingDir.is_dir():
                try:
                    workingDir.mkdir(parents=True)
                except OSError:
                    wx.MessageBox("Unable to create %s" % workingDir, "Error", style=wx.ICON_ERROR)
                    return
            else:
                if any(workingDir.iterdir()):
                    response = wx.MessageDialog(
                        self,
                        "The working directory is not empty.\n\n"
                        "Do you want to delete the current contents before importing?",
                        "Working directory not empty",
                        style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
                    ).ShowModal()
                    if response == wx.ID_YES:
                        emptyWorkingDir = True

            self._do_work(
                self._import_files_work,
                Path(dlg.GetPath()),
                workingDir,
                useJpegtran,
                jpegtran,
                emptyWorkingDir,
            )

    # End the "import files" operation

    ################################################################################
    ####
    #### Export files
    ####
    ################################################################################

    def _export_file_overwrite(self, f, exportDir, srcFile):
        dest = exportDir / f
        wx.CallAfter(self._statusBar.SetStatusText, "Removing %s" % dest)
        dest.unlink()

        wx.CallAfter(self._statusBar.SetStatusText, "Exporting " + f)
        shutil.move(srcFile, exportDir)

    def _export_file_overwrite_check(self, f, exportDir, srcFile):
        if (
            wx.MessageBox(
                "%s already exists in %s; overwrite?" % (f, exportDir),
                "File exists",
                wx.YES_NO,
                self,
            )
            == wx.YES
        ):
            self._do_work(self._export_file_overwrite, f, exportDir, srcFile)

    def _export_file_work(self, dirpath, f, loadedImages):
        images = self._optionsDialog.options["ImageExtensions"]
        other = self._optionsDialog.options["OtherExtensions"]

        ext = Path(f).suffix.lower()
        srcFile = (dirpath / f).absolute()
        img = None
        exportDatetime = None
        if ext in images or len(images) == 0:
            for img in loadedImages:
                if Path(img.get_filename()).absolute() == srcFile:
                    wx.CallAfter(self._images.rm_image, img)
                    break
            else:
                img = list(gen_images_from_files(srcFile, exiftool=self._exiftoolChecked))[0]
            exportDatetime = img.dateTime
        if exportDatetime is None and (ext in other or len(other) == 0):
            otherFile = list(gen_images_from_files(srcFile, exiftool=self._exiftoolChecked))[0]
            exportDatetime = otherFile.dateTime
            print(f, exportDatetime)
            assert exportDatetime is not None
            # exportDatetime = datetime.datetime.fromtimestamp(srcFile.stat().st_ctime)
        if exportDatetime is not None:
            exportDir = Path(
                self._optionsDialog.options["FilingDir"],
                exportDatetime.strftime(self._optionsDialog.options["FilingStruct"]),
            )
            exportDir.mkdir(parents=True, exist_ok=True)
            if (exportDir / f).exists():
                self._do_check(self._export_file_overwrite_check, f, exportDir, srcFile)
            else:
                wx.CallAfter(self._statusBar.SetStatusText, "Exporting " + f)
                shutil.move(srcFile, exportDir)

    def OnExport(self, event):
        fromDir = Path(self._optionsDialog.options["WorkingDir"])

        loadedImages = list(self._images.iter_images())

        # Walk and copy files to working dir
        for dirpath, dirnames, filenames in fromDir.walk():
            for f in filenames:
                self._do_work(self._export_file_work, dirpath, f, loadedImages)

    # End the "export files" operation

    ################################################################################
    ####
    #### Geotag all files
    ####
    ################################################################################

    def _geotag_work(self, img, gpsFiles):
        wx.CallAfter(self._statusBar.SetStatusText, "Geotagging " + img["FileName"])
        geotag = None

        if img.dateTime is not None:
            for gpsFile in gpsFiles:
                geotag = gpsFile.match_time(img.dateTime)
                if geotag is not None:
                    break

        print(img["FileName"], "taken at", geotag)
        if geotag is not None:
            img.set_geotag(geotag)
            wx.CallAfter(self._images.update_image, img)
            img.save_changes()

    def OnGeotagAll(self, event):
        print("Geotag All")
        gpsFiles = []
        item, cookie = self._gpxTree.GetFirstChild(self._gpxRoot)
        while item.IsOk():
            tracks, n = self._gpxTree.GetItemData(item)
            gpsFiles.append(tracks.gpsFile)
            item, cookie = self._gpxTree.GetNextChild(self._gpxRoot, cookie)
        for img in self._images.iter_images():
            self._do_work(self._geotag_work, img, gpsFiles)

    # End the "geotag all files" operation

    def OnOptions(self, event):
        self._optionsDialog.ShowModal()

    def OnNewTrack(self, event):
        if not self._closing:
            for t in self._tracks:
                self._slipMap.RemoveTrack(t)
            self._tracks = []
            item = self._gpxTree.GetSelection()
            wrappedGpsFile, ns = self._gpxTree.GetItemData(item)
            tracks = []
            for n in ns:
                t = wrappedGpsFile.get_track(n)
                tracks.append(t)
            self._tracks += tracks
            region = reduce(lambda x, y: x + y.get_region(), tracks, slippy.Region())
            for t in tracks:
                self._slipMap.AddTrack(t)
            self._slipMap.ShowRegion(region)

    def OnImageSelected(self, img):
        print("Selected", img.get_filename())
        geotag = img.geotag
        if geotag is not None:
            m = slippy.Marker(img, geotag[0], geotag[1], movable=False)
            try:
                self._slipMap.RemoveMarker(self._markers[img])
            except KeyError:
                pass
            self._markers[img] = m
            self._slipMap.AddMarker(m)
            self._slipMap.CentreMap(geotag[0], geotag[1])

    def OnImageDeselected(self, img):
        print("Deselected", img.get_filename())
        try:
            self._slipMap.RemoveMarker(self._markers[img])
            del self._markers[img]
        except KeyError:
            pass

    def OnToggleFullScreen(self, event):
        self._fullscreen = not self._fullscreen
        self.ShowFullScreen(self._fullscreen, wx.FULLSCREEN_NOBORDER | wx.FULLSCREEN_NOCAPTION)

    def OnClose(self, event):
        self._closing = True
        # Kill the worker thread
        self._workerQueue.put((None, None, None))
        if self._workerThread.is_alive():
            self._workerThread.join()
        # Kill the import thread
        self._importQueue.put(None)
        if self._importThread.is_alive():
            self._importThread.join()
        # deinitialize the frame manager
        self._mgr.UnInit()
        # delete the frame
        self.Destroy()


def main():
    app = wx.App(False)
    frame = MyFrame(None)
    frame.Show()

    # Looks like this workaround is necessary to get this to work on windows
    if frame._fullscreen:
        frame.ShowFullScreen(True, wx.FULLSCREEN_NOBORDER | wx.FULLSCREEN_NOCAPTION)

    # print(wx.GetDisplaySize())
    app.MainLoop()


if __name__ == "__main__":
    main()
