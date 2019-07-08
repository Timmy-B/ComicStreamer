#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import date
import tornado.escape
import tornado.ioloop
import tornado.web
import urllib
import mimetypes
import re
import threading

from urllib2 import quote


from sqlalchemy import desc
from sqlalchemy.orm import joinedload,subqueryload,aliased
from sqlalchemy.sql.expression import func, select

import json
import pprint
import mimetypes
from PIL import Image
try:
    from PIL import WebPImagePlugin
except:
    pass


import StringIO
import gzip
import dateutil.parser
import logging
import logging.handlers
import imghdr
import random
import signal
import sys
import socket
import webbrowser
import time

from comicapi.comicarchive import *

import csversion
import utils
from database import *
from monitor import Monitor
from config import ComicStreamerConfig
from folders import AppFolders
from options import Options
from bonjour import BonjourThread
from bookmark import Bookmark
from blacklist import Blacklist
from library import Library

# add webp test to imghdr in case it isn't there already
def my_test_webp(h, f):
    if h.startswith(b'RIFF') and h[8:12] == b'WEBP':
        return 'webp'
imghdr.tests.append(my_test_webp)


# to allow a blank username
def fix_username(username):
    return  username + "ComicStreamer"

def custom_get_current_user(handler):
    user = handler.get_secure_cookie("user")
    if user:
        user = fix_username(user)
    return  user

# you can change default root here :-)
def deviceroot(s):
    if(re.search('(iPhone|iPod).*', s.request.headers["User-Agent"])):
        return "default/"
    elif(re.search('(Android).*', s.request.headers["User-Agent"])):
        return "default/"
    elif(re.search('(iPad).*', s.request.headers["User-Agent"])):
        return "default/"
    else:
        return "default/"

class BaseHandler(tornado.web.RequestHandler):

    @property
    def webroot(self):
        return self.application.webroot
        
    @property
    def library(self):
        return self.application.library

    @property
    def port(self):
        return self.application.port


    def get_current_user(self):
        return custom_get_current_user(self)
    
class GenericAPIHandler(BaseHandler):
    def validateAPIKey(self):
        if self.application.config['security']['use_api_key']:
            api_key = self.get_argument(u"api_key", default="")
            if api_key == self.application.config['security']['api_key']:
                return True
            else:
                raise tornado.web.HTTPError(400)
                return False
    

class JSONResultAPIHandler(GenericAPIHandler):
    def setContentType(self):
        self.add_header("Content-type","application/json; charset=UTF-8")

    def processPagingArgs(self, query):
        per_page = self.get_argument(u"per_page", default=None)
        offset = self.get_argument(u"offset", default=None)
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

        
    def processComicQueryArgs(self, query):
        def hasValue(obj):
            return obj is not None and obj != ""
        
        keyphrase_filter = self.get_argument(u"keyphrase", default=None)
        series_filter = self.get_argument(u"series", default=None)
        path_filter = self.get_argument(u"path", default=None)
        folder_filter = self.get_argument(u"folder", default="")
        title_filter = self.get_argument(u"title", default=None)
        start_filter = self.get_argument(u"start_date", default=None)
        end_filter = self.get_argument(u"end_date", default=None)
        added_since = self.get_argument(u"added_since", default=None)
        modified_since = self.get_argument(u"modified_since", default=None)
        lastread_since = self.get_argument(u"lastread_since", default=None)
        order = self.get_argument(u"order", default=None)
        character = self.get_argument(u"character", default=None)
        team = self.get_argument(u"team", default=None)
        location = self.get_argument(u"location", default=None)
        storyarc = self.get_argument(u"storyarc", default=None)
        alternateseries = self.get_argument(u"alternateseries", default=None)
        volume = self.get_argument(u"volume", default=None)
        publisher = self.get_argument(u"publisher", default=None)
        language = self.get_argument(u"language", default=None)
        credit_filter = self.get_argument(u"credit", default=None)
        tag = self.get_argument(u"tag", default=None)
        genre = self.get_argument(u"genre", default=None)


        if folder_filter != "":
            folder_filter = os.path.normcase(os.path.normpath(folder_filter))
            #print folder_filter
        
        person = None
        role = None
        if hasValue(credit_filter):
            credit_info = credit_filter.split(":")
            if len(credit_info[0]) != 0:
                person = credit_info[0] 
                if len(credit_info) > 1:
                    role = credit_info[1]

        if hasValue(person):
            query = query.join(Credit).filter(Person.name.ilike(person.replace("*","%"))).filter(Credit.person_id==Person.id)
            if role is not None:
                query = query.filter(Credit.role_id==Role.id).filter(Role.name.ilike(role.replace("*","%")))
            #query = query.filter( Comic.persons.contains(unicode(person).replace("*","%") ))
        
        if hasValue(keyphrase_filter):
            keyphrase_filter = unicode(keyphrase_filter).replace("*","%")
            keyphrase_filter = "%" + keyphrase_filter + "%"
            query = query.filter( Comic.series.ilike(keyphrase_filter)
                                | Comic.alternateseries_raw.any(AlternateSeries.name.ilike(keyphrase_filter))
                                | Comic.title.ilike(keyphrase_filter)
                                | Comic.publisher.ilike(keyphrase_filter)
                                | Comic.language.ilike(keyphrase_filter)
                                | Comic.path.ilike(keyphrase_filter)
                                | Comic.comments.ilike(keyphrase_filter)
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
        query = addQueryOnScalar(query, Comic.language, language)
        query = addQueryOnList(query, Comic.alternateseries_raw, AlternateSeries.name, alternateseries)
        query = addQueryOnList(query, Comic.characters_raw, Character.name, character)
        query = addQueryOnList(query, Comic.generictags_raw, GenericTag.name, tag)
        query = addQueryOnList(query, Comic.teams_raw, Team.name, team)
        query = addQueryOnList(query, Comic.locations_raw, Location.name, location)
        query = addQueryOnList(query, Comic.storyarcs_raw, StoryArc.name, storyarc)
        query = addQueryOnList(query, Comic.genres_raw, Genre.name, genre)
        
        #if hasValue(series_filter):
        #    query = query.filter( Comic.series.ilike(unicode(series_filter).replace("*","%") ))
        #if hasValue(title_filter):
        #    query = query.filter( Comic.title.ilike(unicode(title_filter).replace("*","%") ))
        #if hasValue(filename_filter):
        #    query = query.filter( Comic.path.ilike(unicode(filename_filter).replace("*","%") ))
        #if hasValue(publisher):
        #    query = query.filter( Comic.publisher.ilike(unicode(publisher).replace("*","%") ))
        #if hasValue(character):
        #    query = query.filter( Comic.characters_raw.any(Character.name.ilike(unicode(character).replace("*","%") )))
        #if hasValue(tag):
        #    query = query.filter( Comic.generictags.contains(unicode(tag).replace("*","%") ))
        #if hasValue(team):
        #    query = query.filter( Comic.teams.contains(unicode(team).replace("*","%") ))
        #if hasValue(location):
        #    query = query.filter( Comic.locations.contains(unicode(location).replace("*","%") ))
        #if hasValue(storyarc):
        #    query = query.filter( Comic.storyarcs.contains(unicode(storyarc).replace("*","%") ))
        #if hasValue(genre):
        #    query = query.filter( Comic.genres.contains(unicode(genre).replace("*","%") ))
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
                query = query.filter( Comic.date >= dt)
            except:
                pass
        
        if hasValue(end_filter):
            try:
                dt = dateutil.parser.parse(end_filter)
                query = query.filter( Comic.date <= dt)
            except:
                pass
            
        if hasValue(modified_since):
            try:
                dt=dateutil.parser.parse(modified_since)
                resultset = resultset.filter( Comic.mod_ts >= dt )
            except:
                pass

        if hasValue(added_since):
            try:
                dt=dateutil.parser.parse(added_since)
                query = query.filter( Comic.added_ts >= dt )
            except:
                pass
        
        if hasValue(lastread_since):
            try:
                dt=dateutil.parser.parse(lastread_since)
                query = query.filter( Comic.lastread_ts >= dt, Comic.lastread_ts != "" )
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
            if order == "id":
                order_key = Comic.id                
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
            elif order == "issue":
                order_key = Comic.issue_num
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
    
class ZippableAPIHandler(JSONResultAPIHandler):

    def writeResults(self, json_data):
        self.setContentType()
        if self.get_argument(u"gzip", default=None) is not None:
            self.add_header("Content-Encoding","gzip")
            # TODO: make sure browser can handle gzip?
            zbuf = StringIO.StringIO()
            zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 9)
            zfile.write(json.dumps(json_data))
            zfile.close()
    
            self.write(zbuf.getvalue())
        else:
            self.write(json_data)       

class ServerAPIHandler(GenericAPIHandler):
    def get(self):
        self.validateAPIKey()
        cmd = self.get_argument(u"cmd", default=None)
        if cmd == "restart":
            logging.info("Server: Restart")
            self.application.restart()
        elif cmd == "reset":
            logging.info("Server: Rebuild Database")
            self.application.rebuild()
        elif cmd == "stop":
            logging.info("Server: Stop")
            self.application.shutdown()
        elif cmd == "cache":
            logging.info("Server: Clear Pages Cache")
            self.application.library.cache_clear()
            
class ImageAPIHandler(GenericAPIHandler):
    def setContentType(self, image_data):
        
        imtype = imghdr.what(StringIO.StringIO(image_data))
        self.add_header("Content-type","image/{0}".format(imtype))

            
class VersionAPIHandler(JSONResultAPIHandler):
    def get(self):
        self.validateAPIKey()
        response = { 'version': self.application.version,
                    'last_build':  date.today().isoformat() }
        self.setContentType()
        self.write(response)

class DBInfoAPIHandler(JSONResultAPIHandler):
    def get(self):
        self.validateAPIKey()
        stats = self.library.getStats()
        if mysql_active:
            s = "MySQL"
        else:
            s = "SQLite"
        response = {'id'            : stats['uuid'],
                    'last_updated'  : stats['last_updated'].isoformat(),
                    'created'       : stats['created'].isoformat(),
                    'comic_count'   : stats['total'],
                    'series_count'  : stats['series'],
                    'artists_count' : stats['persons'],
                    'cache_active'  : self.library.cache_active,
                    'cache_filled'  : self.library.cache_filled / 1048576,
                    'cache_pages'   : len(self.library.cache_list),
                    'cache_miss'    : self.library.cache_miss,
                    'cache_hit'     : self.library.cache_hit,
                    'cache_discard' : self.library.cache_discard,
                    'cache_max'     : self.library.cache_maxsize,
                    'db_engine'     : s,
                    'db_scheme'     : SCHEMA_VERSION
                    }
        self.setContentType()
        self.write(response)
        
class ScanStatusAPIHandler(JSONResultAPIHandler):
    def get(self):
        self.validateAPIKey()
        status = self.application.monitor.status
        detail = self.application.monitor.statusdetail
        last_complete = self.application.monitor.scancomplete_ts
        
        response = { 'status': status,
                     'detail':  detail,
                     'last_complete':  last_complete,
                     'current_time':  int(time.mktime(datetime.utcnow().timetuple()) * 1000),
                    }
        self.setContentType()
        self.write(response)


class ComicListAPIHandler(ZippableAPIHandler):
    def get(self):
        self.validateAPIKey()

        criteria_args = [
            u"keyphrase", u"series", u"path", u"folder", u"title", u"start_date",
            u"end_date", u"added_since", u"modified_since", u"lastread_since",
            u"order", u"character", u"team", u"location", u"storyarc", u"volume",
            u"publisher", u"language", u"credit", u"tag", u"genre", u"alternateseries"
        ]

        criteria = {key: self.get_argument(key, default=None) for key in criteria_args}
        paging = {
            'per_page': self.get_argument(u"per_page", default=None),
            'offset': self.get_argument(u"offset", default=None)
        }

        resultset, total_results = self.library.list(criteria, paging)

        json_data = resultSetToJson(resultset, "comics", total_results)
        
        self.writeResults(json_data)    

class DeletedAPIHandler(ZippableAPIHandler):
    def get(self):
        self.validateAPIKey()

        since_filter = self.get_argument(u"since", default=None)
        resultset = self.library.getDeletedComics(since_filter)

        json_data = resultSetToJson(resultset, "deletedcomics")
                
        self.writeResults(json_data)    

class ComicListBrowserHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):

        entity_src = self.get_argument(u"entity_src", default=None)
        if entity_src is not None:
            src=entity_src
        else:
            default_src=self.webroot + "/comics"
            arg_string = ""
            ##if '?' in self.request.uri:
            #    arg_string = '?'+self.request.uri.split('?',1)[1]
            src = default_src + arg_string
        self.render(deviceroot(self)+"browser.html",
                    src=src,
                    api_key=self.application.config['security']['api_key']
                )

class FoldersBrowserHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self,args):
        entity_src = self.get_argument(u"entity_src", default=None)
        if entity_src is not None:
                src=entity_src
        else:
            default_src=self.webroot + "/comics"
            arg_string = ""
            ##if '?' in self.request.uri:
            #    arg_string = '?'+self.request.uri.split('?',1)[1]
            src = default_src + arg_string

        if args is None:
            args = "/"
        args = utils.collapseRepeats(args, "/")
            
        self.render(deviceroot(self)+"folders.html",
                    args=args,src=src,
                    api_key = self.application.config['security']['api_key'])

class EntitiesBrowserHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self,args):
        if args is None:
            args = ""
        arg_string = args
        #if '/' in args:
        #   arg_string = args.split('/',1)[1]
        #print arg_string
        #if len(arg_string) == 0:
        #    arg_string = "?api_key=" + self.application.config['security']['api_key']
        #else:
        #    arg_string = arg_string + "&api_key=" + self.application.config['security']['api_key']
            
        self.render(deviceroot(self)+"entities.html",
                    args=arg_string,
                    api_key = self.application.config['security']['api_key'])

class ComicAPIHandler(JSONResultAPIHandler):
    def get(self, id):
        self.validateAPIKey()

        result = [self.library.getComic(id)]

        self.setContentType()
        self.write(resultSetToJson(result, "comics"))

class ComicBookmarkAPIHandler(JSONResultAPIHandler):
    def get(self, comic_id, pagenum):
        self.validateAPIKey()
        
        self.application.bookmark.setBookmark(comic_id, pagenum)
    
        self.setContentType()
        response = { 'status': 0 }
        self.write(response)

class ComicBlacklistAPIHandler(JSONResultAPIHandler):
    def get(self, comic_id, pagenum):
        self.validateAPIKey()
        
        self.application.blacklist.setBlacklist(comic_id, pagenum)
    
        self.setContentType()
        response = { 'status': 0 }
        self.write(response)


class ComicFavoritesAPIHandler(JSONResultAPIHandler):
    def get(self, comic_id, pagenum):
        self.validateAPIKey()
        
        # "HERE FIX: does not work need path...
        """if state == 'clear':
            self.application.library.remove(comic_id)
        else:
            self.application.library(comic_id, pagenum)
        """
        self.setContentType()
        response = { 'status': 0 }
        self.write(response)


class ComicCacheAPIHandler(JSONResultAPIHandler):
    def get(self, comic_id, pagenum):
        self.validateAPIKey()
        
        # "HERE FIX: does not work need path...
        """if state == 'clear':
            self.application.library.remove(comic_id)
        else:
            self.application.library(comic_id, pagenum)
        """
        self.setContentType()
        response = { 'status': 0 }
        self.write(response)


class ComicPageAPIHandler(ImageAPIHandler):
    def get(self, comic_id, pagenum):
        self.validateAPIKey()

        max_height = self.get_argument(u"max_height", default=None)

        image_data = self.library.getComicPage(comic_id, pagenum, True, max_height)


        self.setContentType(image_data)
        self.write(image_data)

class ThumbnailAPIHandler(ImageAPIHandler):
    def get(self, comic_id):
        self.validateAPIKey()
        thumbnail = self.library.getComicThumbnail(comic_id)
        self.setContentType('image/jpg')
        
        if thumbnail != None:
            self.write(thumbnail)
        else:
            with open(AppFolders.missingPath("cover.png"), 'rb') as fd:
                thumbnail = fd.read()
                fd.close()
            thumb = StringIO.StringIO()
            utils.resize(thumbnail, (400, 400), thumb)
            self.write(thumb.getvalue())


class FileAPIHandler(GenericAPIHandler):
    @tornado.web.asynchronous
    def get(self, comic_id):
        self.validateAPIKey()

        obj = self.library.getComic(comic_id)
        if obj is not None:
            (content_type, encoding) = mimetypes.guess_type(obj.path)
            if content_type is None:
                content_type = "application/octet-stream"

            self.add_header("Content-type", content_type)
            self.add_header("Content-Disposition", "attachment; filename=" + os.path.basename(obj.path))    

            # stream response in chunks, cbr/z could be over 300MB in size!
            # TODO: check it doesn't buffer the response, it should send data chunk by chunk
            with open(obj.path, 'rb') as f:
                while True:
                    data = f.read(40960 * 1024)
                    if not data:
                        break
                    self.write(data)
                    self.flush()
            self.finish()

class FolderAPIHandler(JSONResultAPIHandler):
    def get(self, args):            
        self.validateAPIKey()
        if args is not None:
            args = urllib.unquote(args)
            arglist = args.split('/')
            arglist = filter(None, arglist)
            argcount = len(arglist)
        else:
            arglist = list()
            argcount = 0
            
        folder_list = self.application.config['general']['folder_list']

        response = {
            'current' : "",
            'folders' : [],
            'comics' : {
                'url_path' : "",
                'count' : 0
            }   
        }       
        if argcount == 0:
            # just send the list of root level folders
            for idx, val in enumerate(folder_list):
                item = {
                    'name': val,
                    'url_path' : self.webroot + "/folders/" + str(idx)
                }   
                response['folders'].append(item)
            
        else:
            try:
                # need to validate the first arg is an index into the list
                folder_idx = int(arglist[0])
                if folder_idx >= len(folder_list):
                    raise Exception

                # build up a folder by combining the root folder with the following path
                path = os.path.join(folder_list[folder_idx], *arglist[1:] )
                # validate *that* folder
                if not os.path.exists(path):
                    print "Not exist", path, type(path)            
                    raise Exception
                

                response['current'] = path
                # create a list of subfolders    
                for o in os.listdir(path):
                    if os.path.isdir(os.path.join(path,o)):
                        sub_path = u""+self.webroot+"/folders" + args + u"/" + o
                        sub_path = urllib.quote(sub_path.encode("utf-8"))
                        item = {
                            'name': o,
                            'url_path' : sub_path
                            }   
                        response['folders'].append(item)
                # see if there are any comics here
                (ignore, total_results) = self.library.list({'folder': path}, {'per_page': 0, 'offset': 0})
                response['comics']['count'] = total_results
                comic_path = self.webroot + u"/comics?folder=" + urllib.quote(u"{0}".format(path).encode('utf-8'))
                response['comics']['url_path'] = comic_path

            except FloatingPointError as e:
                print e
                raise tornado.web.HTTPError(404, "Unknown folder")
 
        self.setContentType()
        self.write(response)
            
class EntityAPIHandler(JSONResultAPIHandler):
    def get(self, args):            
        self.validateAPIKey()
        session = self.application.dm.Session()
        
        if args is None:
            args = ""
        arglist=args.split('/')
            
        arglist = filter(None, arglist)
        argcount = len(arglist)
        arglist = [utils.unquote(a) for a in arglist]
        
        entities = {
                    'characters' : Character.name,
                    'persons' : Person.name,
                    'language' : Comic.language,
                    'publishers' : Comic.publisher,
                    'roles' : Role.name,
                    'series': Comic.series,
                    'volumes' : Comic.volume,
                    'teams' : Team.name,
                    'storyarcs' : StoryArc.name,
                    'genres' : Genre.name,
                    'locations' : Location.name,
                    'generictags' : GenericTag.name,            
                    'comics' : Comic,
                    'alternateseries' : AlternateSeries.name
                    }
        #logging.debug("In EntityAPIHandler {0}".format(arglist))
        #/entity1/filter1/entity2/filter2...
    
        # validate all entities keys in args
        #( check every other item)
        for e in arglist[0::2]:
            if e not in entities:
                raise tornado.web.HTTPError(404, "Unknown entity:{0}".format(e))
        #look for dupes
        if len(arglist[0::2])!=len(set(arglist[0::2])):
            raise tornado.web.HTTPError(400, "Duplicate entity")
        #look for dupes
        if 'comics' in arglist[0::2] and arglist[-1] != "comics":
            raise tornado.web.HTTPError(400, "\"comics\" must be final entity")


        resp = ""
        # even number means listing entities
        if argcount % 2 == 0:
            name_list = [key for key in entities]
            # (remove already-traversed entities)
            for e in arglist[0::2]:
                try:
                    name_list.remove(e)
                except:    
                    pass
                
            # Find out how many of each entity are left, and build a list of
            # dicts with name and count
            dict_list = []
            for e in name_list:
                tmp_arg_list = list()
                tmp_arg_list.extend(arglist)
                tmp_arg_list.append(e)
                query = self.buildQuery(session, entities, tmp_arg_list)
                e_dict = dict()
                e_dict['name'] = e
                #self.application.dm.engine.echo = True
                e_dict['count'] = query.distinct().count()
                #self.application.dm.engine.echo = False
                #print "----", e_dict, query
                dict_list.append(e_dict)
                
            #name_list = sorted(name_list)

            resp = {"entities" : dict_list}
            self.setContentType()
            self.write(resp)
            return

        # odd number means listing last entity VALUES
        else:
            entity = arglist[-1] # the final entity in the list
            query = self.buildQuery(session, entities, arglist)
            
            if entity == "comics":
            
                query = self.processComicQueryArgs(query)
                query, total_results = self.processPagingArgs(query)

                query = query.options(subqueryload('characters_raw'))
                query = query.options(subqueryload('storyarcs_raw'))
                query = query.options(subqueryload('alternateseries_raw'))
                query = query.options(subqueryload('locations_raw'))
                query = query.options(subqueryload('teams_raw'))
                #query = query.options(subqueryload('credits_raw'))                
                query = query.options(subqueryload('generictags_raw'))                
                query = query.all()
                resp = resultSetToJson(query, "comics", total_results)                
            else:
                resp = {entity : sorted(list(set([i[0] for i in query.all()])))}
            self.application.dm.engine.echo = False

        self.setContentType()
        self.write(resp)
        
    def buildQuery(self, session, entities, arglist):
        """
         Each entity-filter pair will be made into a separate query
         and they will be all intersected together
        """

        entity = arglist[-1]
        querylist = []
        #To build up the query, bridge every entity to a comic table
        querybase = session.query(entities[entity])
        if len(arglist) != 1:
            if entity == 'roles':
                querybase = querybase.join(Credit).join(Comic)
            if entity == 'persons':
                querybase = querybase.join(Credit).join(Comic)
            if entity == 'characters':
                querybase = querybase.join(comics_characters_table).join(Comic)
            if entity == 'teams':
                querybase = querybase.join(comics_teams_table).join(Comic)
            if entity == 'storyarcs':
                querybase = querybase.join(comics_storyarcs_table).join(Comic)
            if entity == 'alternateseries':
                querybase = querybase.join(comics_alternateseries_table).join(Comic)
            if entity == 'genres':
                querybase = querybase.join(comics_genres_table).join(Comic)
            if entity == 'locations':
                querybase = querybase.join(comics_locations_table).join(Comic)
            if entity == 'generictags':
                querybase = querybase.join(comics_generictags_table).join(Comic)
        
        #print "Result entity is====>", entity
        #iterate over list, 2 at a time, building query list,
        #print zip(arglist[0::2], arglist[1::2])
        for e,v in zip(arglist[0::2], arglist[1::2]):
            #print "--->",e,v
            query = querybase
            if e == 'roles':
                if entity != 'persons':
                    query = query.join(Credit)
                query = query.join(Role)
            if e == 'persons':
                if entity != 'roles':
                    query = query.join(Credit)
                query = query.join(Person)
            if e == 'characters':
                query = query.join(comics_characters_table).join(Character)
            if e == 'teams':
                query = query.join(comics_teams_table).join(Team)
            if e == 'storyarcs':
                query = query.join(comics_storyarcs_table).join(StoryArc)
            if e == 'alternateseries':
                query = query.join(comics_alternateseries_table).join(AlternateSeries)

            if e == 'genres':
                query = query.join(comics_genres_table).join(Genre)
            if e == 'locations':
                query = query.join(comics_locations_table).join(Location)
            if e == 'generictags':
                query = query.join(comics_generictags_table).join(GenericTag)
            query = query.filter(entities[e]==v)
            querylist.append(query)
            #print query
                        
        if len(querylist) == 0:
            finalquery = querybase
        else:
            finalquery = querylist[0].intersect(*querylist[1:])
            
        return finalquery
        
class ReaderHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, comic_id):

        obj = self.library.getComic(comic_id)
        page_data = None
        if obj is not None:
            #self.render("templates/reader.html", make_list=self.make_list, id=comic_id, count=obj.page_count)
            #self.render("test.html", make_list=self.make_list, id=comic_id, count=obj.page_count)
            
            title = os.path.basename(obj.path)
            if obj.series is not None and obj.issue is not None:
                title = obj.series + u" #" + obj.issue
                if obj.title is not None :
                    title +=  u" -- " + obj.title
            if obj.lastread_page is None:
                target_page = 0
            else:
                target_page=obj.lastread_page   
                
            self.render(deviceroot(self)+"comic.html",
                        title=title,
                        id=comic_id,
                        count=obj.page_count,
                        page=target_page,
                        api_key=self.application.config['security']['api_key'])
            
        def make_list(self, id, count):
            text = u""
            for i in range(count):
                text +=  u"\'page/" + str(i) + u"\',"
            return text

class UnknownHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render(deviceroot(self)+"missing.html", version=self.application.version)

class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        stats = self.library.getStats()
        stats['last_updated'] = utils.utc_to_local(stats['last_updated']).strftime("%Y-%m-%d %H:%M:%S")
        stats['created'] = utils.utc_to_local(stats['created']).strftime("%Y-%m-%d %H:%M:%S")

        recently_added_comics = self.library.recentlyAddedComics(10)
        recently_read_comics = self.library.recentlyReadComics(10)
        # roles_list = [role.name for role in self.library.getRoles()]
        random_comic = self.library.randomComic()

        if random_comic is None:
            random_comic = type('fakecomic', (object,),{'id':0, '':'No Comics', 'issue':'', 'series':'','title':''})()
        
        caption = u""
        if random_comic.issue is not None:
            caption = random_comic.issue
        if random_comic.title is not None:
            if random_comic.issue is not None:
                caption = caption + u" " + random_comic.title
            caption = random_comic.title

        self.render(deviceroot(self)+"index.html",
                    random_comic=random_comic,random_caption=caption,
                    api_key = self.application.config['security']['api_key']
                )

class ServerPageHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        #stats = self.library.getStats()
        #stats['last_updated'] = utils.utc_to_local(stats['last_updated']).strftime("%Y-%m-%d %H:%M:%S")
        #stats['created'] = utils.utc_to_local(stats['created']).strftime("%Y-%m-%d %H:%M:%S")
        self.render(deviceroot(self)+"server.html",
                    server_time =  int(time.mktime(datetime.utcnow().timetuple()) * 1000),
                    api_key = self.application.config['security']['api_key']
                    )
        #self.render(deviceroot(self)+"server.html", stats=stats,
        #            server_time =  int(time.mktime(datetime.utcnow().timetuple()) * 1000),
        #            api_key = self.application.config['security']['api_key']
        #            )

class RecentlyPageHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        recently_added_comics = self.library.recentlyAddedComics(10)
        recently_read_comics = self.library.recentlyReadComics(10)

        self.render(deviceroot(self)+"recently.html",
                    recently_added = list(recently_added_comics),
                    recently_read = list(recently_read_comics),
                    api_key = self.application.config['security']['api_key']
                    )
        
class PublishersPageHandeler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        publishers_list = self.library.publishers()
        self.render(deviceroot(self)+"publishers.html",
                    publishers=list(publishers_list),
                    api_key=self.application.config['security']['api_key']
                    )

class PublisherPageHandeler(BaseHandler):
    @tornado.web.authenticated
    def get(self, args):
        if args is not None:
            args = urllib.unquote(args.replace("/", "") )
        print args
        # publisher = self.get_argument('publisher', None)
        print "handeler sees: "+ args
        series_list = self.library.seriesByPublisher(args)
        self.render(deviceroot(self)+"publisher.html",
                    series=list(series_list),
                    api_key=self.application.config['security']['api_key']
                    )

class SearchPageHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        
        roles_list = [role.name for role in self.library.getRoles()]
        random_comic = self.library.randomComic()
        
        self.render(deviceroot(self)+"search.html",
                    roles = roles_list,
                    api_key = self.application.config['security']['api_key']
                    )

class GenericPageHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self,page):
        if os.path.isfile(AppFolders.appBase()+"/"+"gui"+"/"+deviceroot(self)+page+".html"):
            self.render(deviceroot(self)+page+".html")
        else:
            self.render(deviceroot(self)+"missing.html", version=self.application.version)

class AboutPageHandler(BaseHandler):
    #@tornado.web.authenticated
    def get(self):
        self.render(deviceroot(self)+"about.html", version=self.application.version)

class APIPageHandler(BaseHandler):
    #@tornado.web.authenticated
    def get(self):
        self.render(deviceroot(self)+"api.html", api_key=self.application.config['security']['api_key'])

class HelpPageHandler(BaseHandler):
    #@tornado.web.authenticated
    def get(self):
        self.render(deviceroot(self)+"help.html", api_key=self.application.config['security']['api_key'])


class LogPageHandler(BaseHandler):
    
    @tornado.web.authenticated

    def get(self):

        log_file = os.path.join(AppFolders.logs(), "ComicStreamer.log")
        
        logtxt = ""
        for line in reversed(open(log_file).readlines()):
            logtxt += line.rstrip() + '\n'


        self.render(deviceroot(self)+"log.html",
                    logtxt=logtxt)
     
class ConfigPageHandler(BaseHandler):
    fakepass = "T01let$tRe@meR"

    def is_port_available(self,port):    
        host = '127.0.0.1'
    
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((host, port))
            s.shutdown(2)
            return False
        except Exception as e:
            print e
            return True

    def render_config(self, formdata, success="", failure=""):
        #convert boolean to "checked" or ""

        formdata['use_pdf'] = "checked" if formdata['use_pdf'] else ""
        formdata['use_cbw'] = "checked" if formdata['use_cbw'] else ""
        formdata['use_folders'] = "checked" if formdata['use_folders'] else ""

        formdata['use_zd'] = "checked" if formdata['use_zd'] else ""
        formdata['use_comicvine'] = "checked" if formdata['use_comicvine'] else ""


        formdata['cbw_autodownload'] = "checked" if formdata['cbw_autodownload'] else ""
        formdata['use_ebook'] = "checked" if formdata['use_ebook'] else ""

        formdata['use_mutool'] = "checked" if formdata['use_mutool'] else ""
        formdata['use_mudraw'] = "checked" if formdata['use_mudraw'] else ""
        

        formdata['use_https'] = "checked" if formdata['use_https'] else ""
        formdata['use_sqlite'] = "checked" if formdata['use_sqlite'] else ""
        formdata['use_mysql'] = "checked" if formdata['use_mysql'] else ""
        formdata['use_api_key'] = "checked" if formdata['use_api_key'] else ""
        formdata['use_cache'] = "checked" if formdata['use_cache'] else ""
        formdata['use_authentication'] = "checked" if formdata['use_authentication'] else ""
        formdata['launch_client'] = "checked" if formdata['launch_client'] else ""
        formdata['fingerprint'] = "checked" if formdata['fingerprint'] else ""
        if (  self.application.config['security']['use_authentication'] ):
            formdata['password'] = ConfigPageHandler.fakepass
            formdata['password_confirm'] = ConfigPageHandler.fakepass
        else:
            formdata['password'] = ""
            formdata['password_confirm'] = ""
        
        self.render(deviceroot(self)+"settings.html",
                    formdata=formdata,
                    api_key = self.application.config['security']['api_key'],
                    success=success,
                    failure=failure)
        
    
    
    @tornado.web.authenticated    
    def get(self):
        
        formdata = dict()
        formdata['use_cache'] = self.application.config['cache']['active']
        formdata['cache_size'] = self.application.config['cache']['size']
        formdata['cache_free'] = self.application.config['cache']['free']
        formdata['cache_location'] = self.application.config['cache']['location']
        formdata['port'] = self.application.config['web']['port']
        formdata['secure_port'] = self.application.config['web.ssl']['port']
        formdata['key_file'] = self.application.config['web.ssl']['key_file']
        formdata['certificate_file'] = self.application.config['web.ssl']['certificate_file']
        formdata['use_https'] = self.application.config['web.ssl']['active']
        formdata['bind'] = self.application.config['web']['bind']
        formdata['webroot'] = self.application.config['web']['webroot']
        formdata['folders'] = "\n".join(self.application.config['general']['folder_list'])
        formdata['use_authentication'] = self.application.config['security']['use_authentication'] 
        formdata['username'] = self.application.config['security']['username']
        formdata['password'] = ""
        formdata['password_confirm'] = ""
        formdata['use_api_key'] = self.application.config['security']['use_api_key'] 
        formdata['api_key'] = self.application.config['security']['api_key']
        formdata['launch_client'] = self.application.config['general']['launch_client']
        formdata['fingerprint'] = self.application.config['general']['fingerprint']
        formdata['use_mysql'] = self.application.config['database']['engine'] == 'mysql'
        formdata['use_sqlite'] = self.application.config['database']['engine'] == 'sqlite'
        formdata['sqlite_location'] = self.application.config['database.sqlite']['location']
        formdata['sqlite_database'] = self.application.config['database.sqlite']['database']
        formdata['mysql_database'] = self.application.config['database.mysql']['database']
        formdata['mysql_username'] = self.application.config['database.mysql']['username']
        formdata['mysql_password'] = utils.decode(self.application.config['general']['install_id'],self.application.config['database.mysql']['password'])
        formdata['mysql_host'] = self.application.config['database.mysql']['host']
        formdata['mysql_port'] = self.application.config['database.mysql']['port']
        formdata['ebook_resolution'] = self.application.config['format.ebook']['resolution']
        formdata['ebook_margin'] = self.application.config['format.ebook']['margin']
        formdata['pdf_resolution'] = self.application.config['format.pdf']['resolution']
        formdata['pdf_engine'] = self.application.config['format.pdf']['engine']
        
        formdata['use_mudraw'] = formdata['pdf_engine'] == 'mudraw'
        formdata['use_mutool'] = formdata['pdf_engine'] == 'mutool'
        formdata['use_pdf2png'] = formdata['pdf_engine'] == 'pdf2png'
        formdata['qpdf'] = self.application.config['format.pdf']['qpdf']
        formdata['mudraw'] = self.application.config['format.pdf']['mudraw']
        formdata['mutool'] = self.application.config['format.pdf']['mutool']
        formdata['pdf2png'] = self.application.config['format.pdf']['pdf2png']
        formdata['cbw_location'] = self.application.config['format.webcomic']['location']

        formdata['use_zd'] = self.application.config['metadata.zilverendolfijn']['active']
        formdata['use_comicvine'] = self.application.config['metadata.comicvine']['active']
        formdata['comicvine_key'] = self.application.config['metadata.comicvine']['key']
        formdata['comicvine_location'] = self.application.config['metadata.comicvine']['location']
        formdata['zilverendolfijn_location'] = self.application.config['metadata.zilverendolfijn']['location']
        formdata['use_folders'] = self.application.config['format.folders']['active']
        formdata['use_cbw'] = self.application.config['format.webcomic']['active']
        formdata['cbw_autodownload'] = self.application.config['format.webcomic']['auto_download']
        formdata['use_pdf'] = self.application.config['format.pdf']['active']
        formdata['use_ebook'] = self.application.config['format.ebook']['active']
        formdata['calibre'] = self.application.config['format.ebook']['calibre']
        formdata['ebook_cache_location'] = self.application.config['format.ebook']['location']
        formdata['ebook_cache_free'] = self.application.config['format.ebook']['free']
        formdata['ebook_cache_size'] = self.application.config['format.ebook']['size']
        self.render_config(formdata)

    @tornado.web.authenticated
    def post(self):
        formdata = dict()
        formdata['folders'] = self.get_argument(u"folders", default="")
        formdata['webroot'] = self.get_argument(u"webroot", default="")
        formdata['bind'] = self.get_argument(u"bind", default="")
        formdata['port'] = self.get_argument(u"port", default="")
        formdata['secure_port'] = self.get_argument(u"secure_port", default="")
        formdata['key_file'] = self.get_argument(u"key_file", default="")
        formdata['certificate_file'] = self.get_argument(u"certificate_file", default="")
        formdata['use_https'] = (len(self.get_arguments("use_https"))!=0)
        formdata['cache_size'] = self.get_argument(u"cache_size", default="")
        formdata['cache_free'] = self.get_argument(u"cache_free", default="")
        formdata['cache_location'] = self.get_argument(u"cache_location", default="")
        formdata['use_cache'] = (len(self.get_arguments("use_cache"))!=0)
        formdata['use_authentication'] = (len(self.get_arguments("use_authentication"))!=0)
        formdata['username'] = self.get_argument(u"username", default="")
        formdata['password'] = self.get_argument(u"password", default="")
        formdata['password_confirm'] = self.get_argument(u"password_confirm", default="")
        formdata['use_api_key'] = (len(self.get_arguments("use_api_key"))!=0)
        formdata['api_key'] = self.get_argument(u"api_key", default="")
        formdata['launch_client'] = (len(self.get_arguments("launch_client"))!=0)
        formdata['fingerprint'] = (len(self.get_arguments("fingerprint"))!=0)
        formdata['db_engine'] = self.get_arguments("db_engine")[0]
        formdata['use_mysql'] = formdata['db_engine'] == 'mysql'
        formdata['use_sqlite'] = formdata['db_engine'] == 'sqlite'
        
        formdata['mysql_username'] = self.get_argument(u"mysql_username", default="")
        formdata['mysql_database'] = self.get_argument(u"mysql_database", default="")
        formdata['mysql_host'] = self.get_argument(u"mysql_host", default="")
        formdata['mysql_port'] = self.get_argument(u"mysql_port", default="")
        formdata['mysql_password'] = self.get_argument(u"mysql_password", default="")


        formdata['comicvine_key'] = self.get_argument(u"comicvine_location", default="")
        formdata['comicvine_location'] = self.get_argument(u"comicvine_key", default="")
        formdata['zilverendolfijn_location'] = self.get_argument(u"zilverendolfijn_location", default="")

        formdata['sqlite_location'] = self.get_argument(u"sqlite_location", default="")
        formdata['sqlite_database'] = self.get_argument(u"sqlite_database", default="")
        formdata['pdf_resolution'] = self.get_argument(u"pdf_resolution", default="")
        formdata['ebook_margin'] = self.get_argument(u"ebook_margin", default="")
        formdata['ebook_resolution'] = self.get_argument(u"ebook_resolution", default="")
        formdata['pdf_engine'] = self.get_argument(u"pdf_engine")

        formdata['use_mutool'] = formdata['pdf_engine'] == 'mutool'
        formdata['use_mudraw'] = formdata['pdf_engine'] == 'mudraw'
        formdata['use_pdf2png'] = formdata['pdf_engine'] == 'pdf2png'

        formdata['cbw_location'] = self.get_argument(u"cbw_location", default="")

        formdata['mudraw'] = self.get_argument(u"mudraw", default="")
        formdata['mutool'] = self.get_argument(u"mutool", default="")
        formdata['pdf2png'] = self.get_argument(u"pdf2png", default="")
        formdata['qpdf'] = self.get_argument(u"qpdf", default="")
        formdata['use_pdf'] = (len(self.get_arguments("use_pdf"))!=0)
        formdata['use_cbw'] = (len(self.get_arguments("use_cbw"))!=0)
        formdata['use_folders'] = (len(self.get_arguments("use_folders"))!=0)
        formdata['use_comicvine'] = (len(self.get_arguments("use_comicvine"))!=0)
        formdata['use_zd'] = (len(self.get_arguments("use_zd"))!=0)
        formdata['cbw_autodownload'] = (len(self.get_arguments("cbw_autodownload"))!=0)
        formdata['use_ebook'] = (len(self.get_arguments("use_ebook"))!=0)
        formdata['calibre'] = self.get_argument(u"calibre", default="")
        formdata['ebook_cache_location'] = self.get_argument(u"ebook_cache_location", default="")
        formdata['ebook_cache_free'] = self.get_argument(u"ebook_cache_free", default="")
        formdata['ebook_cache_size'] = self.get_argument(u"ebook_cache_size", default="")
       
        failure_str = ""
        success_str = ""
        failure_strs = list()
        validated = False
        
        old_folder_list = self.application.config['general']['folder_list']
        new_folder_list = [os.path.normcase(os.path.abspath(os.path.normpath(unicode(a)))) for a in formdata['folders'].splitlines()]

        try:
            for i, f in enumerate(new_folder_list):
                #validate folders exist
                if not (os.path.exists(f) and  os.path.isdir(f)):
                    failure_strs.append(u"Folder {0} doesn't exist.".format(f))
                    break
                # check for repeat or contained 
                for j, f1 in enumerate(new_folder_list):
                    if i != j:
                        if  f1 == f:
                            failure_strs.append(u"Can't have repeat folders.")
                            raise Exception
                        if  f1.startswith(f + os.path.sep):
                            failure_strs.append(u"One folder can't contain another.")
                            raise Exception
        except Exception:
            pass
    
            

        port_failed = False
        old_port = self.application.config['web']['port']

        #validate numeric port
        if not formdata['port'].isdigit():
            port_failed = True
            failure_strs.append(u"Non-numeric port value: {0}".format(formdata['port']))
              
        #validate port range
        if not port_failed:  
            new_port = int(formdata['port'])
            if new_port > 49151 or new_port < 1024:
                failure_strs.append(u"Port value out of range (1024-49151): {0}".format(new_port))
                port_failed = True

        #validate port availability
        
        if self.port != new_port:
            if not port_failed:
                if new_port != old_port and not self.is_port_available(new_port):
                    failure_strs.append(u"Port not available: {0}".format(new_port))
                    port_failed = True
          
        #validate password and username are set
        if formdata['use_authentication'] and (formdata['username']=="" or formdata['password']==""):
            failure_strs.append(u"Username and password must be filled in if the 'use authentication' box is checked")


        if formdata['cache_location'] != "":
            if not os.path.isdir(formdata['cache_location']):
                try:
                    os.makedirs(formdata['cache_location'])
                except:
                    failure_strs.append(u"Cache location failure")
            
            
        if formdata['sqlite_location'] != "":
            if not os.path.isdir(formdata['sqlite_location']):
                failure_strs.append(u"SQLite database location does not exists")
            
        if formdata['sqlite_database'] != "":
            try:
                import tempfile
                test = os.path.join(tempfile.gettempdir(),formdata['sqlite_database'])
                open(test, "wb").close()
                os.remove(test)
            except:
                failure_strs.append(u"SQLite database name contains strange symbols")
            
        if int(formdata['pdf_resolution']) < 72:
            failure_strs.append(u"Min PDF Resoltion is 72")
        
        if int(formdata['pdf_resolution']) > 600:
            failure_strs.append(u"Max PDF Resoltion is 600")

        if int(formdata['ebook_resolution']) < 72:
            failure_strs.append(u"Min PDF Resoltion is 50")
        
        if int(formdata['ebook_resolution']) > 600:
            failure_strs.append(u"Max PDF Resoltion is 600")

        if int(formdata['ebook_margin']) < 0:
            failure_strs.append(u"Min Ebook Margin is 0")

        if int(formdata['ebook_margin']) > 72:
            failure_strs.append(u"Min Ebook Margin is 0")


        #validate password pair is the same
        if formdata['password'] != formdata['password_confirm']:
            failure_strs.append(u"Password fields don't match.")

        if formdata['use_api_key'] and formdata['api_key']=="":
            failure_strs.append(u"API Key must have a value if the box is checked")

        # check cache input... ok?
        try:
            int(formdata['cache_size'])
        except:
            failure_strs.append(u"Cache size not a number")

        try:
            int(formdata['cache_free'])
        except:
            failure_strs.append(u"Cache free size not a number")
        
        # need more validation here on mysql!!!! secure https! database names?
        # FIX: RELEASE1
        
        if len(failure_strs) == 0:
            validated = True
    
        if validated:
            # was the password changed?
            password_changed = True
            if formdata['use_authentication']:
                if formdata['password'] == ConfigPageHandler.fakepass:
                    password_changed = False 
                elif utils.getDigest(formdata['password']) == self.application.config['security']['password_digest']:
                    password_changed = False
            else:
                password_changed = False
        
            if (new_port != old_port or
                formdata['bind'] != self.application.config['web']['bind'] or
                formdata['webroot'] != self.application.config['web']['webroot'] or
                formdata['secure_port'] != self.application.config['web.ssl']['port'] or
                formdata['key_file'] != self.application.config['web.ssl']['key_file'] or
                formdata['certificate_file'] != self.application.config['web.ssl']['certificate_file'] or
                formdata['use_https'] != self.application.config['web.ssl']['active'] or
                new_folder_list != old_folder_list or
                formdata['username'] != self.application.config['security']['username'] or
                password_changed or
                formdata['use_api_key'] != self.application.config['security']['use_api_key'] or
                formdata['api_key'] != self.application.config['security']['api_key'] or
                formdata['db_engine'] != self.application.config['database']['engine'] or
                formdata['mysql_database'] != self.application.config['database.mysql']['database'] or
                utils.encode(self.application.config['general']['install_id'],formdata['mysql_password']) != self.application.config['database.mysql']['password'] or
                formdata['mysql_username'] != self.application.config['database.mysql']['username'] or
                formdata['mysql_port'] != self.application.config['database.mysql']['port'] or
                formdata['mysql_host'] != self.application.config['database.mysql']['host'] or
                formdata['sqlite_database'] != self.application.config['database.sqlite']['database'] or
                formdata['sqlite_location'] != self.application.config['database.sqlite']['location'] or

                formdata['comicvine_location'] != self.application.config['metadata.comicvine']['location'] or
                formdata['comicvine_key'] != self.application.config['metadata.comicvine']['key'] or
                formdata['zilverendolfijn_location'] != self.application.config['metadata.zilverendolfijn']['location'] or

                formdata['cbw_location'] != self.application.config['format.webcomic']['location'] or

                formdata['cbw_autodownload'] != self.application.config['format.webcomic']['auto_download'] or
                formdata['use_comicvine'] != self.application.config['metadata.comicvine']['active'] or
                formdata['use_zd'] != self.application.config['metadata.zilverendolfijn']['active'] or

                formdata['use_cbw'] != self.application.config['format.webcomic']['active'] or
                formdata['use_folders'] != self.application.config['format.folders']['active'] or
                formdata['use_pdf'] != self.application.config['format.pdf']['active'] or
                formdata['pdf_resolution'] != self.application.config['format.pdf']['resolution'] or
                formdata['ebook_margin'] != self.application.config['format.ebook']['margin'] or
                formdata['ebook_resolution'] != self.application.config['format.ebook']['resolution'] or
                formdata['pdf_engine'] != self.application.config['format.pdf']['engine'] or
                formdata['mudraw'] != self.application.config['format.pdf']['mudraw'] or
                formdata['mutool'] != self.application.config['format.pdf']['mutool'] or
                formdata['pdf2png'] != self.application.config['format.pdf']['pdf2png'] or
                formdata['qpdf'] != self.application.config['format.pdf']['qpdf'] or
                formdata['use_ebook'] != self.application.config['format.ebook']['active'] or
                formdata['calibre'] != self.application.config['format.ebook']['calibre'] or
                formdata['ebook_cache_location'] != self.application.config['format.ebook']['location'] or
                formdata['ebook_cache_free'] != self.application.config['format.ebook']['free'] or
                formdata['ebook_cache_size'] != self.application.config['format.ebook']['size'] or
                formdata['launch_client'] != self.application.config['general']['launch_client'] or
                formdata['fingerprint'] != self.application.config['general']['fingerprint'] or
                formdata['use_cache'] != self.application.config['cache']['active'] or
                formdata['cache_size'] != self.application.config['cache']['size'] or
                formdata['cache_free'] != self.application.config['cache']['free'] or
                formdata['cache_location'] != self.application.config['cache']['location']
               ):


                # apply everything from the form
                self.application.config['general']['folder_list'] = new_folder_list
                self.application.config['web']['port'] = new_port
                self.application.config['web']['webroot'] = formdata['webroot']
                self.application.config['web']['bind'] = formdata['bind']
                self.application.config['security']['use_authentication'] = formdata['use_authentication']
                self.application.config['security']['username'] = formdata['username']
                if formdata['password'] != ConfigPageHandler.fakepass:
                    self.application.config['security']['password_digest'] = utils.getDigest(formdata['password'])
                self.application.config['security']['use_api_key'] = formdata['use_api_key']
                if self.application.config['security']['use_api_key']:
                    self.application.config['security']['api_key'] = formdata['api_key']
                else:
                    self.application.config['security']['api_key'] = ""
                    formdata['api_key'] = ""
                self.application.config['general']['launch_client'] = formdata['launch_client']
                self.application.config['general']['fingerprint'] = formdata['fingerprint']

                self.application.config['web.ssl']['port'] = formdata['secure_port']
                self.application.config['web.ssl']['active'] = formdata['use_https']
                self.application.config['web.ssl']['key_file'] = formdata['key_file']
                self.application.config['web.ssl']['certificate_file'] = formdata['certificate_file']

                self.application.config['cache']['active'] = formdata['use_cache']
                self.application.config['cache']['size'] = formdata['cache_size']
                self.application.config['cache']['free'] = formdata['cache_free']
                self.application.config['cache']['location'] = formdata['cache_location']

                self.application.config['format.ebook']['calibre'] = formdata['calibre']
                self.application.config['format.ebook']['location'] = formdata['ebook_cache_location']
                self.application.config['format.ebook']['free'] = formdata['ebook_cache_free']
                self.application.config['format.ebook']['size'] = formdata['ebook_cache_size']
                self.application.config['format.ebook']['active'] =  formdata['use_ebook']
                
                self.application.config['format.webcomic']['active'] = formdata['use_cbw']
                self.application.config['format.folders']['active'] = formdata['use_folders']
                self.application.config['format.webcomic']['location'] = formdata['cbw_location']
                self.application.config['format.webcomic']['auto_download'] = formdata['cbw_autodownload']
                self.application.config['format.pdf']['active'] =  formdata['use_pdf']
                self.application.config['format.pdf']['resolution'] =  formdata['pdf_resolution']
                self.application.config['format.ebook']['resolution'] = formdata['ebook_resolution']
                self.application.config['format.ebook']['margin'] = formdata['ebook_margin']


                self.application.config['metadata.comicvine']['location'] = formdata['comicvine_location']
                self.application.config['metadata.comicvine']['key'] = formdata['comicvine_key']
                self.application.config['metadata.zilverendolfijn']['location'] = formdata['zilverendolfijn_location']

                self.application.config['metadata.comicvine']['active'] =  formdata['use_comicvine']
                self.application.config['metadata.zilverendolfijn']['active'] =  formdata['use_zd']

                self.application.config['format.pdf']['engine'] = formdata['pdf_engine']
                self.application.config['format.pdf']['mudraw'] = formdata['mudraw']
                self.application.config['format.pdf']['mutool'] = formdata['mutool']
                self.application.config['format.pdf']['pdf2png'] = formdata['pdf2png']
                self.application.config['format.pdf']['qpdf'] = formdata['qpdf']
          
                self.application.config['database']['engine'] = formdata['db_engine']
                
                self.application.config['database.sqlite']['location'] = formdata['sqlite_location']
                self.application.config['database.sqlite']['database'] = formdata['sqlite_database']
                # lame password hide should be better...
                self.application.config['database.mysql']['password'] = utils.encode(self.application.config['general']['install_id'],formdata['mysql_password'])
                self.application.config['database.mysql']['username'] = formdata['mysql_username']
                self.application.config['database.mysql']['database'] = formdata['mysql_database']
                self.application.config['database.mysql']['host'] = formdata['mysql_host']
                self.application.config['database.mysql']['port'] = formdata['mysql_port']
                
                
                success_str = "Saved. Server restart needed"                
                self.application.config.write()
        else:
            failure_str = "<br/>".join(failure_strs)
        formdata['password'] = ""
        formdata['password_confirm'] = ""
        logging.info("Config: " + str(self.application.config))
        self.render_config(formdata, success=success_str, failure=failure_str)
        
class LoginHandler(BaseHandler):
    def get(self):
        if  len(self.get_arguments("next")) != 0:
            next=self.get_argument("next")
        else:
            next=self.webroot + "/"
        
        #if password and user are blank, just skip to the "next"
        if (  self.application.config['security']['password_digest'] == utils.getDigest("")  and
              self.application.config['security']['username'] == ""
            ):
            self.set_secure_cookie("user", fix_username(self.application.config['security']['username']))
            self.redirect(next)
        else:
            self.render(deviceroot(self)+'login.html', next=next)

    def post(self):
        next = self.get_argument("next")

        if  len(self.get_arguments("password")) != 0:
                
            #print self.application.password, self.get_argument("password") , next
            if (utils.getDigest(self.get_argument("password"))  ==  self.application.config['security']['password_digest'] and
                self.get_argument("username")  ==  self.application.config['security']['username']):
                #self.set_secure_cookie("auth", self.application.config['security']['password_digest'])
                self.set_secure_cookie("user", fix_username(self.application.config['security']['username']))
                
        self.redirect(next)

class WakeUp:
    def __init__(self, dm):
        self.dm = dm
        pass

    def start(self):
        self.thread = threading.Thread(target=self.mainLoop)
        self.thread.daemon = True
        self.quit = False
        self.thread.start()

    def stop(self):
        self.quit = True
        self.thread.join()

    def mainLoop(self):

        logging.debug("WakeUp: Started")
        i = 0
        while not self.quit:
            try:
                time.sleep(1)
                i += 1
                # call mysql.query to keep it alive...
                if i == 3600:
                    logging.debug("WakeUp: Database")
                    session = self.dm.Session()
                    obj = session.query(SchemaInfo).first()
                    i = 0
                    session.close()
            except:
                break;
        logging.debug("WakeUp: Stopped")


class APIServer(tornado.web.Application):
    def __init__(self, config, opts):
        utils.fix_output_encoding()   
        
        self.config = config
        logging.debug("Config: " + str(config))

        self.opts = opts
        
        self.port = self.config['web']['port']
        self.port_secure = self.config['web.ssl']['port']
        self.webroot = self.config['web']['webroot']
        self.bind = self.config['web']['bind']
        
        self.comicArchiveList = []
        
        #if len(self.config['general']['folder_list']) == 0:
        #    logging.error("No folders on either command-line or config file.  Quitting.")
        #    sys.exit(-1)


        if not os.path.exists(AppFolders.appCachePages()):
            os.makedirs(AppFolders.appCachePages())
    
        if not os.path.exists(AppFolders.appCacheEbooks()):
            os.makedirs(AppFolders.appCacheEbooks())

        if not os.path.exists(AppFolders.appBlacklistPages()):
            os.makedirs(AppFolders.appBlacklistPages())

        if not os.path.exists(AppFolders.appWebComic()):
            os.makedirs(AppFolders.appWebComic())

        #self.dm = DataManager()
        self.dm = DataManager(config)
        self.library = Library(self.dm.Session)
        

        # "HERE FIX Move to cache.py
        cache_location = self.config['cache']['location']
        cache_active = self.config['cache']['active']
        if cache_location == "": cache_location = AppFolders.appCachePages()
        else:
            if not os.path.isdir(cache_location):
                active = False
        
        self.library.cache(cache_location,cache_active,self.config['cache']['size'],self.config['cache']['free'])

        if opts.reset or opts.reset_and_run:
            self.dm.delete()
            self.library.cache_clear()
            
        # quit on a standard reset
        if opts.reset:
            sys.exit(0)
        
        try:
            self.dm.create()
        except SchemaVersionException as e:
            # FIX "HERE frmo place error messgaes.
            msg = "Couldn't open database. Probably the schema has changed."
            logging.error("Database: " + msg)
            utils.alert("Schema change", msg)
            
            if mysql_active:
                logging.error("Database: Please Drop the Database in MySQL and recreate it")
                sys.exit(-1)
            else:
                self.dm.delete()
                self.restart(True)
        except sqlalchemy.exc.OperationalError as e:
            msg = "Could not open database."
            logging.error("Database: " + msg)
            utils.alert("Database Error", msg)
            logging.error("Database: Please delete Database file or restore backup!")
            
            # "HERE FIX open sqlite temp db so you canfix the problem......
            sys.exit(-1)        


        if opts.extract_last_page:
            self.library.lastpage_extractor_for_blacklist()
        
        try:

            if self.config['web.ssl']['active']:

                http_server = tornado.httpserver.HTTPServer(self, no_keep_alive = True, ssl_options={
                    "certfile": self.config['web.ssl']['certificate_file'], # "server.crt",
                    "keyfile": self.config['web.ssl']['key_file'] # "server.key",
                })
                http_server.listen(self.port_secure,address=self.bind)
                
                # "HERE fix not finished
                
                """
                redirect_handlers = [
                    (r'/(.*)', index.RedirectHandler),
                ]
      
                http_settings = {
                    'host': ServerEnvironment.GetHost(),
                    'redirect_port': self.port_secure,
                   # 'xheaders': options.options.xheaders,
                }
                """

            else:
                self.listen(self.port, no_keep_alive = True, address=self.bind)
        
        except Exception as e:
            logging.error(e)
            msg = "Couldn't open socket on port {0}. (Maybe ComicStreamer is already running?)  Quitting.".format(self.port)
            logging.error("Server: " + msg)
            utils.alert("Port not available", msg)
            sys.exit(-1)

        logging.info( "Server: Bind '{1}', Port {0}, Webroot: '{2}'".format(self.port,self.bind,self.webroot))
        
        self.version = csversion.version

        handlers = [
            # Web Pages
            (self.webroot + r"/", MainHandler),
            (self.webroot + r"/(.*)\.html", GenericPageHandler),
            (self.webroot + r"/about", AboutPageHandler),
            (self.webroot + r"/api", APIPageHandler),
            (self.webroot + r"/help", HelpPageHandler),
            (self.webroot + r"/settings", ConfigPageHandler),
            (self.webroot + r"/search", SearchPageHandler),
            (self.webroot + r"/server", ServerPageHandler),
            (self.webroot + r"/recently", RecentlyPageHandler),
            (self.webroot + r"/log", LogPageHandler),
            (self.webroot + r"/comics/browse", ComicListBrowserHandler),
            (self.webroot + r"/comiclist/browse", ComicListBrowserHandler),
            (self.webroot + r"/folders/browse(/.*)*", FoldersBrowserHandler),
            (self.webroot + r"/entities/browse(/.*)*", EntitiesBrowserHandler),
            (self.webroot + r"/comic/([0-9]+)/reader", ReaderHandler),
            (self.webroot + r"/login", LoginHandler),
            (self.webroot + r"/publishers", PublishersPageHandeler),
            (self.webroot + r"/publisher(/.*)*", PublisherPageHandeler),
            # Data
            (self.webroot + r"/dbinfo", DBInfoAPIHandler),
            (self.webroot + r"/version", VersionAPIHandler),
            (self.webroot + r"/command", ServerAPIHandler),
            (self.webroot + r"/scanstatus", ScanStatusAPIHandler),
            (self.webroot + r"/deleted", DeletedAPIHandler),
            (self.webroot + r"/comic/([0-9]+)", ComicAPIHandler),
            (self.webroot + r"/comics", ComicListAPIHandler),
            (self.webroot + r"/comiclist", ComicListAPIHandler),
            (self.webroot + r"/comic/([0-9]+)/page/([0-9]+|clear)/bookmark", ComicBookmarkAPIHandler ),
            (self.webroot + r"/comic/([0-9]+)/page/([0-9]+|clear)/blacklist", ComicBlacklistAPIHandler ),
            (self.webroot + r"/comic/([0-9]+)/page/([0-9]+|clear)/like", ComicFavoritesAPIHandler ),
            (self.webroot + r"/comic/([0-9]+)/page/([0-9]+|clear)/cache", ComicBlacklistAPIHandler ),
            (self.webroot + r"/comic/([0-9]+)/page/([0-9]+)", ComicPageAPIHandler ),
            (self.webroot + r"/comic/([0-9]+)/thumbnail", ThumbnailAPIHandler),
            (self.webroot + r"/comic/([0-9]+)/file", FileAPIHandler),
            (self.webroot + r"/entities(/.*)*", EntityAPIHandler),
            (self.webroot + r"/folders(/.*)*", FolderAPIHandler),
            #(r'/favicon.ico', tornado.web.StaticFileHandler, {'path': os.path.join(AppFolders.appBase(), "static","images")}),
            (self.webroot + r'/.*', UnknownHandler),
            
        ]


        settings = dict(
            template_path=os.path.join(AppFolders.appBase(), "gui"),
            static_path=os.path.join(AppFolders.appBase(), "static"),
            static_url_prefix=self.webroot + "/static/",
            debug=True,
            #autoreload=False,
            login_url=self.webroot + "/login",
            cookie_secret=self.config['security']['cookie_secret'],
            xsrf_cookies=True,
        )

        tornado.web.Application.__init__(self, handlers, **settings)

        self.library.loadBlacklistFromFile(os.path.join(AppFolders.static(),'comicstreamer'))
        
        if not opts.no_monitor:     
            self.monitor = Monitor(self.dm, self.config['general']['folder_list'])
            self.monitor.start()
            self.monitor.scan()
            
        self.bookmark = Bookmark(self.dm)
        self.bookmark.start()

        self.blacklist = Blacklist(self.dm)
        self.blacklist.start()

        if mysql_active:
            self.wakeup = WakeUp(self.dm)
            self.wakeup.start()
        
        if opts.launch_client and self.config['general']['launch_client']:
            if ((platform.system() == "Linux" and os.environ.has_key('DISPLAY')) or
                (platform.system() == "Darwin" and not os.environ.has_key('SSH_TTY')) or
                platform.system() == "Windows"):
               webbrowser.open("http://localhost:{0}".format(self.port), new=0)
        self.bonjour = BonjourThread(self.port)
        self.bonjour.start()

    def rebuild(self):
        # after restart, purge the DB
        sys.argv.insert(1, "--_resetdb_and_run")
        self.restart()
        
    def restart(self,fast=False):
        if not fast:
            self.shutdown()
        executable = sys.executable
        
        new_argv = ["--nobrowser"]
        new_argv.append("-p");
        new_argv.append(str(self.port))
        if self.opts.quiet:
            new_argv.append("-q")
        if self.opts.debug:
            new_argv.append("-d")
        if self.opts.no_monitor:
            new_argv.append("--nomonitor")
#        if self.opts.config_file:
#            new_argv.append("--config-file")
#            new_argv.append(self.opts.config_file)
        if self.opts.user_dir:
            new_argv.append("--user-dir")
            new_argv.append(self.opts.user_dir)
        if self.opts.webroot:
            new_argv.append("--webroot")
            new_argv.append(self.opts.webroot)
        if self.opts.bind:
            new_argv.append("-b")
            new_argv.append(self.opts.bind)
        
        if  "--_resetdb_and_run" in sys.argv:
            new_argv.append("--_resetdb_and_run")

        if getattr(sys, 'frozen', None):
            # only keep selected args
            new_argv.insert(0, os.path.basename(executable) )
            os.execv(executable, new_argv)
        else:
            new_argv.insert(0, os.path.basename(sys.argv[0]) )
            os.execl(executable, executable, *new_argv)    
        
    def shutdown(self):
        
        MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 3

        logging.info('Server: Initiating shutdown...')
        if not self.opts.no_monitor:
            self.monitor.stop()
        self.bookmark.stop()
        if mysql_active:
            self.wakeup.stop()
        self.blacklist.stop()
        self.bonjour.stop()
        
   #     logging.debug('Web: Will shutdown ComicStreamer in maximum %s seconds ...', MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)
        io_loop = tornado.ioloop.IOLoop.instance()
     
        deadline = time.time() + MAX_WAIT_SECONDS_BEFORE_SHUTDOWN
     
        def stop_loop():
            now = time.time()
            if now < deadline and (io_loop._callbacks or io_loop._timeouts):
                io_loop.add_timeout(now + 1, stop_loop)
            else:
                io_loop.stop()
                logging.info('Bye!')
        stop_loop()
        logging.debug('Server: Stopped')
        self.dm.stop()
        
    def log_request(self, handler):
        if handler.get_status() < 300:
            log_method = logging.debug
        elif handler.get_status() < 400:
            log_method = logging.debug
        elif handler.get_status() < 500:
            log_method = logging.warning
        else:
            log_method = logging.error
        request_time = 1000.0 * handler.request.request_time()
        log_method("%d %s %.2fms", handler.get_status(),
                   handler._request_summary(), request_time)
        
    def run(self):
        tornado.ioloop.IOLoop.instance().start()
    
    def runInThread(self):
        import threading
        t = threading.Thread(target=self.run)
        t.start()
