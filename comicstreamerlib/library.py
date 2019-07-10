"""Encapsulates all data acces code to maintain the comic library"""
from datetime import datetime
import dateutil
import os
import random
import datetime

import logging
import StringIO

from PIL import Image
try:
    from PIL import WebPImagePlugin
except:
    pass

from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

from sqlalchemy import func, distinct
from sqlalchemy.orm import subqueryload
from sqlalchemy import func
from sqlalchemy.sql import label
import shutil
import utils
from database import Comic, Blacklist, DatabaseInfo, Person, Role, Credit, Character, GenericTag, Team, Location, \
    StoryArc, Genre, DeletedComic, AlternateSeries
from folders import AppFolders
from sqlalchemy.orm import load_only

from config import ComicStreamerConfig
from comicapi.comicarchive import ComicArchive
from comicapi.comicarchive import *

from comicapi.issuestring import IssueString


def getmtime(file_):
    try:
        res = os.path.getmtime(file_)
        return res
    except:
        return time.time()
        
class Library:

    def __init__(self, session_getter):
        self.getSession = session_getter
        self.comicArchiveList = []
        self.namedEntities = {}
        self.hashEntities = {}
        self.cache_active = False
        self.double = 0
        self.simular = 0
        


    def lastpage_extractor_for_blacklist(self):
        print "Extract Last Pages"
        query = self.getSession.query(Comic)
        x = os.path.join(AppFolders.appBlacklistPages(),"lastpage")
        y = os.path.join(AppFolders.appBlacklistPages(),"lastpage_double")
        z = os.path.join(AppFolders.appBlacklistPages(),"firstpage")
        w = os.path.join(AppFolders.appBlacklistPages(),"firstpage_double")
        if not os.path.isdir(x):
            os.makedirs(x)
        if not os.path.isdir(y):
            os.makedirs(y)
        if not os.path.isdir(z):
            os.makedirs(z)
        if not os.path.isdir(w):
            os.makedirs(w)
        c = 0
        for row in query:
            print('Extracting last page from ' + str(c) + ' '  + row.path)
            c += 1
            ca = self.getComicArchive(row.id,row.path)
            # auto convert webp (disable for chunky or fix web book reader)
            image_data = ca.getPage(row.page_count-1)
            hash = utils.hash(image_data)
            
            # ascept ratio check
            #im = Image.open(StringIO.StringIO(image_data))
            #w,h = im.size
            #if h > w:
            #    continue
            
            
            image_cover = ca.getPage(0)
            image_page2 = ca.getPage(1)
            if image_page2:
                imc = Image.open(StringIO.StringIO(image_cover))
                hash2 = utils.hash(image_cover)
                im2 = Image.open(StringIO.StringIO(image_page2))
                w1,h1 = imc.size
                w2,h2 = im2.size
                if h1 <= w1 and h2 > w2 and not self.checkHashBlacklist(hash2):
                    if os.path.isfile(os.path.join(z,str(hash2))):
                        if os.path.isfile(os.path.join(w,str(hash2))):
                            print "Double Already Exists"
                        else:
                            print "Adding Double"
                            file2 = open(os.path.join(w,str(hash2)), "w")
                            file2.write(image_cover)
                            file2.close()
                    else:
                        print "Adding Firstpage"
                        file2 = open(os.path.join(z,str(hash2)), "w")
                        #file2.write("1")
                        file2.write(image_cover)
                        file2.close()


            
            
                    """
            
            if self.checkHashBlacklist(hash):
                continue
            if os.path.isfile(os.path.join(x,str(hash))):
                if os.path.isfile(os.path.join(y,str(hash))):
                    print "Double Already Exists"
                    continue
                else:
                    print "Adding Double"
                    file = open(os.path.join(y,str(hash)), "w")
                    file.write(image_data)
            else:
                print "Adding Lastpage"
                file = open(os.path.join(x,str(hash)), "w")
                #file.write("1")
                file.write(image_data)
            file.close()
                    """

    def createBlacklistFromFolder(self,file):
        # loop over files in blacklist folder
        # and save them to a file with \n seperated
        # untested
        for root, dirs, filenames in os.walk(AppFolders.appBlacklistPages()):
            for f in filenames:
                with open(file) as f:
                    f.write(str(f)+str(os.stat(file).st_size)+'\n')


    def comicUnBlacklist(self,comic_id):
        pass
 
    def checkBlacklist(self,comic):
        pass
        
    def checkHashBlacklist(self,hash):
        if hash is None:
            return False
        
        obj = self.getSession().query(Blacklist.hash).filter(Blacklist.hash == hash).first()
        if obj is  None:
            return False
        else:
            return True

    

    def getHashEntity(self, cls, hash):
        """Gets related entities such as Characters, Persons etc by name"""
        # this is a bit hackish, we need unique instances between successive
        # calls for newly created entities, to avoid unique violations at flush time
        key = (cls, hash)
        if key not in self.hashEntities.keys():
            obj = self.getSession().query(cls).filter(cls.hash == hash).first()
            self.hashEntities[key] = obj
            if obj is None:
                self.hashEntities[key] = cls(hash=hash)
        return self.hashEntities[key]


    
    
    def comicBlacklist(self,comic_id, pagenum):
        #obj = session.query(database.Blacklist).filter(database.Blacklist.comic_id == int(comic_id),database.Blacklist.page == int(pagenum)).first()
         #       if obj is None:
        
        session = self.getSession()
        
        #self.getComic()
        #x = self.getSession().query(Comic.id, Comic.path, Comic.mod_ts)

        image_data = self.getComicPage(comic_id, pagenum, False)
        hash = utils.hash(image_data)

        #comichash = self.getHashEntity(Blacklist, hash)
        #self.getComic(comic_id).blacklist(comichash)
        
        obj = self.getSession().query(Blacklist.hash).filter(Blacklist.hash == hash).first()
        if obj is None:
            try:
                blacklist = Blacklist()
                blacklist.hash = hash
                blacklist.detect = len(image_data)
                
                file = open(os.path.join(AppFolders.appBlacklistPages(),str(blacklist.hash)), "w")
                file.write(image_data)
                file.close()
                
                #blacklist.comic_id = int(comic_id)
                #blacklist.page = int(pagenum)
                blacklist.ts = datetime.utcnow()
                session.add(blacklist)
                session.commit()
                session.close()
            except Exception, e:
                print str(e)
                logging.error("Blacklist: Problem blocking page {} on comic {}".format(pagenum, comic_id))
        self.cache_delete_page(comic_id, pagenum)

    def loadBlacklistFromFile(self,file):
        with open(file) as f:
            lines = f.readlines()
        blacklist = []
        blfile = []
        detectlist = []
        for line in lines:
            blacklist += [line[:72]]
            try:
                detectlist += [int(line[72:])]
            except:
                detectlist += [-1]
            blfile += [(blacklist[-1],detectlist[-1])]
        session = self.getSession()
        obj = session.query(Blacklist.hash).all()
        if obj is not None:
            l = []
            for i in obj:
                l += [i[0]]

        for i in blfile:
            if i[0] not in l:
                bl = Blacklist()
                bl.hash = i[0]
                bl.detect = i[1]
                bl.ts = datetime.utcnow()
                session.add(bl)
        
        session.commit()
        session.close()
        logging.info("Blacklist: Loaded " + file)
    
    def isBlacklist(self,image, hash=None):
        if hash is None:
            hash = utils.hash(image)
        
        # should be replaced with database query...
        
        obj = self.getSession().query(Blacklist.hash).filter(Blacklist.hash == hash).first()
        if obj is not None:
            with open(AppFolders.missingPath("blacklist.png"), 'rb') as fd:
                image_data = fd.read()
            return image_data
        else:
            return image


    def cache_clear(self):
        if os.path.exists(self.cache_location) and os.path.isdir(self.cache_location):
            shutil.rmtree(self.cache_location)
        self.cache_filled = 0
        self.cache_list = []
        self.cache_hit = 0
        self.cache_miss = 0
        self.cache_discard = 0
    
    def cache(self,location,active,size,free):
        self.cache_active = active
        self.cache_size = size
        self.cache_free = free
        self.cache_filled = 0
        self.cache_list = []
        self.cache_hit = 0
        self.cache_miss = 0
        self.cache_discard = 0
        self.cache_maxsize = size
        self.cache_location = location
        
        self.cache_location = os.path.join(self.cache_location,ComicStreamerConfig()['database']['engine'])
        
        try:
            if not os.path.exists(self.cache_location):
                os.makedirs(self.cache_location)
        except:
            self.cache_active = False;
        
        for subdir, dirs, files in os.walk(self.cache_location):
            # why is this here?
            if os.path.split(subdir)[-1] == 'cache': continue
            for file in files:
                cachefile = os.path.join(subdir, file)
                cache_file_size = utils.file_size_bytes(cachefile)
                #print (os.path.split(subdir)[-1])
                #print file
                self.cache_list += [(os.path.split(subdir)[-1],file,cache_file_size,os.path.getmtime(cachefile))]
                self.cache_filled += cache_file_size

        self.cache_list = sorted(self.cache_list, key = lambda x: int(x[3]))
        
        cache_free_size = utils.get_free_space(self.cache_location)
        self.cache_maxsize = cache_free_size - self.cache_free*1048576 - self.cache_filled
        if self.cache_maxsize < 0:
            self.cache_maxsize += self.cache_delete(abs(self.cache_maxsize))
            if self.cache_maxsize < 0:
                self.cache_maxsize = 0
        if self.cache_size > 0 and self.cache_maxsize > self.cache_size*1048576:
                self.cache_maxsize = self.cache_size
        else:
            self.cache_maxsize = (self.cache_maxsize + self.cache_filled) / 1048576
    
        """
        print "Cache: " + str(self.cache_active)
        if self.cache_size == 0:
            print "Size: Fill"
        else:
            print "Size: " + str(self.cache_size) + "mb"
        print "Free: " + str(self.cache_free) + "mb"
        print "Free FS: " + str(utils.get_free_space(self.cache_location)/1024/1024) + "mb"
        print "Filled: " + str(self.cache_filled/1024/1024) + "mb"
        print "Files: " + str(len(self.cache_list))
        print "Remaining: " + str(cache_free_size/1024/1024) + "mb"
        """

    def cache_delete(self, size):
        #print "delete: " + str(size)
        deleted = 0
        while size - deleted > 0:
            if self.cache_list == []:
                return deleted
            x = self.cache_list[0]
            #print "remove:" + os.path.join(self.cache_location,x[0],x[1])
            os.remove(os.path.join(self.cache_location,x[0],x[1]))
            self.cache_filled -= x[2]
            deleted += x[2]
            self.cache_discard += 1
            self.cache_list.pop(0)
        return deleted

    def cache_delete_page(self, comic_id, page_number, path):
        pass

    def cache_load(self, comic_id, page_number, path):
        if self.cache_active:
            cachepath = self.cache_location + "/" + comic_id + "/"
            cachefile = cachepath + str(page_number)
            if not os.path.exists(cachepath):
                os.makedirs(cachepath)
            if not os.path.isfile(cachefile):
                ca = self.getComicArchive(comic_id,path)
                image = self.isBlacklist(ca.getPage(int(page_number)))
                
                # auto convert webp (disable for chunky or fix web book reader)
                image = utils.webp_patch_convert(image)

                cache_file_size = len(image)
                
                cache_free_size = utils.get_free_space(self.cache_location)
                x = cache_free_size - self.cache_free*1048576 - self.cache_filled
                
                if x < 0:
                    cache_free_size += self.cache_delete(abs(x))
                
                deleted = 0
                if self.cache_size > 0 and self.cache_filled + cache_file_size > self.cache_size*1048576:
                    deleted = self.cache_delete(cache_file_size)
                    cache_free_size += deleted
                else:
                    deleted = cache_file_size
                
                self.cache_maxsize = cache_free_size - self.cache_free*1048576 - self.cache_filled
                if self.cache_maxsize < 0:
                    self.cache_maxsize = 0
                if self.cache_size > 0 and self.cache_maxsize > self.cache_size*1048576:
                        self.cache_maxsize = self.cache_size
                else:
                    self.cache_maxsize = (self.cache_maxsize + self.cache_filled) / 1048576
            
                
                self.cache_miss += 1
                if cache_file_size <= deleted:
                    try:
                        file = open(cachefile, "w")
                        file.write(image)
                        file.close()
                        self.cache_filled += cache_file_size
                        self.cache_list += [(comic_id,page_number,cache_file_size,os.path.getmtime(cachefile))]
                    except:
                        # logging would be better...
                        print "Could not write to cache: " + cachefile
                
                # DEBUG
                """
                if self.cache_size == 0:
                    print "Size: Fill"
                else:
                    print "Size: " + str(self.cache_size) + "mb"
                print "Free: " + str(self.cache_free) + "mb"
                print "Free FS: " + str(utils.get_free_space(self.cache_location)/1024/1024) + "mb"
                print "Filled: " + str(self.cache_filled/1024/1024) + "mb"
                print "Files: " + str(len(self.cache_list))
                print "Remaining: " + str(x/1024/1024) + "mb"
                """
            else:
                file = open(cachefile, "r")
                image = file.read()
                self.cache_hit += 1
                # DEBUG
                #print "Hit"
        else:
            ca = self.getComicArchive(comic_id,path)
            # auto convert webp (disable for chunky or fix web book reader)
            image = utils.webp_patch_convert(self.isBlacklist(ca.getPage(int(page_number))))

        return image

    def getSession(self):
        """SQLAlchemy session"""
        #pass
        return self.getSession



    def getComicThumbnail(self, comic_fingerprint):
        
                filename = comic_fingerprint+".png"
                foldername = filename[0]
                folderpath = AppFolders.appThumbPath(foldername, filename)
                with open(folderpath, 'rb') as fd:
                    thumbnail = fd.read()
                    self.write(thumbnail.getvalue())

                
                
    def getComic(self, comic_id):
        return self.getSession().query(Comic).get(int(comic_id))
    
    def getComicPage(self, comic_id, page_number, cache = True, max_height = None):
        (path, page_count) = self.getSession().query(Comic.path, Comic.page_count) \
                                .filter(Comic.id == int(comic_id)).first()

        image_data = None
        default_img_file = AppFolders.missingPath("page.png")
        
        if path is not None:
            if int(page_number) < page_count:
                if cache:
                    image_data = self.cache_load(comic_id,page_number,path)
                else:
                    ca = self.getComicArchive(comic_id,path)
                    # auto convert webp (disable for chunky or fix web book reader)
                    image_data = utils.webp_patch_convert(self.isBlacklist(ca.getPage(int(page_number))))
                    
        if image_data is None:
            with open(default_img_file, 'rb') as fd:
                image_data = fd.read()
            return image_data

        # resize image
        if max_height is not None:
            try:
                image_data = utils.resizeImage(int(max_height), image_data)
            except Exception as e:
                #logging.error(e)
                pass
                
        return image_data

    def getStats(self):
        stats = {}
        session = self.getSession()
        stats['total'] = session.query(Comic).count()

        dbinfo = session.query(DatabaseInfo).first()
        stats['uuid'] = dbinfo.uuid
        stats['last_updated'] = dbinfo.last_updated
        stats['created'] = dbinfo.created

        stats['series'] = session.query(func.count(distinct(Comic.series))).scalar()
        stats['persons'] = session.query(Person).count()

        return stats

    def getComicPaths(self):
        return self.getSession().query(Comic.id, Comic.path, Comic.mod_ts).all()
        
    def publishers(self):
        return self.getSession().query(Comic.publisher, Comic.imprint).group_by(Comic.publisher).all()
    
    def seriesByPublisher(self, string = ''):
        print "lets get: " + string
        return self.getSession().query(Comic.series, func.min(Comic.issue).label("issue"), Comic.id, Comic.fingerprint, Comic.publisher, Comic.volume)\
            .filter(Comic.publisher == string)\
            .group_by(Comic.series).order_by(Comic.series).all()
    
    def recentlyAddedComics(self, limit = 10):
        return self.getSession().query(Comic)\
            .order_by(Comic.added_ts.desc())\
            .limit(limit)

    def recentlyReadComics(self, limit = 10):
        return self.getSession().query(Comic)\
            .filter(Comic.lastread_ts != "")\
            .order_by(Comic.lastread_ts.desc())\
            .limit(limit)

    def getRoles(self):
        return self.getSession().query(Role).all()

    def randomComic(self):
        
        rowCount = int(self.getSession().query(Comic).count())
        randomRow = self.getSession().query(Comic).options(load_only(Comic.id)).offset(int(rowCount*random.random())).limit(1).first()
        return randomRow

        # probably wrong with deleted ids...
        #rand = random.randrange(0, self.getSession().query(Comic).count())
        #row = self.getSession().query(Comic)[rand]
        #return row
        
        # SQLite specific random call
        #return self.getSession().query(Comic)\
        #    .order_by(func.random()).limit(1).first()

    def getDeletedComics(self, since=None):
        # get all deleted comics first
        session = self.getSession()
        resultset = session.query(DeletedComic)

        # now winnow it down with timestampe, if requested
        if since is not None:
            try:
                dt = dateutil.parser.parse(since)
                resultset = resultset.filter(DeletedComic.ts >= dt)
            except:
                pass
        return resultset.all()

    def createComicFromMetadata(self, md):
        """
        Translate the metadata to actual DB data!
        """

        comic = Comic()
        # store full path, and filename and folder separately, for search efficiency,
        # at the cost of redundant storage
        comic.folder, comic.file = os.path.split(md.path)
        comic.path = md.path

        comic.page_count = md.page_count
        comic.mod_ts = md.mod_ts
        comic.hash = md.hash
        comic.filesize = md.filesize
        comic.fingerprint = md.fingerprint

        if not md.isEmpty:
            if md.series is not None:
                comic.series = unicode(md.series)
            if md.issue is not None:
                comic.issue = unicode(md.issue)
                comic.issue_num = IssueString(unicode(comic.issue)).asFloat()

            if md.alternateNumber is not None:
                comic.alternateIssue = unicode(md.alternateNumber)
                comic.alternateNumber = IssueString(unicode(comic.alternateIssue)).asFloat()
            if md.year is not None:
                try:
                    day = 1
                    month = 1
                    if md.month is not None:
                        month = int(md.month)
                    if md.day is not None:
                        day = int(md.day)
                    year = int(md.year)
                    comic.date = datetime(year, month, day)
                except:
                    pass

            comic.year = md.year
            comic.month = md.month
            comic.day = md.day

            if md.volume is not None:
                comic.volume = int(md.volume)
            if md.publisher is not None:
                comic.publisher = unicode(md.publisher)
            if md.language is not None:
                comic.language = unicode(md.language)
            if md.title is not None:
                comic.title = unicode(md.title)
            if md.comments is not None:
                comic.comments = unicode(md.comments)
            if md.imprint is not None:
                comic.imprint = unicode(md.imprint)
            if md.webLink is not None:
                comic.weblink = unicode(md.webLink)

        if md.characters is not None:
            for c in list(set(md.characters.split(","))):
                character = self.getNamedEntity(Character, c.strip())
                comic.characters_raw.append(character)

        if md.teams is not None:
            for t in list(set(md.teams.split(","))):
                team = self.getNamedEntity(Team, t.strip())
                comic.teams_raw.append(team)

        if md.locations is not None:
            for l in list(set(md.locations.split(","))):
                location = self.getNamedEntity(Location, l.strip())
                comic.locations_raw.append(location)

        if md.alternateSeries is not None:
                for alt in list(set(md.alternateSeries.split(","))):
                    alternateseries = self.getNamedEntity(AlternateSeries, alt.strip())
                    comic.alternateseries_raw.append(alternateseries)

        if md.storyArc is not None:
            for sa in list(set(md.storyArc.split(","))):
                storyarc = self.getNamedEntity(StoryArc, sa.strip())
                comic.storyarcs_raw.append(storyarc)

        if md.genre is not None:
            for g in list(set(md.genre.split(","))):
                genre = self.getNamedEntity(Genre,  g.strip())
                comic.genres_raw.append(genre)

        if md.tags is not None:
            for gt in list(set(md.tags)):
                generictag = self.getNamedEntity(GenericTag,  gt.strip())
                comic.generictags_raw.append(generictag)

        if md.credits is not None:
            for credit in md.credits:
                role = self.getNamedEntity(Role, credit['role'].lower().strip())
                person = self.getNamedEntity(Person, credit['person'].strip())
                comic.credits_raw.append(Credit(person, role))
                
        return comic

    def getNamedEntity(self, cls, name):
        """Gets related entities such as Characters, Persons etc by name"""
        # this is a bit hackish, we need unique instances between successive
        # calls for newly created entities, to avoid unique violations at flush time
        key = (cls, name)
        if key not in self.namedEntities.keys():
            obj = self.getSession().query(cls).filter(cls.name == name).first()
            self.namedEntities[key] = obj
            if obj is None:
                self.namedEntities[key] = cls(name=name)
        return self.namedEntities[key]


    def getComicMetadata(self, path):
        ca = ComicArchive(path,  default_image_path=AppFolders.missingPath("page.png"))

        
        if ca.seemsToBeAComicArchive():

            if ca.hasMetadata( MetaDataStyle.CIX ):
                style = MetaDataStyle.CIX
            elif ca.hasMetadata( MetaDataStyle.CBI ):
                style = MetaDataStyle.CBI
            elif ca.hasMetadata( MetaDataStyle.COMET ):
                style = MetaDataStyle.COMET
            elif ca.hasMetadata( MetaDataStyle.CBW ):
                style = MetaDataStyle.CBW
            else:
                logging.warning(u"Library: File Has No ComicMeta Data")
                if ca.hasMetadata( MetaDataStyle.CALIBRE ):
                    style = MetaDataStyle.CALIBRE
                elif ca.hasMetadata( MetaDataStyle.EPUB ):
                    style = MetaDataStyle.EPUB
                else:
                    style = None
                
            if style is not None:
                md = ca.readMetadata(style)
                if md.isEmpty:
                    md = ca.metadataFromFilename()
            else:
                # No metadata in comic.  make some guesses from the filename
                md = ca.metadataFromFilename()
            
            # patch version 2
            if (md.title is None or md.title == "") and md.issue is None and not md.series is None:
                md.title = md.series
                md.series = None
            
            md.fingerprint = ca.fingerprint()
            md.path = ca.path
            
            md.page_count = ca.page_count
            
            md.mod_ts = datetime.utcfromtimestamp(getmtime(ca.path))
            md.filesize = os.path.getsize(md.path)
            md.hash = ""

            #thumbnail generation
            image_data = ca.getPage(0, AppFolders.missingPath("cover.png"))
            
            #now resize it
            thumb = StringIO.StringIO()
            
            #Lets right thumbs to files. large libraries cause the database to bloat
            try:
                utils.resize(image_data, (400, 400), thumb)
                filename = md.fingerprint+".png"
                foldername = filename[0]
                thumbSubFolder = AppFolders.appThumbFolder(foldername)
                if not os.path.exists(thumbSubFolder):
                    os.makedirs(thumbSubFolder)
                folderpath = AppFolders.appThumbPath(foldername, filename)
                with open(folderpath, 'wb') as f:
                    f.write(thumb.getvalue())

                print("Extracted thumb: "+filename)

            except:
                print("Thumbnail extraction failed")
            # print md
            return md
        return None


    def compare( self , comic_filename, comic_compare_filename):
        """
        Compare a comic file
        """

        """
        md = self.getComicMetadata(comic_filename)
        md_compare = self.getComicMetadata(comic_compare_filename)
        if md_compare is not None:
            compare_comic = self.createComicFromMetadata(md_compare)
        if md is not None:
            comic = self.createComicFromMetadata(md)
        if comic is None or compare_comic is None:
            return False
        """

        # preform metadata check....
        # FIX

        fingerprint_compare = ComicArchive(comic_filename,  default_image_path=AppFolders.missingPath("page.png")).fingerprint(sort=False)
        fingerprint = ComicArchive(comic_compare_filename,  default_image_path=AppFolders.missingPath("page.png")).fingerprint(sort=False)

        if fingerprint == fingerprint_compare:
            return True
        return False


    def addComics(self, comic_list):
        """
        Add comics to the Database
        """
        
        # FIX self.double
        for comic in comic_list:
            query = self.getSession().query(Comic).filter(Comic.fingerprint == comic.fingerprint).first()
            if query is not None:
                

                if self.compare(query.path,comic.path):
                    print "Double: " + comic.path
                    print "Double From: " + query.path
                    # Do something...
                    #os.rename(comic.path, comic.path+ ".DOUBLE")
                    self.double += 1
                else:
                    print "Simular: " + comic.path
                    print "Simular From: " + query.path
                    self.simular += 1
            else:
                self.getSession().add(comic)
        if len(comic_list) > 0:
            self._dbUpdated()
        self.getSession().commit()
        self.getSession().expire_all()
        print "Doubles: " + str(self.double)
        print "Simular: " + str(self.simular)
        #self.double = 0
        #self.simular = 0


    def deleteComics(self, comic_id_list):
        s = self.getSession()
        i = 0
        for comic_id in comic_id_list:
#            print "DEBUG DELETE: " + str(comic_id)
            deleted = DeletedComic()
            deleted.comic_id = int(comic_id)
            s.add(deleted)
            s.delete(s.query(Comic).get(comic_id))
            i += 1
            if i > 100:
                i = 0;
                s.commit()
        if len(comic_id_list) > 0:
            self._dbUpdated()
        s.commit()

    def _dbUpdated(self):
        """Updates DatabaseInfo status"""
        self.getSession().query(DatabaseInfo).first().last_updated = datetime.utcnow()

    def list(self, criteria={}, paging=None):
        if paging is None:
            paging = {'per_page': 10, 'offset': 1}

        query = self.getSession().query(Comic)

        query = self.processComicQueryArgs(query, criteria)
        query, total_results = self.processPagingArgs(query, paging)
        query = query.options(subqueryload('characters_raw'))
        query = query.options(subqueryload('storyarcs_raw'))
        query = query.options(subqueryload('locations_raw'))
        query = query.options(subqueryload('teams_raw'))
        #query = query.options(subqueryload('credits_raw'))
        query = query.options(subqueryload('generictags_raw'))

        return query.all(), total_results

    def processPagingArgs(self, query, paging):
        per_page = paging.get(u"per_page", None)
        offset = paging.get(u"offset", None)
        # offset and max_results should be processed last

        total_results = None
        if per_page is not None:
            total_results = query.distinct().count()
            try:
                max = 0
                max = int(per_page)
                if total_results > max:
                    query = query.limit(max)
            except:
                pass

        if offset is not None:
            try:
                off = 0
                off = int(offset)
                query = query.offset(off)
            except:
                pass

        return query, total_results

    def processComicQueryArgs(self, query, criteria):
        def hasValue(obj):
            return obj is not None and obj != ""

        keyphrase_filter = criteria.get(u"keyphrase", None)
        series_filter = criteria.get(u"series", None)
        alternateseries = criteria.get(u"alternateseries", None)
        path_filter = criteria.get(u"path", None)
        folder_filter = criteria.get(u"folder", "")
        title_filter = criteria.get(u"title", None)
        start_filter = criteria.get(u"start_date", None)
        end_filter = criteria.get(u"end_date", None)
        added_since = criteria.get(u"added_since", None)
        modified_since = criteria.get(u"modified_since", None)
        lastread_since = criteria.get(u"lastread_since", None)
        order = criteria.get(u"order", None)
        character = criteria.get(u"character", None)
        team = criteria.get(u"team", None)
        location = criteria.get(u"location", None)
        storyarc = criteria.get(u"storyarc", None)
        volume = criteria.get(u"volume", None)
        publisher = criteria.get(u"publisher", None)
        language_filter = criteria.get(u"language", None)
        credit_filter = criteria.get(u"credit", None)
        tag = criteria.get(u"tag", None)
        genre = criteria.get(u"genre", None)

        if folder_filter is not None and folder_filter != "":
            folder_filter = os.path.normcase(os.path.normpath(folder_filter))

        person = None
        role = None
        if hasValue(credit_filter):
            credit_info = credit_filter.split(":")
            if len(credit_info[0]) != 0:
                person = credit_info[0]
                if len(credit_info) > 1:
                    role = credit_info[1]

        if hasValue(person):
            query = query.join(Credit)\
                         .filter(Person.name.ilike(person.replace("*", "%"))) \
                         .filter(Credit.person_id == Person.id)
            if role is not None:
                query = query.filter(Credit.role_id == Role.id) \
                             .filter(Role.name.ilike(role.replace("*", "%")))
            #query = query.filter( Comic.persons.contains(unicode(person).replace("*","%") ))

        if hasValue(keyphrase_filter):
            keyphrase_filter = unicode(keyphrase_filter).replace("*", "%")
            keyphrase_filter = "%" + keyphrase_filter + "%"
            
            query = query.filter( Comic.series.ilike(keyphrase_filter)
                                | Comic.alternateseries_raw.any(AlternateSeries.name.ilike(keyphrase_filter))
                                | Comic.title.ilike(keyphrase_filter)
                                | Comic.language.ilike(keyphrase_filter)
                                | Comic.path.ilike(keyphrase_filter)
                                | Comic.comments.ilike(keyphrase_filter)
                                | Comic.publisher.ilike(keyphrase_filter)
                                | Comic.characters_raw.any(Character.name.ilike(keyphrase_filter))
                                | Comic.teams_raw.any(Team.name.ilike(keyphrase_filter))
                                | Comic.generictags_raw.any(GenericTag.name.ilike(keyphrase_filter))
                                | Comic.locations_raw.any(Location.name.ilike(keyphrase_filter))
                                | Comic.storyarcs_raw.any(StoryArc.name.ilike(keyphrase_filter))
                                | Comic.persons_raw.any(Person.name.ilike(keyphrase_filter))
                            )

        def addQueryOnScalar(query, obj_prop, filt):
            if hasValue(filt):
                filt = unicode(filt).replace("*","%")
                return query.filter( obj_prop.ilike(filt))
            else:
                return query

        def addQueryOnList(query, obj_list, list_prop, filt):
            if hasValue(filt):
                filt = unicode(filt).replace("*","%")
                return query.filter( obj_list.any(list_prop.ilike(filt)))
            else:
                return query

        query = addQueryOnScalar(query, Comic.series, series_filter)
        query = addQueryOnScalar(query, Comic.title, title_filter)
        query = addQueryOnScalar(query, Comic.path, path_filter)
        query = addQueryOnScalar(query, Comic.folder, folder_filter)
        query = addQueryOnScalar(query, Comic.publisher, publisher)
        query = addQueryOnScalar(query, Comic.language, language_filter)
        query = addQueryOnList(query, Comic.alternateseries_raw, AlternateSeries.name, alternateseries)
        query = addQueryOnList(query, Comic.characters_raw, Character.name, character)
        query = addQueryOnList(query, Comic.generictags_raw, GenericTag.name, tag)
        query = addQueryOnList(query, Comic.teams_raw, Team.name, team)
        query = addQueryOnList(query, Comic.locations_raw, Location.name, location)
        query = addQueryOnList(query, Comic.storyarcs_raw, StoryArc.name, storyarc)
        query = addQueryOnList(query, Comic.genres_raw, Genre.name, genre)

        if hasValue(volume):
            try:
                vol = 0
                vol = int(volume)
                query = query.filter(Comic.volume == vol)
            except:
                pass

        if hasValue(start_filter):
            try:
                dt = dateutil.parser.parse(start_filter)
                query = query.filter(Comic.date >= dt)
            except:
                pass

        if hasValue(end_filter):
            try:
                dt = dateutil.parser.parse(end_filter)
                query = query.filter(Comic.date <= dt)
            except:
                pass

        if hasValue(modified_since):
            try:
                dt = dateutil.parser.parse(modified_since)
                query = query.filter(Comic.mod_ts >= dt)
            except:
                pass

        if hasValue(added_since):
            try:
                dt = dateutil.parser.parse(added_since)
                query = query.filter(Comic.added_ts >= dt)
            except:
                pass

        if hasValue(lastread_since):
            try:
                dt = dateutil.parser.parse(lastread_since)
                query = query.filter(Comic.lastread_ts >= dt, Comic.lastread_ts != "")
            except:
                pass

        order_key = None
        # ATB temp hack to cover "slicing" bug where
        # if no order specified, the child collections
        # get chopped off sometimes
        if not hasValue(order):
            order = "id"

        if hasValue(order):
            if order[0] == "-":
                order_desc = True
                order = order[1:]
            else:
                order_desc = False
                
            if order == "issue":
                order_key = Comic.issue_num
            if order == "series":
                order_key = Comic.series
            elif order == "modified":
                order_key = Comic.mod_ts
            elif order == "added":
                order_key = Comic.added_ts
            elif order == "lastread":
                order_key = Comic.lastread_ts
            elif order == "volume":
                order_key = Comic.volume
            elif order == "id":
                order_key = Comic.id
            elif order == "date":
                order_key = Comic.date
            elif order == "publisher":
                order_key = Comic.publisher
            elif order == "language":
                order_key = Comic.language
            elif order == "title":
                order_key = Comic.title
            elif order == "path":
                order_key = Comic.path

        if order_key is not None:
            if order_desc:
                order_key = order_key.desc()
            query = query.order_by(order_key)

        return query



    def getComicArchive(self, id, path):
        # should also look at modified time of file
        for ca in self.comicArchiveList:
            if ca.path == path:
                # remove from list and put at end
                self.comicArchiveList.remove(ca)
                self.comicArchiveList.append(ca)
                return ca
        else:
            ca = ComicArchive(path, default_image_path=AppFolders.missingPath("page.png"))
            self.comicArchiveList.append(ca)
            if len(self.comicArchiveList) > 10:
                self.comicArchiveList.pop(0)
            return ca


