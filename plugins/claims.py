"""
StarryPy Claims Plugin

Extends the planet protect plugin to allow registered users to claim and
protect a limited number of planets.

Author: medeor413
"""

from base_plugin import StorageCommandPlugin
from plugins.player_manager import Registered, SuperAdmin
from utilities import Command, send_message


class Claims(StorageCommandPlugin):
    name = "claims"
    depends = ["player_manager", "command_dispatcher", "planet_protect"]
    default_config = {"max_claims_per_person": 5}

    def __init__(self):
        super().__init__()
        self.max_claims = None
        self.planet_protect = self.plugins["planet_protect"]

    def activate(self):
        super().activate()
        if "owners" not in self.storage:
            self.storage["owners"] = {}
        self.max_claims = self.config.get_plugin_config(self.name)[
            "max_claims_per_person"]

    def is_owner(self, alias, location):
        if alias not in self.storage["owners"]:
            return False
        elif str(location) not in self.storage["owners"][alias]:
            return False
        else:
            return True

    @Command("claim",
             role=Registered,
             doc="Claim a planet to be protected.")
    def _claim(self, data, connection):
        location = connection.player.location
        alias = connection.player.alias
        if self.planet_protect.check_protection(location):
            send_message(connection, "This location is already protected.")
        elif alias not in self.storage["owners"]:
            self.storage["owners"][alias] = []
            self.storage["owners"][alias].append(str(location))
            print(self.storage["owners"][alias])
            self.planet_protect.add_protection(location, connection.player)
            send_message(connection, "Successfully claimed planet {}."
                         .format(location))
        else:
            if len(self.storage["owners"][alias]) >= self.max_claims:
                print(self.storage["owners"][alias])
                send_message(connection, "You have reached the maximum "
                                         "number of claimed planets.")
            else:
                self.storage["owners"][alias].append(str(location))
                self.planet_protect.add_protection(location, connection.player)
                print(self.storage["owners"][alias])
                send_message(connection, "Successfully claimed planet {}."
                             .format(location))

    @Command("unclaim",
             role=Registered,
             doc="Unclaim and unprotect the planet you're standing on.")
    def _unclaim(self, data, connection):
        location = connection.player.location
        alias = connection.player.alias
        if not self.planet_protect.check_protection(location):
            send_message(connection, "This planet is not protected.")
        elif not self.is_owner(alias, location):
            send_message(connection, "You don't own this planet!")
        else:
            self.storage["owners"][alias].remove(str(location))
            if len(self.storage["owners"][alias]) == 0:
                self.storage["owners"].pop(alias)
            self.planet_protect.disable_protection(location)
            send_message(connection, "Unclaimed planet {} "
                                     "successfully.".format(location))

    @Command("add_helper",
             role=Registered,
             doc="Add someone to the protected list of your planet.")
    def _add_helper(self, data, connection):
        location = connection.player.location
        alias = connection.player.alias
        target = self.plugins.player_manager.get_player_by_alias(" ".join(data))
        if target is not None:
            if not self.is_owner(alias, location):
                send_message(connection, "You don't own this planet!")
            else:
                protection = self.planet_protect.get_protection(location)
                protection.add_builder(target)
                try:
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
                         .format(target.alias))

    @Command("rm_helper",
             role=Registered,
             doc="Remove someone from the protected list of your planet.")
    def _rm_helper(self, data, connection):
        location = connection.player.location
        alias = connection.player.alias
        target = self.plugins.player_manager.get_player_by_alias(" ".join(data))
        if target is not None:
            if not self.is_owner(alias, location):
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
                         .format(target.alias))

    @Command("helper_list",
             role=Registered,
             doc="List all of the people allowed to build on this planet.")
    def _helper_list(self, data, connection):
        alias = connection.player.alias
        location = connection.player.location
        if not self.planet_protect.check_protection(location):
            send_message(connection,
                         "This location is not protected.")
        elif not self.is_owner(alias, location):
            send_message(connection,
                         "You don't own this planet!")
        else:
            protection = self.planet_protect.get_protection(location)
            players = ", ".join(protection.get_builders())
            send_message(connection,
                         "Players allowed to build at location '{}': {}"
                         "".format(connection.player.location, players))

    @Command("change_owner",
             role=Registered,
             doc="Transfer ownership of the planet to another person.")
    def _change_owner(self, data, connection):
        alias = connection.player.alias
        location = connection.player.location
        target = self.plugins.player_manager.get_player_by_alias(" ".join(data))
        if target is not None:
            if not self.is_owner(alias, location):
                send_message(connection, "You don't own this planet!")
            else:
                if target.alias not in self.storage["owners"]:
                    self.storage["owners"][target.alias] = []
                self.storage["owners"][target.alias].append(str(location))
                self.storage["owners"][alias].remove(str(location))
                if len(self.storage["owners"][alias]) == 0:
                    self.storage["owners"].pop(alias)
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
                         .format(target))
