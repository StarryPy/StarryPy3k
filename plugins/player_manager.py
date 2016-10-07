"""
StarryPy Player Manager Plugin

Provides core player management features:
- implements roles
- implements bans
- manages player database

Original authors: AMorporkian
Updated for release: kharidiron
"""

import asyncio
import datetime
import pprint
import re
import shelve
from operator import attrgetter

from base_plugin import Role, SimpleCommandPlugin
from data_parser import ConnectFailure, ServerDisconnect
from pparser import build_packet
from utilities import Command, DotDict, State, broadcast, send_message, \
    WarpType, WarpWorldType, WarpAliasType
from packets import packets


# Roles

class Owner(Role):
    is_meta = True


class SuperAdmin(Owner):
    is_meta = True


class Admin(SuperAdmin):
    is_meta = True


class Moderator(Admin):
    is_meta = True


class Registered(Moderator):
    is_meta = True


class Guest(Registered):
    is_meta = True


class Ban(Moderator):
    pass


class Kick(Moderator):
    pass


class Whois(Admin):
    pass


class Grant(Admin):
    pass


class Player:
    """
    Prototype class for a player.
    """
    def __init__(self, uuid, species="unknown", name="", alias="", last_seen=None, roles=None,
                 logged_in=False, connection=None, client_id=-1, ip="",
                 planet="", muted=False, state=None, team_id=None):
        """
        Initialize a player object. Populate all the necessary details.

        :param uuid:
        :param species:
        :param name:
        :param last_seen:
        :param roles:
        :param logged_in:
        :param connection:
        :param client_id:
        :param ip:
        :param planet:
        :param muted:
        :param state:
        :param team_id:
        :return:
        """
        self.uuid = uuid
        self.species = species
        self.name = name
        self.alias = alias
        if last_seen is None:
            self.last_seen = datetime.datetime.now()
        else:
            self.last_seen = last_seen
        if roles is None:
            self.roles = set()
        else:
            self.roles = set(roles)
        self.logged_in = logged_in
        self.connection = connection
        self.client_id = client_id
        self.ip = ip
        self.location = planet
        self.muted = muted
        self.team_id = team_id

    def __str__(self):
        """
        Convenience method for peeking at the Player object.

        :return: Pretty-printed dictionary of Player object.
        """
        return pprint.pformat(self.__dict__)

    def check_role(self, role):
        """
        Check if player has a specific role.

        :param role: Role to be checked.
        :return: Boolean: True if player has role, False if they do not.
        """
        for r in self.roles:
            if r.lower() == role.__name__.lower():
                return True
        return False


class Ship:
    """
    Prototype class for a Ship.
    """
    def __init__(self, uuid, player):
        self.uuid = uuid
        self.player = player

    def __str__(self):
        return "{}'s ship".format(self.player)

    def locationtype(self):
        return "ShipWorld"


class Planet:
    """
    Prototype class for a planet.
    """
    def __init__(self, location=(0, 0, 0), planet=0,
                 satellite=0, name=""):
        self.x, self.y, self.z = location
        self.planet = planet
        self.satellite = satellite
        self.name = name

    def _gen_planet_string(self):
        s = list("CelestialWorld:")
        s.append("{}:{}:{}:{}".format(self.x, self.y, self.z, self.planet))
        if self.satellite > int(0):
            s.append(":{}".format(self.satellite))
        return "".join(s)

    def __str__(self):
        return "CelestialWorld:{}:{}:{}:{}:{}".format(self.x, self.y, self.z,
                                                      self.planet,
                                                      self.satellite)

    def locationtype(self):
        return "CelestialWorld"


class IPBan:
    """
    Prototype class a Ban object.
    """
    def __init__(self, ip, reason, banned_by, timeout=None):
        self.ip = ip
        self.reason = reason
        self.timeout = timeout
        self.banned_by = banned_by
        self.banned_at = datetime.datetime.now()


class DeletePlayer(SuperAdmin):
    pass


###

class PlayerManager(SimpleCommandPlugin):
    name = "player_manager"

    def __init__(self):
        self.default_config = {"player_db": "config/player",
                               "owner_uuid": "!--REPLACE IN CONFIG FILE--!",
                               "allowed_species": ["apex", "avian", "glitch", "floran", "human", "hylotl", "penguin", "novakid"]}
        super().__init__()
        self.shelf = shelve.open(self.plugin_config.player_db, writeback=True)
        self.sync()
        self.players = self.shelf["players"]
        self.planets = self.shelf["planets"]
        self.plugin_shelf = self.shelf["plugins"]
        self.players_online = []
        asyncio.ensure_future(self._reap())

    # Packet hooks - look for these packets and act on them

    def on_protocol_request(self, data, connection):
        """
        Catch when a client first pings the server for a connection. Set the
        'state' variable to keep track of this.

        :param data: The packet containing the action.
        :param connection: The connection from which the packet came.
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        connection.state = State.VERSION_SENT
        return True

    def on_handshake_challenge(self, data, connection):
        """
        Catch when a client tries to handshake with server. Update the 'state'
        variable to keep track of this. Note: This step only occurs when a
        server requires name/password authentication.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        connection.state = State.HANDSHAKE_CHALLENGE_SENT
        return True

    def on_handshake_response(self, data, connection):
        """
        Catch when the server responds to a client's handshake. Update the
        'state' variable to keep track of this. Note: This step only occurs
        when a server requires name/password authentication.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        connection.state = State.HANDSHAKE_RESPONSE_RECEIVED
        return True

    def on_client_connect(self, data, connection):
        """
        Catch when a the client updates the server with its connection
        details. This is a key step to fingerprinting the client, and
        ensuring they stay in the wrapper. This is also where we apply our
        bans.

        :param data:
        :param species:
        :param connection:
        :return: Boolean: True on successful connection, False on a
                 failed connection.
        """
        try:
            player = yield from self._add_or_get_player(**data["parsed"])
            self.check_bans(connection)
            self.check_species(player)
        except (NameError, ValueError) as e:
            yield from connection.raw_write(self.build_rejection(str(e)))
            self._set_offline(connection)
            connection.die()
            return False
        player.ip = connection.client_ip
        connection.player = player
        return True

    def on_connect_success(self, data, connection):
        """
        Catch when a successful connection is established. Update the 'state'
        variable to keep track of this. Since the client successfully
        connected, update their details in storage (client id, location,
        logged_in state).

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        response = data["parsed"]
        connection.player.connection = connection
        connection.player.client_id = response["client_id"]
        connection.state = State.CONNECTED
        connection.player.logged_in = True
        self.players_online.append(connection.player.uuid)
        return True

    def on_client_disconnect_request(self, data, connection):
        """
        Catch when a client requests a disconnect from the server. At this
        point, we need to clean up the connection information we have for the
        client (logged_in state, location).

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        return True

    def on_server_disconnect(self, data, connection):
        """
        Catch when the server disconnects a client. Similar to the client
        disconnect packet, use this as a cue to perform cleanup, if it wasn't
        done already.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        self._set_offline(connection)
        return True

    def on_world_start(self, data, connection):
        """
        Hook when a new world instance is started. Use the details passed to
        determine the location of the world, and update the player's
        information accordingly.

        :param data:
        :param connection:
        :return: Boolean: True. Don't stop the packet here.
        """
        planet = data["parsed"]["template_data"]
        if planet["celestialParameters"] is not None:
            location = yield from self._add_or_get_planet(
                **planet["celestialParameters"]["coordinate"])
            connection.player.location = location
        self.logger.info("Player {} is now at location: {}".format(
            connection.player.alias,
            connection.player.location))
        return True

    def on_player_warp_result(self, data, connection):
        """
        Hook when a player warps to a world. This action is also used when
        a player first logs in. Use the details passed to determine the
        location of the world, and update the player's information accordingly.

        :param data:
        :param connection:
        :return: Boolean: True. Don't stop the packet here.
        """
        warp_data = data["parsed"]["warp_action"]
        if warp_data["warp_type"] == WarpType.TO_ALIAS:
            if warp_data["alias_id"] == WarpAliasType.ORBITED:
                # down to planet, need coordinates from world_start
                pass
            elif warp_data["alias_id"] == WarpAliasType.SHIP:
                # back on own ship
                connection.player.location = yield from self._add_or_get_ship(
                    connection.player.uuid)
        elif warp_data["warp_type"] == WarpType.TO_PLAYER:
            target = self.get_player_by_uuid(warp_data["player_id"].decode(
                "utf-8"))
            connection.player.location = target.location
        elif warp_data["warp_type"] == WarpType.TO_WORLD:
            if warp_data["world_id"] == WarpWorldType.CELESTIAL_WORLD:
                pass
            elif warp_data["world_id"] == WarpWorldType.PLAYER_WORLD:
                connection.player.location = yield from self._add_or_get_ship(
                    warp_data["ship_id"])
            elif warp_data["world_id"] == WarpWorldType.UNIQUE_WORLD:
                connection.player.location = yield from \
                    self._add_or_get_instance(warp_data)
            elif warp_data["world_id"] == WarpWorldType.MISSION_WORLD:
                pass
        return True

    # def on_client_context_update(self, data, connection):
    #     """
    #
    #     :param data:
    #     :param connection:
    #     :return: Boolean: True. Must be true, so that packet get passed on.
    #     """
    #     for data_key, data_set in data["parsed"]["contexts"].items():
    #         if isinstance(data_set, dict):
    #             try:
    #                 if "request" in data_set["command"]:
    #                     if "team.acceptInvitation" in data_set["handler"]:
    #                         invitee_uuid = data_set["arguments"]["inviteeUuid"]
    #                         invitee = self.get_player_by_uuid(invitee_uuid)
    #                         self.logger.debug(
    #                             "{} joined team.".format(invitee.name))
    #                     elif "team.removeFromTeam" in data_set["handler"]:
    #                         player_uuid = data_set["arguments"]["playerUuid"]
    #                         target = self.get_player_by_uuid(player_uuid)
    #                         target.team_id = None
    #                         self.logger.debug(
    #                             "{} left team.".format(target.name))
    #                     else:
    #                         continue
    #                 elif "response" in data_set["command"]:
    #                     if data_set["result"]:
    #                         if "teamUuid" in data_set["result"]:
    #                             team_uuid = str(data_set["result"]["teamUuid"])
    #                             if team_uuid != connection.player.team_id:
    #                                 connection.player.team_id = team_uuid
    #             except KeyError:
    #                 continue
    #         else:
    #             continue
    #     return True

    def on_step_update(self, data, connection):
        """
        Catch when the first heartbeat packet is sent to a player. This is the
        final confirmation in the connection process. Update the 'state'
        variable to reflect this.

        :param data:
        :param connection:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        connection.state = State.CONNECTED_WITH_HEARTBEAT
        return True

    # Helper functions - Used by hooks and commands

    def _reap(self):
        """
        Helper function to remove players that are not marked as logged in,
        but really aren't.

        :return: Null.
        """
        while True:
            yield from asyncio.sleep(10)
            # self.logger.debug("Player reaper running:")
            for player in self.players_online:
                target = self.get_player_by_uuid(player)
                if target.connection.state is State.DISCONNECTED or not target.connection:
                    self.logger.warning("Removing stale player connection: {}"
                                        "".format(target.name))
                    target.connection = None
                    target.logged_in = False
                    target.location = None
                    self.players_online.remove(target.uuid)

    def _set_offline(self, connection):
        """
        Convenince function to set all the players variables to off.

        :param connection: The connection to turn off.
        :return: Boolean, True. Always True, since called from the on_ packets.
        """
        connection.player.connection = None
        connection.player.logged_in = False
        connection.player.location = None
        self.players_online.remove(connection.player.uuid)
        return True

    def clean_name(self, name):
        color_strip = re.compile("\^(.*?);")
        alias = color_strip.sub("", name)
        non_ascii_strip = re.compile("[^ -~]")
        alias = non_ascii_strip.sub("", alias)
        multi_whitespace_strip = re.compile("[\s]{2,}")
        alias = multi_whitespace_strip.sub(" ", alias)
        match_non_whitespace = re.compile("[\S]")
        if match_non_whitespace.search(alias) is None:
            return None
        else:
            if len(alias) > 20:
                alias = alias[0:20]
            return alias

    def build_rejection(self, reason):
        """
        Function to build packet to reject connection for client.

        :param reason: String. Reason for rejection.
        :return: Rejection packet.
        """
        return build_packet(packets["connect_failure"],
                            ConnectFailure.build(
                                dict(reason=reason)))

    def sync(self):
        """
        Shelf sync function. Ensure storage shelf contains necessary sections.

        :return: Null
        """
        if "players" not in self.shelf:
            self.shelf["players"] = {}
        if "plugins" not in self.shelf:
            self.shelf["plugins"] = {}
        if "planets" not in self.shelf:
            self.shelf["planets"] = {}
        if "bans" not in self.shelf:
            self.shelf["bans"] = {}
        if "ships" not in self.shelf:
            self.shelf["ships"] = {}
        self.shelf.sync()

    def deactivate(self):
        """
        Deactivate the shelf.

        :return: Null
        """
        for player in self.shelf["players"].values():
            player.connection = None
            player.logged_in = False
        self.shelf.close()
        self.logger.debug("Closed the shelf")

    def add_role(self, player, role):
        """
        Adds a role to a player.

        :param player: Player to receive role.
        :param role: Role to be received.
        :return: Null.
        """
        if issubclass(role, Role):
            r = role.__name__
        else:
            raise TypeError("add_role requires a Role subclass to be passed"
                            " as the second argument.")
        player.roles.add(r)
        self.logger.info("Granted role {} to {}".format(r, player.alias))
        for subrole in role.roles:
            s = self.get_role(subrole)
            if issubclass(s, role):
                self.add_role(player, s)

    def get_role(self, name):
        """
        Returns the roles a player is currently granted.

        :param name:
        :return: List: Roles the user player has.
        """
        # TODO: Need to verify this...
        if issubclass(name, Role):
            return name
        return [x for x in Owner.roles
                if x.__name__.lower() == name.lower()][0]

    def get_rank(self, player):
        """
        Returns the highest rank of the given player.

        :param player: Player to check rank of.
        :return: Int: A number representing the highest rank.
        """
        if player.check_role(Owner):
            return 5
        elif player.check_role(SuperAdmin):
            return 4
        elif player.check_role(Admin):
            return 3
        elif player.check_role(Moderator):
            return 2
        elif player.check_role(Registered):
            return 1
        else:
            return 0

    def get_player_by_uuid(self, uuid):
        """
        Grab a hook to a player by their uuid. Returns player object.

        :param uuid: String: UUID of player to check.
        :return: Mixed: Player object.
        """
        if uuid in self.shelf["players"]:
            return self.shelf["players"][uuid]

    def ban_by_ip(self, ip, reason, connection):
        """
        Ban a player based on their IP address. Should be compatible with both
        IPv4 and IPv6.

        :param ip: String: IP of player to be banned.
        :param reason: String: Reason for player's ban.
        :param connection: Connection of target player to be banned.
        :return: Null
        """
        ban = IPBan(ip, reason, connection.player.alias)
        self.shelf["bans"][ip] = ban
        send_message(connection,
                     "Banned IP: {} with reason: {}".format(ip, reason))

    def unban_by_ip(self, ip, connection):
        """
        Unban a player based on their IP address. Should be compatible with both
        IPv4 and IPv6.

        :param ip: String: IP of player to be unbanned.
        :param connection: Connection of target player to be unbanned.
        :return: Null
        """
        # ban = IPBan(ip, reason, connection.player.alias)
        del self.shelf["bans"][ip]
        send_message(connection,
                     "Ban removed: {}".format(ip))

    def ban_by_name(self, name, reason, connection):
        """
        Ban a player based on their name. This is the easier route, as it is a
        more user friendly to target the player to be banned. Hooks to the
        ban_by_ip mechanism backstage.

        :param name: String: Name of the player to be banned.
        :param reason: String: Reason for player's ban.
        :param connection: Connection of target player to be banned.
        :return: Null
        """
        p = self.get_player_by_alias(name)
        if p is not None:
            self.ban_by_ip(p.ip, reason, connection)
        else:
            send_message(connection,
                         "Couldn't find a player by the name {}".format(name))

    def unban_by_name(self, name,  connection):
        """
        Ban a player based on their name. This is the easier route, as it is a
        more user friendly to target the player to be banned. Hooks to the
        ban_by_ip mechanism backstage.

        :param name: String: Name of the player to be banned.
        :param connection: Connection of target player to be banned.
        :return: Null
        """
        p = self.get_player_by_alias(name)
        if p is not None:
            self.unban_by_ip(p.ip, connection)
        else:
            send_message(connection,
                         "Couldn't find a player by the name {}".format(name))

    def check_bans(self, connection):
        """
        Check if a ban on a player exists. Raise ValueError when true.

        :param connection: The connection of the target player.
        :return: Null.
        :raise: ValueError if player is banned. Pass reason message up with
                exception.
        """
        if connection.client_ip in self.shelf["bans"]:
            self.logger.info("Banned IP ({}) tried to log in.".format(
                connection.client_ip))
            raise ValueError("You are banned!\nReason: {}".format(
                self.shelf["bans"][connection.client_ip].reason))

    def check_species(self, player):
        """
        Check if a player has an unknown species. Raise ValueError when true.
        Context: http://community.playstarbound.com/threads/119569/

        :param player: The player to check.
        :return: Null.
        :raise: ValueError if the player has an unknown species.
        """
        if player.species not in self.plugin_config.allowed_species:
            self.logger.info("Player with unknown species ({}) tried to log in.".format(
                player.species))
            raise ValueError("Connection terminated!\nYour species ({}) is not allowed.".format(
                player.species))

    def get_storage(self, caller):
        """
        Collect the storage for caller.

        :param caller: Entity requesting its storage
        :return: Storage shelf for caller. If called doesn't have anything in
                 storage, return an empty shelf.
        """
        name = caller.name
        if name not in self.plugin_shelf:
            self.plugin_shelf[name] = DotDict({})
        return self.plugin_shelf[name]

    def get_player_by_name(self, name, check_logged_in=False) -> Player:
        """
        Grab a hook to a player by their name. Return Boolean value if only
        checking login status. Returns player object otherwise.

        :param name: String: Name of player to check.
        :param check_logged_in: Boolean: Whether we just want login status
                                (true), or the player's server object (false).
        :return: Mixed: Boolean on logged_in check, player object otherwise.
        """
        lname = name.lower()
        for player in self.shelf["players"].values():
            if player.name.lower() == lname:
                if not check_logged_in or player.logged_in:
                    return player

    def get_player_by_alias(self, alias, check_logged_in=False) -> Player:
        """
        Grab a hook to a player by their name. Return Boolean value if only
        checking login status. Returns player object otherwise.

        :param alias: String: Cleaned name of player to check.
        :param check_logged_in: Boolean: Whether we just want login status
                                (true), or the player's server object (false).
        :return: Mixed: Boolean on logged_in check, player object otherwise.
        """
        lname = alias.lower()
        for player in self.shelf["players"].values():
            if player.alias.lower() == lname:
                if not check_logged_in or player.logged_in:
                    return player

    @asyncio.coroutine
    def _add_or_get_player(self, uuid, species, name="", last_seen=None, roles=None,
                           logged_in=False, connection=None, client_id=-1,
                           ip="", planet="", muted=False, **kwargs) -> Player:
        """
        Given a UUID, try to find the player's info in storage. In the event
        that the player has never connected to the server before, add their
        details into storage for future reference. Return a Player object.

        :param uuid: UUID of connecting character
        :param species: Species of connecting character
        :param name: Name of connecting character
        :param last_seen: Date of last login
        :param roles: Roles granted to character
        :param logged_in: Boolean: Is character currently logged in
        :param connection: Connection of connecting player
        :param client_id: ID for connection given by server
        :param ip: IP address of connection
        :param planet: Current planet character is on/near
        :param muted: Boolean: Is the player currently muted
        :param kwargs: any other keyword arguments
        :return: Player object.
        """

        if isinstance(uuid, bytes):
            uuid = uuid.decode("ascii")
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        alias = self.clean_name(name)
        if alias is None:
            alias = uuid[0:4]

        if uuid in self.shelf["players"]:
            self.logger.info("Known player is attempting to log in: "
                             "{}".format(alias))
            p = self.shelf["players"][uuid]
            if p.logged_in:
                raise ValueError("Player is already logged in.")
            if uuid == self.plugin_config.owner_uuid:
                p.roles = {x.__name__ for x in Owner.roles} | {Owner.__name__}
            if not hasattr(p, "species"):
                p.species = species
            elif p.species != species:
                p.species = species
            if p.name != name:
                p.name = name
            return p
        else:
            if self.get_player_by_name(alias) is not None:
                raise NameError("A user with that name already exists.")
            self.logger.info("Adding new player to database: {} (UUID:{})"
                             "".format(alias, uuid))
            if uuid == self.plugin_config.owner_uuid:
                roles = {x.__name__ for x in Owner.roles} | {Owner.__name__}
            else:
                roles = {x.__name__ for x in Guest.roles}
            new_player = Player(uuid, species, name, alias, last_seen, roles, logged_in,
                                connection, client_id, ip, planet, muted)
            self.shelf["players"][uuid] = new_player
            return new_player

    @asyncio.coroutine
    def _add_or_get_ship(self, uuid):
        """
        Given a ship world's uuid, look up their ship in the ships shelf. If
        ship not in shelf, add it. Return a Ship object.

        :param uuid: Target player to look up
        :return: Ship object.
        """
        def _get_player_name(uuid):
            player = ""
            if isinstance(uuid, bytes):
                uuid = uuid.decode("utf-8")
            for p in self.factory.connections:
                if p.player.uuid == uuid:
                    player = p.player.alias
                    return player

        if uuid in self.shelf["ships"]:
            return self.shelf["ships"][uuid]
        else:
            ship = Ship(uuid, _get_player_name(uuid))
            self.shelf["ships"][uuid] = ship
            return ship

    @asyncio.coroutine
    def _add_or_get_planet(self, location, planet, satellite) -> Planet:
        """
        Look up a planet in the planets shelf, return a Planet object. If not
        present, add it to the shelf. Return a Planet object.

        :param location:
        :param planet:
        :param satellite:
        :return: Planet object.
        """
        # TODO: add planet names to this, since people seem to like using
        # those as a way to refer to the planets as well.
        a, x, y = location
        loc_string = "{}:{}:{}:{}:{}".format(a, x, y, planet, satellite)
        if loc_string in self.shelf["planets"]:
            self.logger.info("Returning to an already logged planet.")
            planet = self.shelf["planets"][loc_string]
        else:
            self.logger.info("Logging new planet to database.")
            planet = Planet(location=location, planet=planet,
                            satellite=satellite)
            self.shelf["planets"][str(planet)] = planet
            self.junk = State
        return planet

    @asyncio.coroutine
    def _add_or_get_instance(self, data):
        """
        Look up a planet in the planets shelf, return a Planet object. If not
        present, add it to the shelf. Return a Planet object.

        :param data:
        :return: Instance object.
        """
        instance_string = list("InstanceWorld:")
        instance_string.append("{}".format(data["world_name"]))
        if data["instance_flag"]:
            instance_string.append(":{}".format(data["instance_id"].decode(
                "utf-8")))
        else:
            instance_string.append(":-")

        return "".join(instance_string)

    # Commands - In-game actions that can be performed

    @Command("kick",
             role=Kick,
             doc="Kicks a player.",
             syntax=("[\"]player name[\"]", "[reason]"))
    def _kick(self, data, connection):
        """
        Kick a play off the server. You must specify a name. You may also
        specify an optional reason.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """

        # FIXME: Kick is currently broken. Kicking someone will cause their
        # starbound client to crash (overkill).
        try:
            alias = data[0]
        except IndexError:
            raise SyntaxWarning("No target provided.")

        try:
            reason = " ".join(data[1:])
        except IndexError:
            reason = "No reason given."

        p = self.get_player_by_alias(alias)
        if p is None:
            send_message(connection,
                         "Couldn't find a player with name {}".format(alias))
        if not p.logged_in:
            send_message(connection,
                         "Player {} is not currently logged in.".format(alias))
        if p.client_id == -1 or p.connection is None:
            p.connection = None
            p.logged_in = False
            p.location = None
            self.players_online.remove(p.uuid)
            return
        kick_string = "You were kicked.\n Reason: {}".format(reason)
        kick_packet = build_packet(packets["server_disconnect"],
                                   ServerDisconnect.build(
                                       dict(reason=kick_string)))
        yield from p.connection.raw_write(kick_packet)
        p.connection = None
        p.logged_in = False
        p.location = None
        self.players_online.remove(p.uuid)
        broadcast(self, "^red;{} has been kicked for reason: "
                            "{}^reset;".format(alias, reason))

    @Command("ban",
             role=Ban,
             doc="Bans a user or an IP address.",
             syntax=("(ip | name)", "(reason)"))
    def _ban(self, data, connection):
        """
        Ban a player. You must specify either a name or an IP. You must also
        specify a 'reason' for banning the player. This information is stored
        and, should the player try to connect again, are great with the
        message:

        > You are banned!
        > Reason: <reason shows here>

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        :raise: SyntaxWarning on incorrect input.
        """
        try:
            target, reason = data[0], " ".join(data[1:])
            if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", target):
                self.ban_by_ip(target, reason, connection)
            else:
                self.ban_by_name(target, reason, connection)
        except:
            raise SyntaxWarning

    @Command("unban",
             role=Ban,
             doc="Unbans a user or an IP address.",
             syntax=("(ip | name)"))
    def _unban(self, data, connection):
        """
        Unban a player. You must specify either a name or an IP.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        :raise: SyntaxWarning on incorrect input.
        """
        try:
            target = data[0]
            if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", target):
                self.unban_by_ip(target, connection)
            else:
                self.unban_by_name(target, connection)
        except:
            raise SyntaxWarning

    @Command("list_bans",
             role=Ban,
             doc="Lists all active bans.")
    def _list_bans(self, data, connection):
        """
        List the current bans.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        if len(self.shelf["bans"].keys()) == 0:
            send_message(connection, "There are no active bans.")
        else:
            res = ["Active bans:"]
            for ban in self.shelf["bans"].values():
                res.append("IP: {ip} - "
                           "Reason: {reason} - "
                           "Banned by: {banned_by}".format(**ban.__dict__))
            send_message(connection, "\n".join(res))

    @Command("grant", "promote", "revoke", "demote",
             role=Grant,
             doc="Grants/Revokes role a player has.",
             syntax=("(role)", "(player)"))
    def _grant(self, data, connection):
        """
        Grant a role to a player.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        :raise: LookupError on unknown player or role entry.
        """
        try:
            role = data[0]
        except IndexError:
            raise SyntaxWarning("Please provide a Role and a target player.")
        if not data[1:]:
            raise SyntaxWarning("Please provide a target player.")
        alias = " ".join(data[1:])
        p = self.get_player_by_alias(alias)
        try:
            if role.lower() not in (x.__name__.lower() for x in Owner.roles):
                raise LookupError("Unknown role {}".format(role))
            if p is None:
                raise LookupError("Unknown player {}".format(alias))
            if p is connection.player:
                raise LookupError("Can't use this command on yourself!")
            if role.lower() not in (x.lower() for x in connection.player.roles):
                raise LookupError("Can't promote {} to rank {}, you are not "
                                  "a high enough rank for that!".format(
                                  alias, role.lower()))
            if self.get_rank(connection.player) <= self.get_rank(p):
                raise LookupError("Can't change roles of {}, you do "
                                  "not outrank them!".format(alias))
            p.roles = set()
            ro = [x for x in Owner.roles if x.__name__.lower() ==
                  role.lower()][0]
            self.add_role(p, ro)
            send_message(connection,
                         "{} has been given the role {}.".format(
                             p.alias, ro.__name__))
            if p.connection is not None:
                send_message(p.connection,
                             "You've been given the role {} by {}".format(
                                 ro.__name__, connection.player.alias))
        except LookupError as e:
            send_message(connection, str(e))

    @Command("list_players",
             role=Whois,
             doc="Lists all players.",
             syntax=("[wildcards]",))
    def _list_players(self, data, connection):
        """
        List the players in the database. Wildcard formats are allowed in this
        search (not really. NotImplemementedYet...) Careful, this list can get
        pretty big for a long running or popular server.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        players = [player for player in self.players.values()]
        players.sort(key=attrgetter("name"))
        send_message(connection,
                     "{} players found:".format(len(players)))
        for x, player in enumerate(players):
            player_info = "  {0}. {1}{2}"
            if player.logged_in:
                l = " (logged-in, ID: {})".format(player.client_id)
            else:
                l = ""
            send_message(connection, player_info.format(x + 1, player.alias,
                                                        l))

    @Command("del_player",
             role=DeletePlayer,
             doc="Deletes a player",
             syntax=("(username)",
                     "[*force=forces deletion of a logged in player."
                     " ^red;NOT RECOMMENDED^reset;.]"))
    def _delete_player(self, data, connection):
        """
        Removes a player from the player database. By default. you cannot
        remove a logged-in player, so either they need to be removed from
        the server first, or you have to apply the *force operation.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        :raise: NameError if is not available. ValueError if player is
                currently logged in.
        """
        if data[-1] == "*force":
            force = True
            data.pop()
        else:
            force = False
        alias = " ".join(data)
        player = self.get_player_by_alias(alias)
        if player is None:
            raise NameError
        if (not force) and player.logged_in:
            raise ValueError(
                "Can't delete a logged-in player; please kick them first. If "
                "absolutely necessary, append *force to the command.")
        self.players.pop(player.uuid)
        del player
        send_message(connection, "Player {} has been deleted.".format(alias))
