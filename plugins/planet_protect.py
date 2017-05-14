"""
StarryPy Planet Protect Plugin

Provides a means of protecting planets from being edited by players who are
not on the planet's list of allowed editors.

Original authors: AMorporkian
Updated for release: kharidiron
"""

import asyncio

import time

import packets
import pparser
from base_plugin import StorageCommandPlugin
from data_parser import GiveItem
from utilities import Direction, Command, send_message, \
    EntityInteractionType, EntitySpawnType


###

class ProtectedLocation:
    """
    Prototype class for a protected planet/location.
    """
    def __init__(self, location, allowed_builder):
        self.protected = True
        self.location = location
        self.allowed_builders = {allowed_builder.uuid}

    def unprotect(self):
        self.protected = False

    def protect(self):
        self.protected = True

    def add_builder(self, builder):
        self.allowed_builders.add(builder.uuid)

    def del_builder(self, builder):
        if builder.uuid in self.allowed_builders:
            self.allowed_builders.remove(builder.uuid)

    def check_builder(self, builder):
        return builder.uuid in self.allowed_builders

    def get_builders(self):
        return self.allowed_builders


class PlanetProtect(StorageCommandPlugin):
    name = "planet_protect"
    depends = ["player_manager", "command_dispatcher"]

    def activate(self):
        super().activate()
        if "locations" not in self.storage:
            self.storage["locations"] = {}
        if "converted" not in self.storage:
            for protection in self.storage["locations"].values():
                convert = {}
                for alias in protection.allowed_builders:
                    plr = self.plugins['player_manager']\
                        .get_player_by_alias(alias)
                    if plr:
                        convert[alias] = plr.uuid
                protection.allowed_builders = {x for x in convert.values()}
            self.storage["converted"] = True

    # Packet hooks - look for these packets and act on them

    def on_spawn_entity(self, data, connection):
        """
        Catch when a player tries spawning an object in the world.

        :param data: The packet containing the action.
        :param connection: The connection from which the packet came.
        :return: Boolean, Varied. If the server generates the packet,
                 let it pass. If planet is not protected, let it pass.
                 If player is an Admin, let it pass. If player is list of
                 builders, let it pass. Otherwise, block the packet from
                 reaching the server.
        """
        if not self.check_protection(connection.player.location):
            return True
        protection = self.get_protection(connection.player.location)
        if not protection.protected:
            return True
        if connection.player.perm_check("planet_protect.bypass"):
            return True
        elif protection.check_builder(connection.player):
            return True
        else:
            action = data["parsed"]["spawn_type"]
            if action not in [EntitySpawnType.OBJECT, EntitySpawnType.VEHICLE]:
                return True
        yield from self._protection_warn(data, connection)

        item_base = GiveItem.build(dict(name=data["parsed"]["payload"],
                                        count=1,
                                        variant_type=7,
                                        description=""))
        item_packet = pparser.build_packet(packets.packets['give_item'],
                                           item_base)
        yield from asyncio.sleep(.1)
        yield from connection.raw_write(item_packet)
        return False

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
        if not self.check_protection(connection.player.location):
            return True
        protection = self.get_protection(connection.player.location)
        if not protection.protected:
            return True
        elif connection.player.perm_check("planet_protect.bypass"):
            return True
        elif protection.check_builder(connection.player):
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
        yield from self._protection_warn(data, connection)
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
        if not self.check_protection(connection.player.location):
            return True
        protection = self.get_protection(connection.player.location)
        if not protection.protected:
            return True
        elif connection.player.perm_check("planet_protect.bypass"):
            return True
        elif protection.check_builder(connection.player):
            return True
        else:
            yield from self._protection_warn(data, connection)
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

    # Helper functions - Used by hooks and commands

    def check_protection(self, location):
        """
        Check if the current location is protected.

        :param location: Location to be checked.
        :return: Boolean: True if location is in protected list, False if not.
        """
        if str(location) in self.storage["locations"]:
            protection = self.get_protection(str(location))
            return protection.protected
        else:
            return str(location) in self.storage["locations"]

    def get_protection(self, location) -> ProtectedLocation:
        """
        Given a protected locations identifier (index), return the
        location's ProtectedLocation object.

        :param location: The location to be loaded.
        :return: ProtectedLocation object for location.
        """
        return self.storage["locations"][str(location)]

    def add_protection(self, location, player):
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

    def disable_protection(self, location):
        """
        Remove protection from a location.

        :param location: Location to have protection removed.
        :return: Null.
        """
        self.storage["locations"][str(location)].unprotect()

    @asyncio.coroutine
    def _protection_warn(self, data, connection):
        """
        Warn a player about planet being protected (if they do a restricted
        activity). One minute cool-down between warnings.
        """
        try:
            if time.time() - connection.player.warned < 60:
                return
        except AttributeError:
            connection.player.warned = time.time()
            self.logger.debug(connection.player.warned)

        send_message(connection,
                     "^red;This is a protected planet and you're not "
                     "allowed to do that.^reset;")
        self.logger.debug("Warning {}; on a protected planet.".format(
            connection.player.alias
        ))
        connection.player.warned = time.time()

    # Commands - In-game actions that can be performed

    @Command("protect",
             perm="planet_protect.protect",
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
        self.add_protection(location, connection.player)
        send_message(connection, "Protected location: {}".format(location))

    @Command("unprotect",
             perm="planet_protect.protect",
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
        self.disable_protection(location)
        send_message(connection, "Unprotected location ()".format(location))

    @Command("add_builder",
             perm="planet_protect.manage_protection",
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
        p = self.plugins.player_manager.find_player(" ".join(data))
        if p is not None:
            protection = self.get_protection(location)
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
             perm="planet_protect.manage_protection",
             doc="Deletes a player from the current location's build list",
             syntax="[\"](player name)[\"]")
    def _del_builder(self, data, connection):
        """
        Remove a builder to the builder's list for a protected location.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        p = self.plugins.player_manager.find_player(" ".join(data))
        if p is not None:
            protection = self.get_protection(connection.player.location)
            protection.del_builder(p)
            send_message(connection,
                         "Removed player from build list for this location.")
        else:
            send_message(connection,
                         "Couldn't find a player with name {}".format(
                             " ".join(data)))

    @Command("list_builders",
             perm="planet_protect.manage_protection",
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
        if not self.check_protection(connection.player.location):
            send_message(connection,
                         "This location has never been protected.")
        else:
            protection = self.get_protection(connection.player.location)
            uuids = protection.get_builders()
            aliases = []
            for uid in uuids:
                aliases.append(self.plugins['player_manager']
                               .get_player_by_uuid(uid).alias)
            aliases = ", ".join(aliases)
            send_message(connection,
                         "Players allowed to build at location '{}': {}"
                         "".format(connection.player.location, aliases))
