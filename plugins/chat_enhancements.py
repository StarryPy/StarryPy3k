"""
StarryPy Chat Enhancements Plugin

Provides enhancements to the vanilla Starbound chat, including colored names
based on user roles, and timestamps per message.

Note: Name colors are in the wrapper only, and do not actually effect the
player's name tag.

Original authors: teihoo, FZFalzar
Updated for release: kharidiron
"""
import asyncio
from datetime import datetime

import data_parser
import pparser
import packets
from base_plugin import SimpleCommandPlugin
from utilities import Command, DotDict, ChatSendMode, ChatReceiveMode, \
    send_message, link_plugin_if_available


###

class ChatEnhancements(SimpleCommandPlugin):
    name = "chat_enhancements"
    depends = ["player_manager", "command_dispatcher"]
    default_config = {"chat_timestamps": True,
                      "timestamp_color": "^gray;",
                      "colors": DotDict({
                          "Owner": "^#F7434C;",
                          "SuperAdmin": "^#E23800;",
                          "Admin": "^#C443F7;",
                          "Moderator": "^#4385F7;",
                          "Registered": "^#A0F743;",
                          "default": "^yellow;"
                      })}

    def __init__(self):
        super().__init__()
        self.command_dispatcher = None
        self.colors = None
        self.cts = None
        self.cts_color = None

    def activate(self):
        super().activate()
        self.command_dispatcher = self.plugins.command_dispatcher.plugin_config
        self.colors = self.config.get_plugin_config(self.name)["colors"]
        self.cts = self.config.get_plugin_config(self.name)["chat_timestamps"]
        self.cts_color = self.config.get_plugin_config(self.name)[
            "timestamp_color"]
        link_plugin_if_available(self, "irc_bot")

    # Packet hooks - look for these packets and act on them

    def on_connect_success(self, data, connection):
        """
        Catch when a successful connection is established. Set the player's
        chat style to be the server default.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        return True

    def on_chat_received(self, data, connection):
        sender = ""
        if data["parsed"]["name"]:
            if data["parsed"]["name"] != "server":
                sender = self.plugins['player_manager'].get_player_by_name(
                    data["parsed"]["name"])
                try:
                    sender = self.decorate_line(sender.connection)
                except AttributeError:
                    self.logger.warning("Sender {} is sending a message that "
                                        "the wrapper isn't handling correctly"
                                        "".format(data["parsed"]["name"]))
                    sender = data["parsed"]["name"]

        yield from send_message(connection,
                                data["parsed"]["message"],
                                mode=data["parsed"]["header"]["mode"],
                                client_id=data["parsed"]["header"]["client_id"],
                                name=sender,
                                channel=data["parsed"]["header"]["channel"])

    def on_chat_sent(self, data, connection):
        """
        Catch when someone sends a message. Add a timestamp to the message (if
        that feature is turned on). Colorize the player's name based on their
        role.

        :param data: The packet containing the message.
        :param connection: The connection from which the packet came.
        :return: Boolean. True if an error occurred while generating a colored
                 name (so that we don't stop the packet from flowing). Null if
                 the message came from the server (since it doesn't need
                 colors) or if the message is a command.
        """
        message = data['parsed']['message']
        if message.startswith(self.command_dispatcher.command_prefix):
            return True
        if self.plugins['chat_manager'].mute_check(connection.player):
            return False

        return True

    # Helper functions - Used by commands

    def decorate_line(self, connection):
        if self.cts:
            now = datetime.now()
            timestamp = "{}{}{}> <".format(self.cts_color,
                                           now.strftime("%H:%M"),
                                           "^reset;")
        else:
            timestamp = ""
        try:
            sender = timestamp + self._colored_name(connection.player)
        except AttributeError as e:
            self.logger.warning(
                "AttributeError in colored_name: {}".format(str(e)))
            sender = connection.player.alias
        return sender

    def _colored_name(self, data):
        """
        Generate colored name based on target's role.

        :param data: target to check against
        :return: DotDict. Name of target will be colorized.
        """
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

        return color + data.alias + "^reset;"

    @asyncio.coroutine
    def _send_to_server(self, message, mode, connection):
        msg_base = data_parser.ChatSent.build(dict(message=" ".join(message),
                                                   send_mode=mode))
        msg_packet = pparser.build_packet(packets.packets['chat_sent'],
                                          msg_base)
        yield from connection.client_raw_write(msg_packet)

    # Commands - In-game actions that can be performed

    @Command("l",
             doc="Send message only to people on same world.",
             syntax="(message)")
    def _local(self, data, connection):
        """
        Local chat. Sends a message only to characters who are on the same
        planet.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null
        """
        if self.plugins['chat_manager'].mute_check(connection.player):
            send_message(connection, "You are muted and cannot chat.")
            return False
        if data:
            yield from self._send_to_server(data,
                                            ChatSendMode.LOCAL,
                                            connection)
            return True

    @Command("u",
             doc="Send message to the entire universe.",
             syntax="(message)")
    def _universe(self, data, connection):
        """
        Universal chat. Sends a message that everyone can see.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null
        """
        if self.plugins['chat_manager'].mute_check(connection.player):
            send_message(connection, "You are muted and cannot chat.")
            return False
        if data:
            yield from self._send_to_server(data,
                                            ChatSendMode.UNIVERSE,
                                            connection)
            try:
                # Try sending it to IRC if we have that available.
                asyncio.ensure_future(
                    self.plugins["irc_bot"].bot_write(
                        "<{}> {}".format(connection.player.alias,
                                         " ".join(data))))
            except KeyError:
                pass
            return True

    @Command("p",
             doc="Send message to only party members.")
    def _party(self, data, connection):
        """
        Party chat. Sends a message to only members of your party.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null
        """
        if self.plugins['chat_manager'].mute_check(connection.player):
            send_message(connection, "You are muted and cannot chat.")
            return False
        if data:
            yield from self._send_to_server(data,
                                            ChatSendMode.PARTY,
                                            connection)
            return True

    @Command("whisper", "w",
             doc="Send message privately to a person.")
    def _whisper(self, data, connection):
        """
        Whisper. Sends a message to only one person.

        This command shadows the built-in whisper.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null
        """
        try:
            name = data[0]
        except IndexError:
            raise SyntaxWarning("No target provided.")

        recipient = self.plugins.player_manager.get_player_by_alias(name)
        if recipient is not None:
            if not recipient.logged_in:
                send_message(connection,
                             "Player {} is not currently logged in."
                             "".format(name))
                return False
            message = " ".join(data[1:])
            client_id = connection.player.client_id
            sender = self.decorate_line(connection)
            send_mode = ChatReceiveMode.WHISPER
            channel = "Private"
            yield from send_message(recipient.connection,
                                    message,
                                    client_id=client_id,
                                    name=sender,
                                    mode=send_mode,
                                    channel=channel)
            yield from send_message(connection,
                                    message,
                                    client_id=client_id,
                                    name=sender,
                                    mode=send_mode,
                                    channel=channel)
        else:
            yield from send_message(connection,
                                    "Couldn't find a player with name {}"
                                    "".format(name))
