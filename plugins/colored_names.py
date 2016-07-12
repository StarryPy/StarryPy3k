"""
StarryPy Colored Names Plugin

Provides colored names in the chat window for users based on role status. Does
not effect players nametags directly. Also provides timestamps on messages, if
so desired.

Original authors: teihoo, FZFalzar
Updated for release: kharidiron
"""

# TODO: Fundamental issue - by colorizing names, we prevent player's messages
#       from being logged in the 'players' chat tab. This is because messages
#       are sent using the 'broadcast' bit, with no username or client_id
#       attached. Instead, the message body itself contains all the trappings:
#       timestamp, username, colors and finally the message itself.

import asyncio

from utilities import DotDict
from datetime import datetime
from base_plugin import BasePlugin
from utilities import ChatSendMode


###

class ColoredNames(BasePlugin):
    name = "colored_names"
    depends = ["player_manager", "command_dispatcher"]

    def __init__(self):
        super().__init__()
        self.config = None
        self.colors = {}

    def activate(self):
        super().activate()
        self.config = self.plugins.command_dispatcher.plugin_config
        asyncio.ensure_future(self.load_config())

    @asyncio.coroutine
    def load_config(self):
        """
        Utility function for loading colored names. Check if definitions exit in
        config.json. If not, use defaults.
        :return: DotDict. Contains Role:Color definitions.
        """
        # TODO: These roles are hard-coded. Ideally, we should let server admins
        #       define their own roles and colors-per-role.
        #       See StarryPy/StarryPy3k#4.
        try:
            self.colors = DotDict(self.config.config.colors)
            self.logger.sender("Configuration loaded!")
        except AttributeError:
            self.logger.warning(
                "Failed to load from config! Initiating with default values")
            self.colors = DotDict({
                "Owner": "^#F7434C;",
                "SuperAdmin": "^#E23800;",
                "Admin": "^#C443F7;",
                "Moderator": "^#4385F7;",
                "Registered": "^#A0F743;",
                "default": "^reset;"
            })

    def on_chat_sent(self, data, connection):
        """
        Catch when someone sends a message. Add a timestamp to the message (if
        that feature is turned on). Colorize the player's name based on their
        role.
        :param data: The packet containing the message.
        :param connection: The connection from which the packet came.
        :return: Boolean. True if an error occurred while generating a colored
                 name (so that we don't stop the packet from flowing). Null if
                 the message came from the server (since it doesn't need colors)
                 or if the message is a command.
        """
        message = data['parsed']['message']
        if not message.startswith(self.config.command_prefix):
            now = datetime.now()
            try:
                # Check if option is set in config.json
                if self.config.chattimestamps:
                    timestamp = "[{}]".format(now.strftime("%H:%M"))
                else:
                    timestamp = ""
            except ValueError:
                # If not, use the default case (True)
                self.config.chattimestamps = True
                timestamp = "[{}]".format(now.strftime("%H:%M"))

            # Determine message sender for later
            sender = self.plugins['player_manager'].get_player_by_name(
                connection.player.name)

            try:
                p = data['parsed']
                if sender.name == "server":
                    # Server messages don't get colorized
                    return

                # Colorize message based on SendMode [OBSOLETE]
                # TODO: Only one chat channel now. Either this should be deleted
                #       or chat-channels will need to be re-implemented in
                #       StarryPy.
                if p['send_mode'] == ChatSendMode.WORLD:
                    cts_color = "^green;"
                elif p['send_mode'] == ChatSendMode.UNIVERSE:
                    cts_color = "^yellow;"  # <- Starbound default color
                else:
                    cts_color = "^gray;"

                sender = self.colored_name(sender)
                msg = "{}{} <{}{}> {}".format(
                    cts_color,
                    timestamp,
                    sender,
                    cts_color,
                    p['message']
                )

                # Check if people are on the same planet. If so, and WORLD chat
                # is enabled, send it only to them. Otherwise, send it to out
                # to broadcast (to everyone).
                if p['send_mode'] == ChatSendMode.WORLD:
                    for p in self.factory.protocols:
                        if p.player.location == connection.player.location:
                            yield from p.send_message(msg)
                else:
                    yield from self.factory.broadcast(msg)

            except AttributeError as e:
                self.logger.warning(
                    "AttributeError in colored_name: {}".format(str(e)))
                cts_color = ""
                yield from connection.send_message(
                    "{}<{}{}> {}".format(cts_color,
                                         connection.player.name,
                                         cts_color,
                                         sender.message))
                return True
        return

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
