"""
StarryPy Discord Plugin

Provides a Discord bot that echos conversations between the game server and
a Discord guild channel.

Original authors: kharidiron
"""

import re
import logging
import asyncio

import discord

from base_plugin import BasePlugin
from utilities import ChatSendMode, ChatReceiveMode, link_plugin_if_available


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

    def __init__(self):
        self.granted_perms = set()
        self.revoked_perms = set()
        self.permissions = set()
        self.priority = 0
        self.name = "MockPlayer"
        self.alias = "MockPlayer"

    def perm_check(self, perm):
        if not perm:
            return True
        elif "special.allperms" in self.permissions:
            return True
        elif perm.lower() in self.revoked_perms:
            return False
        elif perm.lower() in self.permissions:
            return True
        else:
            return False


class MockConnection:
    """
    A mock connection object for command passing.
    """
    def __init__(self, owner):
        self.owner = owner
        self.player = MockPlayer()

    async def send_message(self, *messages):
        for message in messages:
            message = self.owner.color_strip.sub("", message)
            await self.owner.bot_write(message,
                                            target=self.owner.command_target)
        return None

class DiscordClient(discord.Client):

    def __init__(self, plugin):
        intents = discord.Intents.default()  
        intents.message_content = True
        discord.Client.__init__(self, intents = intents)
        self.starry_plugin = plugin
        self.channel = None
        self.staff_channel = None

    async def on_ready(self):
        self.channel = self.get_channel(self.starry_plugin.channel_id)
        self.staff_channel = self.get_channel(self.starry_plugin.staff_channel_id)
        if not self.channel:
            self.starry_plugin.logger.error("Couldn't get channel! Messages can't be "
                              "sent! Ensure the channel ID is correct.")
        if not self.staff_channel:
            self.starry_plugin.logger.warning("Couldn't get staff channel! Reports "
                                "will be sent to the main channel.")

    async def on_message(self, message):
        await self.starry_plugin.send_to_game(message)


class DiscordPlugin(BasePlugin):
    name = "discord_bot"
    depends = ['command_dispatcher']
    default_config = {
        "enabled": True,
        "token": "-- token --",
        "client_id": "-- client_id --",
        "channel": "-- channel id --",
        "staff_channel": "-- channel id --",
        "strip_colors": True,
        "log_discord": False,
        "command_prefix": "!",
        "rank_roles": {
            "A Discord Rank": "A StarryPy Rank"
        }
    }

    def __init__(self):
        BasePlugin.__init__(self)
        self.enabled = True
        self.token = None
        self.channel_id = None
        self.staff_channel_id = None
        self.token = None
        self.client_id = None
        self.mock_connection = None
        self.prefix = None
        self.command_prefix = None
        self.dispatcher = None
        self.color_strip = re.compile("\^(.*?);")
        self.command_target = None
        self.sc = None
        self.irc_bot_exists = False
        self.irc = None
        self.chat_manager = None
        self.rank_roles = None
        self.discord_logger = None
        self.discord_client = None
        self.discord_task = None
        self.allowed_commands = ('who', 'help', 'uptime', 'motd', 'show_spawn',
                                 'ban', 'unban', 'kick', 'list_bans', 'mute',
                                 'unmute', 'set_motd', 'whois', 'broadcast',
                                 'user', 'del_player', 'maintenance_mode',
                                 'shutdown', 'save')

    async def activate(self):
        self.enabled = self.config.get_plugin_config(self.name)["enabled"]
        if not self.enabled:
            return;
        await super().activate()

        self.dispatcher = self.plugins.command_dispatcher
        self.irc_bot_exists = link_plugin_if_available(self, 'irc_bot')
        if self.irc_bot_exists:
            self.irc = self.plugins['irc_bot']
        self.prefix = self.config.get_plugin_config("command_dispatcher")[
            "command_prefix"]
        self.command_prefix = self.config.get_plugin_config(self.name)[
            "command_prefix"]
        self.token = self.config.get_plugin_config(self.name)["token"]
        self.client_id = int(self.config.get_plugin_config(self.name)["client_id"])
        self.channel_id = int(self.config.get_plugin_config(self.name)["channel"])
        self.staff_channel_id = int(self.config.get_plugin_config(self.name)[
            "staff_channel"])
        self.sc = self.config.get_plugin_config(self.name)["strip_colors"]

        self.discord_task = asyncio.create_task(self.start_bot())
        self.discord_task.add_done_callback(self.error_handler)

        self.mock_connection = MockConnection(self)
        self.rank_roles = self.config.get_plugin_config(self.name)[
            "rank_roles"]
        if link_plugin_if_available(self, "chat_manager"):
            self.chat_manager = self.plugins['chat_manager']
        self.discord_logger = logging.getLogger("discord")
        self.discord_logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - '
                                          '%(name)s # %(message)s',
                                          datefmt='%Y-%m-%d %H:%M:%S'))
        self.discord_logger.addHandler(ch)

    # Packet hooks - look for these packets and act on them

    async def on_connect_success(self, data, connection):
        """
        Hook on bot successfully connecting to server.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so packet moves on.
        """
        if not self.enabled:
            return True;
        asyncio.ensure_future(self.make_announce(connection, "joined")).add_done_callback(self.error_handler)
        return True

    async def on_client_disconnect_request(self, data, connection):
        """
        Hook on bot disconnecting from the server.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so packet moves on.
        """
        if not self.enabled:
            return True;
        asyncio.ensure_future(self.make_announce(connection, "left")).add_done_callback(self.error_handler)
        return True

    async def on_chat_sent(self, data, connection):
        """
        Hook on message being broadcast on server. Display it in Discord.

        If 'sc' is True, colors are stripped from game text. e.g. -

        ^red;Red^reset; Text -> Red Text.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so packet moves on.
        """
        if not self.enabled:
            return True;
        if not data["parsed"]["message"].startswith(self.prefix):
            msg = data["parsed"]["message"]
            if self.sc:
                msg = self.color_strip.sub("", msg)
            if msg == "!killdiscord": #FOR TESTING: REMOVE ME
                asyncio.ensure_future(self.discord_client.logout())
            if data["parsed"]["send_mode"] == ChatSendMode.UNIVERSE:
                if self.chat_manager:
                    if not self.chat_manager.mute_check(connection.player):
                        alias = connection.player.alias
                        asyncio.ensure_future(self.bot_write("**<{}>** {}"
                                                             .format(alias,
                                                                     msg)))
        return True

    # Helper functions - Used by commands

    async def start_bot(self):
        """
        :param :
        :param :
        :return: Null
        """
        self.logger.info("Starting Discord Bot")
        try:
            if(self.discord_client != None):
                asyncio.ensure_future(self.discord_client.close())
            self.discord_client = DiscordClient(self);
            await self.discord_client.login(self.token)
            await self.discord_client.connect()
        except Exception as e:
            self.logger.exception(e)
            raise e

    async def send_to_game(self, message):
        """
        Broadcast a message on the server. Make sure it isn't coming from the
        bot (or else we get duplicate messages).

        :param message: The message packet.
        :return: Null
        """
        nick = message.author.display_name
        text = message.clean_content
        guild = message.guild
        if message.author.id != self.client_id:
            if message.content[0] == self.command_prefix and (message.channel == self.discord_client.channel or message.channel == self.discord_client.staff_channel):
                self.command_target = message.channel
                asyncio.ensure_future(self.handle_command(message.content[1:],
                                                          message.author))
            elif message.channel == self.discord_client.channel:
                for emote in guild.emojis:
                    text = text.replace("<:{}:{}>".format(emote.name,
                                                          emote.id),
                                        ":{}:".format(emote.name))
                await self.factory.broadcast("[^orange;DC^reset;] <{}>"
                                                  " {}".format(nick, text),
                                                  mode=ChatReceiveMode.BROADCAST)
                if self.config.get_plugin_config(self.name)["log_discord"]:
                    self.logger.info("<{}> {}".format(nick, text))
                if self.irc_bot_exists and self.irc.enabled:
                    asyncio.ensure_future(self.irc.bot_write(
                                          "[DC] <{}> {}".format(nick, text)))

    async def make_announce(self, connection, circumstance):
        """
        Send a message to Discord when someone joins/leaves the server.

        :param connection: Connection of connecting player on server.
        :param circumstance:
        :return: Null.
        """
        await asyncio.sleep(1)
        if hasattr(connection, "player"):
            await self.bot_write("**{}** has {} the server.".format(
                connection.player.alias, circumstance))

    async def handle_command(self, data, user):
        split = data.split()
        command = split[0]
        to_parse = split[1:]
        roles = sorted(user.roles, reverse=True)
        role = "Guest"
        for x in roles:
            if x.name in self.rank_roles:
                role = self.rank_roles[x.name]
                break
        self.mock_connection.player.permissions = \
            self.plugins.player_manager.ranks[role.lower()]["permissions"]
        self.mock_connection.player.priority = \
            self.plugins.player_manager.ranks[role.lower()]["priority"]
        self.mock_connection.player.alias = user.display_name
        self.mock_connection.player.name = user.display_name
        if command in self.dispatcher.commands:
            # Only handle commands that work from Discord
            if command in self.allowed_commands:
                await self.dispatcher.run_command(command,
                                                       self.mock_connection,
                                                       to_parse)
            else:
                await self.bot_write("Command not handled by Discord.",
                                          target=self.command_target)
        else:
            await self.bot_write("Command not found.",
                                      target=self.command_target)

    async def bot_write(self, msg, target=None):
        if self.discord_client == None or not self.discord_client.is_ready():
            await self.start_bot()
        if target is None:
            target = self.discord_client.channel
        if target is None:
            return
        asyncio.ensure_future(target.send(msg)).add_done_callback(self.error_handler)

    def error_handler(self, future):
        try:
            future.result()
        except Exception as e:
            self.logger.error("Caught an unhandled exception in Discord bot.  Will restart.")
            self.logger.exception(e)
            self.discord_task = asyncio.create_task(self.start_bot())
            self.discord_task.add_done_callback(self.error_handler)
