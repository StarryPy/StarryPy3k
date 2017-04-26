"""
StarryPy Claims Plugin

Extends the planet protect plugin to allow registered users to claim and
protect a limited number of planets.

Author: medeor413
"""

import asyncio
import packets

from base_plugin import StorageCommandPlugin
from data_parser import PlayerWarp
from pparser import build_packet
from utilities import Command, send_message, link_plugin_if_available


class Claims(StorageCommandPlugin):
    name = "claims"
    depends = ["player_manager", "command_dispatcher", "planet_protect"]
    default_config = {"max_claims_per_person": 5}

    def __init__(self):
        super().__init__()
        self.max_claims = None
        self.planet_protect = self.plugins["planet_protect"]
        self.planet_announcer = None

    def activate(self):
        super().activate()
        if "owners" not in self.storage:
            self.storage["owners"] = {}
        if "access" not in self.storage:
            self.storage["access"] = {}
        self.max_claims = self.config.get_plugin_config(self.name)[
            "max_claims_per_person"]
        if link_plugin_if_available(self, "planet_announcer"):
            self.planet_announcer = self.plugins["planet_announcer"]

    def is_owner(self, connection, location):
        uuid = connection.player.uuid
        if connection.player.perm_check("planet_protect.bypass"):
            return True
        if uuid not in self.storage["owners"]:
            return False
        elif str(location) not in self.storage["owners"][uuid]:
            return False
        else:
            return True

    def on_world_start(self, data, connection):
        """
        Catch when a player beams onto a world.

        :param data: The packet containing the world information.
        :param connection: The connection from which the packet came.
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        asyncio.ensure_future(self._protect_ship(connection))
        asyncio.ensure_future(self._access_check(connection))
        return True

    @asyncio.coroutine
    def _protect_ship(self, connection):
        """
        Add protection to a ship.

        :param connection: Connection of player to have ship protected.
        :return: Null.
        """
        yield from asyncio.sleep(3)
        try:
            if connection.player.location.locationtype() is "ShipWorld":
                ship = connection.player.location
                uuid = connection.player.uuid
                if ship.uuid.decode("utf-8") == uuid:
                    if not self.planet_protect.check_protection(ship):
                        self.planet_protect. add_protection(ship,
                                                            connection.player)
                        send_message(connection,
                                     "Your ship has been auto-claimed in "
                                     "your name.")
                        if uuid not in self.storage["owners"]:
                            self.storage["owners"][uuid] = []
                        self.storage["owners"][uuid].append(str(ship))
                    if uuid not in self.storage["owners"]:
                        self.storage["owners"][uuid] = [str(ship)]
                    elif str(ship) not in self.storage["owners"][uuid]:
                        self.storage["owners"][uuid].append(str(ship))
        except AttributeError:
            pass

    @asyncio.coroutine
    def _access_check(self, connection):
        yield from asyncio.sleep(.5)
        if str(connection.player.location) in self.storage["access"]:
            access = self.storage["access"][str(connection.player.location)]
            if connection.player.perm_check("planet_protect.bypass"):
                return
            elif connection.player.uuid in access["list"] and not \
                    access["whitelist"]:
                wp = PlayerWarp.build({"warp_action": {"warp_type": 3,
                                                       "alias_id": 2}})
                full = build_packet(packets.packets['player_warp'], wp)
                yield from connection.client_raw_write(full)
            elif connection.player.uuid not in access["list"] and \
                    access["whitelist"]:
                wp = PlayerWarp.build({"warp_action": {"warp_type": 3,
                                                       "alias_id": 2}})
                full = build_packet(packets.packets['player_warp'], wp)
                yield from connection.client_raw_write(full)

    # noinspection PyMethodMayBeStatic
    def _pretty_world_name(self, location):
        """
        Returns a more nicely formatted version of a raw world name.
        Currently only works with CelestialWorld names.

        :param location: String: The name to be formatted.
        :return: String: A formatted version of the name.
        """
        loc = location.split(":")
        if loc.pop(0) != "CelestialWorld":
            return location
        else:
            loc[0] = "X: " + loc[0]
            loc[1] = "Y: " + loc[1]
            loc.remove(loc[2])
            if loc[3] is "0":
                loc.remove(loc[3])
            else:
                loc[3] = chr(int(loc[3]) + ord("a"))
            return " ".join(loc)

    @Command("claim",
             perm="claims.claim",
             doc="Claim a planet to be protected.")
    def _claim(self, data, connection):
        location = connection.player.location
        uuid = connection.player.uuid
        if self.planet_protect.check_protection(location):
            send_message(connection, "This location is already protected.")
        elif not str(location).startswith("CelestialWorld"):
            send_message(connection, "This location cannot be claimed.")
        elif uuid not in self.storage["owners"]:
            self.storage["owners"][uuid] = []
            self.storage["owners"][uuid].append(str(location))
            self.planet_protect.add_protection(location, connection.player)
            send_message(connection, "Successfully claimed planet {}."
                         .format(location))
        else:
            if len(self.storage["owners"][uuid]) >= self.max_claims:
                send_message(connection, "You have reached the maximum "
                                         "number of claimed planets.")
            else:
                self.storage["owners"][uuid].append(str(location))
                self.planet_protect.add_protection(location, connection.player)
                send_message(connection, "Successfully claimed planet {}."
                             .format(location))

    @Command("unclaim",
             perm="claims.claim",
             doc="Unclaim and unprotect the planet you're standing on.")
    def _unclaim(self, data, connection):
        location = connection.player.location
        uuid = connection.player.uuid
        if not self.planet_protect.check_protection(location):
            send_message(connection, "This planet is not protected.")
        elif not self.is_owner(connection, location):
            send_message(connection, "You don't own this planet!")
        elif location.locationtype() is "ShipWorld":
            send_message(connection, "Can't unclaim your ship!")
        else:
            self.storage["owners"][uuid].remove(str(location))
            if len(self.storage["owners"][uuid]) == 0:
                self.storage["owners"].pop(uuid)
            self.planet_protect.disable_protection(location)
            send_message(connection, "Unclaimed planet {} "
                                     "successfully.".format(location))

    @Command("add_builder",
             priority=1,
             perm="claims.manage_claims",
             doc="Add someone to the protected list of your planet.")
    def _add_builder(self, data, connection):
        location = connection.player.location
        alias = connection.player.alias
        uuid = connection.player.uuid
        target = self.plugins.player_manager.find_player(" ".join(data))
        if not self.planet_protect.check_protection(location):
            send_message(connection, "This location is not protected.")
        if target is not None:
            if not self.is_owner(connection, location):
                send_message(connection, "You don't own this planet!")
            else:
                protection = self.planet_protect.get_protection(location)
                protection.add_builder(target)
                try:
                    send_message(connection, "Granted build access to player"
                                             " {}.".format(target.alias))
                    yield from send_message(target.connection, "You've been "
                                                               "granted build "
                                                               "access on {}."
                                            .format(location))
                except AttributeError:
                    send_message(connection, "Player {} isn't online, granted "
                                             "build access anyways."
                                 .format(target.alias))
        else:
            send_message(connection, "Player {} could not be found."
                         .format(" ".join(data)))

    @Command("del_builder",
             priority=1,
             perm="claims.manage_claims",
             doc="Remove someone from the protected list of your planet.")
    def _del_builder(self, data, connection):
        location = connection.player.location
        alias = connection.player.alias
        uuid = connection.player.uuid
        target = self.plugins.player_manager.find_player(" ".join(data))
        if not self.planet_protect.check_protection(location):
            send_message(connection, "This location is not protected.")
        if target is not None:
            if not self.is_owner(connection, location):
                send_message(connection, "You don't own this planet!")
            elif str.lower(target.alias) == str.lower(alias):
                send_message(connection, "Can't remove yourself from the build"
                                         " list!")
            else:
                protection = self.planet_protect.get_protection(location)
                protection.del_builder(target)
                send_message(connection, "Player {} was removed from the "
                                         "build list for location {}."
                             .format(target.alias, location))
        else:
            send_message(connection, "Player {} could not be found."
                         .format(" ".join(data)))

    @Command("list_builders",
             priority=1,
             perm="claims.manage_claims",
             doc="List all of the people allowed to build on this planet.")
    def _list_builders(self, data, connection):
        uuid = connection.player.uuid
        location = connection.player.location
        if not self.planet_protect.check_protection(location):
            send_message(connection, "This location is not protected.")
        elif not self.is_owner(connection, location):
            send_message(connection, "You don't own this planet!")
        else:
            protection = self.planet_protect.get_protection(location)
            uuids = protection.get_builders()
            players = ", ".join([self.plugins['player_manager']
                                .get_player_by_uuid(x).alias for x in uuids])
            send_message(connection,
                         "Players allowed to build at location '{}': {}"
                         "".format(connection.player.location, players))

    @Command("change_owner",
             perm="claims.manage_claims",
             doc="Transfer ownership of the planet to another person.")
    def _change_owner(self, data, connection):
        uuid = connection.player.uuid
        location = connection.player.location
        target = self.plugins.player_manager.find_player(" ".join(data))
        if not self.planet_protect.check_protection(location):
            send_message(connection, "This location is not protected.")
        if target is not None:
            if not self.is_owner(connection, location):
                send_message(connection, "You don't own this planet!")
            elif location.locationtype() is "ShipWorld":
                send_message(connection, "Can't transfer ownership of your "
                                         "ship!")
            elif target.perm_check("claims.claim"):
                send_message(connection, "Target is not high enough rank to "
                                         "own a planet!")
            else:
                if target.uuid not in self.storage["owners"]:
                    self.storage["owners"][target.uuid] = []
                if len(self.storage["owners"][target.uuid]) >= \
                        self.max_claims:
                    send_message(connection, "The target player has reached "
                                             "the maximum number of claims!")
                    return
                self.storage["owners"][target.uuid].append(str(location))
                self.storage["owners"][uuid].remove(str(location))
                if len(self.storage["owners"][uuid]) == 0:
                    self.storage["owners"].pop(uuid)
                self.planet_protect.add_protection(location, target)
                send_message(connection, "Transferred ownership of {} to {}."
                             .format(location, target.alias))
                try:
                    yield from send_message(target.connection, "You've been "
                                                               "made owner of "
                                                               "{}."
                                            .format(location))
                except AttributeError:
                    send_message(connection, "Player {} isn't online, "
                                             "made owner anyways."
                                 .format(target.alias))
        else:
            send_message(connection, "Player {} could not be found."
                         .format(" ".join(data)))

    @Command("list_claims",
             perm="claims.claim",
             doc="List all of the planets you've claimed.")
    def _list_claims(self, data, connection):
        uuid = connection.player.uuid
        if self.storage["owners"][uuid]:
            send_message(connection, "You've claimed the following worlds:")
            for location in self.storage["owners"][uuid]:
                send_message(connection, self._pretty_world_name(location))
        else:
            send_message(connection, "You haven't claimed any worlds.")

    @Command("set_greeting",
             priority=1,
             perm="claims.manage_claims",
             doc="Sets a custom greeting message for the planet, or clears "
                 "it if unspecified.")
    def _set_greeting(self, data, connection):
        location = str(connection.player.location)
        msg = " ".join(data)
        if self.planet_announcer:
            if self.is_owner(connection, location):
                if not msg:
                    if location in self.planet_announcer.storage["greetings"]:
                        self.planet_announcer.storage["greetings"].pop(
                            location)
                        yield from send_message(connection, "Greeting message "
                                                            "cleared.")
                else:
                    self.planet_announcer.storage["greetings"][location] = msg
                    yield from send_message(connection, "Greeting message "
                                                        "set to \"{}\"."
                                            .format(msg))
            else:
                yield from send_message(connection, "You don't own this "
                                                    "planet!")
        else:
            send_message(connection, "Planet greetings are not available on "
                                     "this server.")

    @Command("planet_access",
             perm="claims.planet_access",
             doc="Allows or disallows players to beam down to the planet.")
    def _planet_access(self, data, connection):
        location = str(connection.player.location)
        uuid = connection.player.uuid
        if not self.planet_protect.check_protection(location):
            send_message(connection, "This location is not protected.")
        elif not self.is_owner(connection, location):
            send_message(connection, "You don't own this planet!")
        else:
            if location not in self.storage["access"]:
                self.storage["access"][location] = {"whitelist": False,
                                                    "list": []}
            access = self.storage["access"][location]
            allow = "disallowed"
            if access["whitelist"]:
                allow = "allowed"
            if not data:
                yield from send_message(connection, "Argument not recognized. "
                                                    "Usage: /planet_access ["
                                                    "name] add/remove")
            elif data[0].lower() == "whitelist":
                if data[1].lower() == "true":
                    access["whitelist"] = True
                    access["list"] = [uuid]
                    send_message(connection, "Switched to whitelist mode "
                                             "and access list cleared.")
                elif data[1].lower() == "false":
                    access["whitelist"] = False
                    access["list"] = []
                    send_message(connection, "Switched to blacklist mode "
                                             "and access list cleared.")
                else:
                    send_message(connection, "Argument not recognized. "
                                             "Usage: /planet_access "
                                             "whitelist true/false")
            elif data[0].lower() == "list":
                access_list = [self.plugins.player_manager.get_player_by_uuid(
                    x).alias for x in access["list"]]
                access_list = ", ".join(access_list)
                send_message(connection, "The following people are {} "
                                         "access to this planet:\n{}"
                             .format(allow, access_list))
            elif data[0].lower() == "help":
                send_message(connection, "Syntax:")
                send_message(connection, "/planet_access whitelist true/false")
                send_message(connection, "Sets whether the planet should use a "
                                         "whitelist (only players on the list "
                                         "may enter) or a blacklist (default, "
                                         "only players on the list are"
                                         " forbidden).")
                send_message(connection, "/planet_access [name] add remove")
                send_message(connection, "Adds or removes a player from the "
                                         "list.")
                send_message(connection, "/planet_access list")
                send_message(connection, "Lists players on the access list.")
                send_message(connection, "/planet_access help")
                send_message(connection, "Displays this help.")
            else:
                target = self.plugins.player_manager.find_player(" ".join(data[0:-1]))
                if not target:
                    send_message(connection, "Argument not recognized. "
                                             "See /planet_access help "
                                             "for usage.")
                if data[-1] == "add":
                    if target.uuid not in access["list"]:
                        if not access["whitelist"] and target == \
                                connection.player:
                            send_message(connection, "Can't add yourself to "
                                                     "the blacklist!")
                        else:
                            access["list"].append(target.uuid)
                            send_message(connection, "{} is now {} access to "
                                                     "this planet"
                                         .format(target.alias, allow))
                    else:
                        send_message(connection, "{} is already {} access to "
                                                 "this planet."
                                     .format(target.alias, allow))
                elif data[-1] == "remove":
                    if target.uuid in access["list"]:
                        if access["whitelist"] and target == connection.player:
                            send_message(connection, "Can't remove yourself "
                                                     "from the whitelist!")
                        else:
                            access["list"].remove(target.uuid)
                            send_message(connection, "{} has been removed "
                                                     "from the {} list"
                                                     " for this planet."
                                         .format(target.alias, allow))
                    else:
                        send_message(connection, "{} is not on the {} list "
                                                 "for this planet."
                                     .format(target.alias, allow))
                else:
                    send_message(connection, "Argument not recognized. "
                                             "Usage: /planet_access [name] "
                                             "add/remove")
    @Command("purge_claims",
             perm="claims.purge_claims",
             doc="Purge the claims of the target player, if something "
                 "breaks.",
             syntax="(target)")
    def _purge_claims(self, data, connection):
        target = self.plugins.player_manager.find_player(" ".join(data))
        if target.uuid in self.storage['owners']:
            self.storage['owners'][target.uuid] = []
            yield from send_message(connection, "Purged claims of {}"
                                    .format(target.alias))
        else:
            yield from send_message(connection, "Target has no claims.")