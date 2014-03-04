import aiohttp
import asyncio
from base_plugin import BasePlugin
 
 
class Pushover(BasePlugin):
    """
    Sends a Pushover (pushover.net) notification whenever a player joins.
    """
    name = "pushover"
    default_config = {"sound_depart": "none", "sound_join": "none"}

    @asyncio.coroutine
    def send_pushover(self, msg, sound):
        payload = {'token': self.plugin_config.api_key, 
                   'user': self.plugin_config.user_key, 
                   'message': msg,
                   'sound': sound}
        response = yield from aiohttp.request("POST",
                                              'https://api.pushover.net/1/messages.json',
                                              data=payload)
        body = (yield from response.read())
        response.close()
 
    def on_connect_response(self, data, protocol):
        name = protocol.player.name
        if self.plugin_config.send_join and name not in self.plugin_config.ignored_players:
            message = "Player %s has joined the server" % name
            
            asyncio.Task(self.send_pushover(message, self.plugin_config.sound_depart))
            return True

    def on_client_disconnect(self, data, protocol):
        name = protocol.player.name
        if self.plugin_config.send_depart and name not in self.plugin_config.ignored_players:
            message = "Player %s has left the server" % name
            
            asyncio.Task(self.send_pushover(message, self.plugin_config.sound_join))
            return True
