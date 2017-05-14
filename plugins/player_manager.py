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
import json
from operator import attrgetter

from base_plugin import SimpleCommandPlugin
from data_parser import ConnectFailure, ServerDisconnect
from pparser import build_packet
from utilities import Command, DotDict, State, broadcast, send_message, \
    WarpType, WarpWorldType, WarpAliasType
from packets import packets


class Player:
    """
    Prototype class for a player.
    """
    def __init__(self, uuid, species="unknown", name="", alias="",
                 last_seen=None, ranks=None, logged_in=False,
                 connection=None, client_id=-1, ip="", planet="",
                 muted=False, state=None, team_id=None):
        """
        Initialize a player object. Populate all the necessary details.

        :param uuid:
        :param species:
        :param name:
        :param last_seen:
        :param ranks:
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
        if ranks is None:
            self.ranks = set()
        else:
            self.ranks = set(ranks)
        self.granted_perms = set()
        self.revoked_perms = set()
        self.permissions = set()
        self.chat_prefix = ""
        self.priority = 0
        self.logged_in = logged_in
        self.connection = connection
        self.client_id = client_id
        self.ip = ip
        self.location = planet
        self.last_location = planet
        self.muted = muted
        self.team_id = team_id

    def __str__(self):
        """
        Convenience method for peeking at the Player object.

        :return: Pretty-printed dictionary of Player object.
        """
        return pprint.pformat(self.__dict__)

    def update_ranks(self, ranks):
        """
        Update the player's info to match any changes made to their ranks.

        :return: Null.
        """
        self.permissions = set()
        highest_rank = None
        for r in self.ranks:
            if not highest_rank:
                highest_rank = r
            self.permissions |= ranks[r]['permissions']
            if ranks[r]['priority'] > ranks[highest_rank]['priority']:
                highest_rank = r
        self.permissions |= self.granted_perms
        self.permissions -= self.revoked_perms
        if highest_rank:
            self.priority = ranks[highest_rank]['priority']
            self.chat_prefix = ranks[highest_rank]['prefix']
        else:
            self.priority = 0
            self.chat_prefix = ""

    def perm_check(self, perm):
        if not perm:
            return True
        elif "special.allperms" in self.permissions:
            return True
        elif perm.lower() in self.revoked_perms:
            return False
        elif perm.lower() in self.permissions:
            return True
        else:
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


###

class PlayerManager(SimpleCommandPlugin):
    name = "player_manager"

    def __init__(self):
        self.default_config = {"player_db": "config/player",
                               "owner_uuid": "!--REPLACE IN CONFIG FILE--!",
                               "allowed_species": ["apex", "avian", "glitch",
                                                   "floran", "human", "hylotl",
                                                   "penguin", "novakid"],
                               "owner_ranks": ["Owner"],
                               "new_user_ranks": ["Guest"]}
        super().__init__()
        self.shelf = shelve.open(self.plugin_config.player_db, writeback=True)
        self.sync()
        self.players = self.shelf["players"]
        self.planets = self.shelf["planets"]
        self.plugin_shelf = self.shelf["plugins"]
        self.players_online = []
        try:
            with open("config/permissions.json", "r") as file:
                self.rank_config = json.load(file)
        except IOError as e:
            self.logger.error("Fatal: Could not read permissions file!")
            self.logger.error(e)
            raise SystemExit
        except json.JSONDecodeError as e:
            self.logger.error("Fatal: Could not parse permissions.json!")
            self.logger.error(e)
            raise SystemExit
        self.ranks = self._rebuild_ranks(self.rank_config)
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
        connection.player.last_seen = datetime.datetime.now()
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
        if data["parsed"]["warp_success"]:
            warp_data = data["parsed"]["warp_action"]
            p = connection.player
            if warp_data["warp_type"] == WarpType.TO_ALIAS:
                if warp_data["alias_id"] == WarpAliasType.ORBITED:
                    # down to planet, need coordinates from world_start
                    p.last_location = p.location
                    pass
                elif warp_data["alias_id"] == WarpAliasType.SHIP:
                    # back on own ship
                    p.last_location = p.location
                    p.location = yield from self._add_or_get_ship(p.uuid)
                elif warp_data["alias_id"] == WarpAliasType.RETURN:
                    p.location, p.last_location = p.last_location, p.location
            elif warp_data["warp_type"] == WarpType.TO_PLAYER:
                target = self.get_player_by_uuid(warp_data["player_id"]
                    .decode("utf-8"))
                p.last_location = p.location
                p.location = target.location
            elif warp_data["warp_type"] == WarpType.TO_WORLD:
                if warp_data["world_id"] == WarpWorldType.CELESTIAL_WORLD:
                    p.last_location = p.location
                    pass
                elif warp_data["world_id"] == WarpWorldType.PLAYER_WORLD:
                    p.last_location = p.location
                    p.location = yield from self._add_or_get_ship(
                        warp_data["ship_id"])
                elif warp_data["world_id"] == WarpWorldType.UNIQUE_WORLD:
                    p.last_location = p.location
                    p.location = yield from self._add_or_get_instance(warp_data)
                elif warp_data["world_id"] == WarpWorldType.MISSION_WORLD:
                    p.last_location = p.location
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
        Convenience function to set all the players variables to off.

        :param connection: The connection to turn off.
        :return: Boolean, True. Always True, since called from the on_ packets.
        """
        connection.player.connection = None
        connection.player.logged_in = False
        connection.player.location = None
        connection.player.last_seen = datetime.datetime.now()
        self.players_online.remove(connection.player.uuid)
        return True

    def clean_name(self, name):
        color_strip = re.compile("\^(.*?);")
        alias = color_strip.sub("", name)
        non_ascii_strip = re.compile("[^ -~]")
        alias = non_ascii_strip.sub("", alias)
        multi_whitespace_strip = re.compile("[\s]{2,}")
        alias = multi_whitespace_strip.sub(" ", alias)
        trailing_leading_whitespace_strip = re.compile("^[ \s]+|[ \s]+$")
        alias = trailing_leading_whitespace_strip.sub("", alias)
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

    def _rebuild_ranks(self, ranks):
        """
        Rebuilds rank configuration from file, including inherited permissions.

        :param ranks: The initial rank config.
        :return: Dict: The built rank permissions.
        """
        final = {}

        def build_inherits(inherits):
            finalperms = set()
            for inherit in inherits:
                if 'inherits' in ranks[inherit]:
                    finalperms |= build_inherits(ranks[inherit]['inherits'])
                finalperms |= set(ranks[inherit]['permissions'])
            return finalperms

        for rank, config in ranks.items():
            config['permissions'] = set(config['permissions'])
            if 'inherits' in config:
                config['permissions'] |= build_inherits(config['inherits'])
            final[rank] = config

        return final

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
        p = self.find_player(name)
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
        p = self.find_player(name)
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

    def get_player_by_uuid(self, uuid):
        """
        Grab a hook to a player by their uuid. Returns player object.

        :param uuid: String: UUID of player to check.
        :return: Mixed: Player object.
        """
        if uuid in self.shelf["players"]:
            return self.shelf["players"][uuid]

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

    def get_player_by_client_id(self, id) -> Player:
        """
        Grab a hook to a player by their client id. Returns player object.

        :param id: Integer: Client Id of the player to check.
        :return: Player object.
        """
        for player in self.shelf["players"].values():
            if player.client_id == id and player.logged_in:
                return player

    def get_player_by_ip(self, ip, check_logged_in=False) -> Player:
        """
        Grab a hook to a player by their IP. Returns boolean if only
        checking login status. Returns Player object otherwise.

        :param ip: IP of player to check.
        :param check_logged_in: Boolean: Whether we just want login status
                                (true), or the player's server object (false)
        :return: Mixed: Boolean on logged_in check, player object otherwise.
        """
        for player in self.shelf["players"].values():
            if player.ip == ip:
                if not check_logged_in or player.logged_in:
                    return player

    def find_player(self, search, check_logged_in=False):
        """
        Convenience method to try and find a player by a variety of methods.
        Checks for alias, then raw name, then client id.

        :param search: The alias, raw name, or id of the player to check.
        :param check_logged_in: Boolean: Return the login status only if true.
        :return: Mixed: Boolean on logged_in check, player object otherwise.
        """
        player = self.get_player_by_alias(search, check_logged_in)
        if player is not None:
            return player
        player = self.get_player_by_name(search, check_logged_in)
        if player is not None:
            return player
        try:
            search = int(search)
            player = self.get_player_by_client_id(search)
            if player is not None:
                return player
        except ValueError:
            pass
        if len(search) == 32:
            player = self.get_player_by_uuid(search)
            if player is not None:
                return player
        player = self.get_player_by_ip(search, check_logged_in)
        if player is not None:
            return player

    @asyncio.coroutine
    def _add_or_get_player(self, uuid, species, name="", last_seen=None,
                           ranks=None, logged_in=False, connection=None,
                           client_id=-1, ip="", planet="", muted=False,
                           **kwargs) -> Player:
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
            if not hasattr(p, "species"):
                p.species = species
            elif p.species != species:
                p.species = species
            if p.name != name:
                p.name = name
                p.alias = self.clean_name(name)
                if p.alias is None:
                    p.alias = uuid[0:4]
            p.update_ranks(self.ranks)
            return p
        else:
            if self.get_player_by_alias(alias) is not None:
                raise NameError("A user with that name already exists.")
            self.logger.info("Adding new player to database: {} (UUID:{})"
                             "".format(alias, uuid))
            if uuid == self.plugin_config.owner_uuid:
                ranks = set(self.plugin_config.owner_ranks)
            else:
                ranks = set(self.plugin_config.new_user_ranks)
            new_player = Player(uuid, species, name, alias, last_seen,
                                ranks, logged_in, connection, client_id, ip,
                                planet, muted)
            new_player.update_ranks(self.ranks)
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
        def _get_player_name(uid):
            player = ""
            if isinstance(uid, bytes):
                uid = uid.decode("utf-8")
            for p in self.factory.connections:
                if p.player.uuid == uid:
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
             perm="player_manager.kick",
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

        p = self.find_player(alias)
        if p is None:
            send_message(connection,
                         "Couldn't find a player with name {}".format(alias))
            return
        if p.priority >= connection.player.priority:
            send_message(connection, "Can't kick {}, they are equal or "
                                     "higher than your rank!".format(p.alias))
            return
        if not p.logged_in:
            send_message(connection,
                         "Player {} is not currently logged in.".format(alias))
            return
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
             perm="player_manager.ban",
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
            if self.find_player(target).priority >= connection.player.priority:
                send_message(connection, "Can't ban {}, they are equal or "
                                         "higher than your rank!"
                             .format(target))
                return
            if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", target):
                self.ban_by_ip(target, reason, connection)
            else:
                self.ban_by_name(target, reason, connection)
        except:
            raise SyntaxWarning

    @Command("unban",
             perm="player_manager.ban",
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
             perm="player_manager.ban",
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

    @Command("user",
             perm="player_manager.user",
             doc="Manages user permissions; see /user help for details.")
    def _user(self, data, connection):
        if not data:
            yield from send_message(connection, "No arguments provided. See "
                                                "/user help for usage info.")
        elif data[0].lower() == "help":
            send_message(connection, "Syntax:")
            send_message(connection, "/user addperm (user) (permission)")
            send_message(connection, "Adds a permission to a player. Fails if "
                                     "the user doesn't have the permission.")
            send_message(connection, "/user rmperm (player) (permission)")
            send_message(connection, "Removes a permission from a player. "
                                     "Fails if the user doesn't have the"
                                     " permission, or if the target's priority"
                                     " is higher than the user's.")
            send_message(connection, "/user addrank (player) (rank)")
            send_message(connection, "Adds a rank to a player. Fails if the "
                                     "rank to be added is equal to or "
                                     "greater than the user's highest rank.")
            send_message(connection, "/user rmrank (player) (rank)")
            send_message(connection, "Removes a rank from a player. Fails if "
                                     "the target outranks or is equal in rank"
                                     " to the user.")
            send_message(connection, "/user listperms (player)")
            send_message(connection, "Lists the permissions a player has.")
            send_message(connection, "/user listranks (player)")
            send_message(connection, "Lists the ranks a player has.")
        elif data[0].lower() == "addperm":
            target = self.find_player(data[1])
            if target:
                if not data[2]:
                    yield from send_message(connection, "No permission "
                                                        "specified.")
                elif not connection.player.perm_check(data[2]):
                    yield from send_message(connection, "You don't have "
                                            "permission to do that!")
                elif data[2].lower() in target.permissions:
                    yield from send_message(connection, "Player {} already "
                                                        "has permission {}."
                                            .format(target.alias, data[2]))
                else:
                    target.revoked_perms.discard(data[2].lower())
                    target.granted_perms.add(data[2].lower())
                    target.update_ranks(self.ranks)
                    if target.logged_in:
                        yield from send_message(target.connection,
                                                "You were granted permission "
                                                "{} by {}."
                                                .format(data[2].lower(),
                                                        connection.player.alias))
                    yield from send_message(connection, "Granted permission "
                                                        "{} to {}."
                                            .format(data[2], target.alias))
            else:
                yield from send_message(connection, "User {} not "
                                                    "found.".format(data[1]))
        elif data[0].lower() == "rmperm":
            target = self.find_player(data[1])
            if target:
                if not data[2]:
                    yield from send_message(connection, "No permission "
                                                        "specified.")
                elif not connection.player.perm_check(data[2]):
                    yield from send_message(connection, "You don't have "
                                            "permission to do that!")
                elif target.priority >= connection.player.priority:
                    yield from send_message(connection, "You don't have "
                                            "permission to do that!")
                elif data[2].lower() not in target.permissions:
                    yield from send_message(connection, "Player {} does not "
                                                        "have permission {}."
                                            .format(target.alias, data[2]))
                else:
                    target.granted_perms.discard(data[2].lower())
                    target.revoked_perms.add(data[2].lower())
                    target.update_ranks(self.ranks)
                    if target.logged_in:
                        yield from send_message(target.connection,
                                                "{} removed permission {} "
                                                "from you."
                                                .format(connection.player.alias,
                                                        data[2].lower()))
                    yield from send_message(connection, "Removed permission "
                                                        "{} from {}."
                                            .format(data[2], target.alias))
            else:
                yield from send_message(connection, "User {} not "
                                                    "found.".format(data[1]))
        elif data[0].lower() == "addrank":
            target = self.find_player(data[1])
            if target:
                if not data[2]:
                    send_message(connection, "No rank specified.")
                    return
                if data[2] not in self.ranks:
                    send_message(connection, "Rank {} does not exist."
                                 .format(data[2]))
                    return
                rank = self.ranks[data[2]]
                if rank["priority"] >= connection.player.priority:
                    yield from send_message(connection, "You don't have "
                                            "permission to do that!")
                elif data[2] in target.ranks:
                    yield from send_message(connection, "Player {} already "
                                                        "has rank {}."
                                            .format(target.alias, data[2]))
                else:
                    target.ranks.add(data[2])
                    target.update_ranks(self.ranks)
                    if target.logged_in:
                        yield from send_message(target.connection,
                                                "You were granted rank {} by {}."
                                                .format(data[2],
                                                        connection.player.alias))
                    yield from send_message(connection, "Granted rank "
                                                        "{} to {}."
                                            .format(data[2], target.alias))
            else:
                yield from send_message(connection, "User {} not "
                                                    "found.".format(data[1]))
        elif data[0].lower() == "rmrank":
            target = self.find_player(data[1])
            if target:
                if not data[2]:
                    send_message(connection, "No rank specified.")
                    return
                if data[2] not in self.ranks:
                    send_message(connection, "Rank {} does not exist."
                                 .format(data[2]))
                    return
                if target.priority >= connection.player.priority:
                    yield from send_message(connection, "You don't have "
                                            "permission to do that!")
                elif data[2] not in target.ranks:
                    yield from send_message(connection, "Player {} does not "
                                                        "have rank {}."
                                            .format(target.alias, data[2]))
                else:
                    target.ranks.remove(data[2])
                    target.update_ranks(self.ranks)
                    if target.logged_in:
                        yield from send_message(target.connection, "{} removed"
                                                                   " rank {} "
                                                                   "from you."
                                                .format(connection.player.alias,
                                                        data[2]))
                    yield from send_message(connection, "Removed rank "
                                                        "{} from {}."
                                            .format(data[2], target.alias))
            else:
                yield from send_message(connection, "User {} not "
                                                    "found.".format(data[1]))
        elif data[0].lower() == "listperms":
            target = self.find_player(data[1])
            if target:
                perms = ", ".join(target.permissions)
                yield from send_message(connection, "Permissions for user {}:"
                                                    "\n{}"
                                        .format(target.alias, perms))
            else:
                yield from send_message(connection, "User {} not "
                                                    "found.".format(data[1]))
        elif data[0].lower() == "listranks":
            target = self.find_player(data[1])
            if target:
                ranks = ", ".join(target.ranks)
                yield from send_message(connection, "Ranks for user {}:"
                                                    "\n{}"
                                        .format(target.alias, ranks))
            else:
                yield from send_message(connection, "User {} not "
                                                    "found.".format(data[1]))
        else:
            yield from send_message(connection, "Argument not recognized. "
                                                "See /user help for usage "
                                                "info.")

    @Command("list_players",
             perm="player_manager.list_players",
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
             perm="player_manager.delete_player",
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
        if not data:
            send_message(connection, "No arguments provided.")
            return
        if data[-1] == "*force":
            force = True
            data.pop()
        else:
            force = False
        alias = " ".join(data)
        player = self.find_player(alias)
        if player is None:
            raise NameError
        if player.priority >= connection.player.priority:
            send_message(connection, "Can't delete {}, they are equal or "
                                     "higher rank than you!"
                         .format(player.alias))
            return
        if (not force) and player.logged_in:
            raise ValueError(
                "Can't delete a logged-in player; please kick them first. If "
                "absolutely necessary, append *force to the command.")
        self.players.pop(player.uuid)
        del player
        send_message(connection, "Player {} has been deleted.".format(alias))
