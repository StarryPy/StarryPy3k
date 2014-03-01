import asyncio

from base_plugin import BasePlugin
from utilities import extractor, syntax, send_message


class CommandDispatcher(BasePlugin):
    """
    A plugin which handles user commands. All plugins wishing to provide
    commands should register themselves through CommandDispatcher.

    This should be done by using the @Command decorator in a
    SimpleCommandPlugin subclass, though it could be done manually in tricky
    use-cases.
    """
    name = "command_dispatcher"

    def __init__(self):
        super().__init__()
        self.commands = {}

    def register(self, fn, name, aliases=None):
        """
        Registers a function with a given name. Recursively applies itself
        for any aliases provided.

        :param fn: The function to be called.
        :param name: The primary command name.
        :param aliases:
        :return:
        """
        self.logger.debug("Adding command with name %s", name)
        if aliases is not None:
            for alias in aliases:
                self.register(fn, alias)

        if name in self.commands:
            self.logger.info("Got duplicate command name")
            raise NameError("A command is already registered with the name %s"
                            % name)
        self.commands[name] = fn

    def send_syntax_error(self, command, error, protocol):
        """
        Sends a syntax error to the user regarding a command.

        :param command: The command name
        :param error: The error (a string or an exception)
        :param protocol: The player protocol.
        :return: None
        """
        send_message(protocol,
                     "Syntax error: %s" % error,
                     syntax(command,
                            self.commands[command],
                            self.config.config.command_prefix))
        return None

    def send_name_error(self, player_name, protocol):
        """
        Sends an error about an incorrect player name.
        :param player_name: The non-existent player's name
        :param protocol: The active player protocol.
        :return: None
        """
        send_message(protocol, "Unknown player %s" % player_name)
        return None

    @asyncio.coroutine
    def run_command(self, command, protocol, to_parse):
        try:
            yield from self.commands[command](extractor(to_parse),
                                              protocol)
        except SyntaxWarning as e:
            self.send_syntax_error(command, e, protocol)
        except NameError as e:
            self.send_name_error(e, protocol)
        except:
            self.logger.exception("Unknown exception encountered. Ignoring.",
                                  exc_info=True)

    def on_chat_sent(self, data, protocol):
        if data['parsed']['message'].startswith(
                self.config.config.command_prefix):
            to_parse = data['parsed']['message'][len(
                self.config.config.command_prefix):].split()
            try:
                command = to_parse[0]
            except IndexError:
                return True  # It's just a slash.
            if command not in self.commands:
                return True  # There's no command here that we know of.
            else:
                asyncio.Task(self.run_command(command, protocol, to_parse[1:]))
                return False  # We're handling the command in the event loop.
        else:
            return True
