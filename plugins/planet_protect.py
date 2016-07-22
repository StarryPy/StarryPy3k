"""
StarryPy Planet Protect Plugin

Provides a means of protecting planets from being edited by players who are
not on the planet's list of allowed editors.

Original authors: AMorporkian
Updated for release: kharidiron
"""

import asyncio

from base_plugin import StorageCommandPlugin
from plugins.player_manager import Admin, Ship
from utilities import Direction, Command, send_message


# Roles

class Protect(Admin):
    pass


###

class ProtectedLocation:
    """
    Prototype class for a protected planet/location.
    """
    def __init__(self, location, allowed_builder):
        self.protected = True
        self.location = location
        self.allowed_builders = {allowed_builder.name}

    def unprotect(self):
        self.protected = False

    def protect(self):
        self.protected = True

    def add_builder(self, builder):
        self.allowed_builders.add(builder.name)

    def del_builder(self, builder):
        self.allowed_builders.remove(builder.name)

    def check_builder(self, builder):
        return builder.name in self.allowed_builders

    def get_builders(self):
        return self.allowed_builders


class PlanetProtect(StorageCommandPlugin):
    name = "planet_protect"

    def activate(self):
        super().activate()
        if "locations" not in self.storage:
            self.storage["locations"] = {}

    # Packet hooks - look for these packets and act on them

    def on_world_start(self, data, connection):
        """
        Catch when a player beams onto a world.

        :param data: The packet containing the world information.
        :param connection: The connection from which the packet came.
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        asyncio.ensure_future(self._protect_ship(connection))
        return True

    def on_entity_interact(self, data, connection):
        """
        Catch when a player interacts with an object in the world.

        :param data: The packet containing the action.
        :param connection: The connection from which the packet came.
        :return: Boolean, Varied. If the server generates the packet,
                 let it pass. If planet is not protected, let it pass.
                 If player is an Admin, let it pass. If player is list of
                 builders, let it pass. Otherwise, block the packet from
                 reaching the server.
        """
        if data["direction"] == Direction.TO_CLIENT:
            return True
        if not self._check_protection(connection.player.location):
            return True
        protection = self._get_protection(connection.player.location)
        if not protection.protected:
            return True
        if connection.player.check_role(Admin):
            return True
        elif connection.player.name in protection.get_builders():
            return True
        else:
            return False

    def on_entity_create(self, data, connection):
        """
        Catch when a player performs an action that causes a new entity to
        be created.

        :param data: The packet containing the action.
        :param connection: The connection from which the packet came.
        :return: Boolean: True if player is being created, or an allowed
                 entity creation. False otherwise.
        """
        if data["direction"] == Direction.TO_SERVER:
            if data["data"][0] == 0x00:
                return True  # A player is being sent, let's let it through.
        return (yield from self.on_entity_interact(data, connection))

    # Rather than recreating the same check for every different type of
    # packet we want to protect against, just map the process of
    # on_entity_interact to all of them, since the check process is that same.
    on_damage_tile = on_entity_interact
    on_damage_tile_group = on_entity_interact
    on_spawn_entity = on_entity_interact
    on_modify_tile_list = on_entity_interact
    on_tile_update = on_entity_interact
    on_tile_array_update = on_entity_interact

    # Helper functions - Used by hooks and commands

    def _check_protection(self, location):
        """
        Check if the current location is protected.

        :param location: Location to be checked.
        :return: Boolean: True if location is in protected list, False if not.
        """
        return str(location) in self.storage["locations"]

    def _get_protection(self, location) -> ProtectedLocation:
        """
        Given a protected locations identifier (index), return the
        location's ProtectedLocation object.

        :param location: The location to be loaded.
        :return: ProtectedLocation object for location.
        """
        return self.storage["locations"][str(location)]

    def _add_protection(self, location, player):
        """
        Add an allowed builder to a location. If the location is not already
        protected, make it protected.

        :param location: Location to have builder added.
        :param player: Player to be added to builders list.
        :return: ProtectedLocation object for location.
        """
        if str(location) not in self.storage["locations"]:
            protection = ProtectedLocation(location, player)
            self.storage["locations"][str(location)] = protection
        else:
            protection = self.storage["locations"][str(location)]
            protection.protect()
            protection.add_builder(player)
        return protection

    def _disable_protection(self, location):
        """
        Remove protection from a location.

        :param location: Location to have protection removed.
        :return: Null.
        """
        self.storage["locations"][str(location)].unprotect()

    @asyncio.coroutine
    def _protect_ship(self, connection):
        """
        Add protection to a ship.

        :param connection: Connection of player to have ship protected.
        :return: Null.
        """
        yield from asyncio.sleep(.5)
        if isinstance(connection.player.location, Ship):
            ship = connection.player.location
            if not self._check_protection(ship):
                if ship.player == connection.player.name:
                    self._add_protection(ship, connection.player)
                    send_message(connection,
                                 "Your ship has been auto-protected.")

    # Commands - In-game actions that can be performed

    @Command("protect",
             role=Protect,
             doc="Protects a planet",
             syntax="")
    def _protect(self, data, connection):
        """
        Protect a location. Location is taken for the player's current
        location.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        location = connection.player.location
        self._add_protection(location, connection.player)
        send_message(connection, "Protected location: {}".format(location))

    @Command("unprotect",
             role=Protect,
             doc="Removes protection from a planet",
             syntax="")
    def _unprotect(self, data, connection):
        """
        Unprotect a location. Location is taken for the player's current
        location.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        location = connection.player.location
        self._disable_protection(location)
        send_message(connection, "Unprotected location ()".format(location))

    @Command("add_builder",
             role=Protect,
             doc="Adds a player to the current location's build list.",
             syntax="[\"](player name)[\"]")
    def _add_builder(self, data, connection):
        """
        Add a builder to the builder's list for a protected location.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        location = connection.player.location
        p = self.plugins.player_manager.get_player_by_name(" ".join(data))
        if p is not None:
            protection = self._get_protection(location)
            protection.add_builder(p)
            send_message(connection,
                         "Added {} to allowed list for {}".format(
                             p.name, connection.player.location))
            try:
                yield from p.connection.send_message(
                    "You've been granted build access on {} by {}".format(
                        connection.player.location, connection.player.name))
            except AttributeError:
                send_message(connection,
                             "{} isn't online, granted anyways.".format(
                                 p.name))
        else:
            send_message(connection,
                         "Couldn't find a player with name {}".format(
                             " ".join(data)))

    @Command("del_builder",
             role=Protect,
             doc="Deletes a player from the current location's build list",
             syntax="[\"](player name)[\"]")
    def _del_builder(self, data, connection):
        """
        Remove a builder to the builder's list for a protected location.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        p = self.plugins.player_manager.get_player_by_name(" ".join(data))
        if p is not None:
            protection = self._get_protection(connection.player.location)
            protection.del_builder(p)
            send_message(connection,
                         "Removed player from build list for this location.")
        else:
            send_message(connection,
                         "Couldn't find a player with name {}".format(
                             " ".join(data)))

    @Command("list_builders",
             role=Protect,
             doc="Lists all players granted build permissions "
                 "at current location",
             syntax="")
    def _list_builders(self, data, connection):
        """
        List all builders allowed to build at this location.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        if not self._check_protection(connection.player.location):
            send_message(connection,
                         "This location has never been protected.")
        else:
            protection = self._get_protection(connection.player.location)
            players = ", ".join(protection.get_builders())
            send_message(connection,
                         "Players allowed to build at location '{}': {}"
                         "".format(connection.player.location, players))
