from base_plugin import BasePlugin


class CommandDispatcher(BasePlugin):
    name = "command_dispatcher"

    def activate(self):
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
        print(data['parsed'])
        print(self.commands)
        if data['parsed'].message.startswith(self.config.config.command_prefix):
            to_parse = data['parsed'].message[len(
                self.config.config.command_prefix):].split()
            print(to_parse)
            command = to_parse[0]
            print(command)
            if command not in self.commands:
                return True
            else:
                print("Command found.")
                #if self.commands[command]
                self.commands[command](data, protocol)
                return False