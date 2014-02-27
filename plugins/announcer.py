import asyncio
from base_plugin import BasePlugin


class Announcer(BasePlugin):
    name = "announcer"
    depends = ["colored_names"]

    @asyncio.coroutine
    def send_announce(self, protocol, message):
        timestamp = self.plugins.colored_names.timestamps()
        player_name = self.plugins.colored_names.colored_name(protocol.player)
        yield from self.factory.broadcast("%s%s %s" % (timestamp,
                                                       player_name,
                                                       message))
        self.logger.debug("Sent announcement message for %s.",
                          protocol.player.name)

    def on_connect_response(self, data, protocol):
        if data['parsed']['success']:
            asyncio.Task(self.send_announce(protocol, "joined."))
        return True

    def on_client_disconnect(self, data, protocol):
        asyncio.Task(self.send_announce(protocol, "left."))
        return True
