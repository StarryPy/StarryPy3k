"""
StarryPy Chat Enhancements Plugin

Provides enhancements to the vanilla Starbound chat, including colored names
based on user roles, and timestamps per message.

Note: Name colors are in the wrapper only, and do not actually effect the
player's name tag.

Original authors: teihoo, FZFalzar
Updated for release: kharidiron
"""
from datetime import datetime

from base_plugin import SimpleCommandPlugin
from utilities import Command, DotDict, ChatReceiveMode, send_message


###

class ChatEnhancements(SimpleCommandPlugin):
    name = "chat_enhancements"
    depends = ["player_manager", "command_dispatcher"]
    default_config = {"chat_style": "universal",
                      "chat_timestamps": True,
                      "timestamp_color": "^gray;",
                      "colors": DotDict({
                          "Owner": "^#F7434C;",
                          "SuperAdmin": "^#E23800;",
                          "Admin": "^#C443F7;",
                          "Moderator": "^#4385F7;",
                          "Registered": "^#A0F743;",
                          "default": "^reset;"
                      })}

    def __init__(self):
        super().__init__()
        self.command_dispatcher = None
        self.colors = None
        self.cts = None
        self.cts_color = None
        self.chat_style = "universal"

    def activate(self):
        super().activate()
        self.command_dispatcher = self.plugins.command_dispatcher.plugin_config
        self.chat_style = self.config.get_plugin_config(self.name)[
            "chat_style"]
        self.colors = self.config.get_plugin_config(self.name)["colors"]
        self.cts = self.config.get_plugin_config(self.name)["chat_timestamps"]
        self.cts_color = self.config.get_plugin_config(self.name)[
            "timestamp_color"]

    # Packet hooks - look for these packets and act on them

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

        sender = self.decorate_line(connection)

        if self.chat_style == "universal":
            yield from self._send_to_universe(message,
                                              sender,
                                              connection.player.client_id)
        elif self.chat_style == "planetary":
            yield from self._send_to_planet(message,
                                            sender,
                                            connection.player.client_id,
                                            str(connection.player.location))

    # Helper functions - Used by commands

    def decorate_line(self, connection):
        if self.cts:
            now = datetime.now()
            timestamp = "{}{}{}> <".format(self.cts_color,
                                           now.strftime("%H:%M"),
                                           "^reset;")
        else:
            timestamp = ""
        player = self.plugins['player_manager'].get_player_by_alias(
            connection.player.alias)
        try:
            sender = timestamp + self._colored_name(player)
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

    def _send_to_planet(self, msg, sender, client_id, location):
        send_mode = ChatReceiveMode.CHANNEL
        channel = location
        for p in self.factory.connections:
            if str(p.player.location) == location:
                yield from send_message(p,
                                        msg,
                                        client_id=client_id,
                                        name=sender,
                                        mode=send_mode,
                                        channel=channel)

    def _send_to_universe(self, msg, sender, client_id):
        send_mode = ChatReceiveMode.BROADCAST
        channel = ""
        for p in self.factory.connections:
            yield from send_message(p,
                                    msg,
                                    client_id=client_id,
                                    name=sender,
                                    mode=send_mode,
                                    channel=channel)

    # def _send_to_party(self, msg, sender, client_id, team_id):
    #     send_mode = ChatReceiveMode.CHANNEL
    #     channel = str(team_id)
    #     for p in self.factory.connections:
    #         if str(p.player.team_id) == team_id:
    #             yield from p.send_message(msg,
    #                                       client_id=client_id,
    #                                       name=sender,
    #                                       mode=send_mode,
    #                                       channel=channel)

    # Commands - In-game actions that can be performed

    @Command("local", "l",
             doc="Send message only to people on same world.")
    def _local(self, data, connection):
        """
        Local chat. Sends a message only to characters who are on the same
        planet. If the "chat_style" variable is set to "planetary", this
        command has no special effect.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null
        """
        if self.plugins['chat_manager'].mute_check(connection.player):
            send_message(connection, "You are muted and cannot chat.")
            return False
        if data:
            message = " ".join(data)
            sender = self.decorate_line(connection)
            yield from self._send_to_planet(message,
                                            sender,
                                            connection.player.client_id,
                                            str(connection.player.location))

    @Command("universe", "u",
             doc="Send message to the entire universe.")
    def _universe(self, data, connection):
        """
        Universal chat. Sends a message that everyone can see. If the
        "chat_style" variable is set to "universal", this command has no
        special effect.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null
        """
        if self.plugins['chat_manager'].mute_check(connection.player):
            send_message(connection, "You are muted and cannot chat.")
            return False
        if data:
            message = " ".join(data)
            sender = self.decorate_line(connection)
            yield from self._send_to_universe(message,
                                              sender,
                                              connection.player.client_id)

    # @Command("party", "p",
    #          doc="Send message to only party members.")
    # def _party(self, data, connection):
    #     """
    #     Party chat. Sends a message to only members of your party. This
    #     works the same regardless of the global-chat style used.
    #
    #     :param data: The packet containing the command.
    #     :param connection: The connection from which the packet came.
    #     :return: Null
    #     """
    #     if data:
    #         message = " ".join(data)
    #         sender = self._decorate_line(connection)
    #         yield from self._send_to_party(message,
    #                                        sender,
    #                                        connection.player.client_id,
    #                                        connection.player.team_id)

    @Command("whisper", "w",
             doc="Send message privately to a person.")
    def _whisper(self, data, connection):
        """
        Whisper. Sends a message to only one person. This
        works the same regardless of the global-chat style used.

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
