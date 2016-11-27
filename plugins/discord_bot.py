"""
StarryPy Discord Plugin

Provides a Discord bot that echos conversations between the game server and
a Discord guild channel.

Original authors: kharidiron
"""

import re
import asyncio

import discord

from base_plugin import BasePlugin
from plugins.player_manager import Owner, Guest
from utilities import ChatSendMode, ChatReceiveMode, link_plugin_if_available

bot = discord.Client()


# Roles

class DiscordBot(Guest):
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
    guest = {x.__name__ for x in DiscordBot.roles}
    roles = set()
    name = "DiscordBot"
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

# Discord listener

@bot.event
@asyncio.coroutine
def on_message(message):
    yield from DiscordPlugin.send_to_game(message)


###

class DiscordPlugin(BasePlugin):
    name = "discord_bot"
    depends = ['command_dispatcher']
    default_config = {
        "token": "-- token --",
        "client_id": "-- client_id --",
        "channel": "-- channel id --",
        "strip_colors": True,
        "log_discord": False
    }
    client_id = None
    connection = None
    dispatcher = None

    def __init__(self):
        super().__init__()
        self.token = None
        self.channel = None
        self.token = None
        self.connection = None
        self.prefix = None
        self.dispatcher = None
        self.bot = bot
        self.color_strip = re.compile("\^(.*?);")
        self.sc = None
        self.irc_bot_exists = False
        self.irc_bot = None

    def activate(self):
        super().activate()
        self.connection = MockConnection(self)
        DiscordPlugin.connection = self.connection
        self.dispatcher = self.plugins.command_dispatcher
        DiscordPlugin.dispatcher = self.dispatcher
        self.prefix = self.config.get_plugin_config("command_dispatcher")[
            "command_prefix"]
        self.token = self.config.get_plugin_config(self.name)["token"]
        self.client_id = self.config.get_plugin_config(self.name)["client_id"]
        self.channel = self.config.get_plugin_config(self.name)["channel"]
        self.sc = self.config.get_plugin_config(self.name)["strip_colors"]
        asyncio.ensure_future(self.start_bot())
        self.update_id(self.client_id)

    # Packet hooks - look for these packets and act on them

    def on_connect_success(self, data, connection):
        """
        Hook on bot successfully connecting to server.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so packet moves on.
        """
        asyncio.ensure_future(self.make_announce(connection, "joined"))
        return True

    def on_client_disconnect_request(self, data, connection):
        """
        Hook on bot disconnecting from the server.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so packet moves on.
        """
        asyncio.ensure_future(self.make_announce(connection, "left"))
        return True

    def on_chat_sent(self, data, connection):
        """
        Hook on message being broadcast on server. Display it in Discord.

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

            if data["parsed"]["send_mode"] == ChatSendMode.UNIVERSE:
                asyncio.ensure_future(
                    self.bot_write("**<{}>** {}".format(connection.player.alias,
                                                        msg)))
        return True

    # Helper functions - Used by commands

    @asyncio.coroutine
    def start_bot(self):
        """
        :param :
        :param :
        :return: Null
        """
        self.logger.info("Starting Discord Bot")
        try:
            yield from bot.login(self.token, loop=self.loop)
            yield from bot.connect()
        except Exception as e:
            self.logger.exception(e)

    @classmethod
    def update_id(cls, client_id):
        cls.client_id = client_id

    @classmethod
    @asyncio.coroutine
    def send_to_game(cls, message):
        """
        Broadcast a message on the server. Make sure it isn't coming from the
        bot (or else we get duplicate messages).

        :param message: The message packet.
        :return: Null
        """
        nick = message.author.display_name
        text = message.clean_content
        server = message.server
        if message.author.id != cls.client_id:
            if message.content[0] == ".":
                asyncio.ensure_future(cls.handle_command(message.content[1:]))
            else:
                for emote in server.emojis:
                    text = text.replace("<:{}:{}>".format(emote.name,emote.id),
                                        ":{}:".format(emote.name))
                yield from cls.factory.broadcast("<^orange;Discord^reset;> <{}> {}"
                                                 "".format(nick, text),
                                                 mode=ChatReceiveMode.BROADCAST)
                if cls.config.get_plugin_config(cls.name)["log_discord"]:
                    cls.logger.info("<{}> {}".format(nick, text))
                if link_plugin_if_available(cls, "irc_bot"):
                    asyncio.ensure_future(cls.plugins['irc_bot'].bot_write(
                                          "<DC><{}> {}".format(nick, text)))

    @asyncio.coroutine
    def make_announce(self, connection, circumstance):
        """
        Send a message to Discord when someone joins/leaves the server.

        :param connection: Connection of connecting player on server.
        :param circumstance:
        :return: Null.
        """
        yield from asyncio.sleep(1)
        yield from self.bot_write("{} has {} the server.".format(
            connection.player.alias, circumstance))

    @asyncio.coroutine
    def handle_command(data):
        split = data.split()
        command = split[0]
        to_parse = split[1:]
        DiscordPlugin.connection.player.roles = DiscordPlugin.connection.player.guest
        if command in DiscordPlugin.dispatcher.commands:
            # Only handle commands that work from Discord
            if command in ('who', 'help'):
                yield from DiscordPlugin.dispatcher.run_command(command,
                                                       DiscordPlugin.connection,
                                                       to_parse)
        else:
            yield from self.bot_write("Command not found.")

    @asyncio.coroutine
    def bot_write(self, msg, target=None):
        if target is None:
            target = bot.get_channel(self.channel)
        asyncio.ensure_future(bot.send_message(target, msg))
