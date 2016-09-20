"""
StarryPy Planet Backups Plugin

Plugin to allow the backup and restoration of worlds.

Original authors: kharidiron
"""

# TODO: This whole plugin

from base_plugin import SimpleCommandPlugin
from utilities import get_syntax, Command, send_message


class PlanetBackups(SimpleCommandPlugin):
    name = "planet_backups"
    depends = ["command_dispatcher"]

    def __init__(self):
        super().__init__()
        self.command_prefix = None
        self.commands = None

    def activate(self):
        super().activate()
        cd = self.plugins.command_dispatcher
        self.command_prefix = cd.plugin_config.command_prefix
        self.commands = cd.commands

    # Commands - In-game actions that can be performed

    # @Command("em",
    #          doc="Perform emote actions.")
    # def _emote(self, data, connection):
    #     """
    #     Command to provide in-game text emotes.
    #
    #     :param data: The packet containing the command.
    #     :param connection: The connection which sent the command.
    #     :return: Null.
    #     """
    #     if not data:
    #         # list emotes available to player
    #         pass
    #     else:
    #         # perform emote
    #         pass
