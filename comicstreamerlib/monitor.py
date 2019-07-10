#!/usr/bin/env python
import sys
import os
import hashlib
import md5
import mmap
import datetime
import time
import threading
import Queue
import logging
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
import watchdog

from comicapi.comicarchive import *
from comicapi.issuestring import *
import utils
import comicstreamerlib.utils

from database import *
from library import Library

class  MonitorEventHandler(watchdog.events.FileSystemEventHandler):
    
    def __init__(self, monitor):
        self.monitor = monitor
        self.ignore_directories = True
        
    def on_any_event(self,event):
        if event.is_directory:
            return
        self.monitor.handleSingleEvent(event)


class Monitor():
        
    def __init__(self, dm, paths):
        
        self.dm = dm
        self.style = MetaDataStyle.CIX
        self.queue = Queue.Queue(0)
        self.paths = paths
        self.eventList = []
        self.mutex = threading.Lock()
        self.eventProcessingTimer = None
        self.quit_when_done = False  # for debugging/testing
        self.status = "IDLE"
        self.statusdetail = ""
        self.scancomplete_ts = ""

    def start(self):
        self.thread = threading.Thread(target=self.mainLoop)
        self.thread.daemon = True
        self.quit = False
        self.thread.start()


    def stop(self):
        self.observer.stop()
        self.observer.join()
        self.quit = True
        self.thread.join()

    def mainLoop(self):

        logging.debug("Monitor: Started")

        for l in self.paths:
            logging.info(u"Monitor: Scanning '"+l+"'")

        self.session = self.dm.Session
        self.library = Library(self.session)
        self.observer = Observer()
        self.eventHandler = MonitorEventHandler(self)
        self.status = u"INDEXING"
        for path in self.paths:
            if os.path.exists(path):
                self.setStatusDetail(u"Watchdog (BUG?)")
                logging.info("Monitor: Watchdog: Indexing")
                
                # if I make this threaded? then it does not wait???
                self.observer.schedule(self.eventHandler, path, recursive=True)
                logging.debug("Monitor: Watchdog: Stopped Indexing")
        self.observer.start()
        while True:
            try:
                (msg, args) = self.queue.get(block=True, timeout=1)
            except:
                msg = None
                
            #dispatch messages
            if msg == "scan":
                self.dofullScan(self.paths)

            if msg == "events":
                self.doEventProcessing(args)
            
            #time.sleep(1)
            if self.quit:
                break
    
        self.session.close()
        self.session = None
        self.observer.stop()
        self.observer.join()
        logging.debug("Monitor: Stopped")
        
    def scan(self):
        self.queue.put(("scan", None))
    
    def handleSingleEvent(self, event):
        # events may happen in clumps.  start a timer
        # to defer processing.  if the timer is already going,
        # it will be canceled
        
        # in the future there can be more smarts about
        # granular file events.  for now this will be
        # good enough to just get a a trigger that *something*
        # changed
        
        self.mutex.acquire()
        if self.eventProcessingTimer is not None:
            self.eventProcessingTimer.cancel()
        self.eventProcessingTimer = threading.Timer(30, self.handleEventProcessing)
        self.eventProcessingTimer.start()
        
        self.mutex.release()
    
    def handleEventProcessing(self):
        
        # trigger a full rescan
        self.mutex.acquire()
        
        self.scan()
        
        # remove the timer
        if self.eventProcessing is not None:
            self.eventProcessingTimer = None
            
        self.mutex.release()

    """
    def checkIfRemovedOrModified(self, comic, pathlist):
        remove = False
        
        def inFolderlist(filepath, pathlist):
            for p in pathlist:
                if p in filepath:
                    return True
            return False
        
        if not (os.path.exists(comic.path)):
            # file is missing, remove it from the comic table, add it to deleted table
            self.setStatusDetail(u"Updating")
            logging.debug(u"Monitor: Flushing Missing {0}".format(comic.path))
            remove = True
        elif not inFolderlist(comic.path, pathlist):
            self.setStatusDetail(u"Updating")
            logging.debug(u"Monitor: Flushing Unwanted {0}".format(comic.path))
            remove = True
        else:
            # file exists.  check the mod date.
            # if it's been modified, remove it, and it'll be re-added
            #curr = datetime.datetime.fromtimestamp(os.path.getmtime(comic.path))
            curr = datetime.utcfromtimestamp(getmtime(comic.path))
            prev = comic.mod_ts
            if curr != prev:
                self.setStatusDetail(u"Updating")
                logging.debug(u"Monitor: Flushing Modifed {0}".format(comic.path))
                remove = True
           
        return remove
    """

    def getComicMetadata(self, path):
        logging.debug(u"Monitor: Scanning File {0} {1}\r".format(self.read_count, path))
        self.read_count += 1
        sys.stdout.flush()
        return self.library.getComicMetadata(path)
    


    def setStatusDetail(self, detail, level=logging.DEBUG):
        self.statusdetail = detail
        if level == logging.DEBUG:
            logging.debug("Monitor: "+detail)
        else:
            logging.info("Monitor: "+detail)

    def setStatusDetailOnly(self, detail):
        self.statusdetail = detail
            
    def commitMetadataList(self, md_list):
        comics = []
        for md in md_list:
            self.add_count += 1
            comic = self.library.createComicFromMetadata(md)
            comics.append(comic)
            if self.quit:
                self.setStatusDetail(u"Monitor: Stopped")
                return
        for i in comics:
            self.library.checkBlacklist(i)
            if self.quit:
                self.setStatusDetail(u"Monitor: Stopped")
                return
        self.library.addComics(comics)
    
    def getRecursiveFilelist(self, dirs):
        filename_encoding = sys.getfilesystemencoding()
        filelist = []
        index = 0
        for p in dirs:
            # if path is a folder, walk it recursivly, and all files underneath
            if type(p) == str:
                #make sure string is unicode
                p = p.decode(filename_encoding) #, 'replace')
            elif type(p) != unicode:
                #it's probably a QString
                p = unicode(p)
            if os.path.isdir( p ):
                for root,dirs,files in os.walk( p ):
                                # issue #26: try to exclude hidden files and dirs
                    files = [f for f in files if not f[0] == '.']
                    dirs[:] = [d for d in dirs if not d[0] == '.']
                    for f in files:
                        if type(f) == str:
                                                #make sure string is unicode
                            f = f.decode(filename_encoding, 'replace')
                        elif type(f) != unicode:
                                                    #it's probably a QString
                            f = unicode(f)
                        filelist.append(os.path.join(root,f))
                        if self.quit:
                            return filelist
            else:
                self.setStatusDetailOnly(u"Monitor: {0} Files Indexed".format(index))
                index = index + 1
                filelist.append(p)
            
        return filelist
  
    def createAddRemoveLists(self, dirs):
        ix = {}
        db_set = set()
        current_set = set()
        self.dbfiles = len(db_set)
        filelist = self.getRecursiveFilelist(dirs)
        if self.quit:
            return [],[]
        for path in filelist:
            try:
                current_set.add((path, datetime.utcfromtimestamp(os.path.getmtime(path))))
            except:
                logging.debug(u"Monitor: Failed To Access '{0}'".format(path))
                filelist.remove(path)
            
        logging.debug(u"Monitor: %d Files Found " % len(current_set))
        try:
            for comic_id, path, md_ts in self.library.getComicPaths():
                db_set.add((path, md_ts))
                ix[path] = comic_id
                if self.quit:
                    return [],[]
        except:
            logging.debug(u"Monitor: Failed To Access '{0}'".format(path))
        to_add = current_set - db_set
        to_remove = db_set - current_set
        logging.debug(u"Monitor: %d Files In Library " % len(db_set))
        logging.debug(u"Monitor: %d Files To Remove" % len(to_remove))
        logging.info(u"Monitor: %d Files To Scan" % len(to_add))


        return [r[0] for r in to_add], [ix[r[0]] for r in to_remove]

    def dofullScan(self, dirs):

        self.status = u"CHECKING"

        self.setStatusDetailOnly(u"Files")

        self.add_count = 0      
        self.remove_count = 0

        filelist, to_remove = self.createAddRemoveLists(dirs)
        if self.quit:
            self.status = u"QUITING"
            self.setStatusDetailOnly(u"")
            return

        self.setStatusDetail(u"Removing {0} Files".format(len(to_remove)))
        if len(to_remove) > 0:
            self.library.deleteComics(to_remove)

        self.setStatusDetail(u"Scanning {0} Files".format(len(filelist)))
        self.status = u"SCANNING"
        md_list = []
        self.read_count = 0
        commitlength = 10
        for filename in filelist:
        
            md = self.getComicMetadata(filename)
            if md is not None:
                md_list.append(md)
            self.setStatusDetailOnly(u"File {0}/{1} Found {2}".format(len(filelist), self.read_count,self.add_count))
            if self.quit:
                self.status = u"QUITING"
                self.setStatusDetailOnly(u"")
                return
            
            #every so often, commit to DB
            if self.read_count % commitlength == 0 and self.read_count != 0:
                if len(md_list) > 0:
                    self.commitMetadataList(md_list)
                    md_list = []
                commitlength = 200
        
        if len(md_list) > 0:
            self.commitMetadataList(md_list)
        
        self.setStatusDetail(u"Metadata {0}/{1} Files".format(self.read_count,len(filelist)))

 
        
        self.status = u"IDLE"
        self.statusdetail = ""
        self.scancomplete_ts = int(time.mktime(datetime.utcnow().timetuple()) * 1000)
        
        logging.info(u"Monitor: Added {0} Files".format(self.add_count))
        logging.info(u"Monitor: Removed {0} Files".format(self.remove_count))
            
        if self.quit_when_done:
            self.quit = True

    """
    def doEventProcessing(self, eventList):
        logging.debug(u"Monitor: event_list:{0}".format(eventList))
    """
        
if __name__ == '__main__':
    
    if len(sys.argv) < 2:
        print >> sys.stderr, u"usage:  {0} comic_folder ".format(sys.argv[0])
        sys.exit(-1)    

    
    utils.fix_output_encoding()
    
    dm = DataManager()
    dm.create()
    m = Monitor(dm, sys.argv[1:])
    m.quit_when_done = True
    m.start()
    m.scan()

    #while True:
    #   time.sleep(10)

    m.stop()
