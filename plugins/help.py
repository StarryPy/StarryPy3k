"""
StarryPy Help Plugin

Provides the 'help' command in game, for displaying help/usage information on
in-game commands.

Original authors: AMorporkian
Updated for release: kharidiron
"""

from base_plugin import SimpleCommandPlugin
from utilities import get_syntax, Command, send_message


class HelpPlugin(SimpleCommandPlugin):
    name = "help_plugin"
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

    @Command("help",
             perm="help.help",
             doc="Help command.")
    def _help(self, data, connection):
        """
        Command to provide in-game help with commands.

        If invoked with no arguments, lists all commands available to a player.
        When invoked with a trailing command, provides usage details for the
        command.

        :param data: The packet containing the command.
        :param connection: The connection which sent the command.
        :return: Null.
        """
        if not data:
            commands = []
            for c, f in self.commands.items():
                if self.plugins.player_manager.perm_check(connection.player,
                                                          f.perm):
                    commands.append(c)
            send_message(connection,
                         "Available commands: {}".format(" ".join(
                             [command for command in sorted(commands)])))
        else:
            try:
                docstring = self.commands[data[0]].__doc__
                send_message(connection,
                             "Help for {}: {}".format(data[0], docstring),
                             get_syntax(data[0],
                                        self.commands[data[0]],
                                        self.command_prefix))
            except KeyError:
                self.logger.error("Help failed on command {}.".format(data[0]))
                send_message(connection,
                             "Unknown command {}.".format(data[0]))
