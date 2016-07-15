"""
StarryPy IRC Plugin

Provides a mock IRC user that echos conversations between the game server and
an IRC channel.

Original authors: AMorporkian
Updated for release: kharidiron
"""

import re
import asyncio

import irc3

from base_plugin import BasePlugin
from plugins.player_manager import Owner, Guest
from utilities import broadcast


# Roles

class IRCBot(Guest):
    is_meta = True


# Mock Objects

class MockPlayer:
    """
    A mock player object for command passing.

    We have to make it 'Mock' because there are all sorts of things in the
    real Player object that don't map correctly, and would cause all sorts
    of headaches.
    """
    owner = {x.__name__ for x in Owner.roles}
    guest = {x.__name__ for x in IRCBot.roles}
    roles = set()
    name = "IRCBot"
    logged_in = True

    def check_role(self, role):
        """
        Mimics the 'check_role' function of the real Player object.

        This is mainly a hack to make sure commands give in IRC don't give
        more information than they should (eg - only see what a guest sees).

        :param role: Role to be checked. We're ignoring this.
        :return: Boolean: False. We're a restricted bot.
        """
        return False


class MockConnection:
    """
    A mock connection object for command passing.
    """
    def __init__(self, owner):
        self.owner = owner
        self.player = MockPlayer()

    @asyncio.coroutine
    def send_message(self, *messages):
        for message in messages:
            yield from self.owner.bot_write(message)
        return None


# IRC Formatting Functions

def _base_cc(text, start_code, end_code=15):
    if end_code is None:
        end_code = start_code
    return chr(start_code) + text + chr(end_code)


def _color(text, color="00", background=""):
    return _base_cc(color + background + text, 3)


def _bold(text):
    return _base_cc(text, 2)


def _italic(text):
    return _base_cc(text, 29)


def _underline(text):
    return _base_cc(text, 21)


def _strikethrough(text):
    return _base_cc(text, 19)


def _underline2(text):
    return _base_cc(text, 31)


def _reverse(text):
    return _base_cc(text, 21)


###

class IRCPlugin(BasePlugin):
    name = "irc_bot"
    depends = ['command_dispatcher']
    default_config = {
        "server": "irc.freenode.net",
        "channel": "#starrypy",
        "username": "starrypy3k_bot",
        "strip_colors": True
    }

    def __init__(self):
        super().__init__()
        self.server = None
        self.channel = None
        self.username = None
        self.connection = None
        self.prefix = None
        self.dispatcher = None
        self.bot = None
        self.ops = None
        self.color_strip = re.compile("\^(.*?);")
        self.sc = None

    def activate(self):
        super().activate()
        self.connection = MockConnection(self)
        self.dispatcher = self.plugins.command_dispatcher
        self.prefix = self.config.get_plugin_config("command_dispatcher")[
            "command_prefix"]
        self.server = self.config.get_plugin_config(self.name)["server"]
        self.channel = self.config.get_plugin_config(self.name)["channel"]
        self.username = self.config.get_plugin_config(self.name)["username"]
        self.sc = self.config.get_plugin_config(self.name)["strip_colors"]

        self.bot = irc3.IrcBot(nick=self.username,
                               autojoins=[self.channel],
                               host=self.server)
        self.bot.log = self.logger

        self.bot.include("irc3.plugins.core")
        self.bot.include("irc3.plugins.userlist")

        x = irc3.event(irc3.rfc.PRIVMSG, self.forward)
        x.compile(None)
        y = irc3.event(r"^:\S+ 353 [^&#]+(?P<channel>\S+) :(?P<nicknames>.*)",
                       self.name_check)
        y.compile(None)
        self.bot.attach_events(x)
        self.bot.attach_events(y)
        self.bot.create_connection()

        self.ops = set()
        asyncio.Task(self.update_ops())

    # Packet hooks - look for these packets and act on them

    def on_connect_success(self, data, connection):
        """
        Hook on bot successfully connecting to server.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so packet moves on.
        """
        asyncio.Task(self.announce_join(connection))
        return True

    def on_client_disconnect_request(self, data, connection):
        """
        Hook on bot disconnecting from the server.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so packet moves on.
        """
        asyncio.Task(self.announce_leave(connection.player))
        return True

    def on_chat_sent(self, data, connection):
        """
        Hook on message being broadcast on server. Display it in IRC.

        If 'sc' is True, colors are stripped from game text. e.g. -

        ^red;Red^reset; Text -> Red Text.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so packet moves on.
        """
        if not data["parsed"]["message"].startswith(self.prefix):
            msg = data["parsed"]["message"]
            if self.sc:
                msg = self.color_strip.sub("", msg)
            asyncio.Task(
                self.bot_write("<{}> {}".format(connection.player.name, msg)))
        return True

    # Helper functions - Used by commands

    def forward(self, mask, event, target, data):
        """
        Catch a message that is sent as a private message to the bot. If the
        message begins with a '.', treat it as a server command. Otherwise,
        treat the message as normal text, and pass it along to the server.

        :param mask: Chat mask.
        :param event: Unused.
        :param target: Chat target.
        :param data: Message body.
        :return: None
        """
        if data[0] == ".":
            asyncio.Task(self.handle_command(target, data[1:], mask))
        elif target == self.channel:
            nick = mask.split("!")[0]
            asyncio.Task(self.send_message(data, nick))
        return None

    def name_check(self, channel=None, nicknames=None):
        """
        Build a list of the Ops currently in the IRC channel... I think?

        :param channel: Unused.
        :param nicknames:
        :return: Null
        """
        self.ops = set(
            [nick[1:] for nick in nicknames.split() if nick[0] == "@"])

    @asyncio.coroutine
    def send_message(self, data, nick):
        """
        Broadcast a message on the server.

        :param data: The message to be broadcast.
        :param nick: The person sending the message from IRC.
        :return: Null
        """
        message = data
        broadcast(self.factory, "IRC: <{}> {}".format(nick, message))

    @asyncio.coroutine
    def announce_join(self, connection):
        """
        Send a message to IRC when someone joins the server.

        :param connection: Connection of connecting player on server.
        :return: Null.
        """
        yield from asyncio.sleep(1)
        yield from self.bot_write(
            "{} joined the server.".format(_color(_bold(
                connection.player.name), "10")))

    @asyncio.coroutine
    def announce_leave(self, player):
        """
        Send a message to IRC when someone leaves the server.

        :param player: Player leaving server.
        :return: Null.
        """
        yield from self.bot_write(
            "{} has left the server.".format(player.name))

    @asyncio.coroutine
    def bot_write(self, msg, target=None):
        """
        Method for writing messages to IRC channel.

        :param msg: Message to be posted.
        :param target: Channel where message should be posted.
        :return: Null.
        """
        if target is None:
            target = self.channel
        self.bot.privmsg(target, msg)

    @asyncio.coroutine
    def handle_command(self, target, data, mask):
        """
        Handle commands that have been sent in via IRC.

        :param target: Channel where command should be posted.
        :param data: Packet containing the command data.
        :param mask:
        :return: Null.
        """
        split = data.split()
        command = split[0]
        to_parse = split[1:]
        self.connection.player.roles = self.connection.player.guest
        if mask.split("!")[0] in self.ops:
            self.connection.player.roles = self.connection.player.owner
        if command in self.dispatcher.commands:
            yield from self.dispatcher.run_command(command,
                                                   self.connection,
                                                   to_parse)
        else:
            yield from self.bot_write(target, "Command not found.")

    @asyncio.coroutine
    def update_ops(self):
        """
        Update the list of Ops. Maybe? Really not sure...

        :return: Null.
        """
        while True:
            yield from asyncio.sleep(6)
            self.bot.send("NAMES {}".format(self.channel))
