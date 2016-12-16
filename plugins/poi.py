"""
StarryPy POI Plugin

Plugin to move players' ships to points of interest designated by admins.

Original code by: kharidiron
Reimplemented by: medeor413
"""

import asyncio

import data_parser
import pparser
import packets
from plugins.player_manager import Admin
from base_plugin import StorageCommandPlugin
from utilities import Command, send_message


# Roles

class POIControl(Admin):
    pass


###

class POI(StorageCommandPlugin):
    name = "poi"
    depends = ["command_dispatcher"]

    def __init__(self):
        super().__init__()

    def activate(self):
        super().activate()
        if "pois" not in self.storage:
            self.storage["pois"] = {}

    # Helper functions - Used by commands

    @asyncio.coroutine
    def _move_ship(self, connection, location):
        """
        Generate packet that moves ship.

        :param connection: Player being moved.
        :param location: The intended destination of the player.
        :return: Null.
        :raise: NotImplementedError when POI does not exist.
        """
        if location not in self.storage["pois"]:
            send_message(connection, "That POI does not exist!")
            raise NotImplementedError
        else:
            location = self.storage["pois"][location]
            destination = data_parser.FlyShip.build(dict(
                world_x=location.x,
                world_y=location.y,
                world_z=location.z,
                world_planet=location.planet,
                world_satellite=location.satellite
            ))
            flyship_packet = pparser.build_packet(packets.packets["fly_ship"],
                                                  destination)
            yield from connection.client_raw_write(flyship_packet)

    # Commands - In-game actions that can be performed

    @Command("poi",
             doc="Moves a player's ship to the specified Point of Interest, "
                 "or prints the POIs if no argument given.",
             syntax="[\"][POI name][\"]")
    def _poi(self, data, connection):
        """
        Move a players ship to the specified POI, free of fuel charge,
        no matter where they are in the universe.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        # TODO - Or maybe not - when player already above spawn planet,
        # nothing happens. It would be nice to generate an alert on this case.
        if len(data) == 0:
            poi_list = (self.storage["pois"].keys())
            pois = ", ".join(poi_list)
            send_message(connection,
                         "Points of Interest: {}".format(pois))
            return
        planet = connection.player.location
        poi = " ".join(data).lower()
        if planet.locationtype() != "ShipWorld" or planet.uuid.decode("utf-8")\
                != connection.player.uuid:
            send_message(connection,
                         "You must be on your ship for this to work.")
            return
        try:
            yield from self._move_ship(connection, poi)
            send_message(connection,
                         "Now en route to {}. Please stand by...".format(poi))
        except NotImplementedError:
            pass

    @Command("set_poi",
             role=POIControl,
             doc="Set the planet you're on as a POI.",
             syntax="[\"](POI name)[\"]")
    def _set_poi(self, data, connection):
        """
        Set the current planet as a Point of Interest. Note, you must be
        standing on a planet for this to work.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        planet = connection.player.location
        if len(data) == 0:
            send_message(connection,
                         "No name for POI specified.")
            return
        poi_name = " ".join(data).lower()
        if poi_name in self.storage["pois"]:
            send_message(connection,
                         "A POI with this name already exists!")
            return
        if not str(planet).startswith("CelestialWorld"):
            send_message(connection,
                         "You must be standing on a planet for this to work.")
            return
        self.storage["pois"][poi_name] = planet
        send_message(connection,
                     "POI {} added to list!".format(poi_name))

    @Command("del_poi",
             role=POIControl,
             doc="Remove the specified POI from the POI list.",
             syntax="[\"](POI name)[\"]")
    def _del_poi(self, data, connection):
        """
        Remove the specified Point of Interest from the POI list.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        if len(data) == 0:
            send_message(connection,
                         "No POI specified.")
            return
        poi_name = " ".join(data).lower()
        if poi_name in self.storage["pois"]:
            self.storage["pois"].pop(poi_name)
            send_message(connection,
                         "Deleted POI {}.".format(poi_name))
        else:
            send_message(connection,
                         "That POI does not exist.")
            return
