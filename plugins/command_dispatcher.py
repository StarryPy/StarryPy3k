"""
StarryPy Command Dispatcher Plugin

A plugin which handles user commands. All plugins wishing to provide commands
should register themselves through CommandDispatcher.

This should be done by using the @Command decorator in a SimpleCommandPlugin
subclass, though it could be done manually in tricky use-cases.

Original authors: AMorporkian
Updated for release: kharidiron
"""

import asyncio

from base_plugin import BasePlugin
from utilities import extractor, get_syntax, send_message


class CommandDispatcher(BasePlugin):
    name = "command_dispatcher"
    default_config = {"command_prefix": "/"}

    def __init__(self):
        super().__init__()
        self.commands = {}

    # Packet hooks - look for these packets and act on them

    def on_chat_sent(self, data, connection):
        """
        Catch a chat packet as it goes by. If the first character in its
        string is the command_prefix, it is a command. Grab it and start
        interpreting its contents.

        :param data: Packet which is being transmitted.
        :param connection: Connection which sent the packet.
        :return: Boolean: True if the message is not a command (or not one we
                 know about), so that the packets keeps going. False if it is
                 a command we know, so that it stops here after it is
                 processed.
        """
        if data['parsed']['message'].startswith(
                self.plugin_config.command_prefix):
            to_parse = data['parsed']['message'][len(
                self.plugin_config.command_prefix):].split()

            try:
                command = to_parse[0]
            except IndexError:
                return True  # It's just a slash.

            if command not in self.commands:
                return True  # There's no command here that we know of.
            else:
                asyncio.ensure_future(self.run_command(command,
                                                       connection,
                                                       to_parse[1:]))
                return False  # We're handling the command in the event loop.
        else:
            # Not a command, just text, so pass it along.
            return True

    # Helper functions - Used by commands

    def register(self, fn, name, aliases=None):
        """
        Registers a function with a given name. Recursively applies itself
        for any aliases provided.

        :param fn: The function to be called.
        :param name: The primary command name.
        :param aliases: Additional names a command can have.
        :return: Null.
        :raise: NameError on duplicate command name.
        """
        self.logger.debug("Adding command with name {}".format(name))
        if aliases is not None:
            for alias in aliases:
                self.register(fn, alias)

        if name in self.commands:
            self.logger.info("Got duplicate command name")
            raise NameError("A command is already registered with the name: "
                            "{}".format(name))
        self.commands[name] = fn

    def _send_syntax_error(self, command, error, connection):
        """
        Sends a syntax error to the user regarding a command.

        :param command: The command name
        :param error: The error (a string or an exception)
        :param connection: The player connection.
        :return: None.
        """
        send_message(connection,
                     "Syntax error: {}".format(error),
                     get_syntax(command,
                                self.commands[command],
                                self.plugin_config.command_prefix))
        return None

    def _send_name_error(self, player_name, connection):
        """
        Sends an error about an incorrect player name.

        :param player_name: The non-existent player's name
        :param connection: The active player connection.
        :return: None
        """
        send_message(connection, "Unknown player {}".format(player_name))
        return None

    @asyncio.coroutine
    def run_command(self, command, connection, to_parse):
        """
        Evaluate the command passed in, passing along the arguments. Raise
        various errors depending on what might have gone wrong.

        :param command: Command to be executed. Looked up in commands dict.
        :param connection: Connection which is calling the command.
        :param to_parse: Arguments to provide to the command.
        :return: Null.
        :raise: SyntaxWarning on improper syntax usage. NameError when object
                could not be found. ValueError when improper input is provided.
                General Exception error as a last-resort catch-all.
        """
        try:
            yield from self.commands[command](extractor(to_parse),
                                              connection)
        except SyntaxWarning as e:
            self._send_syntax_error(command, e, connection)
        except NameError as e:
            self._send_name_error(e, connection)
        except ValueError as e:
            send_message(connection, str(e))
        except SystemExit as e:
            raise SystemExit
        except:
            self.logger.exception("Unknown exception encountered. Ignoring.",
                                  exc_info=True)
