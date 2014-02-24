from base_plugin import BasePlugin


class CommandDispatcher(BasePlugin):
    name = "command_dispatcher"

    def __init__(self):
        super().__init__()
        self.commands = {}

    def register(self, fn, name, aliases=None):
        if aliases is not None:
            for alias in aliases:
                self.register(fn, alias)
        if name in self.commands:
            raise KeyError("A command is already registered with the name %s"
                           % name)
        self.commands[name] = fn

    def on_chat_sent(self, data, protocol):
        if data['parsed'].message.startswith(self.config.config.command_prefix):
            to_parse = data['parsed'].message[len(
                self.config.config.command_prefix):].split()
            command = to_parse[0]
            if command not in self.commands:
                return True
            else:
                try:
                    yield from self.commands[command](to_parse[1:], protocol)
                except:
                    self.logger.exception("Exc", exc_info=True)
                return False
        return True