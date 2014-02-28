from base_plugin import BasePlugin
from utilities import extractor, syntax


class CommandDispatcher(BasePlugin):
    name = "command_dispatcher"

    def __init__(self):
        super().__init__()
        self.commands = {}

    def register(self, fn, name, aliases=None):
        self.logger.info("Adding command with name %s", name)
        if aliases is not None:
            for alias in aliases:
                self.register(fn, alias)
        if name in self.commands:
            self.logger.info("Got duplicate command name")
            raise NameError("A command is already registered with the name %s"
                            % name)
        self.commands[name] = fn

    def on_chat_sent(self, data, protocol):
        if data['parsed']['message'].startswith(
                self.config.config.command_prefix):
            to_parse = data['parsed']['message'][len(
                self.config.config.command_prefix):].split()
            try:
                command = to_parse[0]
            except IndexError:
                return True
            if command not in self.commands:
                return True
            else:
                try:
                    yield from self.commands[command](extractor(to_parse[1:]),
                                                      protocol)
                except SyntaxWarning as e:
                    yield from protocol.send_message("Syntax error: %s" % e,
                                                     syntax(command,
                                                            self.commands[
                                                                command],
                                                            self.config.config.command_prefix))
                except NameError as e:
                    yield from protocol.send_message("Unknown player %s" % e)
                except:
                    self.logger.exception("Exc", exc_info=True)
                finally:
                    return False
        return True