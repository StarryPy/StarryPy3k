import asyncio

import irc3

from base_plugin import BasePlugin

temp_server = "irc.freenode.net"
temp_channel = "##starrypy"
temp_username = "starrypytest"


class IRCPlugin(BasePlugin):
    name = "irc_bot"

    def activate(self):
        self.bot = irc3.IrcBot(nick=temp_username, autojoins=[temp_channel],
                               host=temp_server, includes=['irc3.plugins.core'])
        x = irc3.event(irc3.rfc.PRIVMSG, self.forward)
        x.compile(None)
        self.bot.create_connection()
        self.bot.add_event(x)

    def forward(self, mask, event, target, data):
        if target == temp_channel:
            nick = mask.split("!")[0]
            print(nick)
            message = data
            asyncio.Task(
                self.factory.broadcast("IRC: <%s> %s" % (nick, message)))

    def on_client_connect(self, data, protocol):
        asyncio.Task(self.announce_join(protocol))
        return True

    def on_client_disconnect(self, data, protocol):
        asyncio.Task(self.announce_leave(protocol.player))
        return True

    def on_chat_sent(self, data, protocol):
        if not data['parsed']['message'].startswith(
                self.config.config.command_prefix):
            asyncio.Task(self.bot_write("<%s> %s" %
                                        (protocol.player.name,
                                         data['parsed']['message'])))
        return True

    @asyncio.coroutine
    def announce_join(self, protocol):
        yield from asyncio.sleep(1)
        yield from self.bot_write(
            "%s joined the server." % protocol.player.name)

    @asyncio.coroutine
    def announce_leave(self, player):
        yield from self.bot_write("%s has left the server." % player.name)

    @asyncio.coroutine
    def bot_write(self, msg):
        self.bot.privmsg(temp_channel, msg)