#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#      wymypy.py
#
#      Copyright 2007 Marc Lentz <manatlan@gmail.com>
#
#      This program is free software; you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation; either version 2 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program; if not, write to the Free Software
#      Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
import time
import threading
import urllib2
from pandora import Pandora as PandoraPython
from pandora.connection import AuthenticationError

import config
from plugins import wPlugin

class WorkerThread(threading.Thread):
    def __init__(self, MPD, pandora):
        threading.Thread.__init__(self)
        self.mpd     = MPD
        self.pandora = pandora
        self.shouldDie = False
    
    def run(self):
        while not self.shouldDie:
            try:
                idx, tot = self.mpd.getPlaylistPosition()
                self.mpd.logger.debug("pandora_worker - tot: %d idx: %d", tot, idx)
                
                if tot - idx < 3:
                    for i in range(0,2):
                        try:
                            song = self.pandora.getNextSong()
                        except AuthenticationError:
                            self.pandora.authenticate(username=config.PANDORA_USERNAME, password=config.PANDORA_PASSWORD)
                            song = self.pandora.getNextSong()
                        self.mpd.add([song['audioURL']])
                time.sleep(5)
            except Exception, e:
                self.mpd.logger.exception(e)


class Pandora(wPlugin):
    def init(self):
        self.button_index = 51
        
        # setup proxy
        if config.PANDORA_PROXY:
           proxy_support = urllib2.ProxyHandler({"http" : config.PANDORA_PROXY})
           opener = urllib2.build_opener(proxy_support)
           urllib2.install_opener(opener)
        
        # setup pandora
        self.pandora = PandoraPython()
        if not self.pandora.authenticate(username=config.PANDORA_USERNAME, password=config.PANDORA_PASSWORD):
            raise ValueError("Wrong pandora credentials or proxy supplied")
        self.stationCache = self.pandora.getStationList()
        
        self.currentStationId = None
        self.currentStationName = None
        self.playing = False
        
        self.worker = WorkerThread(self.mpd, self.pandora)
        self.worker.daemon = True
    
    def show(self):
        return """
            <button onclick='ajax_pandora()'>Pandora</button>
        """
    
    def ajax_pandora(self):
        yield "<h2>Pandora Radio</h2>"
        
        # current station + options
        yield "Current station: " + str(self.currentStationName)
        if self.playing:
            yield """ <button onclick='ajax_pandoraOpe("stop");'>[]</button>"""
        else:
            yield """ <button onclick='ajax_pandoraOpe("play");'>></button>"""
        
        # list stations
        index = 0
        for station in self.stationCache:
            classe = index % 2 == 0 and " class='p'" or ''
            yield "<li%s>" % classe
            yield """<a href='#' onclick='ajax_switchStation("%s", "%s");'><span>></span></a>""" % (station['stationId'], station['stationName'].replace("'", ""))
            yield station ['stationName']
            yield "</li>"
            index += 1
    
    def ajax_switchStation(self, stationdId, stationName):
        self.currentStationId = stationdId
        self.currentStationName = stationName

        try:
            self.pandora.switchStation(stationdId)
        except AuthenticationError:
            self.pandora.authenticate(username=config.PANDORA_USERNAME, password=config.PANDORA_PASSWORD)
            self.pandora.switchStation(stationdId)
        except Exception, e:
            self.mpd.logger.exception(e)
        
        return self.ajax_pandora()
    
    def ajax_pandoraOpe(self, op):
        if op == "play" and self.currentStationId:
            self.worker.shouldDie = False
            self.worker.start()
            self.playing = True
        else:
            self.worker.shouldDie = True
            self.worker.join()
            self.playing = False
            
        return self.ajax_pandora()
    
