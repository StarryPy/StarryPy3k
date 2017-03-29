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
    name = "DiscordBot"
    logged_in = True
    granted_perms = set()
    revoked_perms = set()
    permissions = set()


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
            if self.owner.irc_bot_exists:
                asyncio.ensure_future(self.owner.irc.bot_write(
                    message))
            yield from self.owner.bot_write(message)
        return None


class DiscordPlugin(BasePlugin, discord.Client):
    name = "discord_bot"
    depends = ['command_dispatcher']
    default_config = {
        "token": "-- token --",
        "client_id": "-- client_id --",
        "channel": "-- channel id --",
        "strip_colors": True,
        "log_discord": False,
        "command_prefix": "!"
    }

    def __init__(self):
        BasePlugin.__init__(self)
        discord.Client.__init__(self)
        self.token = None
        self.channel = None
        self.token = None
        self.client_id = None
        self.mock_connection = None
        self.prefix = None
        self.command_prefix = None
        self.dispatcher = None
        self.color_strip = re.compile("\^(.*?);")
        self.sc = None
        self.irc_bot_exists = False
        self.irc = None
        self.chat_manager = None

    def activate(self):
        BasePlugin.activate(self)
        self.dispatcher = self.plugins.command_dispatcher
        self.irc_bot_exists = link_plugin_if_available(self, 'irc_bot')
        if self.irc_bot_exists:
            self.irc = self.plugins['irc_bot']
        self.prefix = self.config.get_plugin_config("command_dispatcher")[
            "command_prefix"]
        self.command_prefix = self.config.get_plugin_config(self.name)[
            "command_prefix"]
        self.token = self.config.get_plugin_config(self.name)["token"]
        self.client_id = self.config.get_plugin_config(self.name)["client_id"]
        self.channel = self.config.get_plugin_config(self.name)["channel"]
        self.sc = self.config.get_plugin_config(self.name)["strip_colors"]
        asyncio.ensure_future(self.start_bot())
        self.update_id(self.client_id)
        self.mock_connection = MockConnection(self)
        if link_plugin_if_available(self, "chat_manager"):
            self.chat_manager = self.plugins['chat_manager']

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
                if self.chat_manager:
                    if not self.chat_manager.mute_check(connection.player):
                        alias = connection.player.alias
                        asyncio.ensure_future(self.bot_write("**<{}>** {}"
                                                             .format(alias,
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
            yield from self.login(self.token, loop=self.loop)
            yield from self.connect()
        except Exception as e:
            self.logger.exception(e)

    def update_id(self, client_id):
        self.client_id = client_id

    @asyncio.coroutine
    def on_message(self, message):
        yield from self.send_to_game(message)

    @asyncio.coroutine
    def send_to_game(self, message):
        """
        Broadcast a message on the server. Make sure it isn't coming from the
        bot (or else we get duplicate messages).

        :param message: The message packet.
        :return: Null
        """
        nick = message.author.display_name
        text = message.clean_content
        server = message.server
        if message.author.id != self.client_id:
            if message.content[0] == self.command_prefix:
                asyncio.ensure_future(self.handle_command(message.content[
                                                          1:], nick))
            else:
                for emote in server.emojis:
                    text = text.replace("<:{}:{}>".format(emote.name,
                                                          emote.id),
                                        ":{}:".format(emote.name))
                yield from self.factory.broadcast("[^orange;DC^reset;] <{}>"
                                                  " {}".format(nick, text),
                                                  mode=ChatReceiveMode.BROADCAST)
                if self.config.get_plugin_config(self.name)["log_discord"]:
                    self.logger.info("<{}> {}".format(nick, text))
                if self.irc_bot_exists:
                    asyncio.ensure_future(self.irc.bot_write(
                                          "[DC] <{}> {}".format(nick, text)))

    @asyncio.coroutine
    def make_announce(self, connection, circumstance):
        """
        Send a message to Discord when someone joins/leaves the server.

        :param connection: Connection of connecting player on server.
        :param circumstance:
        :return: Null.
        """
        yield from asyncio.sleep(1)
        yield from self.bot_write("**{}** has {} the server.".format(
            connection.player.alias, circumstance))

    @asyncio.coroutine
    def handle_command(self, data, user):
        split = data.split()
        command = split[0]
        to_parse = split[1:]
        self.mock_connection.player.permissions = \
            self.plugins.player_manager.ranks["Guest"]["permissions"]
        if command in self.dispatcher.commands:
            # Only handle commands that work from Discord
            if command in ('who', 'help', 'uptime'):
                if self.irc_bot_exists:
                    asyncio.ensure_future(self.irc.bot_write(
                        "[DC] <{}> .{}".format(user, " ".join(split))
                    ))
                yield from self.dispatcher.run_command(command,
                                                       self.mock_connection,
                                                       to_parse)
        else:
            yield from self.bot_write("Command not found.")

    @asyncio.coroutine
    def bot_write(self, msg, target=None):
        if target is None:
            target = self.get_channel(self.channel)
        asyncio.ensure_future(self.send_message(target, msg))
