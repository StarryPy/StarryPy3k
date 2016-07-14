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

import packets
from base_plugin import Role, SimpleCommandPlugin
from data_parser import ConnectFailure, ServerDisconnect
from pparser import build_packet
from server import StarryPyServer
from utilities import Command, send_message, broadcast, DotDict, State, \
    WarpType
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


class Grant(Owner):
    pass


class Revoke(Owner):
    pass


class Player:
    """
    Prototype class for a player.
    """
    def __init__(self, uuid, name="", last_seen=None, roles=None,
                 logged_in=True, protocol=None, client_id=-1, ip="",
                 planet="", muted=False, state=None):
        """
        Initialize a player object. Populate all the necessary details.

        :param uuid:
        :param name:
        :param last_seen:
        :param roles:
        :param logged_in:
        :param protocol:
        :param client_id:
        :param ip:
        :param planet:
        :param muted:
        :param state:
        :return:
        """
        self.uuid = uuid
        self.name = name
        if last_seen is None:
            self.last_seen = datetime.datetime.now()
        else:
            self.last_seen = last_seen
        if roles is None:
            self.roles = set()
        else:
            self.roles = set(roles)
        self.logged_in = logged_in
        self.protocol = protocol
        self.client_id = client_id
        self.ip = ip
        self.location = planet
        self.muted = muted

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
    def __init__(self, player):
        self.player = player

    def __str__(self):
        return "{}'s ship".format(self.player)


class Planet:
    """
    Prototype class for a planet.
    """
    def __init__(self, location=(0, 0, 0), planet=0,
                 satellite=0):
        self.a, self.x, self.y = location
        self.planet = planet
        self.satellite = satellite

    def __str__(self):
        return "{}:{}:{}:{}:{}".format(self.a, self.x, self.y,
                                       self.planet, self.satellite)


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
                               "owner_uuid": "!--REPLACE IN CONFIG FILE--!"}
        super().__init__()
        self.shelf = shelve.open(self.plugin_config.player_db, writeback=True)
        self.sync()
        self.players = self.shelf["players"]
        self.planets = self.shelf["planets"]
        self.plugin_shelf = self.shelf["plugins"]

    # Packet hooks - look for these packets and act on them

    def on_protocol_request(self, data, protocol):
        """
        Catch when a client first pings the server for a connection. Set the
        'state' variable to keep track of this.

        :param data:
        :param protocol:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        protocol.state = State.VERSION_SENT
        return True

    def on_handshake_challenge(self, data, protocol):
        """
        Catch when a client tries to handshake with server. Update the 'state'
        variable to keep track of this. Note: This step only occurs when a
        server requires name/password authentication.

        :param data:
        :param protocol:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        protocol.state = State.HANDSHAKE_CHALLENGE_SENT
        return True

    def on_handshake_response(self, data, protocol):
        """
        Catch when the server responds to a client's handshake. Update the
        'state' variable to keep track of this. Note: This step only occurs
        when a server requires name/password authentication.

        :param data:
        :param protocol:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        protocol.state = State.HANDSHAKE_RESPONSE_RECEIVED
        return True

    def on_client_connect(self, data, protocol: StarryPyServer):
        """
        Catch when a the client updates the server with its connection
        details. This is a key step to fingerprinting the client, and
        ensuring they stay in the wrapper. This is also where we apply our
        bans.

        :param data:
        :param protocol:
        :return: Boolean: True on successful connection, False on a
                 failed connection.
        """
        try:
            player = yield from self.add_or_get_player(**data["parsed"])
            self.check_bans(protocol)
        except (NameError, ValueError) as e:
            yield from protocol.raw_write(self.build_rejection(str(e)))
            protocol.die()
            return False
        player.ip = protocol.client_ip
        protocol.player = player
        return True

    def on_connect_success(self, data, protocol):
        """
        Catch when a successful connection is established. Update the 'state'
        variable to keep track of this. Since the client successfully
        connected, update their details in storage (client id, location,
        logged_in state).

        :param data:
        :param protocol:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        response = data["parsed"]
        protocol.player.logged_in = True
        protocol.player.client_id = response["client_id"]
        protocol.player.protocol = protocol
        protocol.player.location = yield from self.add_or_get_ship(
            protocol.player.name)
        protocol.state = State.CONNECTED
        return True

    def on_client_disconnect_request(self, data, protocol):
        """
        Catch when a client requests a disconnect from the server. At this
        point, we need to clean up the connection information we have for the
        client (logged_in state, location).

        :param data:
        :param protocol:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        # TODO: This likely needs more attention as clients disconnecting
        # cause an error in the client_loop in the server factory.
        protocol.player.protocol = None
        protocol.player.logged_in = False
        protocol.player.location = None
        return True

    def on_server_disconnect(self, data, protocol):
        """
        Catch when the server disconnects a client. Similar to the client
        disconnect packet, use this as a cue to perform cleanup, if it wasn't
        done already.

        :param data:
        :param protocol:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        protocol.player.protocol = None
        protocol.player.logged_in = False
        return True

    def on_player_warp(self, data, protocol):
        """
        Hook when a player warps. Currently, nothing is done with this.

        :param data:
        :param protocol:
        :return: Boolean: True. Even though we don't do anything with this, we
                 don't want to stop the packet here currently.
        """
        if data["parsed"]["warp_type"] == WarpType.TO_ALIAS:
            pass
        elif data["parsed"]["warp_type"] == WarpType.TO_PLAYER:
            pass
        elif data["parsed"]["warp_type"] == WarpType.TO_WORLD:
            pass
        return True

    def on_world_start(self, data, protocol: StarryPyServer):
        """
        Hook when a new world instance is started. Use the details passed to
        determine the location of the world, and update the player's
        information accordingly.

        :param data:
        :param protocol:
        :return: Boolean: True. Don't stop the packet here.
        """
        # TODO: We only enumerate worlds and ships currently. We need to
        # expand this to include mission worlds and instance worlds too.
        planet = data["parsed"]["template_data"]
        if planet["celestialParameters"] is not None:
            location = yield from self.add_or_get_planet(
                **planet["celestialParameters"]["coordinate"])
            protocol.player.location = location
        else:
            if not isinstance(protocol.player.location, Ship):
                protocol.player.location = yield from self.add_or_get_ship(
                    protocol.player.name)
        self.logger.info("Player {} is now at location: {}".format(
            protocol.player.name,
            protocol.player.location))
        return True

    def on_step_update(self, data, protocol):
        """
        Catch when the first heartbeat packet is sent to a player. This is the
        final confirmation in the connection process. Update the 'state'
        variable to reflect this.

        :param data:
        :param protocol:
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        protocol.state = State.CONNECTED_WITH_HEARTBEAT
        return True

    # Helper functions - Used by hooks and commands

    def build_rejection(self, reason):
        """
        Function to build packet to reject connection for client.

        :param reason: String. Reason for rejection.
        :return: Rejection packet.
        """
        return build_packet(packets.packets["connect_failure"],
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
            player.protocol = None
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
        self.logger.info("Granted role {} to {}".format(r, player.name))
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

    def ban_by_ip(self, ip, reason, protocol):
        """
        Ban a player based on their IP address. Should be compatible with both
        IPv4 and IPv6.

        :param ip: String: IP of player to be banned.
        :param reason: String: Reason for player's ban.
        :param protocol: Connection of target player to be banned.
        :return: Null
        """
        ban = IPBan(ip, reason, protocol.player.name)
        self.shelf["bans"][ip] = ban
        send_message(protocol,
                     "Banned IP: {} with reason: {}".format(ip, reason))

    def ban_by_name(self, name, reason, protocol):
        """
        Ban a player based on their name. This is the easier route, as it is a
        more user friendly to target the player to be banned. Hooks to the
        ban_by_ip mechanism backstage.

        :param name: String: Name of the player to be banned.
        :param reason: String: Reason for player's ban.
        :param protocol: Connection of target player to be banned.
        :return: Null
        """
        p = self.get_player_by_name(name)
        if p is not None:
            self.ban_by_ip(p.ip, reason, protocol)
        else:
            send_message(protocol,
                         "Couldn't find a player by the name {}".format(name))

    def check_bans(self, protocol):
        """
        Check if a ban on a player exists. Raise ValueError when true.

        :param protocol: The connection of the target player.
        :return: Null.
        :raise: ValueError if player is banned. Pass reason message up with
                exception.
        """
        if protocol.client_ip in self.shelf["bans"]:
            self.logger.info("Banned IP ({}) tried to log in.".format(
                protocol.client_ip))
            raise ValueError("You are banned!\nReason: {}".format(
                self.shelf["bans"][protocol.client_ip].reason))

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

    @asyncio.coroutine
    def add_or_get_player(self, uuid, name="", last_seen=None, roles=None,
                          logged_in=True, protocol=None, client_id=-1, ip="",
                          planet="", muted=False, **kwargs) -> Player:
        """
        Given a UUID, try to find the player's info in storage. In the event
        that the player has never connected to the server before, add their
        details into storage for future reference. Return a Player object.

        :param uuid: UUID of connecting character
        :param name: Name of connecting character
        :param last_seen: Date of last login
        :param roles: Roles granted to character
        :param logged_in: Boolean: Is character currently logged in
        :param protocol: Connection of connecting player
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

        if uuid in self.shelf["players"]:
            self.logger.info("Known player is attempting to log in: "
                             "{}".format(name))
            p = self.shelf["players"][uuid]
            if p.logged_in:
                raise ValueError("Player is already logged in.")
            if uuid == self.plugin_config.owner_uuid:
                p.roles = {x.__name__ for x in Owner.roles}
            return p
        else:
            if self.get_player_by_name(name) is not None:
                raise NameError("A user with that name already exists.")
            self.logger.info("Adding new player to database: {} (UUID:{})"
                             "".format(uuid, name))
            if uuid == self.plugin_config.owner_uuid:
                roles = {x.__name__ for x in Owner.roles}
            else:
                roles = {x.__name__ for x in Guest.roles}
            new_player = Player(uuid, name, last_seen, roles, logged_in,
                                protocol, client_id, ip, planet, muted)
            self.shelf["players"][uuid] = new_player
            return new_player

    @asyncio.coroutine
    def add_or_get_ship(self, player_name):
        """
        Given a player's name, look up their ship in the ships shelf. If ship
        not in shelf, add it. Return a Ship object.

        :param player_name: Target player to look up
        :return: Ship object.
        """
        if player_name in self.shelf["ships"]:
            return self.shelf["ships"][player_name]
        else:
            ship = Ship(player_name)
            self.shelf["ships"][player_name] = ship
            return ship

    @asyncio.coroutine
    def add_or_get_planet(self, location, planet, satellite) -> Planet:
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
        return planet

    # Commands - In-game actions that can be performed

    @Command("kick",
             role=Kick,
             doc="Kicks a player.",
             syntax=("[\"]player name[\"]", "[reason]"))
    def kick(self, data, protocol):
        """
        Kick a play off the server. You must specify a name. You may also
        specify an optional reason.

        :param data:
        :param protocol:
        :return: Null
        """

        # FIXME: Kick is currently broken. Kicking someone will cause their
        # starbound client to crash (overkill).
        try:
            name = data[0]
        except IndexError:
            raise SyntaxWarning("No target provided.")

        try:
            reason = " ".join(data[1:])
        except IndexError:
            reason = "No reason given."

        p = self.get_player_by_name(" ".join(data))
        if not p.logged_in:
            send_message(protocol,
                         "Player {} is not currently logged in.".format(name))
            return False
        if p is not None:
            kick_packet = ServerDisconnect.build({
                "reason": "You were kicked.\n Reason: {}".format(reason)})
            to_send = build_packet(packets['server_disconnect'], kick_packet)
            yield from p.protocol.raw_write(to_send)
            broadcast(self.factory,
                      "{} has kicked {}. Reason: {}".format(
                          protocol.player.name,
                          p.name,
                          reason))
        else:
            send_message(protocol,
                         "Couldn't find a player with name {}".format(name))

    @Command("ban",
             role=Ban,
             doc="Bans a user or an IP address.",
             syntax=("(ip | name)", "(reason)"))
    def ban(self, data, protocol):
        """
        Ban a player. You must specify either a name or an IP. You must also
        specify a 'reason' for banning the player. This information is stored
        and, should the player try to connect again, are great with the
        message:

        > You are banned!
        > Reason: <reason shows here>

        :param data:
        :param protocol:
        :return: Null
        :raise: SyntaxWarning on incorrect input.
        """
        try:
            target, reason = data[0], " ".join(data[1:])
            if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", target):
                self.ban_by_ip(target, reason, protocol)
            else:
                self.ban_by_name(target, reason, protocol)
        except:
            raise SyntaxWarning

    @Command("list_bans",
             role=Ban,
             doc="Lists all active bans.")
    def list_bans(self, data, protocol):
        """
        List the current bans.

        :param data:
        :param protocol:
        :return:
        """
        if len(self.shelf["bans"].keys()) == 0:
            send_message(protocol, "There are no active bans.")
        else:
            res = ["Active bans:"]
            for ban in self.shelf["bans"].values():
                res.append("IP: {ip} - "
                           "Reason: {reason} - "
                           "Banned by: {banned_by}".format(**ban.__dict__))
            send_message(protocol, "\n".join(res))

    @Command("grant", "promote",
             role=Grant,
             doc="Grants a role to a player.",
             syntax=("(role)", "(player)"))
    def grant(self, data, protocol):
        """
        Grant a role to a player.

        :param data:
        :param protocol:
        :return: Null
        :raise: LookupError on unknown player or role entry.
        """
        role = data[0]
        name = " ".join(data[1:])
        p = self.get_player_by_name(name)
        try:
            if role.lower() not in (x.__name__.lower() for x in Owner.roles):
                raise LookupError("Unknown role {}".format(role))
            if p is None:
                raise LookupError("Unknown player {}".format(name))
            ro = [x for x in Owner.roles if
                  x.__name__.lower() == role.lower()][0]
            self.add_role(p, ro)
            send_message(protocol,
                         "Granted role {} to {}.".format(ro.__name__, p.name))
            if p.protocol is not None:
                send_message(p.protocol,
                             "You've been granted the role {} by {}".format(
                                 ro.__name__, protocol.player.name))
        except LookupError as e:
            send_message(protocol, str(e))

    @Command("list_players",
             role=Whois,
             doc="Lists all players.",
             syntax=("[wildcards]",))
    def list_players(self, data, protocol):
        """
        List the players in the database. Wildcard formats are allowed in this
        search (not really. NotImplemementedYet...) Careful, this list can get
        pretty big for a long running or popular server.

        :param data:
        :param protocol:
        :return: Null
        """
        players = [player for player in self.players.values()]
        players.sort(key=attrgetter("name"))
        send_message(protocol,
                     "{} players found:".format(len(players)))
        for x, player in enumerate(players):
            player_info = "  {0}. {1}{2}"
            if player.logged_in:
                l = " (logged-in, ID: {})".format(player.client_id)
            else:
                l = ""
            send_message(protocol, player_info.format(x + 1, player.name, l))

    @Command("del_player",
             role=DeletePlayer,
             doc="Deletes a player",
             syntax=("(username)",
                     "[*force=forces deletion of a logged in player."
                     " ^red;NOT RECOMMENDED^reset;.]"))
    def delete_player(self, data, protocol):
        """
        Removes a player from the player database. By default. you cannot
        remove a logged-in player, so either they need to be removed from
        the server first, or you have to apply the *force operation.

        :param data:
        :param protocol:
        :return: Null
        :raise: NameError if is not available. ValueError if player is
                currently logged in.
        """
        if data[-1] == "*force":
            force = True
            data.pop()
        else:
            force = False
        name = " ".join(data)
        player = self.get_player_by_name(name)
        if player is None:
            raise NameError
        if (not force) and player.logged_in:
            raise ValueError(
                "Can't delete a logged-in player; please kick them first. If "
                "absolutely necessary, append *force to the command.")
        self.players.pop(player.uuid)
        del player
        send_message(protocol, "Player {} has been deleted.".format(name))

    # @Command("test_broadcast")
    # def test_broadcast(self, data, protocol):
    #     self.planetary_broadcast(protocol.player, " ".join(data))
    #
    # def planetary_broadcast(self, player, message):
    #     for p in self.players.values():
    #         if p.logged_in and p.location is player.location:
    #             send_message(p.protocol,
    #                          message,
    #                          name=p.name)
    #     return None
