"""
StarryPy Chat Enhancements Plugin

Provides enhancements to the vanilla Starbound chat, including colored names
based on user roles, and timestamps per message.

Note: Name colors are in the wrapper only, and do not actually effect the
player's name tag.

Original authors: teihoo, FZFalzar
Updated for release: kharidiron
"""

from utilities import DotDict, ChatReceiveMode
from datetime import datetime
from base_plugin import BasePlugin


###

class ChatEnhancements(BasePlugin):
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
        if not message.startswith(
                self.command_dispatcher.command_prefix):

            if self.cts:
                now = datetime.now()
                timestamp = "{}{}{}> <".format(self.cts_color,
                                               now.strftime("%H:%M"),
                                               "^reset;")
            else:
                timestamp = ""

            # Determine message sender for later; we do it this way so we
            # can get the role information conveniently at the same time.
            sender = self.plugins['player_manager'].get_player_by_name(
                connection.player.name)
            client_id = connection.player.client_id
            msg = data['parsed']['message']

            try:
                sender = timestamp + self.colored_name(sender)

                if self.chat_style == "universal":
                    send_mode = ChatReceiveMode.BROADCAST
                    channel = ""

                    for p in self.factory.connections:
                        yield from p.send_message(msg,
                                                  client_id=client_id,
                                                  name=sender,
                                                  mode=send_mode,
                                                  channel=channel)
                elif self.chat_style == "planetary":
                    send_mode = ChatReceiveMode.CHANNEL
                    channel = "FIXME"
                    # TODO: Need to make Starbound-compatible location names
                    for p in self.factory.connections:
                        if p.player.location == connection.player.location:
                            yield from p.send_message(msg,
                                                      client_id=client_id,
                                                      name=sender,
                                                      mode=send_mode,
                                                      channel=channel)

                # Check if people are on the same planet. If so, and WORLD chat
                # is enabled, send it only to them. Otherwise, send it to out
                # to broadcast (to everyone).
                # if p['send_mode'] == ChatSendMode.WORLD:
                #     for p in self.factory.connections:
                #         if p.player.location == connection.player.location:
                #             yield from p.send_message(msg)
                # else:
                #     yield from self.factory.broadcast(msg)
            except AttributeError as e:
                self.logger.warning(
                    "AttributeError in colored_name: {}".format(str(e)))
                for p in self.factory.connections:
                    yield from p.send_message(msg,
                                              client_id=client_id,
                                              name=connection.player.name,
                                              mode=ChatReceiveMode.BROADCAST)
                return True
        return

    # Helper functions - Used by commands

    def colored_name(self, data):
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

        return color + data.name + "^reset;"
