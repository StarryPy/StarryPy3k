"""
StarryPy Announcer Plugin

Announces when a player joins or leaves the server.
"""

import asyncio

from base_plugin import BasePlugin
from utilities import broadcast


class Announcer(BasePlugin):
    name = "announcer"

    @asyncio.coroutine
    def send_announce(self, connection, message):
        yield from broadcast(self.factory,
                             "{} {}".format(connection.player.name, message))

    def on_connect_success(self, data, connection):
        asyncio.ensure_future(self.send_announce(connection, "joined."))
        return True

    def on_client_disconnect_request(self, data, connection):
        asyncio.ensure_future(self.send_announce(connection, "left."))
        return True
