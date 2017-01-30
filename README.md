# ComicStream: ToiletStreamer Edition

For now no mac or windows package! 

ComicStreamer ToiletStreamer Edition Windows Alplha (https://dl.dropboxusercontent.com/u/12474226/32/ComicStreamer%200.9.5.exe) with broken web settings so edit the settings manually! Will fix soon!
    (cache is also broken, probably old python package or windows xp)

## Help wanted
- front-end html/css could use some help
- webp support in webcomicbook reader used in the web reader

## Settings
Keep clicking on "tha brain" :-) Did I mention the fron-end help wanted :-)

## ToDo!

- MySQL support (I created a test data set and it chokes at more then 30.000 files with sqlite :-/)
- Find a good epub page to jpg converter for ebook support (pdf works great! better then any ebook reader)
- Fix some gui stuff (redirect with restarting & resetting)
- Added new db features...
- Create Windows & Mac packages
- Fix Cache did not work on xp :-/
- Test Test Test!

![screw](https://raw.githubusercontent.com/Tristan79/ComicStreamer/master/ad.png)

   
## Work done

Tristan79 Work on this fork (januari 28 2017)

- Fixed bug (appartently source didn't work for months)
- Added cbt/tar support
- Patched webp (it does not load in web comic book, haven't tested chunky so converted to jpeg :/)
- Experimental Cache System (since remote storage could be slow, even usb2 vs ssd :-)

Tristan79 Work on this fork (may 15 2016)

- Lot of bug fixes, 
- New (tryout gui) the old gui is still there for use
- Fixes for jpg, bmp, 7z, pdf & other bugfull stuff
- Added option to have alternative mobile site for android/ipad/etc...

If you have web development or graphic design skills, and would like to help out, please contact me at tristan@monkeycat.nl.




# OLD README.md

#### Work on this fork (september 5 2015)
 - added webroot option to configuration, useful for proxy pass configurations (issue #24)
 - little unrar automation: after pip installation, run `paver libunrar'
   to automatically fetch compile and install the unrar library.
 - now the scanning component ignores hidden (dot) files (issue #26)
 - added new logo from blindpet (issue #27)
 - upgraded to latest releases of various dependent packages
#### Work on this fork (april 5 2015)

 - refactoring database access in a Library object (see library branch)
 - fulltext indexing and faceting support using whoosh (see whoosh branch)
 - mobile optimized user interface based on angularjs and bootstrap. Designed
   to work with the new search api with facet support

All of these features are **experimental** and still unfinished.

-----
#### Introduction


ComicStreamer is a media server app for sharing a library of comic files via a simple REST API to client applications.
It allows for searching for comics based on a rich set of metadata including fields like series name, title, publisher,
story arcs, characters, and creator credits.  Client applications may access comics by entire archive file, or by fetching pag
e images, one at a time.

A web interface is available for searching and viewing comics files, and also for configuration, log viewing, and some control
operations.

It's best used on libraries that have been tagged internally with tools like [ComicTagger](http://code.google.com/p/comictagger/) or
[ComicRack](http://comicrack.cyolito.com/). However, even without tags, it will try to parse out some information from the filename
(usually series, issue number, and publication year).

ComicStreamer is very early ALPHA stages, and may be very flakey, eating up memory and CPU cycles. In particular, with very large datasets,
filters on the sub-lists (characters, credits, etc. ) can be slow.

[Chunky Comic Reader](http://chunkyreader.com/) for iPad has added experimental ComicStreamer support. Pro upgrade required, but it's well
worth it for the other features you get.  Check it out!  If you are comic reader developer (any platform), and would like to add CS support,
please contact me if you need any special support or features.

----------

#### Requirements (for running from source) 

* python 2.7

(via pip):

* tornado
* sqlalchemy >= 0.9
* watchdog
* python-dateutil
* pillow (PIL fork)
* configobj >= 5.0.5
* natsort

Optional:

* pybonjour (for automatic server discovery)


------
#### Installation

For source, just unzip somewhere.  For the binary packages, it's the usual drill for that platform.
(No setup.py yet, sorry)

Settings, database, and logs are kept in the user folder:

* On Linux: "~/.ComicStreamer"
* On Mac OS: "~/Library/Application Support/ComicStreamer"
* On Windows:  "%APPDATA%\ComicStreamer"

----------
#### Running

From the source, just run "comicstreamer" in the base folder (on windows you may want to rename it comicstreamer.py).

For the binary builds, run from the installed app icon.  There should be no taskbar/dock presence, but an icon should appear in the system tray
(windows), or status menu (mac).

A web browser should automatically open to "http://localhost:32500".  On your first run, use the "config" page to set the comic folders, and
the "control" page to restart the server.  It will start scanning, and all comics in the given folders and sub folders will be added to database.

Some tips:

* Use "--help" option to list command-line options
* Use the "--reset" option (CLI) or control page "Rebuild Database" to wipe the database if you're having problems.

