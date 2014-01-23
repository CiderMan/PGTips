PGTips: Photograph GeoTagger
============================

Application to import, losslessly rotate, geotag and file photographs or any combination of the above.

*** Please note: this is immature software. Use at your own risk and, in particular, ensure that it has not damaged the copies of your files before deleting the originals ***

This application is in very early alpha at this stage. I have worked on it on-and-off for several years but it is still a long way from feature complete. However, it now supports my primary use-case so I've made it available publicly in case that is of use for others.

The primary use-case is:
* "Import" (that is, copy to a working directory) all photos (and other files, e.g. video) from a directory hierarchy (which is the SD card from my digital camera).
* Any JPEGs are losslessly rotated according to their orientation flag.
* Load a number of GPS tracks
* Set the geotag for those images that were taken at a time covered by one of the loaded GPS tracks
* "Export" the files to a user-defined directory structure based on the time that the photo was taken, e.g. .../2013/2013_12/2013_12_25/IMG0001.jpg

The two differentiating features of this application are:

1) It is platform independent. While predominantly developed under Linux, I also use it under Windows. There is no fundamental reason why it shouldn't also run under MacOS but I have no means of testing it.

2) The map pane caches the map tiles off-line. It does not allow you to download an area at different zoom levels automatically (since this would violate the terms-of-use of pretty much every service that I looked at) but, provided you have viewed the tiles at some point, they will subsequently be available off-line.

Depedencies
-----------

I've tried to keep the dependencies as few as possible.
* The application is written in Python - developed using 2.7 but I have briefly run it with 2.6 and didn't hit any problems.
* It uses the wxPython GUI framework, so you will need to have that too.
* It uses the fantastic EXIFTool for image EXIF querying and setting.

It also has the following optional dependencies:
* To support lossless rotation of JPEG images, you will need the jpegtran and jpegexiforient executables.

That's it!

For Ubuntu (and similar Linux distros), you probably need something like the following packages: python2.7, python-wxgtk2.8, libimage-exiftool-perl and libjpeg-turbo-progs.

For Windows, you should be able to find the applications that you need from the follwoing links:
* Python: http://www.python.org/download/
* wxPython: http://www.wxpython.org/download.php
* EXIFTool: http://www.sno.phy.queensu.ca/~phil/exiftool/ (Note that the downloaded executable needs to be renamed to exiftool.exe for PGTips to use it)
* jpegtran: http://jpegclub.org/jpegtran/
* jpegexiforient: https://github.com/CiderMan/jpegexiforient

Running it
----------

Once you have the dependencies installed, clone the repository and run pgtips.py. You will probably want to go to Tools->Options and configure a few things, including the working and export directories, the file extensions to process and the paths to exiftool and jpegtran (if they are not in your path).

* To import files into your working directory, use File->Import files...
* File->Load GPS files will do what the option says, though note that only GPX and TCX files are currently supported.
* Geotag->Geotag all images will determine the geotag for an image and write it to the EXIF data - overwriting any existing geotag.
* File->Export files will export the files in the working directory to a directory structure (based on when the photo was taken) of your choosing.

There are lots of incomplete, ir even completely missing, features - not to mention bugs. Please feel free to raise any of these as issues... epecially if you want to help implement or fix them!

*** Please note: this is immature software. Use at your own risk and, in particular, ensure that it has not damaged the copies of your files before deleting the originals ***

