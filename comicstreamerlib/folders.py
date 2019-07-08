import os
import sys
import platform
import logging

appname = 'ComicStreamer'

from options import Options

class AppFolders():
    
    @staticmethod
    def makeFolders():
        def make(folder):
            if not os.path.exists(folder):
                os.makedirs(folder)
        make(AppFolders.logs())
        make(AppFolders.settings())
        make(AppFolders.appData())
        make(AppFolders.appCachePages())
        make(AppFolders.appBlacklistPages())
        make(AppFolders.appCacheEbooks())
        make(AppFolders.appWebComic())
    
    @staticmethod
    def runningAtRoolLevel():
        return False
    
    @staticmethod
    def windowsAppDataFolder():
        return os.environ['APPDATA']

    @staticmethod
    def userFolder():
        opts = Options()
        opts.parseCmdLineArgs(False)
        
        filename_encoding = sys.getfilesystemencoding()

        if opts.user_dir is not None:
            folder = opts.user_dir
        elif platform.system() == "Windows":
            folder = os.path.join( AppFolders.windowsAppDataFolder(), appname )
        elif platform.system() == "Darwin":
            folder = os.path.join( os.path.expanduser('~') , 'Library/Application Support/'+appname)
        else:
            folder = os.path.join( os.path.expanduser('~') , '.'+appname)
            
        if folder is not None:
            folder = folder.decode(filename_encoding)
        return folder
        
    @staticmethod
    def appBase():
        encoding = sys.getfilesystemencoding()
        if getattr(sys, 'frozen', None):
            if platform.system() == "Darwin":
                return sys._MEIPASS
            else: # Windows
                return os.path.dirname( os.path.abspath( unicode(sys.executable, encoding) ) )
        else:
            return os.path.dirname( os.path.abspath(unicode(__file__, encoding)) )

    @staticmethod
    def logs():
        if AppFolders.runningAtRoolLevel():
            if platform.system() == "Windows":
                folder = os.path.join( AppFolders.windowsAppDataFolder(), appname )
            else:
                folder = "/var/log/"+appname
        else:
            folder = os.path.join(AppFolders.userFolder(), "logs")
        return folder
    
    @staticmethod
    def settings():
        if AppFolders.runningAtRoolLevel():
            if platform.system() == "Windows":
                folder = os.path.join( AppFolders.windowsAppDataFolder(), appname )
            elif platform.system() == "Darwin":
                folder = os.path.join( '/Library/Application Support/'+appname)
            else:
                folder = "/etc/"+appname
        else:
            folder = os.path.join(AppFolders.userFolder())
        return folder
    
    @staticmethod
    def appData():
        if AppFolders.runningAtRoolLevel():
            if platform.system() == "Windows":
                folder = os.path.join( AppFolders.windowsAppDataFolder(), appname )
            elif platform.system() == "Darwin":
                folder = os.path.join( '/Library/Application Support/'+appname)
            else:
                folder = "/var/lib/"+appname
        else:
            folder = os.path.join(AppFolders.userFolder())
        return folder


    @staticmethod
    def appWebComic():
        return os.path.join(AppFolders.appData(), "webcomic")

    @staticmethod
    def appCachePages():
        return os.path.join(AppFolders.appData(), "cache", "pages")

    @staticmethod
    def appCacheEbooks():
        return os.path.join(AppFolders.appData(), "cache", "ebooks")

    @staticmethod
    def appBlacklistPages():
        return os.path.join(AppFolders.appData(), "blacklist")


    @staticmethod
    def static():
        return os.path.join(AppFolders.appBase(), "static")
    

    @staticmethod
    def missingPath(filename):
        return os.path.join(AppFolders.appBase(), "static", "images", "missing", filename)
    
    @staticmethod
    def imagePath(filename):
        return os.path.join(AppFolders.appBase(), "static", "images", filename)

    @staticmethod
    def iconsPath(filename):
        return os.path.join(AppFolders.appBase(), "static", "icons", filename)
