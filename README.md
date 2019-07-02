# ComicStream: ComicStreamer Edition Alpha

Improved ComicStreamer!

Note: this is my personal working branch... for my Mac, I could break stuff at any time! Add hacked-in mac tested features...
If something is not working __fork it, fix it, pull request it!__ (or use the original fork :-/ :-)

With CBT, CB7 support, new alpha interface, crude caching system, and a lot of bug fixes

__Experimental__

MySQL support, static library only

PDF, EPUB, MOBI, AZW3, FB2, LIT, DJVU, CHM Support through calibre's ebook-convert and mupdf's mudraw and qpdf

WebComic support CBW (Hack version)... I got it to display and download CtrlAltDel :-) Currently rewritting the hack to something proper...


## Help wanted (fork it pull request it!)
There is something missing... yes! 

_Are you are a database wizard..._

-  __MySQL support__ you can not delete commics... (good for static libs if not for the previous point)

_... or are you a web magician and able to fix the build in html webcomicbooks reader..._

- webp support
- page chooser (slider and/or page number selection?)

_...Or general web page_
- Add link to result tables to the entity browser in popup
- secondary sort on table (e.g. date/year then issue)
- Fix setup stuff (redirect with restarting & resetting)


Please help!

Did I say I got stuck for a year now on MySQL and SQLAlchemy...

![screw](https://raw.githubusercontent.com/Tristan79/ComicStreamer/master/ad.png)
   
## Work done

- Made the web hyperlinked (well somewhat)... i am missing alternative serie title... :-/ o well

Tristan79 Work on this fork (januari 31 -february 12 2017)

- EBook support (basic metadata support)
- Much better (faster) random comic query
- MySQL support (experimental, no modify!) 
- Fixed bug (appartently source didn't work for months)
- Page blocker
- Added cbt/tar/webp support
- Comex was disabled, enabled!
- Patched webp (it does not load in web comic book, haven't tested chunky so converted to jpeg :/)
- Experimental Cache System (since remote storage could be slow, even usb2 vs ssd :-)
- Fixed a lot of gui bugs.
- Fixed pdf
- Fixed command line

pre alpha support for
- blacklisting
- comic identification (for finding doubles)
- favorites
- multiuser
- wake up media already when server comes out of idle to minimize wait time

Tristan79 Work on this fork (may 15 2016)

- Lot of bug fixes, 
- New (tryout gui) the old gui is still there for use
- Fixes for jpg, bmp, 7z, pdf & other bugfull stuff
- Added option to have alternative mobile site for android/ipad/etc...

If you have web development or graphic design skills, and would like to help out, please contact me at tristan@monkeycat.nl.

## Further ToDo! / Help Wanted!

Web Page
- search result not limited to 10/20../100 
- publisher with special chars in name not recognized in entity browser
- Remove showing null comics in table
- Log should be automaticlly updated
- setup redirect with first run

Database
- Other databases backend support
- Faster (or better database, __sqlalchemy wizard help needed!!!__)
- New db features...
- Very large dataset sqlite will bump into locked db file

General
- Find a good epub page to png/jpg converter for ebook support (pdf works great! better then any ebook reader)
- OSX Calibre works... in remark to previous line :-) so other options/settings/windows?
- ebook caching (now it does not delete)
- Folder with images add as comic
- Create Windows & Mac packages
- Fix Cache did not work on xp :-/ (missing webp?)
- Broke monitor (check!)
- seven zip does not work on newer files not even with the github bug fixed version
- Show unscanned/error files!
- Server won't shutdown if monitor is still checking files...
- SWF support??
- PDF and Calibre converters location not working (hardcoded)
- Better cache system with preloading
- Folder list will disappear after error reading it...

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

