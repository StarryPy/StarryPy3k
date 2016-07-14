"""
StarryPy Message of the Day (MOTD) Plugin

Provides a 'Message of the Day' text to players when the connect to the server.

Ported by: kharidiron
"""
import asyncio

from base_plugin import SimpleCommandPlugin
from plugins.player_manager import Moderator
from utilities import Command, send_message


# Roles

class SetMOTD(Moderator):
    pass


###

class MOTD(SimpleCommandPlugin):
    name = "motd"
    depends = ["command_dispatcher"]
    default_config = {"message": "Insert your MOTD message here. "
                                 "^red;Note^reset; color codes work."}

    def __init__(self):
        super().__init__()
        self.motd = None

    def activate(self):
        super().activate()
        self.motd = self.config.get_plugin_config(self.name)["message"]

    def on_connect_success(self, data, connection):
        """
        Client successfully connected hook. If a client connects, show them the
        Message of the day. We have to wrap the display of the MOTD in a future
        so that we can delay its display by one second. Otherwise, the packet
        gets sent to the client before it has a chance to render it.

        :param data: The packet saying the client connected.
        :param connection: The connection from which the packet came.
        :return: Boolean: True. Anything else stops the client from being able
                 to connect.
        """
        asyncio.ensure_future(self._display_motd(connection))
        return True

    @asyncio.coroutine
    def _display_motd(self, connection):
        """
        Helper routine for displaying the MOTD on client connect. Sleeps for
        one second before displaying the MOTD. Do this in a non-blocking
        fashion.

        :param connection: The connection we're showing the message to.
        :return: Null.
        """
        yield from asyncio.sleep(1)
        yield from send_message(connection, "{}".format(self.motd))
        return

    @Command("set_motd",
             role=SetMOTD,
             doc="Sets the 'Message of the Day' text.",
             syntax="(message text)")
    def _set_motd(self, data, connection):
        """
        Sets the 'Message of the Day' text.

        :param data: The packet containing the message.
        :param connection: The connection from which the packet came.
        :return: Boolean. True if successful, False if failed.
        """
        if data:
            new_message = " ".join(data)
            self.motd = new_message
            self.config.update_config(self.name, {"message": new_message})
            send_message(connection, "MOTD set.")
            return True

    @Command("motd",
             doc="Displays the 'Message of the Day' text.")
    def _motd(self, data, connection):
        """
        Displays the 'Message of the Day' text to the requesting user.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        asyncio.ensure_future(
            send_message(connection, "{}".format(self.motd)))
