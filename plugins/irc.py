import asyncio

import irc3

from base_plugin import BasePlugin
from plugins.player_manager import Owner, Guest
from utilities import broadcast


class MockPlayer:
    """
    A mock player object for command passing.
    """
    owner = {x.__name__ for x in Owner.roles}
    guest = {x.__name__ for x in Guest.roles}
    roles = set()
    name = "IRCBot"


class MockProtocol:
    """
    A mock protocol for command passing.
    """

    def __init__(self, owner):
        self.owner = owner
        self.player = MockPlayer()

    @asyncio.coroutine
    def send_message(self, *messages):
        for message in messages:
            yield from self.owner.bot_write(message)
        return None


def base_cc(text, start_code, end_code=15):
    if end_code is None:
        end_code = start_code
    return chr(start_code) + text + chr(end_code)


def color(text, color="00", background=""):
    return base_cc(color + background + text, 3)


def bold(text):
    return base_cc(text, 2)


def italic(text):
    return base_cc(text, 29)


def underline(text):
    return base_cc(text, 21)


def strikethrough(text):
    return base_cc(text, 19)


def underline2(text):
    return base_cc(text, 31)


def reverse(text):
    return base_cc(text, 21)


class IRCPlugin(BasePlugin):
    name = "irc_bot"
    depends = ['command_dispatcher']

    def activate(self):
        super().activate()
        self.storage = self.plugins.player_manager.get_storage(self)
        self.protocol = MockProtocol(self)
        self.prefix = self.config.get_plugin_config('command_dispatcher')[
            'command_prefix']
        if "server" not in self.storage:
            self.storage['server'] = "irc.freenode.net"
        if "channel" not in self.storage:
            self.storage['channel'] = "#starrypy"
        if "username" not in self.storage:
            self.storage['username'] = "starrypy3k_bot"
        self.dispatcher = self.plugins.command_dispatcher
        self.bot = irc3.IrcBot(nick=self.storage['username'],
                               autojoins=[self.storage['channel']],
                               host=self.storage['server'])
        self.bot.log = self.logger
        self.bot.include('irc3.plugins.core')
        self.bot.include('irc3.plugins.userlist')
        x = irc3.event(irc3.rfc.PRIVMSG, self.forward)
        x.compile(None)
        y = irc3.event(r'^:\S+ 353 [^&#]+(?P<channel>\S+) :(?P<nicknames>.*)',
                       self.name_check)
        y.compile(None)
        self.bot.attach_events(x)
        self.bot.attach_events(y)
        self.bot.create_connection()
        self.ops = set()
        asyncio.Task(self.update_ops())

    @asyncio.coroutine
    def send_message(self, data, nick):
        message = data
        broadcast(self.factory, "IRC: <%s> %s" % (nick, message))

    def forward(self, mask, event, target, data):
        if data[0] == ".":
            asyncio.Task(self.handle_command(target, data[1:], mask))
        elif target == self.storage['channel']:
            nick = mask.split("!")[0]
            asyncio.Task(self.send_message(data, nick))
        return None

    def on_connect_success(self, data, protocol):
        asyncio.Task(self.announce_join(protocol))
        return True

    def on_client_disconnect_request(self, data, protocol):
        asyncio.Task(self.announce_leave(protocol.player))
        return True

    def on_chat_sent(self, data, protocol):
        if not data['parsed']['message'].startswith(self.prefix):
            asyncio.Task(
                self.bot_write("<{}> {}".format(protocol.player.name,
                                                data['parsed']['message'])))
        return True

    @asyncio.coroutine
    def announce_join(self, protocol):
        yield from asyncio.sleep(1)
        yield from self.bot_write("{} joined the server.".format(
            color(bold(protocol.player.name), '10')))

    @asyncio.coroutine
    def announce_leave(self, player):
        yield from self.bot_write("{} has left the server.".format(player.name))

    @asyncio.coroutine
    def bot_write(self, msg, target=None):
        if target is None:
            target = self.storage['channel']
        self.bot.privmsg(target, msg)

    @asyncio.coroutine
    def handle_command(self, target, data, mask):
        split = data.split()
        command = split[0]
        to_parse = split[1:]
        self.protocol.player.roles = self.protocol.player.guest
        if mask.split("!")[0] in self.ops:
            self.protocol.player.roles = self.protocol.player.owner
        if command in self.dispatcher.commands:
            yield from self.dispatcher.run_command(command,
                                                   self.protocol,
                                                   to_parse)
        else:
            yield from self.bot_write(target, "Command not found.")

    def name_check(self, channel=None, nicknames=None):
        self.ops = set(
            [nick[1:] for nick in nicknames.split() if nick[0] == "@"])

    @asyncio.coroutine
    def update_ops(self):
        while True:
            yield from asyncio.sleep(10)
            self.bot.send("NAMES {}".format(self.storage['channel']))
