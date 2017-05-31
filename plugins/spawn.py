"""
StarryPy Spawn Plugin

Plugin to move players ships to a designated 'spawn' planet.

Original authors: kharidiron
"""

import asyncio

import data_parser
import pparser
import packets
from base_plugin import StorageCommandPlugin
from utilities import Command, send_message, SystemLocationType


# Roles

###

class Spawn(StorageCommandPlugin):
    name = "spawn"
    depends = ["command_dispatcher"]

    def __init__(self):
        super().__init__()

    def activate(self):
        super().activate()
        if "spawn" not in self.storage:
            self.storage["spawn"] = {}

    # Helper functions - Used by commands

    @asyncio.coroutine
    def _move_ship(self, connection):
        """
        Generate packet that moves ship.

        :param connection: Player being moved to spawn.
        :return: Null.
        :raise: NotImplementedError when spawn planet not yet set.
        """
        if "spawn_location" not in self.storage["spawn"]:
            send_message(connection, "Spawn planet not currently set.")
            raise NotImplementedError
        else:
            spawn_location = self.storage["spawn"]["spawn_location"]
            destination = data_parser.FlyShip.build(dict(
                world_x=spawn_location.x,
                world_y=spawn_location.y,
                world_z=spawn_location.z,
                location=dict(
                    type=SystemLocationType.COORDINATE,
                    world_x=spawn_location.x,
                    world_y=spawn_location.y,
                    world_z=spawn_location.z,
                    world_planet=spawn_location.planet,
                    world_satellite=spawn_location.satellite
                )
            ))
            flyship_packet = pparser.build_packet(packets.packets["fly_ship"],
                                                  destination)
            yield from connection.client_raw_write(flyship_packet)

    # Commands - In-game actions that can be performed

    @Command("spawn",
             perm="spawn.spawn",
             doc="Moves a player's ship to the spawn planet.")
    def _spawn(self, data, connection):
        """
        Move a players ship to the spawn planet, free of fuel charge,
        no matter where they are in the universe.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        # TODO - Or maybe not - when player already above spawn planet,
        # nothing happens. It would be nice to generate an alert on this case.
        planet = connection.player.location
        if planet.locationtype() != "ShipWorld" or planet.uuid \
                != connection.player.uuid:
            send_message(connection,
                         "You must be on your ship for this to work.")
            return
        try:
            yield from self._move_ship(connection)
            send_message(connection,
                         "Now en route to spawn. Please stand by...")
        except NotImplementedError:
            pass

    @Command("set_spawn",
             perm="spawn.set_spawn",
             doc="Set the spawn planet.")
    def _set_spawn(self, data, connection):
        """
        Set the current planet as the spawn plant. Note, you must be standing
        on a planet for this to work.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        planet = connection.player.location
        if not str(planet).startswith("CelestialWorld"):
            send_message(connection,
                         "You must be standing on a planet for this to work.")
            return
        self.storage["spawn"]["spawn_location"] = planet
        send_message(connection, "Spawn planet set to {}.".format(str(planet)))

    @Command("show_spawn",
             perm="spawn.show_spawn",
             doc="Print the current spawn location.")
    def _show_spawn(self, data, connection):
        """
        Display the coordinates of the current spawn location.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        if "spawn_location" not in self.storage["spawn"]:
            send_message(connection, "Spawn planet not currently set.")
        else:
            spawn_location = self.storage["spawn"]["spawn_location"]
            send_message(connection, "{}".format(spawn_location))
