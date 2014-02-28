import asyncio
from utilities import DotDict
from datetime import datetime
from base_plugin import BasePlugin
 
__author__ = 'teihoo, FZFalzar'
 
 
class ColoredNames(BasePlugin):
    """
    Plugin that brings colors to player names in the chat box.
    """
    name = "colored_names"
 
    #activate is main entry point for plugin
    def activate(self):
        super().activate()
        asyncio.Task(self.load_config())

    @asyncio.coroutine
    def load_config(self):
        try:
            self.colors = DotDict(self.config.config.colors)
            self.logger.info("Configuration loaded!")
        except:
            self.logger.warning("Failed to load from config! Initiating with default values")
            self.colors = DotDict({
                "Admin": "^#F7434C",
                "SuperAdmin": "^#E23800;",
                "Admin": "^#C443F7;",
                "Moderator": "^#4385F7",
                "Registered": "^#A0F743;",
                "default": "^green;"
                })
 
    def on_chat_sent(self, data, protocol):
        #print(data)
        if not data['parsed']['message'].startswith(self.config.config.command_prefix):
            now = datetime.now()
            try:
                if self.config.config.chattimestamps:
                    timestamp = "[%s]" % now.strftime("%H:%M")
                else:
                    timestamp = ""
            except:
                self.config.config.chattimestamps=True
                timestamp = "[%s]" % now.strftime("%H:%M")
            info = self.plugins['player_manager'].get_player_by_name(protocol.player.name)
            try:
                p = data['parsed']
                if info.name == "server":
                    return
                if p['channel'] == 1:
                    cts_color = "^green;"
                elif p['channel'] == 0:
                    cts_color = "^yellow;"
                else:
                    cts_color = "^gray;"
                sender = self.colored_name(info)
                msg = "%s%s <%s%s> %s" % (
                    cts_color,
                    timestamp,
                    sender,
                    cts_color,
                    p['message']
                )
                if p['channel'] == 1:
                    for p in self.factory.protocols:
                        if p.player.location == protocol.player.location:
                            yield from p.send_message(msg)
                else:
                    yield from self.factory.broadcast(msg)
            except AttributeError as e:
                self.logger.warning("Received AttributeError in colored_name. %s", str(e))
                yield from protocol.send_message("%s<%s%s> %s" % (cts_color,
                                                                  protocol.player.name,
                                                                  cts_color,
                                                                  info.message
                                                                  ))
                return True
        return False
 
    def colored_name(self, data):
        if "Owner" in data.roles:
            color = self.colors.Owner
        elif "SuperAdmin" in data.roles:
            color = self.colors.SuperAdmin
        elif "Admin" in data.roles:
            color = self.colors.Admin
        elif "Moderator" in data.roles:
            color = self.colors.Moderator
        elif "Registered" in data.roles:
            color = self.colors.Registered
        else:
            color = self.colors.default

        return color + data.name + "^green;"