import zipfile
import os
import struct
import tempfile
import subprocess
import platform
import locale
import shutil
import tarfile
import re
import sys
import urllib2
import HTMLParser
import urlparse


import zipfile
from lxml import etree


from natsort import natsorted
import ctypes
import io
import pylzma
from py7zlib import Archive7z
import rarfile

import xml.etree.ElementTree as ET

from comicstreamerlib.config import ComicStreamerConfig
from comicstreamerlib.utils import *

config = ComicStreamerConfig()

from PIL import Image
try:
    from PIL import WebPImagePlugin
except:
    pass

from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True


ImageExtensions = [".bmp", ".jpg", "jpeg", ".png", ".gif", "webp", ".pcx", "tiff", ".dcx", ".tga" ]

from comicstreamerlib.folders import AppFolders

if platform.system() == "Windows":
    import _subprocess
import time

import StringIO
try: 
    import Image
    pil_available = True
except ImportError:
    pil_available = False

sys.path.insert(0, os.path.abspath(".") )

#from settings import ComicTaggerSettings
from comicinfoxml import ComicInfoXml
from comicbookinfo import ComicBookInfo
from comet import CoMet
from genericmetadata import GenericMetadata, PageType
from filenameparser import FileNameParser
from PyPDF2 import PdfFileReader

class MetaDataStyle:
    CBI = 0
    CIX = 1
    COMET = 2
    CALIBRE = 3
    EPUB = 4
    CBW = 5
    name = [ 'ComicBookLover', 'ComicRack', 'CoMet' , 'Calibre', 'Epub' , 'WebComic' ]

#------------------------------------------
# Zip Implementation
#------------------------------------------

class ZipArchiver:

    def __init__( self, path ):
        self.path = path

    def getArchiveComment( self ):
        zf = zipfile.ZipFile( self.path, 'r' )
        comment = zf.comment
        zf.close()
        return comment

    def setArchiveComment( self, comment ):
        return self.writeZipComment( self.path, comment )

    def readArchiveFile( self, archive_file ):
        data = ""
        zf = zipfile.ZipFile( self.path, 'r' )

        try:
            data = zf.read( archive_file )
        except zipfile.BadZipfile as e:
            print >> sys.stderr, u"bad zipfile [{0}]: {1} :: {2}".format(e, self.path, archive_file)
            zf.close()
            raise IOError
        except Exception as e:
            zf.close()
            print >> sys.stderr, u"bad zipfile [{0}]: {1} :: {2}".format(e, self.path, archive_file)
            raise IOError
        finally:
            zf.close()
        return data

    def removeArchiveFile( self, archive_file ):
        try:
            self.rebuildZipFile(  [ archive_file ] )
        except:
            return False
        else:
            return True

    def writeArchiveFile( self, archive_file, data ):
        #  At the moment, no other option but to rebuild the whole
        #  zip archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        try:
            self.rebuildZipFile(  [ archive_file ] )

            #now just add the archive file as a new one
            zf = zipfile.ZipFile(self.path, mode='a', compression=zipfile.ZIP_DEFLATED )
            zf.writestr( archive_file, data )
            zf.close()
            return True
        except:
            return False

    def getArchiveFilenameList( self ):
        try:
            zf = zipfile.ZipFile( self.path, 'r' )
            namelist = zf.namelist()
            zf.close()
            return namelist
        except Exception as e:
            print >> sys.stderr, u"Unable to get zipfile list [{0}]: {1}".format(e, self.path)
            return []


    def getArchiveFilesizeList( self ):
        try:
            zf = zipfile.ZipFile( self.path, 'r' )
            namelist = zf.namelist()
            sizelist = []
            for i in namelist:
                sizelist += [(i,zf.getinfo(i).file_size)]
            zf.close()
            return sizelist
        except Exception as e:
            print >> sys.stderr, u"Unable to get zipfile list [{0}]: {1}".format(e, self.path)
            return []


    # zip helper func
    def rebuildZipFile( self, exclude_list ):

        # this recompresses the zip archive, without the files in the exclude_list
        #print ">> sys.stderr, Rebuilding zip {0} without {1}".format( self.path, exclude_list )

        # generate temp file
        tmp_fd, tmp_name = tempfile.mkstemp( dir=os.path.dirname(self.path) )
        os.close( tmp_fd )

        zin = zipfile.ZipFile (self.path, 'r')
        zout = zipfile.ZipFile (tmp_name, 'w')
        for item in zin.infolist():
            buffer = zin.read(item.filename)
            if ( item.filename not in exclude_list ):
                zout.writestr(item, buffer)

        #preserve the old comment
        zout.comment = zin.comment

        zout.close()
        zin.close()

        # replace with the new file
        os.remove( self.path )
        os.rename( tmp_name, self.path )


    def writeZipComment( self, filename, comment ):
        """
        This is a custom function for writing a comment to a zip file,
        since the built-in one doesn't seem to work on Windows and Mac OS/X

        Fortunately, the zip comment is at the end of the file, and it's
        easy to manipulate.  See this website for more info:
        see: http://en.wikipedia.org/wiki/Zip_(file_format)#Structure
        """

        #get file size
        statinfo = os.stat(filename)
        file_length = statinfo.st_size

        try:
            fo = open(filename, "r+b")

            #the starting position, relative to EOF
            pos = -4

            found = False
            value = bytearray()

            # walk backwards to find the "End of Central Directory" record
            while ( not found ) and ( -pos != file_length ):
                # seek, relative to EOF
                fo.seek( pos,  2)

                value = fo.read( 4 )

                #look for the end of central directory signature
                if bytearray(value) == bytearray([ 0x50, 0x4b, 0x05, 0x06 ]):
                    found = True
                else:
                    # not found, step back another byte
                    pos = pos - 1
                #print pos,"{1} int: {0:x}".format(bytearray(value)[0], value)

            if found:

                # now skip forward 20 bytes to the comment length word
                pos += 20
                fo.seek( pos,  2)

                # Pack the length of the comment string
                format = "H"                   # one 2-byte integer
                comment_length = struct.pack(format, len(comment)) # pack integer in a binary string

                # write out the length
                fo.write( comment_length )
                fo.seek( pos+2,  2)

                # write out the comment itself
                fo.write( comment )
                fo.truncate()
                fo.close()
            else:
                raise Exception('Failed to write comment to zip file!')
        except:
            return False
        else:
            return True

    def copyFromArchive( self, otherArchive ):
        # Replace the current zip with one copied from another archive
        try:
            zout = zipfile.ZipFile (self.path, 'w')
            for fname in otherArchive.getArchiveFilenameList():
                data = otherArchive.readArchiveFile( fname )
                if data is not None:
                    zout.writestr( fname, data )
            zout.close()

            #preserve the old comment
            comment = otherArchive.getArchiveComment()
            if comment is not None:
                if not self.writeZipComment( self.path, comment ):
                    return False
        except  Exception as e:
            print >> sys.stderr, u"Error while copying to {0}: {1}".format(self.path, e)
            return False
        else:
            return True

class SevenZipArchiver:

    def __init__( self, path ):
        self.path = path

    def getArchiveComment( self ):
	#fp = open( self.path, 'r' )
        #szf = Archive7z( fp )
        #comment = szf.comment
	#fp.close()
        #return comment
        return ""

    def setArchiveComment( self, comment ):
        return False

    def readArchiveFile( self, archive_file ):
        data = ""
        fp = open( self.path, 'r' )

        try:
            szf = Archive7z( fp )
            data = szf.getmember( archive_file ).read()
        except Exception as e:
            #import traceback
            #traceback.print_exc(file=sys.stdout)
            #UnsupportedCompressionMethodError: '!'
            fp.close()
            print >> sys.stderr, u"bad 7zip file [{0}]: {1} :: {2}".format(e, self.path, archive_file)
            raise IOError
        finally:
            fp.close()
        return data

    def removeArchiveFile( self, archive_file ):
        return False
        
    def writeArchiveFile( self, archive_file, data ):
        return False

    def getArchiveFilenameList( self ):
        try:
            fp = open( self.path, 'r' )
            szf = Archive7z( fp )
            namelist = list(szf.getnames())
            fp.close()
            return namelist
        except Exception as e:
            print >> sys.stderr, u"Unable to get 7zipfile list [{0}]: {1}".format(e, self.path)
            return []

    def getArchiveFilesizeList( self ):
        try:
            fp = open( self.path, 'r' )
            szf = Archive7z( fp )
            t = szf.getmembers()
            n = list(szf.getnames())
            
            sizelist = []
            for i in range(len(t)):
                sizelist += [(n[i],t[i].size)]
            fp.close()
            return sizelist
        except Exception as e:
            print >> sys.stderr, u"Unable to get 7zipfile list [{0}]: {1}".format(e, self.path)
            return []

class TarArchiver:

    def __init__( self, path ):
        self.path = path

    def getArchiveComment( self ):
        return ""

    def setArchiveComment( self, comment ):
        return False
    
    def readArchiveFile( self, archive_file ):
        data = ""
        zf = tarfile.TarFile( self.path, 'r' )
        try:
            data = zf.extractfile(archive_file).read()
        except Exception as e:
            zf.close()
            print >> sys.stderr, u"bad tarfile [{0}]: {1} :: {2}".format(e, self.path, archive_file)
            raise IOError
        finally:
            zf.close()
        return data

    def removeArchiveFile( self, archive_file ):
        return False
    
    def writeArchiveFile( self, archive_file, data ):
        return False

    def getArchiveFilenameList( self ):
        try:
            zf = tarfile.TarFile( self.path, 'r')
            namelist = zf.getnames()
            zf.close()
            return namelist
        except Exception as e:
            print >> sys.stderr, u"Unable to get tarfile list [{0}]: {1}".format(e, self.path)
            return []

    def getArchiveFilesizeList( self ):
        try:
            zf = tarfile.TarFile( self.path, 'r')
            t = zf.getmembers()
            sizelist = []
            for i in t:
                sizelist += [(i.name,i.size)]
            zf.close()
            return sizelist
        except Exception as e:
            print >> sys.stderr, u"Unable to get tarfile list [{0}]: {1}".format(e, self.path)
            return []


#------------------------------------------
# RAR implementation
#------------------------------------------

class RarArchiver:

    devnull = None
    def __init__( self, path, rar_exe_path ):
        self.path = path
        self.rar_exe_path = rar_exe_path

        if RarArchiver.devnull is None:
            RarArchiver.devnull = open(os.devnull, "w")

        # windows only, keeps the cmd.exe from popping up
        if platform.system() == "Windows":
            self.startupinfo = subprocess.STARTUPINFO()
            self.startupinfo.dwFlags |= _subprocess.STARTF_USESHOWWINDOW
        else:
            self.startupinfo = None

    def __del__(self):
        #RarArchiver.devnull.close()
        pass

    def getArchiveComment( self ):

        rarc = self.getRARObj()
        return rarc.comment

    def setArchiveComment( self, comment ):

        if self.rar_exe_path is not None:
            try:
                # write comment to temp file
                tmp_fd, tmp_name = tempfile.mkstemp()
                f = os.fdopen(tmp_fd, 'w+b')
                f.write( comment )
                f.close()

                working_dir = os.path.dirname( os.path.abspath( self.path ) )

                # use external program to write comment to Rar archive
                subprocess.call([self.rar_exe_path, 'c', '-w' + working_dir , '-c-', '-z' + tmp_name, self.path],
                    startupinfo=self.startupinfo,
                    stdout=RarArchiver.devnull)

                if platform.system() == "Darwin":
                    time.sleep(1)

                os.remove( tmp_name)
            except:
                return False
            else:
                return True
        else:
            return False

    def readArchiveFile( self, archive_file ):

        # Make sure to escape brackets, since some funky stuff is going on
        # underneath with "fnmatch"
        #archive_file = archive_file.replace("[", '[[]')
        entries = []

        rarc = self.getRARObj()

        tries = 0
        while tries < 7:
            try:
                tries = tries+1
                data = rarc.open(archive_file).read()
                entries = [(rarc.getinfo(archive_file), data)]


                #shutil.rmtree(tmp_folder, ignore_errors=True)

                #entries = rarc.read_files( archive_file )

                if entries[0][0].file_size != len(entries[0][1]):
                    print >> sys.stderr, u"readArchiveFile(): [file is not expected size: {0} vs {1}]  {2}:{3} [attempt # {4}]".format(
                                entries[0][0].file_size,len(entries[0][1]), self.path, archive_file, tries)
                    continue

            except (OSError, IOError) as e:
                print >> sys.stderr, u"readArchiveFile(): [{0}]  {1}:{2} attempt#{3}".format(str(e), self.path, archive_file, tries)
                time.sleep(1)
            except Exception as e:
                print >> sys.stderr, u"Unexpected exception in readArchiveFile(): [{0}] for {1}:{2} attempt#{3}".format(str(e), self.path, archive_file, tries)
                break

            else:
                #Success"
                #entries is a list of of tuples:  ( rarinfo, filedata)
                if tries > 1:
                    print >> sys.stderr, u"Attempted read_files() {0} times".format(tries)
                if (len(entries) == 1):
                    return entries[0][1]
                else:
                    raise IOError

        raise IOError



    def writeArchiveFile( self, archive_file, data ):

        if self.rar_exe_path is not None:
            try:
                tmp_folder = tempfile.mkdtemp()

                tmp_file = os.path.join( tmp_folder, archive_file )

                working_dir = os.path.dirname( os.path.abspath( self.path ) )

                # TODO: will this break if 'archive_file' is in a subfolder. i.e. "foo/bar.txt"
                # will need to create the subfolder above, I guess...
                f = open(tmp_file, 'w')
                f.write( data )
                f.close()

                # use external program to write file to Rar archive
                subprocess.call([self.rar_exe_path, 'a', '-w' + working_dir ,'-c-', '-ep', self.path, tmp_file],
                    startupinfo=self.startupinfo,
                    stdout=RarArchiver.devnull)

                if platform.system() == "Darwin":
                    time.sleep(1)
                os.remove( tmp_file)
                os.rmdir( tmp_folder)
            except:
                return False
            else:
                return True
        else:
            return False

    def removeArchiveFile( self, archive_file ):
        if self.rar_exe_path is not None:
            try:
                # use external program to remove file from Rar archive
                subprocess.call([self.rar_exe_path, 'd','-c-', self.path, archive_file],
                    startupinfo=self.startupinfo,
                    stdout=RarArchiver.devnull)

                if platform.system() == "Darwin":
                    time.sleep(1)
            except:
                return False
            else:
                return True
        else:
            return False

    def getArchiveFilenameList( self ):

        rarc = self.getRARObj()
        #namelist = [ item.filename for item in rarc.infolist() ]
        #return namelist

        tries = 0
        while tries < 7:
            try:
                tries = tries+1
                #namelist = [ item.filename for item in rarc.infolist() ]
                namelist = []
                for item in rarc.infolist():
                    if item.file_size != 0:
                        namelist.append( item.filename )

            except (OSError, IOError) as e:
                print >> sys.stderr, u"getArchiveFilenameList(): [{0}] {1} attempt#{2}".format(str(e), self.path, tries)
                time.sleep(1)

            else:
                #Success"
                return namelist

        raise e


    def getArchiveFilesizeList( self ):

        rarc = self.getRARObj()
        #namelist = [ item.filename for item in rarc.infolist() ]
        #return namelist

        tries = 0
        while tries < 7:
            try:
                tries = tries+1
                #namelist = [ item.filename for item in rarc.infolist() ]
                namelist = []
                for item in rarc.infolist():
                    if item.file_size != 0:
                        namelist += [(item.filename,item.file_size)]

            except (OSError, IOError) as e:
                print >> sys.stderr, u"getArchiveFilenameList(): [{0}] {1} attempt#{2}".format(str(e), self.path, tries)
                time.sleep(1)

            else:
                #Success"
                return namelist

        raise e


    def getRARObj( self ):
        tries = 0
        while tries < 7:
            try:
                tries = tries+1
                rarc = rarfile.RarFile( self.path )

            except (OSError, IOError) as e:
                print >> sys.stderr, u"getRARObj(): [{0}] {1} attempt#{2}".format(str(e), self.path, tries)
                time.sleep(1)

            else:
                #Success"
                return rarc

        raise e

#------------------------------------------
# Folder implementation
#------------------------------------------

class FolderArchiver:

    def __init__( self, path ):
        self.path = path
        self.comment_file_name = "ComicTaggerFolderComment.txt"

    def getArchiveComment( self ):
        return self.readArchiveFile( self.comment_file_name )

    def setArchiveComment( self, comment ):
        return self.writeArchiveFile( self.comment_file_name, comment )

    def readArchiveFile( self, archive_file ):

        data = ""
        fname = os.path.join( self.path, archive_file )
        try:
            with open( fname, 'rb' ) as f:
                data = f.read()
                f.close()
        except IOError as e:
            pass

        return data

    def writeArchiveFile( self, archive_file, data ):

        fname = os.path.join( self.path, archive_file )
        try:
            with open(fname, 'w+') as f:
                f.write( data )
                f.close()
        except:
            return False
        else:
            return True

    def removeArchiveFile( self, archive_file ):

        fname = os.path.join( self.path, archive_file )
        try:
            os.remove( fname )
        except:
            return False
        else:
            return True

    def getArchiveFilenameList( self ):
        return self.listFiles( self.path )

    def listFiles( self, folder ):

        itemlist = list()

        for item in os.listdir( folder ):
            itemlist.append( item )
            if os.path.isdir( item ):
                itemlist.extend( self.listFiles( os.path.join( folder, item ) ))

        return itemlist

#------------------------------------------
# Unknown implementation
#------------------------------------------

class UnknownArchiver:

    def __init__( self, path ):
        self.path = path

    def getArchiveComment( self ):
        return ""
    def setArchiveComment( self, comment ):
        return False
    def readArchiveFile( self ):
        return ""
    def writeArchiveFile( self, archive_file, data ):
        return False
    def removeArchiveFile( self, archive_file ):
        return False
    def getArchiveFilenameList( self ):
        return []
    def getArchiveFilesizeList( self ):
        return []

#------------------------------------------
# PDF Implementation
#------------------------------------------

class PdfArchiver:
    def __init__( self, path ):
        self.path = path

    def getArchiveComment( self ):
        return ""
    def setArchiveComment( self, comment ):
        return False
    def readArchiveFile( self, page_num ):
        resolution = config['format.pdf']['resolution']
        #resolution = 150
   
        cache_location = config['format.ebook']['location']
        if cache_location == "" or not os.path.exists(cache_location):
            cache_location = AppFolders.appCacheEbooks()
        cache = os.path.join(cache_location,os.path.basename(self.path)+u".decrypted.cache.pdf")

        corrected_path_temp = self.path
        if os.path.isfile(cache):
            corrected_path_temp = cache
 
        page_num_corr = page_num
        cover = os.path.join(os.path.dirname(self.path),'cover.jpg')
        if os.path.isfile(cover):
            if page_num_corr == '0.png':
                data = ""
                fname = cover
                try:
                    with open( fname, 'rb' ) as f:
                        data = f.read()
                        f.close()
                        return data
                except:
                    pass
    
        #return subprocess.check_output(['pdftopng', '-r', str(resolution), '-f', str(int(os.path.basename(page_num)[:-4])), '-l', str(int(os.path.basename(page_num)[:-4])), self.path,  '-'])
        
        try:
            if platform.system() == "Windows":
                return subprocess.check_output(['mutool.exe', 'draw','-r', str(resolution), '-o','-', corrected_path_temp, str(int(os.path.basename(page_num_corr)[:-4]))])
            else:
                return subprocess.check_output(['./mudraw', '-r', str(resolution), '-o','-', corrected_path_temp, str(int(os.path.basename(page_num_corr)[:-4]))])
        except:
            pass

    def writeArchiveFile( self, archive_file, data ):
        return False
    def removeArchiveFile( self, archive_file ):
        return False
    
    def getArchiveFilesizeList( self ):
        sizelist = []
        for i in self.getArchiveFilenameList():
            sizelist += [(i,-1)]
        return sizelist
   
   
    def getArchiveFilenameList( self ):
        out = []
        try:
            if os.path.isfile(os.path.join(os.path.dirname(self.path),'cover.jpg')):
                out.append("0.png")
        
            cache_location = config['format.ebook']['location']
            if cache_location == "" or not os.path.exists(cache_location):
                cache_location = AppFolders.appCacheEbooks()

            cache = os.path.join(cache_location,os.path.basename(self.path)+u".decrypted.cache.pdf")
            corrected_path_temp = self.path
            if os.path.isfile(cache):
                corrected_path_temp = cache
            
            pdf = PdfFileReader(open(corrected_path_temp, 'rb'))
            if pdf.isEncrypted:
                try:
                    pdf.decrypt('')
                    for page in range(1, pdf.getNumPages() + 1):
                        out.append(str(page) + ".png")
                except Exception as e:
                    # error... decode...
                    if platform.system() == "Windows":
                        subprocess.call(["qpdf.exe","--password=","--decrypt",self.path,cache])
                    else:
                        subprocess.call(["./qpdf","--password=","--decrypt",self.path,cache])
                    
                    # restart process...
                    if os.path.isfile(os.path.join(os.path.dirname(self.path),'cover.jpg')):
                        out.append("0.png")
                        
                    pdf = PdfFileReader(open(cache, 'rb'))
                    out = []
                    try:
                        for page in range(1, pdf.getNumPages() + 1):
                            out.append(str(page) + ".png")
                    except Exception as e:
                        print >> sys.stderr, u"PDF Unreadble [{0}]: {1}".format(str(e),self.path)

            else:
                for page in range(1, pdf.getNumPages() + 1):
                    out.append(str(page) + ".png")
        except Exception as e:
            print >> sys.stderr, u"PDF Unreadable [{0}]: {1}".format(str(e),self.path)
        return out

#------------------------------------------
# EBook Implementation
#------------------------------------------

ebook_extentions = [".epub",".mobi",".chm",".azw3",".lit",".fb2",".djvu"]

class EbookArchiver(PdfArchiver):

    cache_file = None

    def getCover(self):
        # bad bad, should follow the manifest or use a ebooklib...
        data = None
        zf = zipfile.ZipFile( self.path, 'r' )
        try:
            data = zf.read( 'cover.jpeg' )
        except zipfile.BadZipfile as e:
            print >> sys.stderr, u"bad zipfile [{0}]: {1} :: {2}".format(e, self.path, 'cover.jpeg' )
            zf.close()
            raise IOError
        except Exception as e:
            zf.close()
            print >> sys.stderr, u"bad zipfile [{0}]: {1} :: {2}".format(e, self.path, 'cover.jpeg' )
            raise IOError
        finally:
            zf.close()
        return data


    def readArchiveFile( self, page_num ):
  
        ext = os.path.splitext(self.path)[1].lower()
        if ext in ebook_extentions:
            if not self.convert(): return

        resolution = config['format.ebook']['resolution']
        #resolution = 72
        
        if page_num == '0.png':
            
            try:
                x = self.getCover()
                # maybe if is unneeded...
                if x:
                    return x
            except:
                pass

            cover = os.path.join(os.path.dirname(self.path),'cover.jpg')
            if os.path.isfile(cover):
                data = ""
                fname = cover
                try:
                    with open( fname, 'rb' ) as f:
                        data = f.read()
                        f.close()
                        return data
                except:
                    pass
    
        #return subprocess.check_output(['pdftopng', '-r', str(resolution), '-f', str(int(os.path.basename(page_num)[:-4])), '-l', str(int(os.path.basename(page_num)[:-4])), self.path,  '-'])
        
        if platform.system() == "Windows":
            return subprocess.check_output(['.\mutool.exe', 'draw','-r', str(resolution), '-o','-', self.cache_file, str(int(os.path.basename(page_num)[:-4]))])
        else:
            return subprocess.check_output(['./mudraw', '-r', str(resolution), '-o','-', self.cache_file, str(int(os.path.basename(page_num)[:-4]))])

    def convert( self ):
        cache_location = config['format.ebook']['location']
        if cache_location == "" or not os.path.exists(cache_location):
            cache_location = AppFolders.appCacheEbooks()
        self.cache_file = os.path.join(cache_location,os.path.basename(self.path)+u".cache.pdf")
        corrected_path_temp = self.cache_file + u".tmp.pdf"
        if not os.path.isfile(self.cache_file):
            try:
                margin = config['format.ebook']['margin']
                format_arg = ["--pdf-page-numbers","--margin-top",str(margin),"--margin-bottom",str(margin),"--margin-left",str(margin),"--margin-right",str(margin),"--pdf-add-toc"]
                if platform.system() == "Windows":
                    subprocess.check_output(['%PROGRAMFILES%\calibre\ebook-convert.exe', self.path, corrected_path_temp] + format_arg)
                else:
                    subprocess.check_output(['/Applications/calibre.app/Contents/MacOS/ebook-convert', self.path, corrected_path_temp] + format_arg)
                #rename file after process is done... tmp cache
                os.rename(corrected_path_temp,self.cache_file)
                return True
            except Exception as e:
                print >> sys.stderr, u"EBOOK Unreadable [{0}]: {1}".format(str(e),self.path)
                return False
        else:
            return True

    def getArchiveFilesizeList( self ):
        sizelist = []
        for i in self.getArchiveFilenameList():
            sizelist += [(i,-1)]
        return sizelist
    
    
    def getArchiveFilenameList( self ):
        out = []
        try:
            if os.path.isfile(os.path.join(os.path.dirname(self.path),'cover.jpg')):
                out.append("0.png")

            ext = os.path.splitext(self.path)[1].lower()
            if ext in ebook_extentions:
                if not self.convert(): return out
                           
            pdf = PdfFileReader(open(self.cache_file, 'rb'))
            if pdf.isEncrypted:
                try:
                    pdf.decrypt('')
                    for page in range(1, pdf.getNumPages() + 1):
                        out.append(str(page) + ".png")
                except Exception as e:
                    print >> sys.stderr, u"EBOOK Cached PDF Decrypted Failed [{0}]: {1}".format(str(e),self.path)
            else:
                for page in range(1, pdf.getNumPages() + 1):
                    out.append(str(page) + ".png")
        except Exception as e:
            print >> sys.stderr, u"EBOOK Cached PDF Unreadable [{0}]: {1}".format(str(e),self.cache_file)
        return out

#------------------------------------------
# Web (CBW) Implentation
#------------------------------------------


class WebArchiver:

    cache_file = None

    def __init__( self, path ):
        self.path = path

    def getArchiveComment( self ):
        return ""
    
    def setArchiveComment( self, comment ):
        return False

    def readArchiveFile( self, page_num ):
        cache_location = config['format.webcomic']['location']
        if cache_location == "" or not os.path.exists(cache_location):
            cache_location = AppFolders.appWebComic()
        cache_folder = os.path.join(cache_location,os.path.basename(self.path))
        ext = os.path.splitext(self.path)[1].lower()
        if ext == ".cbw":
            cache_folder = cache_folder[:-4]
      
        if not os.path.isdir(cache_folder):
            
            print "Web Comic: Could find web comic cache " + cache_folder
            return

        scraperfile = os.path.join(cache_folder,"WebComicBrowseScraperIndex.txt")

        # read filename from file...

        image_file = ""
        image_url = ""
        if os.path.isfile(scraperfile):
            mode = 0
            found = False
            try:
                with open(scraperfile) as f:
                    for line in (line for line in f if line.rstrip('\n')):
                        if mode == 1:
                            image_url = line[:-1]
                            mode = 2
                        elif mode == 3:
                            mode = 0
                        elif mode == 2:
                            print item_page
                            print os.path.splitext(page_num)[0]
                            if str(item_page) == os.path.splitext(page_num)[0]:
                                image_file = line[:-1]
                                found = True
                                break
                            mode = 3
                        elif mode == 0:
                            if line[0] == '[':
                                item_page = int(line[1:-2])
                                image_url = ""
                                mode = 1
                            else:
                                break
            except:
                print "Web Comic: BrowseScraper: Warning Page " + str(page_num) + ": Scraperfile corrupted: "+ scraperfile
                return ""

        if image_file != "":
            
            # try reading it...
            imagefilename = os.path.join(cache_folder,image_file)
            print 'gvd'
            print imagefilename
            if os.path.isfile(imagefilename):
                print 'GVD'
                try:
                    with open(imagefilename, 'rb') as fd:
                        data = fd.read()
                        #i=Image.open(StringIO.StringIO(data))
                        print "FFDDFDFDFDFDFDFDFDF"
                        return data
                except:
                    print "Web Comic: BrowseScraper: Warning Page " + str(page_num) + ": Not an image: "+ imagefilename

            
        if image_url != "":
            try:
                req = urllib2.Request(image_url, headers={ 'User-Agent': 'Mozilla/5.0' })
                response  = urllib2.urlopen(req)
                image_data = response.read()
            except:
                print "Web Comic: BrowseScraper: Page " + str(page_num) + ": Could not get " + image_url
                return ""
            try:
                i=Image.open(StringIO.StringIO(image_data))
                img_ext = i.format.lower()
                imagefilename = os.path.join(cache_folder,str(page_num))
                f = open(imagefilename + ".tmp", 'w')
                f.write(image_data)
                f.close
                os.rename(imagefilename + ".tmp",imagefilename)
                return image_data
            except:
                print "Web Comic: BrowseScraper: Page " + str(page_num) + ": Not an image: "+ image_url
                return ""
        print "Web Comic: BrowseScraper: Failed Page " + str(page_num)
        return ""
  
    def writeArchiveFile( self, archive_file, data ):
        return False
    
    def removeArchiveFile( self, archive_file ):
        return False
    
    def getArchiveFilesizeList( self ):
        sizelist = []
        for i in self.getArchiveFilenameList():
            sizelist += [(i,-1)]
        return sizelist
     
     
    def readCBW(self):
        h= HTMLParser.HTMLParser()
        # We ignore composition... you implement that
        images = []
        cache = []
        nextlist = []
        old_scrape = ""
        scrape = ""
        
        cache_location = config['format.webcomic']['location']
        if cache_location == "" or not os.path.exists(cache_location):
            cache_location = AppFolders.appWebComic()
        cache_folder = os.path.join(cache_location,os.path.basename(self.path))
        ext = os.path.splitext(self.path)[1].lower()
        if ext == ".cbw":
            cache_folder = cache_folder[:-4]
      
        if not os.path.isdir(cache_folder):
            try:
                os.makedirs(cache_folder)
            except:
                print "Web Comic: Could not make folder " + cache_folder
                return images

        tree = ET.parse(self.path)
        
        root = tree.find('Images')
        
        if root is None:
            return images
        pages = 0
        
        for n in root:
        
            if n.tag == 'Image':
                try:
                    type = n.attrib['Type']
                except:
                    type = "Unknown"
                
                try:
                    url =  n.attrib['Url']
                except:
                    continue
        
        
                if type == "BrowseScraper" or url[0] == "?":
                    start = ""
                    image = ""
                    nextpage = ""
    
                    # Not implemented
                    image_MaximumMatches = "1"
                    image_Reverse=False
                    image_Sort=False
                    image_AddOwn=False
                    image_Cut=""
                    
                    nextpage_MaximumMatches = "1"
                    nextpage_Reverse=False
                    nextpage_Sort=False
                    nextpage_AddOwn=False
                    nextpage_Cut=""
                    
                    if url[0] == "?":
                        url = url[1:]
                    url_split =  url.split('|')
                    start = url_split[0]
                    if len(url_split) == 3:
                        image = url_split[1]
                        nextpage = url_split[2]
                    else:
                        i = 1
                        try:
                            parts = n.find('Parts')
                            for p in parts:
                                if i == 1:
                                    image = h.unescape(p.text) #.encode('ascii','ignore')
                                
                                    try:
                                        image_MaximumMatches = p.attrib['MaximumMatches']
                                    except:
                                        pass
                                    try:
                                        image_Reverse = p.attrib['Reverse']
                                    except:
                                        pass
                                    try:
                                        image_Sort = p.attrib['Sort']
                                    except:
                                        pass
                                    try:
                                        image_Cut = p.attrib['Cut']
                                    except:
                                        pass
                                    try:
                                        image_AddOwn = p.attrib['AddOwn']
                                    except:
                                        pass
                                else:
                                    nextpage = h.unescape(p.text)


                                
                                    try:
                                        nextpage_MaximumMatches = p.attrib['MaximumMatches']
                                    except:
                                        pass
                                    try:
                                        nextpage_Reverse = p.attrib['Reverse']
                                    except:
                                        pass
                                    try:
                                        nextpage_Sort = p.attrib['Sort']
                                    except:
                                        pass
                                    try:
                                        nextpage_Cut = p.attrib['Cut']
                                    except:
                                        pass
                                    try:
                                        nextpage_AddOwn = p.attrib['AddOwn']
                                    except:
                                        pass
                                i += 1
                                if i > 2: break
                        except:
                            print "Web Comic: BrowseScraper: Failed"
                            continue
                    if i <= 2:
                        print "Web Comic: BrowseScraper: Failed"
                        continue
                        
                    print "Web Comic: BrowseScraper " + start #+ "\n" + image + "\n" + nextpage
                    
                    lastpage = False
                    old_scrape = scrape
                    scrape = start
                    
                    scraperfile = os.path.join(cache_folder,"WebComicBrowseScraperIndex.txt")

                    # remove partial images
                    for item in os.listdir( cache_folder ):
                        if item.endswith(".tmp"):
                            os.remove( os.path.join( cache_folder, item ) )
                    
                    mode = 0
                    ####
                    #### FUNCTION LOAD SCRAPERFILE
                    ####
                    if os.path.isfile(scraperfile):
                        try:
                            with open(scraperfile) as f:
                                item_page = 0
                                item_next = ""
                                item_filename = ""
                                item_source = ""
                                
                                lc_item_page = 0
                                lc_item_next = ""
                                lc_item_filename = ""
                                lc_item_source = ""
                                
                                firstt = True
                                
                                mode = 0 # 0 = page, 1 = source, 2 = next, 3 = filename
                                for line in (line for line in f if line.rstrip('\n')):
                                    data = line[:-1]
                                    print str(mode) + " + " + data
                                    if mode == 0:
                                        x = data[1:-1].strip()
                                        print x
                                        print "GOFVEFRDOME"
                                        item_page = int(x)
                                        lc_item_page = item_page
                                        lc_item_next = item_next
                                        lc_item_filename = item_filename
                                        lc_item_source = item_source
                                        if firstt:
                                            firstt = False
                                        else:
                                            pages = item_page
                                            nextlist += [item_next]
                                            images += [item_source]
                                            cache += [item_filename]
                                        mode = 1
                                    elif mode == 1:
                                        item_source = data
                                        mode = 2
                                    elif mode == 2:
                                        item_filename = data
                                        mode = 3
                                    elif mode == 3:
                                        item_next = data
                                        mode = 0
                            #raw_input("abort")
                            if mode == 0:

                                lc_item_page = item_page
                                lc_item_next = item_next
                                lc_item_filename = item_filename
                                lc_item_source = item_source
                                if not firstt:
                                    pages = item_page
                                    nextlist += [item_next]
                                    images += [item_source]
                                    cache += [item_filename]
                            elif mode == 3:
                                if not firstt:
                                    pages = item_page - 1
                                    images += [item_source]
                                    cache += [item_filename]
                            else:
                                # file corrupted....
                                old_scrape = scrape
                                scrape = start
                                pages = 0
                                
                            if lc_item_next != "":
                                old_scrape = scrape
                                scrape = lc_item_next
                    
                            
                            
                        except Exception, e:
                            import traceback
                            traceback.print_exc(file=sys.stdout)
                            print str(e)
                            print "FUCKING KUTOZII"
                            old_scrape = scrape
                            scrape = start
                            pages = 0
                    
                    ####
                    #### SCRAPING
                    ####
                    #raw_input("You can abort now")
                    
                    next_url = ""
                    imagefilename = ""
                    
                    while not lastpage:
                        pages += 1
                        try:
                            print "Page: " + str(pages)
                            print scrape
                            req = urllib2.Request(scrape, headers={ 'User-Agent': 'Mozilla/5.0' })
                            response  = urllib2.urlopen(req)
                            self.content = response.read()
                            print "HERE"
                            # going from .net to python regular expressions
                            
                            # replace ?P<link> with ?<link>
                            # escape char with /
                            
                            im = image.replace("?<link>","?P<link>")
                            im = im.replace('-','\-')

                            imagefilename = ""
                            
                            pattern = re.compile(im)
                            
                            m = pattern.search(self.content)
                            if m:
                                image_url = m.group(0).strip()
                                
                                src = re.search(r'src="(.*?)"', image_url)
                                
                                if src:
                                    url = src.group(0)[5:].split('"', 1)[0]
                     
                                    if url[0:4] != 'http':
                                        image_url = (urlparse.urljoin(scrape, '/') + url).replace("//","/").replace("http:/","http://")
                                    else:
                                        image_url = url
                                    images += [image_url]
                                elif image_url.strip('"')[0:4] == "http":
                                    image_url = image_url.strip('"').split('"', 1)[0]
                                    images += [image_url]
                                elif image_url.strip('"')[0:2] == "//":
                                    image_url = "http:" + image_url.strip('"').split('"', 1)[0]
                                    images += [image_url]
                                elif image_url[0] == "/":
                                    image_url = (urlparse.urljoin(scrape, '/') + image_url).replace("//","/").replace("http:/","http://")
                                
                                else:
                                    print "COULD BE NOT IMPLEMENTED: " + image_url
                                    image_url = (urlparse.urljoin(scrape, '/') + image_url).replace("//","/").replace("http:/","http://")
                                
                            
                            
                                try:
                                    req = urllib2.Request(image_url, headers={ 'User-Agent': 'Mozilla/5.0' })
                                    response  = urllib2.urlopen(req)
                                    image_data = response.read()
                                    
                                    try:
                                        i=Image.open(StringIO.StringIO(image_data))
                                        img_ext = i.format.lower()
                                        imagefilename = os.path.join(cache_folder,str(pages)+"."+img_ext)
                                        cache += [str(pages)+"."+img_ext]
                                        f = open(imagefilename + ".tmp", 'w')
                                        f.write(image_data)
                                        f.close
                                        # such that we do not het partial images...
                                        os.rename(imagefilename + ".tmp",imagefilename)
                                    except IOError:
                                        print "Web Comic: BrowseScraper: Not an image"
                                    # check if image?
                                    
                            
                        
                                except Exception, e:
                                    print str(e)
                            else:
                                pass # Match attempt failed
                    
                            print str(pages) + " NEXT PAGE"  + nextpage
                            np = nextpage.replace("?<link>","?P<link>")
                            np = np.replace('-','\-')
                            pat = re.compile(np)
                            n = pat.search(self.content)
                            next_url = ""
                            if n:
                                next_url = n.group(0).strip()
                                print "DFDDFDF" + next_url
                        
                                href = re.search(r'href="(.*?)"',next_url)
                            
                            
                                if href:
                                    url = href.group(0)[6:].split('"', 1)[0]
                                    if url[0:4] != 'http':
                                        next_url = (urlparse.urljoin(scrape, '/') + url).replace("//","/").replace("http:/","http://")
                                    else:
                                        next_url = url
                                    nextlist += [next_url]
                                elif next_url.strip('"')[0:4] == "http":
                                    next_url = next_url.strip('"').split('"', 1)[0]
                                    nextlist += [next_url]
                                elif next_url.strip('"')[0:2] == "//":
                                    next_url = "http:" + next_url.strip('"').split('"', 1)[0]
                                    nextlist += [next_url]
                                elif next_url[0] == "/":
                                    next_url = (urlparse.urljoin(scrape, '/') + next_url).replace("//","/").replace("http:/","http://")
                                else:
                                    lastpage = True
                                    print "NOT IMPLEMENTED"
                                    continue
                            else:
                                next_url = ""
                                print "HERE"
                            print next_url
                                
                        except Exception, e:
                            print str(e)
                            print "Web Comic: BrowseScraper: Failed to scrape page"
                            lastpage = True
                        if next_url == "": # or pages == 2:
                            lastpage = True
                        if scrape != next_url:
                            old_scrape = scrape
                            scrape = next_url
                        else:
                            lastpage = True

                        imagefilename = os.path.basename(imagefilename)
                        thefile = open(scraperfile, 'a')
                        
                        print mode
                        print image_url
                        print next_url
                        print imagefilename

                        if mode == 3 and next_url != "":
                            thefile.write(next_url + "\n")
                            mode = 0
                        
                        else:
                            thefile.write("[" + str(pages) + "]\n")
                            if image_url != "":
                                thefile.write(image_url + "\n")
                                if imagefilename != "":
                                    thefile.write(imagefilename + "\n")
                                    if next_url != "":
                                        thefile.write(next_url + "\n")
                                        lastpage = False
                        thefile.close()
                         

                elif type == "Url":
                    print "UrlScraper"
                    req = urllib2.Request(image_url, headers={ 'User-Agent': 'Mozilla/5.0' })
                    response  = urllib2.urlopen(req)
                    image_data = response.read()
                    
                    
                                                        
                    try:
                        i=Image.open(StringIO.StringIO(image_data))
                        img_ext = i.format.lower()
                        imagefilename = os.path.join(cache_folder,str(pages)+"."+img_ext)
                        cache += [str(pages)+"."+img_ext]
                        f = open(imagefilename + ".tmp", 'w')
                        f.write(image_data)
                        f.close
                        # such that we do not het partial images...
                        os.rename(imagefilename + ".tmp",imagefilename)
                    except IOError:
                        print "Web Comic: BrowseScraper: Not an image"
                elif type == "IndexScraper" or url[0] == "!":
                    print "IndexScraper"
                    print "NOT IMPLEMENTED"
        print cache
        return cache


    def getArchiveFilenameList( self ):
        out = []
        
        try:
            return self.readCBW()
        except Exception, e:
            print str(e)
            print "oops"
        
        return out


#------------------------------------------
# ComicArchive
#------------------------------------------


class ComicArchive:

    logo_data = None

    class ArchiveType:
        Zip, SevenZip, Rar, Folder, Pdf, Ebook, Tar, Web, Unknown = range(9)
    
    def __init__( self, path, rar_exe_path=None, default_image_path=None ):
        self.path = path
        self.rar_exe_path = rar_exe_path
        self.ci_xml_filename = 'ComicInfo.xml'
        self.comet_default_filename = 'CoMet.xml'
        self.has_epub = False
        self.resetCache()
        self.default_image_path = default_image_path

        # Use file extension to decide which archive test we do first
        ext = os.path.splitext(path)[1].lower()

        self.archive_type = self.ArchiveType.Unknown
        self.archiver = UnknownArchiver( self.path )

        # test all known types even if they have the wrong extension
        if ext == ".cbw":
            if self.webTest():
                self.archive_type =  self.ArchiveType.Web
                self.archiver = WebArchiver( self.path )

        elif ext == ".cbr" or ext == ".rar":
            if self.rarTest():
                self.archive_type =  self.ArchiveType.Rar
                self.archiver = RarArchiver( self.path, rar_exe_path=self.rar_exe_path )

            elif self.zipTest():
                self.archive_type =  self.ArchiveType.Zip
                self.archiver = ZipArchiver( self.path )

            elif self.sevenZipTest():
                self.archive_type = self.ArchiveType.SevenZip
                self.archiver = SevenZipArchiver( self.path )

            elif self.tarTest():
                self.archive_type = self.ArchiveType.Tar
                self.archiver = TarArchiver( self.path )
    
        elif ext == ".cbz" or ext == ".zip":
            if self.zipTest():
                self.archive_type = self.ArchiveType.Zip
                self.archiver = ZipArchiver( self.path )
            
            elif self.rarTest():
                self.archive_type =  self.ArchiveType.Rar
                self.archiver = RarArchiver( self.path, rar_exe_path=self.rar_exe_path )

            elif self.sevenZipTest():
                self.archive_type = self.ArchiveType.SevenZip
                self.archiver = SevenZipArchiver( self.path )

            elif self.tarTest():
                self.archive_type = self.ArchiveType.Tar
                self.archiver = TarArchiver( self.path )
                
        elif ext == ".cb7" or ext == ".7z":
            if self.sevenZipTest():
                self.archive_type = self.ArchiveType.SevenZip
                self.archiver = SevenZipArchiver( self.path )

            elif self.zipTest():
                self.archive_type = self.ArchiveType.Zip
                self.archiver = ZipArchiver( self.path )

            elif self.rarTest():
                self.archive_type =  self.ArchiveType.Rar
                self.archiver = RarArchiver( self.path, rar_exe_path=self.rar_exe_path )

            elif self.tarTest():
                self.archive_type = self.ArchiveType.Tar
                self.archiver = TarArchiver( self.path )

        elif ext == ".cbt" or ext == ".tar":
            if self.tarTest():
                self.archive_type = self.ArchiveType.Tar
                self.archiver = TarArchiver( self.path )

            elif self.zipTest():
                self.archive_type =  self.ArchiveType.Zip
                self.archiver = ZipArchiver( self.path )

            elif self.sevenZipTest():
                self.archive_type = self.ArchiveType.SevenZip
                self.archiver = SevenZipArchiver( self.path )

            elif self.rarTest():
                self.archive_type =  self.ArchiveType.Rar
                self.archiver = RarArchiver( self.path, rar_exe_path=self.rar_exe_path )

        elif ext == ".pdf":
            self.archive_type = self.ArchiveType.Pdf
            self.archiver = PdfArchiver(self.path)
        
        elif ext in ebook_extentions:
            if ext == ".epub":
                self.has_epub = True
            self.archive_type = self.ArchiveType.Ebook
            self.archiver = EbookArchiver(self.path)
        else:
            if self.zipTest():
                self.archive_type =  self.ArchiveType.Zip
                self.archiver = ZipArchiver( self.path )

            elif self.rarTest():
                self.archive_type =  self.ArchiveType.Rar
                self.archiver = RarArchiver( self.path, rar_exe_path=self.rar_exe_path )

            elif self.sevenZipTest():
                
                self.archive_type = self.ArchiveType.SevenZip
                self.archiver = SevenZipArchiver( self.path )

            elif self.tarTest():
                self.archive_type = self.ArchiveType.Tar
                self.archiver = TarArchiver( self.path )

        if ComicArchive.logo_data is None:
            #fname = ComicTaggerSettings.getGraphic('nocover.png')
            fname = self.default_image_path
            with open(fname, 'rb') as fd:
                ComicArchive.logo_data = fd.read()

    """
    Fingerprint a comic file
    """
    def fingerprint( self , sort=True):
        fp = []
        # FIX: if type == pdf or web... epub etc... we need another fingerprint
        if self.archive_type == self.ArchiveType.Ebook or self.archive_type == self.ArchiveType.Web or self.archive_type == self.ArchiveType.Pdf:
            return hashfile(self.path)
            # hash the complete file
        else:
            s = self.getNumberOfPages()
            fp += [str(s)]
            # hash all the pages sort them and hash that string :-)
            for page in range(0,s):
                fp += [hash(self.getPage(page))]
        if sort:
            return hash(str()+''.join(sorted(fp)))
        else:
            return hash(str()+''.join(fp))

    
    # Clears the cached data
    def resetCache( self ):
        self.has_cix = None
        self.has_cbi = None
        self.has_comet = None
        self.comet_filename = None
        self.page_count  = None
        self.page_list  = None
        self.cix_md  = None
        self.cbi_md  = None
        self.comet_md  = None

    def loadCache( self, style_list ):
        for style in style_list:
            self.readMetadata(style)

    def rename( self, path ):
        self.path = path
        self.archiver.path = path


    def zipTest( self ):
        return zipfile.is_zipfile( self.path )


    def webTest( self ):
        try:
            opf = open(self.path, 'r')
            cf = opf.read()
            tree = etree.fromstring(cf)
        except:
            return False
        return True
        
        
    def sevenZipTest( self ):
        try:
            Archive7z(open(self.path)).getnames()
        except:
            return False
        else: 
            return True


    def tarTest( self ):
        try:
            return tarfile.is_tarfile( self.path )
        except:
            return False
        else: 
            return True


    def rarTest( self ):
        try:
            rarc = rarfile.RarFile( self.path )
        except: # InvalidRARArchive:
            return False
        else:
            return True


    def isWeb( self ):
        return self.archive_type ==  self.ArchiveType.Web
    def isZip( self ):
        return self.archive_type ==  self.ArchiveType.Zip
    def isSevenZip( self ):
        return self.archive_type ==  self.ArchiveType.SevenZip
    def isRar( self ):
        return self.archive_type ==  self.ArchiveType.Rar
    def isPdf(self):
        return self.archive_type ==  self.ArchiveType.Pdf
    def isEbook(self):
        return self.archive_type ==  self.ArchiveType.Ebook
    def isTar(self):
        return self.archive_type ==  self.ArchiveType.Tar
    def isFolder( self ):
        return self.archive_type ==  self.ArchiveType.Folder

    def isWritable( self, check_rar_status=True ):
        if self.archive_type == self.ArchiveType.Unknown :
            return False

        elif check_rar_status and self.isRar() and self.rar_exe_path is None:
            return False

        elif self.isSevenZip():
            return False

        elif self.isPdf():
            return False

        elif self.isWeb():
            return False
            
        elif self.isBook():
            return False

        elif self.isTar():
            return False

        elif not os.access(self.path, os.W_OK):
            return False

        elif ((self.archive_type != self.ArchiveType.Folder) and
                (not os.access( os.path.dirname( os.path.abspath(self.path)), os.W_OK ))):
            return False

        return True

    def isWritableForStyle( self, data_style ):

        if self.isRar() and data_style == MetaDataStyle.CBI:
            return False

        return self.isWritable()

    def seemsToBeAComicArchive( self ):

        # Do we even care about extensions??
        ext = os.path.splitext(self.path)[1].lower()

        if (
              ( self.isZip() or self.isTar() or  self.isRar() or self.isPdf() or self.isEbook() or self.isSevenZip() or self.isFolder() )
              and
              ( self.getNumberOfPages() > 0)

            ):
            return True
        else:  #### FIX THIS!!!!
            if self.isWeb():
                self.getNumberOfPages()
                return True
            return False


    def readMetadata( self, style ):
        if style == MetaDataStyle.CIX:
            return self.readCIX()
        elif style == MetaDataStyle.CBI:
            return self.readCBI()
        elif style == MetaDataStyle.COMET:
            return self.readCoMet()
        elif style == MetaDataStyle.CALIBRE:
            return self.readCALIBRE()
        elif style == MetaDataStyle.CBW:
            return self.readCBWMeta()
        elif style == MetaDataStyle.EPUB:
            return self.readEPUB()
        else:
            return GenericMetadata()

    def writeMetadata( self, metadata, style ):
        retcode = None
        if style == MetaDataStyle.CIX:
            retcode = self.writeCIX( metadata )
        elif style == MetaDataStyle.CBI:
            retcode = self.writeCBI( metadata )
        elif style == MetaDataStyle.COMET:
            retcode = self.writeCoMet( metadata )
        return retcode


    def hasMetadata( self, style ):
        if style == MetaDataStyle.CIX:
            return self.hasCIX()
        elif style == MetaDataStyle.CBI:
            return self.hasCBI()
        elif style == MetaDataStyle.COMET:
            return self.hasCoMet()
        elif style == MetaDataStyle.CBW:
            return self.hasCBW()
        elif style == MetaDataStyle.CALIBRE:
            return self.hasCALIBRE()
        elif style == MetaDataStyle.EPUB:
            return self.hasEPUB()

        else:
            return False

    def removeMetadata( self, style ):
        retcode = True
        if style == MetaDataStyle.CIX:
            retcode = self.removeCIX()
        elif style == MetaDataStyle.CBI:
            retcode = self.removeCBI()
        elif style == MetaDataStyle.COMET:
            retcode = self.removeCoMet()
        return retcode

    def getPage( self, index , error_img=None):
        # very bad handling of missing...

        image_data = None

        filename = self.getPageName( index )
       
        if filename is not None:
            try:

                image_data = self.archiver.readArchiveFile( filename )
            except IOError:
                # "HERE FIX also return error!
                print >> sys.stderr, u"Error reading in page.  Substituting missing page."
                if error_img:
                    image_data = error_img
                else:
                    image_data = ComicArchive.logo_data
        try:
                Image.open(StringIO.StringIO(image_data))
        except IOError:
            # "HERE FIX also return error!
            print >> sys.stderr, u"Error reading in page.  Substituting missing page."
            if error_img:
                image_data = error_img
            else:
                image_data = ComicArchive.logo_data
        return image_data

    def getPageName( self, index ):

        if index is None:
            return None

        page_list = self.getPageNameList()

        num_pages = len( page_list )
        if num_pages == 0 or index >= num_pages:
            return None

        return  page_list[index]

    def getScannerPageIndex( self ):

        scanner_page_index = None

        #make a guess at the scanner page
        name_list = self.getPageNameList()
        count = self.getNumberOfPages()

        #too few pages to really know
        if count < 5:
            return None

        # count the length of every filename, and count occurences
        length_buckets = dict()
        for name in name_list:
            fname =  os.path.split(name)[1]
            length = len(fname)
            if length_buckets.has_key( length ):
                length_buckets[ length ] += 1
            else:
                length_buckets[ length ] = 1

        # sort by most common
        sorted_buckets = sorted(length_buckets.iteritems(), key=lambda (k,v): (v,k), reverse=True)

        # statistical mode occurence is first
        mode_length = sorted_buckets[0][0]

        # we are only going to consider the final image file:
        final_name = os.path.split(name_list[count-1])[1]

        common_length_list = list()
        for name in name_list:
            if len(os.path.split(name)[1]) == mode_length:
                common_length_list.append( os.path.split(name)[1] )

        prefix = os.path.commonprefix(common_length_list)

        if mode_length <= 7 and prefix == "":
            #probably all numbers
            if len(final_name) > mode_length:
                scanner_page_index = count-1

        # see if the last page doesn't start with the same prefix as most others
        elif not final_name.startswith(prefix):
            scanner_page_index = count-1

        return scanner_page_index


    def getPageNameList( self , sort_list=True):

        if self.page_list is None:
            # get the list file names in the archive, and sort
            files = self.archiver.getArchiveFilenameList()
            # seems like some archive creators are on  Windows, and don't know about case-sensitivity!
            if sort_list:
                def keyfunc(k):
                    #hack to account for some weird scanner ID pages
                    #basename=os.path.split(k)[1]
                    #if basename < '0':
                    #	k = os.path.join(os.path.split(k)[0], "z" + basename)
                    return k.lower()
                # try:
                    files = natsorted(files, key=keyfunc,signed=False)
                # except:
                #     # "HERE FIX patch ...bug with strange encoding... should we check zip/rar/etc files for encoding?
                #     try:
                #         files = natsorted([i.decode('windows-1252') for i in files], key=keyfunc,signed=False)
                #     except:
                #         print "COMIC ERROR: FILES NOT SORTED"
                #         return files

            # make a sub-list of image files
            self.page_list = []
            for name in files:
                if ( name[-4:].lower() in ImageExtensions and os.path.basename(name)[0] != "." ):
                    self.page_list.append(name)

        return self.page_list

    def getNumberOfPages( self ):
        if self.page_count is None:
            self.page_count = len( self.getPageNameList( ) )
        return self.page_count

    def readCBI( self ):
        if self.cbi_md is None:
            raw_cbi = self.readRawCBI()
            if raw_cbi is None:
                self.cbi_md = GenericMetadata()
            else:
                self.cbi_md = ComicBookInfo().metadataFromString( raw_cbi )

            self.cbi_md.setDefaultPageList( self.getNumberOfPages() )

        return self.cbi_md

    def readRawCBI( self ):
        if ( not self.hasCBI() ):
            return None

        return self.archiver.getArchiveComment()

    def hasCBI(self):
        if self.has_cbi is None:

            #if ( not ( self.isZip() or self.isRar()) or not self.seemsToBeAComicArchive() ):
            if not self.seemsToBeAComicArchive() or self.isWeb() or self.isPdf() or self.isEbook():
                self.has_cbi = False
            else:
                comment = self.archiver.getArchiveComment()
                self.has_cbi = ComicBookInfo().validateString( comment )

        return self.has_cbi

    def writeCBI( self, metadata ):
        if metadata is not None:
            self.applyArchiveInfoToMetadata( metadata )
            cbi_string = ComicBookInfo().stringFromMetadata( metadata )
            write_success =  self.archiver.setArchiveComment( cbi_string )
            if write_success:
                self.has_cbi = True
                self.cbi_md = metadata
            self.resetCache()
            return write_success
        else:
            return False

    def removeCBI( self ):
        if self.hasCBI():
            write_success = self.archiver.setArchiveComment( "" )
            if write_success:
                self.has_cbi = False
                self.cbi_md = None
            self.resetCache()
            return write_success
        return True


    def readCALIBRE( self ):
    
        def readEPUBMeta( fname ):
            ns = {
                'n':'urn:oasis:names:tc:opendocument:xmlns:container',
                'pkg':'http://www.idpf.org/2007/opf',
                'dc':'http://purl.org/dc/elements/1.1/'
            }

            # prepare to read from the .epub file
            #zip = zipfile.ZipFile(fname)

            # find the contents metafile
            #txt = zip.read('META-INF/container.xml')
            #tree = etree.fromstring(txt)
            #cfname = tree.xpath('n:rootfiles/n:rootfile/@full-path',namespaces=ns)[0]

            # grab the metadata block from the contents metafile
            opf = open(fname, 'r')
            cf = opf.read()
            tree = etree.fromstring(cf)
            p = tree.xpath('/pkg:package/pkg:metadata',namespaces=ns)[0]

            # repackage the data
            res = {}
            for s in ['title','language','creator','date','identifier','publisher','description']:
                ex = p.xpath('dc:%s/text()'%(s),namespaces=ns)
                if ex != []:
                    res[s] = ex[0]
            return res
        
        metadata = GenericMetadata()
        try:
            meta = readEPUBMeta( os.path.join(os.path.dirname(self.path),'metadata.opf') )
            metadata.title = meta.get('title')
            metadata.publisher = meta.get('publisher')
            metadata.language = meta.get('language')
            metadata.identifier = meta.get('identifier')
            if meta.get('description') is not None:
                metadata.comments = re.sub("<.*?>", " ", meta.get('description'))
            if meta.get('creator') is not None:
                metadata.addCredit( meta.get('creator') , 'writer'  )
            metadata.isEmpty = False
        except:
            print  >> sys.stderr, u"Error reading in raw EPUB meta!"
        return metadata
  
    def hasCALIBRE(self):
        return os.path.isfile(os.path.join(os.path.dirname(self.path),'metadata.opf'))


    def hasCBW(self):
        cbw = os.path.isfile(self.path) and os.path.splitext(self.path)[1].lower() == ".cbw"
        if cbw:
            root = ET.parse(self.path).find('Info')
            if root is None:
                return False
            return True
        return False
    
    
    def readCBWMeta(self):

        root = ET.parse(self.path).find('Info')
        
        metadata = GenericMetadata()
        md = metadata

        # Helper function
        def xlate( tag ):
            node = root.find( tag )
            if node is not None:
                return node.text
            else:
                return None
                
        md.series =           xlate( 'Series' )
        md.title =            xlate( 'Title' )
        md.issue =            xlate( 'Number' )
        md.issueCount =       xlate( 'Count' )
        md.volume =           xlate( 'Volume' )
        md.alternateSeries =  xlate( 'AlternateSeries' )
        md.alternateNumber =  xlate( 'AlternateNumber' )
        md.alternateCount =   xlate( 'AlternateCount' )
        md.comments =         xlate( 'Summary' )
        md.notes =            xlate( 'Notes' )
        md.year =             xlate( 'Year' )
        md.month =            xlate( 'Month' )
        md.day =              xlate( 'Day' )
        md.publisher =        xlate( 'Publisher' )
        md.imprint =          xlate( 'Imprint' )
        md.genre =            xlate( 'Genre' )
        md.webLink =          xlate( 'Web' )
        md.language =         xlate( 'LanguageISO' )
        md.format =           xlate( 'Format' )
        md.manga =            xlate( 'Manga' )
        md.characters =       xlate( 'Characters' )
        md.teams =            xlate( 'Teams' )
        md.locations =        xlate( 'Locations' )
        md.pageCount =        xlate( 'PageCount' )
        md.scanInfo =         xlate( 'ScanInformation' )
        md.storyArc =         xlate( 'StoryArc' )
        md.seriesGroup =      xlate( 'SeriesGroup' )
        md.maturityRating =   xlate( 'AgeRating' )

        tmp = xlate( 'BlackAndWhite' )
        md.blackAndWhite = False
        if tmp is not None and tmp.lower() in [ "yes", "true", "1" ]:
            md.blackAndWhite = True
        # Now extract the credit info
        for n in root:
            if (  n.tag == 'Writer' or 
                n.tag == 'Penciller' or
                n.tag == 'Inker' or
                n.tag == 'Colorist' or
                n.tag == 'Letterer' or
                n.tag == 'Editor' 
            ):
                if n.text is not None:
                    for name in n.text.split(','):
                        metadata.addCredit( name.strip(), n.tag )

            if n.tag == 'CoverArtist':
                if n.text is not None:
                    for name in n.text.split(','):
                        metadata.addCredit( name.strip(), "Cover" )

        # parse page data now	
        pages_node = root.find( "Pages" )
        if pages_node is not None:        	
            for page in pages_node:
                metadata.pages.append( page.attrib )
                #print page.attrib

        metadata.isEmpty = False

        print "HERExddd"
        cache_location = config['format.webcomic']['location']
        if cache_location == "" or not os.path.exists(cache_location):
            cache_location = AppFolders.appWebComic()
        cache_folder = os.path.join(cache_location,os.path.basename(self.path))
        ext = os.path.splitext(self.path)[1].lower()
        if ext == ".cbw":
            cache_folder = cache_folder[:-4]
      
        if not os.path.isdir(cache_folder):
            return metadata

        scraperfile = os.path.join(cache_folder,"WebComicBrowseScraperIndex.txt")

        # read filename from file...

        if os.path.isfile(scraperfile):
            item_page = 1
            last_page = 1
            try:
                with open(scraperfile) as f:
                    for line in (line for line in f if line.rstrip('\n')):
                        if line[0] == '[':
                            item_page_tmp = int(line[1:-2])
                            last_page = item_page
                            item_page = item_page_tmp
            except:
                print "Web Comic: BrowseScraper: Warning"
                md.pageCount = last_page
            md.pageCount = item_page
        else:
            md.pageCount = 1
        return metadata


    def readEPUB( self ):
        
        def readEPUBMeta( fname ):
            ns = {
                'n':'urn:oasis:names:tc:opendocument:xmlns:container',
                'pkg':'http://www.idpf.org/2007/opf',
                'dc':'http://purl.org/dc/elements/1.1/'
            }

            # prepare to read from the .epub file
            zip = zipfile.ZipFile(fname)

            # find the contents metafile
            txt = zip.read('META-INF/container.xml')
            tree = etree.fromstring(txt)
            cfname = tree.xpath('n:rootfiles/n:rootfile/@full-path',namespaces=ns)[0]

            # grab the metadata block from the contents metafile
            cf = zip.read(cfname)
            tree = etree.fromstring(cf)
            p = tree.xpath('/pkg:package/pkg:metadata',namespaces=ns)[0]

            # repackage the data
            #print cf.decode('UTF8')
            res = {}
            for s in ['title','language','creator','date','identifier','publisher','description']:
                ex = p.xpath('dc:%s/text()'%(s),namespaces=ns)
                if ex != []:
                    res[s] = ex[0]
            return res
        
        metadata = GenericMetadata()
        try:
            meta = readEPUBMeta( self.path )
            metadata.title = meta.get('title')
            metadata.publisher = meta.get('publisher')
            metadata.language = meta.get('language')
            metadata.identifier = meta.get('identifier')
            if meta.get('description') is not None:
                metadata.comments = re.sub("<.*?>", " ", meta.get('description'))
            if meta.get('creator') is not None:
                metadata.addCredit( meta.get('creator') , 'writer'  )
            metadata.isEmpty = False
        except:
            print  >> sys.stderr, u"Error reading in raw EPUB meta!"
        return metadata
  
    def hasEPUB(self):
        if self.has_epub is None:
            return False
        else:
            return True

    def readCIX( self ):
        if self.cix_md is None:
            raw_cix = self.readRawCIX()
            if raw_cix is None or raw_cix == "":
                self.cix_md = GenericMetadata()
            else:
                self.cix_md = ComicInfoXml().metadataFromString( raw_cix )

            #validate the existing page list (make sure count is correct)
            if len ( self.cix_md.pages ) !=  0 :
                if len ( self.cix_md.pages ) != self.getNumberOfPages():
                    # pages array doesn't match the actual number of images we're seeing
                    # in the archive, so discard the data
                    self.cix_md.pages = []

            if len( self.cix_md.pages ) == 0:
                self.cix_md.setDefaultPageList( self.getNumberOfPages() )

        return self.cix_md

    def readRawCIX( self ):
        if not self.hasCIX():
            return None
        try:
            raw_cix = self.archiver.readArchiveFile( self.ci_xml_filename )
        except IOError:
            print  >> sys.stderr, u"Error reading in raw CIX!"
            raw_cix = ""
        return  raw_cix

    def writeCIX(self, metadata):

        if metadata is not None:
            self.applyArchiveInfoToMetadata( metadata, calc_page_sizes=True )
            cix_string = ComicInfoXml().stringFromMetadata( metadata )
            write_success = self.archiver.writeArchiveFile( self.ci_xml_filename, cix_string )
            if write_success:
                self.has_cix = True
                self.cix_md = metadata
            self.resetCache()
            return write_success
        else:
            return False

    def removeCIX( self ):
        if self.hasCIX():
            write_success = self.archiver.removeArchiveFile( self.ci_xml_filename )
            if write_success:
                self.has_cix = False
                self.cix_md = None
            self.resetCache()
            return write_success
        return True


    def hasCIX(self):
        if self.has_cix is None:

            if not self.seemsToBeAComicArchive() or self.isWeb() or self.isPdf() or self.isEbook():
                self.has_cix = False
            elif self.ci_xml_filename in self.archiver.getArchiveFilenameList():
                self.has_cix = True
            else:
                self.has_cix = False
        return self.has_cix


    def readCoMet( self ):
        if self.comet_md is None:
            raw_comet = self.readRawCoMet()
            if raw_comet is None or raw_comet == "":
                self.comet_md = GenericMetadata()
            else:
                self.comet_md = CoMet().metadataFromString( raw_comet )

            self.comet_md.setDefaultPageList( self.getNumberOfPages() )
            #use the coverImage value from the comet_data to mark the cover in this struct
            # walk through list of images in file, and find the matching one for md.coverImage
            # need to remove the existing one in the default
            if self.comet_md.coverImage is not None:
                cover_idx = 0
                for idx,f in enumerate(self.getPageNameList()):
                    if self.comet_md.coverImage == f:
                        cover_idx = idx
                        break
                if cover_idx != 0:
                    del (self.comet_md.pages[0]['Type'] )
                    self.comet_md.pages[ cover_idx ]['Type'] = PageType.FrontCover

        return self.comet_md

    def readRawCoMet( self ):
        if not self.hasCoMet():
            print >> sys.stderr, self.path, "doesn't have CoMet data!"
            return None

        try:
            raw_comet = self.archiver.readArchiveFile( self.comet_filename )
        except IOError:
            print >> sys.stderr, u"Error reading in raw CoMet!"
            raw_comet = ""
        return  raw_comet

    def writeCoMet(self, metadata):

        if metadata is not None:
            if not self.hasCoMet():
                self.comet_filename = self.comet_default_filename

            self.applyArchiveInfoToMetadata( metadata )
            # Set the coverImage value, if it's not the first page
            cover_idx = int(metadata.getCoverPageIndexList()[0])
            if cover_idx != 0:
                metadata.coverImage = self.getPageName( cover_idx )

            comet_string = CoMet().stringFromMetadata( metadata )
            write_success = self.archiver.writeArchiveFile( self.comet_filename, comet_string )
            if write_success:
                self.has_comet = True
                self.comet_md = metadata
            self.resetCache()
            return write_success
        else:
            return False

    def removeCoMet( self ):
        if self.hasCoMet():
            write_success = self.archiver.removeArchiveFile( self.comet_filename )
            if write_success:
                self.has_comet = False
                self.comet_md = None
            self.resetCache()
            return write_success
        return True

    def hasCoMet(self):
        if self.has_comet is None:
            self.has_comet = False
            if not self.seemsToBeAComicArchive() or self.isWeb() or self.isPdf() or self.isEbook():
                return self.has_comet

            #look at all xml files in root, and search for CoMet data, get first
            for n in self.archiver.getArchiveFilenameList():
                if ( os.path.dirname(n) == "" and
                    os.path.splitext(n)[1].lower() == '.xml'):
                    # read in XML file, and validate it
                    try:
                        data = self.archiver.readArchiveFile( n )
                    except:
                        data = ""
                        print >> sys.stderr, u"Error reading in Comet XML for validation!"
                    if CoMet().validateString( data ):
                        # since we found it, save it!
                        self.comet_filename = n
                        self.has_comet = True
                        break

            return self.has_comet



    def applyArchiveInfoToMetadata( self, md, calc_page_sizes=False):
        md.pageCount = self.getNumberOfPages()

        if calc_page_sizes:
            for p in md.pages:
                idx = int( p['Image'] )
                if pil_available:
                    if 'ImageSize' not in p or 'ImageHeight' not in p or 'ImageWidth' not in p:
                        data = self.getPage( idx )
                        if data is not None:
                            try:
                                im = Image.open(StringIO.StringIO(data))
                                w,h = im.size

                                p['ImageSize'] = str(len(data))
                                p['ImageHeight'] = str(h)
                                p['ImageWidth'] = str(w)
                            except IOError:
                                p['ImageSize'] = str(len(data))

                else:
                    if 'ImageSize' not in p:
                        data = self.getPage( idx )
                        p['ImageSize'] = str(len(data))



    def metadataFromFilename( self , parse_scan_info=True):

        metadata = GenericMetadata()

        fnp = FileNameParser()
        fnp.parseFilename( self.path )

        if fnp.issue != "":
            metadata.issue = fnp.issue
        if fnp.series != "":
            metadata.series = fnp.series
        if fnp.volume != "":
            metadata.volume = fnp.volume
        if fnp.year != "":
            metadata.year = fnp.year
        if fnp.issue_count != "":
            metadata.issueCount = fnp.issue_count
        if parse_scan_info:
            if fnp.remainder != "":
                metadata.scanInfo = fnp.remainder

        metadata.isEmpty = False

        return metadata

    def exportAsZip( self, zipfilename ):
        if self.archive_type == self.ArchiveType.Zip:
            # nothing to do, we're already a zip
            return True

        zip_archiver = ZipArchiver( zipfilename )
        return zip_archiver.copyFromArchive( self.archiver )