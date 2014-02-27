import asyncio
import random
from base_plugin import SimpleCommandPlugin, command

__author__ = 'FZFalzar'

class ServerAds(SimpleCommandPlugin):
    name = "ServerAds"
    depends = ["colored_names"]

    #activate is main entry point for plugin
    def activate(self):
        super().activate()
        asyncio.Task(self.load_config())
        self.prevMsgIdx = 0
        self.rNum = 0
        self.broadcast = asyncio.Task(self.broadcast_thread())

    @asyncio.coroutine
    def broadcast_thread(self):
        while True:
            yield from asyncio.sleep(self.interval)
            timestamp = self.plugins.colored_names.timestamps()
            #make sure we do not re-broadcast the last message, for variety
            if len(self.serverads_list) > 1:
                while self.rNum == self.prevMsgIdx:
                    #randomly pick from the array
                    self.rNum = random.randint(0, len(self.serverads_list) - 1)
                    #override previous index
                self.prevMsgIdx = self.rNum
                print("[%s] %s %s" % (self.name, self.serverads_prefix, self.serverads_list[self.rNum]))
                yield from self.factory.broadcast("%s%s ^#00FF00;%s" % (timestamp, self.serverads_prefix, self.serverads_list[self.rNum]))
            elif len(self.serverads_list) <= 1:
                print("[%s] %s %s" % (self.name, self.serverads_prefix, self.serverads_list[0]))
                yield from self.factory.broadcast("%s%s ^#00FF00;%s" % (timestamp, self.serverads_prefix, self.serverads_list[0]))

    def dobroadcast(self):
        #make sure we do not re-broadcast the last message, for variety
        timestamp = self.plugins.colored_names.timestamps()
        if len(self.serverads_list) > 1:
            while self.rNum == self.prevMsgIdx:
                #randomly pick from the array
                self.rNum = random.randint(0, len(self.serverads_list) - 1)
                #override previous index
                self.prevMsgIdx = self.rNum
            print("[%s] %s %s" % (self.name, self.serverads_prefix, self.serverads_list[self.rNum]))
            self.factory.broadcast("%s%s ^#00FF00;%s" % (timestamp, self.serverads_prefix, self.serverads_list[self.rNum]), 0, "", "ServerAds")
        elif len(self.serverads_list) <= 1:
            print("[%s] %s %s" % (self.name, self.serverads_prefix, self.serverads_list[0]))
            self.factory.broadcast("%s%s ^#00FF00;%s" % (timestamp, self.serverads_prefix, self.serverads_list[0]), 0, "", "ServerAds")

    @command("ads_interval")
    def ads_interval(self, data, protocol):
        """Sets interval for display of serverads. Syntax: /ads_interval [duration in seconds]"""
        timestamp = self.plugins.colored_names.timestamps()
        if len(data) == 0:
            asyncio.Task(protocol.send_message(self.ads_interval.__doc__))
            asyncio.Task(protocol.send_message("%sCurrent interval: %s seconds" % timestamp, self.interval))
            return
        num = data[0]
        try:
            self.interval = int(num)
            asyncio.Task(self.save_config())
            asyncio.Task(protocol.send_message("%sInterval set -> %s seconds" % timestamp, self.interval))
        except:
            asyncio.Task(protocol.send_message("%sInvalid input! %s" % timestamp, num))
            asyncio.Task(protocol.send_message(self.ads_interval.__doc__))
            return

    @command("ads_reload")
    def ads_reload(self, data, protocol):
        """Reloads configuration values. Syntax: /ads_reload"""
        timestamp = self.plugins.colored_names.timestamps()
        asyncio.Task(self.load_config())
        asyncio.Task(protocol.send_message("%sServerAds reloaded!" % timestamp))


#=======================================================================================================================
    @asyncio.coroutine
    def load_config(self):
        try:
            self.serverads_list = self.config.config.serverads['serverads_list']
            self.serverads_prefix = self.config.config.serverads['serverads_prefix']
            self.interval = self.config.config.serverads['serverads_interval']
            print("[%s] Configuration loaded successfully" % self.name)
        except Exception as e:
            #self.logger.info("Error occured! %s" % e)
            print("[%s] Error occured! %s" % (self.name, "Failed to load config values!"))
            self.serverads_list = ["Welcome to the server!", "Have a nice stay!"]
            self.serverads_prefix = "[SA]"
            self.interval = 30

    @asyncio.coroutine
    def save_config(self):
        self.config.config.serverads['serverads_list'] = self.serverads_list
        self.config.config.serverads['serverads_prefix'] = self.serverads_prefix
        self.config.config.serverads['serverads_interval'] = self.interval
        self.config.save_config()
        print("[%s] Configuration saved successfully" % self.name)