import traceback

from base_plugin import SimpleCommandPlugin
from utilities import syntax, command


class HelpPlugin(SimpleCommandPlugin):
    name = "help_plugin"

    def activate(self):
        super().activate()
        self.commands = self.plugins['command_dispatcher'].commands

    @command("help", doc="Help command.")
    def _help(self, data, protocol):
        if not data:
            commands = []
            for c, f in self.commands.items():
                if f.roles - protocol.player.roles:
                    continue
                commands.append(c)
            yield from protocol.send_message(
                "Available commands: %s" % " ".join(
                    [command for command in commands]))
        else:
            try:
                yield from protocol.send_message("Help for %s: %s"
                                                 % (
                    data[0], self.commands[data[0]].__doc__))
                yield from protocol.send_message(syntax(
                    data[0],
                    self.commands[data[0]],
                    self.config.config.command_prefix))
            except:
                traceback.print_exc()
                yield from protocol.send_message(
                    "Unknown command %s." % data[0])

