import asyncio

from base_plugin import BasePlugin


class Announcer(BasePlugin):
    @asyncio.coroutine
    def send_announce(self, protocol, message):
        yield from self.factory.broadcast("%s %s" % (protocol.player.name,
                                                     message))
        print("Sent message")
        return

    def on_connect_response(self, data, protocol):
        if data['parsed'].success:
            asyncio.Task(self.send_announce(protocol, "joined."))
        return True

    def on_client_disconnect(self, data, protocol):
        asyncio.Task(self.send_announce(protocol, "left."))
        return True
