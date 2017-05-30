"""
StarryPy Planet Announcer Plugin

Announces to all players on a world when another player enters the world.
Allows Admins to set a custom greeting message on a world.

Reimplemented for StarryPy3k by medeor413.
"""

import asyncio

from base_plugin import StorageCommandPlugin
from utilities import send_message, Command


class PlanetAnnouncer(StorageCommandPlugin):
    name = "planet_announcer"
    depends = ["player_manager", "command_dispatcher"]

    def __init__(self):
        super().__init__()

    def activate(self):
        super().activate()
        if "greetings" not in self.storage:
            self.storage["greetings"] = {}

    def on_world_start(self, data, connection):
        asyncio.ensure_future(self._announce(connection))
        return True

    @asyncio.coroutine
    def _announce(self, connection):
        """
        Announce to all players in the world when a new player beams in,
        and display the greeting message to the new player, if set.

        :param connection: The connection of the player beaming in.
        :return: Null.
        """
        yield from asyncio.sleep(.5)
        location = str(connection.player.location)
        for uuid in self.plugins["player_manager"].players_online:
            p = self.plugins["player_manager"].get_player_by_uuid(uuid)
            if str(p.location) == location and p.connection != connection:
                send_message(p.connection, "{} has beamed down to the planet!"
                             .format(connection.player.alias))
        if location in self.storage["greetings"]:
            send_message(connection, self.storage["greetings"][location])

    @Command("set_greeting",
             perm="planet_announcer.set_greeting",
             doc="Sets the greeting message to be displayed when a player "
                 "enters this planet, or clears it if unspecified.")
    def _set_greeting(self, data, connection):
        location = str(connection.player.location)
        msg = " ".join(data)
        if not msg:
            if location in self.storage["greetings"]:
                self.storage["greetings"].pop(location)
                yield from send_message(connection, "Greeting message "
                                                    "cleared.")
        else:
            self.storage["greetings"][location] = msg
            yield from send_message(connection, "Greeting message set to \"{}"
                                                "\".".format(msg))
