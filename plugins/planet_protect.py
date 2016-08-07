"""
StarryPy Planet Protect Plugin

Provides a means of protecting planets from being edited by players who are
not on the planet's list of allowed editors.

Original authors: AMorporkian
Updated for release: kharidiron
"""

import asyncio

from base_plugin import StorageCommandPlugin
from plugins.player_manager import Admin
from utilities import Direction, Command, send_message, EntityInteractionType


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
        self.allowed_builders = {allowed_builder.alias}

    def unprotect(self):
        self.protected = False

    def protect(self):
        self.protected = True

    def add_builder(self, builder):
        self.allowed_builders.add(builder.alias)

    def del_builder(self, builder):
        self.allowed_builders.remove(builder.alias)

    def check_builder(self, builder):
        return builder.alias in self.allowed_builders

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

    def on_entity_interact_result(self, data, connection):
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
        if not self._check_protection(connection.player.location):
            return True
        protection = self._get_protection(connection.player.location)
        if not protection.protected:
            return True
        if connection.player.check_role(Admin):
            return True
        elif connection.player.alias in protection.get_builders():
            return True
        else:
            action = data["parsed"]["interaction_type"]
            if action in [EntityInteractionType.OPEN_CREW_UI,
                          EntityInteractionType.OPEN_SPECIAL_UI,
                          EntityInteractionType.OPEN_SCRIPTED_UI,
                          EntityInteractionType.OPEN_COCKPIT_UI,
                          EntityInteractionType.OPEN_CRAFTING_UI,
                          EntityInteractionType.OPEN_NPC_UI,
                          EntityInteractionType.OPEN_SAIL_UI,
                          EntityInteractionType.OPEN_TELEPORTER_UI,
                          EntityInteractionType.GO_PRONE,
                          EntityInteractionType.NOMINAL]:
                return True
        return False

    def on_tile_update(self, data, connection):
        """
        Hook for tile update packet. Use to verify if changes to tiles are
        allowed for player.

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
        elif connection.player.alias in protection.get_builders():
            return True
        else:
            return False

    # Rather than recreating the same check for every different type of
    # packet we want to protect against, just map the process of
    # on_tile_update to all of them, since the check process is that same.
    on_damage_tile = on_tile_update
    on_damage_tile_group = on_tile_update
    on_modify_tile_list = on_tile_update
    on_tile_array_update = on_tile_update
    on_collect_liquid = on_tile_update
    on_tile_liquid_update = on_tile_update
    on_connect_wire = on_tile_update
    on_disconnect_all_wires = on_tile_update
    on_spawn_entity = on_tile_update

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
        if connection.player.location.locationtype() is "ShipWorld":
            ship = connection.player.location
            if not self._check_protection(ship):
                if ship.player == connection.player.alias:
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
        p = self.plugins.player_manager.get_player_by_alias(" ".join(data))
        if p is not None:
            protection = self._get_protection(location)
            protection.add_builder(p)
            send_message(connection,
                         "Added {} to allowed list for {}".format(
                             p.alias, connection.player.location))
            try:
                yield from p.connection.send_message(
                    "You've been granted build access on {} by {}".format(
                        connection.player.location, connection.player.alias))
            except AttributeError:
                send_message(connection,
                             "{} isn't online, granted anyways.".format(
                                 p.alias))
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
        p = self.plugins.player_manager.get_player_by_alias(" ".join(data))
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
