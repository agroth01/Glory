# Author: Alexander Groth
# Version: 1.0
# License: MIT License

#------------------#
#   DEPENDENCIES   #
#------------------#
import requests
import time
import configparser
import urllib3
import os, sys
from collections import defaultdict
# import pygame mixer without welcome message
with open(os.devnull, 'w') as f:
    oldstdout = sys.stdout
    sys.stdout = f
    from pygame import mixer, error
    sys.stdout = oldstdout

#---------------#
#   CONSTANTS   #
#---------------#
EVENT_DATA_URL = "https://127.0.0.1:2999/liveclientdata/eventdata"
PLAYER_SCORE_URL = "https://127.0.0.1:2999/liveclientdata/playerscores?summonerName="
CONFIG_FILE = "config.ini"

# Tracks stats of player
class Player:
    def __init__(self, summonerName):
        self.summonerName = summonerName
        self.kills = 0
        self.deaths = 0
        self.assists = 0
        self.creepScore = 0

    # call the riot api and get stats of the player
    def _get_stats(self):
        try:
            api_path = PLAYER_SCORE_URL + self.summonerName
            result = requests.get(api_path, verify=False)
            return result.json()
        except Exception as e:
            return "fuck"

    def _set_stats(self, stats):
        self.kills = int(stats["kills"])
        self.deaths = int(stats["deaths"])
        self.assists = int(stats["assists"])
        self.creepScore = int(stats["creepScore"])

    # sets the cached stats to what is currently in game
    def refresh(self):
        self._set_stats(self._get_stats())

    # compare live game stats to cached stats and call events if changed
    def update(self, event):
        live_stats = self._get_stats()
        if (live_stats == "fuck"):
            return

        # death
        deaths = int(live_stats["deaths"])
        if (deaths != self.deaths):
            self.deaths = deaths
            event.call_event("onDeath")

        # kill
        kills = int(live_stats["kills"])
        if (kills != self.kills):
            self.kills = kills
            event.call_event("onKill")

        # assist
        assists = int(live_stats["assists"])
        if (assists != self.assists):
            self.assists = assists
            event.call_event("onAssist")

        # cs
        creepScore = int(live_stats["creepScore"])
        if (creepScore != self.creepScore):
            self.creepScore = creepScore
            event.call_event("onCreepKilled")

    # sets all stats back to 0
    def reset(self):
        self.kills = 0
        self.deaths = 0
        self.assists = 0
        self.creepScore = 0


# Contains all events to be called
class EventHandler:
    def __init__(self, root):
        self.root = root
        self.config = root.config

    # called when getting a kill
    def on_kill(self):
        if (self.config.get('Events', 'kills') != "True"):
            return

        self._play_sound(self.root.config.get('Sounds', 'onKillSound'))

    # called when dying
    def on_death(self):
        if (self.config.get('Events', 'deaths') != "True"):
            return

        self._play_sound(self.root.config.get('Sounds', 'onDeathSound'))

    # called when getting an assist
    def on_assist(self):
        if (self.config.get('Events', 'assists') != "True"):
            return

        self._play_sound(self.root.config.get('Sounds', 'onAssistSound'))

    # called when the cs of player increases
    def on_creep_kill(self):
        pass

    # called when player is inside a new game
    def on_game_join(self):
        print("Player joined game")

    # called when player is no longer inside a game
    def on_game_leave(self):
        self.root.player.reset()
        print("Player left the game")

    def _play_sound(self, soundfile):
        try:
            mixer.music.load("soundfiles/" + soundfile)
            mixer.music.play()
            print("Playing sound file: " + soundfile)
        except error:
            print("Error: Could not find sound file: " + soundfile)

# Event system implementation
class Events:
    def __init__(self):
        self.subscribers = defaultdict(list)

    def subscribe(self, event_type, function):
        self.subscribers[event_type].append(function)

    def call_event(self, event_type):
        if event_type in self.subscribers:
            for function in self.subscribers[event_type]:
                function()

# Main app object. Contains program loop and controls all modules
class Glory:
    def __init__(self):
        # create empty error message and flag
        error_message = ""
        success = True

        try:
            # load config from file
            self.config = configparser.ConfigParser()
            self.config.read(CONFIG_FILE)

            # disable the insecure warnings from requests library
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            # create and set up the audio manager
            mixer.init()
            mixer.music.set_volume(float(self.config.get('Application', 'audioVolume')))

            # load player
            self.player = Player(self.config.get('Application', 'summonerName'))

            # make sure summoner name is set
            if (self.config.get('Application', 'summonerName') == ""):
                success = False
                error_message += "Please set the summoner name in config file\n"

            # set up events
            self.events = Events()
            self.event_handler = EventHandler(self)

            # subscribe to events
            self.events.subscribe("onKill", self.event_handler.on_kill)
            self.events.subscribe("onDeath", self.event_handler.on_death)
            self.events.subscribe("onAssist", self.event_handler.on_assist)
            self.events.subscribe("onCreepKilled", self.event_handler.on_creep_kill)
            self.events.subscribe("onGameJoin", self.event_handler.on_game_join)
            self.events.subscribe("onGameLeave", self.event_handler.on_game_leave)

            # app variables
            self.in_game = False

        except Exception as e:
            success = False
            error_message += e + "\n"

        # start program if initialization is successful
        if (success):
            self._main_loop()

        else:
            self._error_handler(error_message)

    def _error_handler(self, error):
        print(error)
        input("Press ENTER to quit...")

    def _first_time_event(self):
        self.in_game = self._in_game()

        # set stats to current game stats to prevent events when starting program
        if (self.in_game):
            print("Player already in game")
            self.player.refresh()

    def _main_loop(self):
        self._first_time_event()

        while True:
            # track start of loop for delta time
            loop_start_time = time.time()

            # only run if in game
            if (self._in_game()):
                # check if player just joined a game
                if not (self.in_game):
                    self.events.call_event("onGameJoin")
                    self.in_game = True

                # update the player stats
                self.player.update(self.events)

            # not in game
            else:
                if (self.in_game):
                    self.events.call_event("onGameLeave")
                    self.in_game = False

            # keep to fixed rate
            delta = time.time() - loop_start_time
            fixedDeltaTime = float(self.config.get('Application', 'fixedDeltaTime'))
            if (delta < fixedDeltaTime):
                time.sleep(fixedDeltaTime - delta)

    # determines if there is a live game running
    def _in_game(self):
        try:
            response = requests.get(EVENT_DATA_URL, verify=False, timeout=0.5)
            if (response.json()["Events"][0]["EventName"] == "GameStart"):
                return True
            else:
                return False
        except:
            return False

if __name__ == '__main__':
    Glory()
