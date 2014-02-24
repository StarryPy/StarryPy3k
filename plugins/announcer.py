import asyncio

from base_plugin import BasePlugin


class Announcer(BasePlugin):
    @asyncio.coroutine
    def send_announce(self, protocol, message):
        yield from asyncio.sleep(1)
        yield from self.factory.broadcast("%s %s" % (protocol.player.name,
                                                     message))
        print("Sent message")
        return

    def on_client_connect(self, data, protocol):
        asyncio.Task(self.send_announce(protocol, "joined."))
        return True

    def on_client_disconnect(self, data, protocol):
        asyncio.Task(self.send_announce(protocol, "left."))
        return True