import base64
import datetime
from operator import attrgetter
import pprint
import shelve
import asyncio
import re

from base_plugin import Role, SimpleCommandPlugin
from data_parser import StarString, ConnectFailure
import packets
from pparser import build_packet
from server import StarryPyServer
from utilities import Command, send_message, broadcast, DotDict, State, WarpType


class Owner(Role):
    is_meta = True


class SuperAdmin(Owner):
    is_meta = True


class Admin(SuperAdmin):
    is_meta = True


class Moderator(Admin):
    is_meta = True


class Guest(Moderator):
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
    def __init__(self, uuid, name='', last_seen=None, roles=None,
                 logged_in=True, protocol=None, client_id=-1, ip="0.0.0.0",
                 planet='', muted=False, state=None):
        """
        When a player connects, let be sure we store all the right things.
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
        Convenience method for peeking at the player object.
        :return:
        """
        return pprint.pformat(self.__dict__)

    def check_role(self, role):
        """
        Find out what roles a player has.
        :param role:
        :return:
        """
        for r in self.roles:
            if r.lower() == role.__name__.lower():
                return True
        return False


class Ship:
    """
    Prototype class for a ship.
    """
    def __init__(self, player):
        self.player = player

    def __str__(self):
        return "%s's ship" % self.player


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
        return "%d:%d:%d:%d:%d" % (self.a, self.x, self.y,
                                      self.planet, self.satellite)


class IPBan:
    def __init__(self, ip, reason, banned_by, timeout=None):
        self.ip = ip
        self.reason = reason
        self.timeout = timeout
        self.banned_by = banned_by
        self.banned_at = datetime.datetime.now()


class DeletePlayer(SuperAdmin):
    pass


class PlayerManager(SimpleCommandPlugin):
    name = "player_manager"

    def __init__(self):
        with open("config/sector_magic_string") as f:
            ms = f.read()
        self.default_config = {"player_db": "config/player",
                               "unlocked_sector_magic": ms,
                               "owner_uuid": "!--REPLACE IN CONFIG FILE--!"}
        super().__init__()
        self.shelf = shelve.open(self.plugin_config.player_db, writeback=True)
        self.sync()
        self.players = self.shelf['players']
        self.planets = self.shelf['planets']
        self.plugin_shelf = self.shelf['plugins']
        self.unlocked_sector_magic = base64.decodebytes(
            self.plugin_config.unlocked_sector_magic.encode("ascii"))

    @Command("test_broadcast")
    def test_broadcast(self, data, protocol):
        self.planetary_broadcast(protocol.player, " ".join(data))

    def planetary_broadcast(self, player, message):
        for p in self.players.values():
            if p.logged_in and p.location is player.location:
                send_message(p.protocol,
                             message,
                             name=p.name)
        return None

    def sync(self):
        if 'players' not in self.shelf:
            self.shelf['players'] = {}
        if 'plugins' not in self.shelf:
            self.shelf['plugins'] = {}
        if 'planets' not in self.shelf:
            self.shelf['planets'] = {}
        if 'bans' not in self.shelf:
            self.shelf['bans'] = {}
        if 'ships' not in self.shelf:
            self.shelf['ships'] = {}
        self.shelf.sync()

    def on_protocol_request(self, data, protocol):
        protocol.state = State.VERSION_SENT
        return True

    def on_handshake_challenge(self, data, protocol):
        protocol.state = State.HANDSHAKE_CHALLENGE_SENT
        return True

    def on_handshake_response(self, data, protocol):
        protocol.state = State.HANDSHAKE_RESPONSE_RECEIVED
        self.logger.info("on_handshake_response")
        return True

    def on_connect_success(self, data, protocol):
        response = data['parsed']
        protocol.player.logged_in = True
        protocol.player.client_id = response['client_id']
        protocol.player.protocol = protocol
        protocol.player.location = yield from self.add_or_get_ship(
            protocol.player.name)
        protocol.state = State.CONNECTED
        return True

    def build_rejection(self, reason):
        return build_packet(packets.packets['connect_failure'],
                            ConnectFailure.build(
                                dict(reason=reason)))

    def on_client_connect(self, data, protocol: StarryPyServer):
        """
        When we see a client_connect packet, handle it.
        :param data:
        :param protocol:
        :return:
        """
        try:
            player = yield from self.add_or_get_player(**data['parsed'])
            self.check_bans(protocol)
        except (NameError, ValueError) as e:
            yield from protocol.raw_write(self.build_rejection(str(e)))
            protocol.die()
            return False
        player.ip = protocol.client_ip
        protocol.player = player
        return True

    def on_client_disconnect_request(self, data, protocol):
        protocol.player.protocol = None
        protocol.player.logged_in = False
        protocol.player.location = None
        return True

    def on_server_disconnect(self, data, protocol):
        protocol.player.protocol = None
        protocol.player.logged_in = False
        return True

    def on_player_warp(self, data, protocol):
        if data['parsed']['warp_type'] == WarpType.TO_ALIAS:
            pass
        elif data['parsed']['warp_type'] == WarpType.TO_PLAYER:
            pass
        elif data['parsed']['warp_type'] == WarpType.TO_WORLD:
            pass
        return True

    def on_world_start(self, data, protocol: StarryPyServer):
        # FIXME: Planet information has been shifted out of on_world_start
        # planet = data['parsed']['planet']
        # if planet['celestialParameters'] is not None:
        #     location = yield from self.add_or_get_planet(
        #         **planet['celestialParameters']['coordinate'])
        #     protocol.player.location = location
        # else:
        #     if not isinstance(protocol.player.location, Ship):
        #         protocol.player.location = yield from self.add_or_get_ship(
        #             protocol.player.name)
        # self.logger.info("Player %s is now at location: %s",
        #                  protocol.player.name,
        #                  protocol.player.location)
        return True

    def on_step_update(self, data, protocol):
        protocol.state = State.CONNECTED_WITH_HEARTBEAT
        return True

    def deactivate(self):
        for player in self.shelf['players'].values():
            player.protocol = None
            player.logged_in = False
        self.shelf.close()
        self.logger.debug("Closed the shelf")

    @asyncio.coroutine
    def add_or_get_player(self, uuid, name='', last_seen=None, roles=None,
                          logged_in=True, protocol=None, client_id=-1,
                          ip="0.0.0.0",
                          planet='', muted=False,
                          **kwargs) -> Player:
        if isinstance(uuid, bytes):
            uuid = uuid.decode("ascii")
        if isinstance(name, bytes):
            self.logger.debug(name)
            name = name.decode("utf-8")
        if uuid in self.shelf['players']:
            self.logger.info("Returning existing player.")
            p = self.shelf['players'][uuid]
            if p.logged_in:
                raise ValueError("Player is already logged in.")
            if uuid == self.plugin_config.owner_uuid:
                p.roles = {x.__name__ for x in Owner.roles}
            return p
        else:
            if self.get_player_by_name(name) is not None:
                raise NameError("A user with that name already exists.")
            self.logger.info("Creating new player with UUID %s and name %s",
                             uuid, name)
            if uuid == self.plugin_config.owner_uuid:
                roles = {x.__name__ for x in Owner.roles}
            else:
                roles = {x.__name__ for x in Guest.roles}
            new_player = Player(uuid, name, last_seen, roles, logged_in,
                                protocol, client_id, ip, planet, muted)
            self.shelf['players'][uuid] = new_player
            return new_player

    @asyncio.coroutine
    def add_or_get_ship(self, player_name):
        if player_name in self.shelf['ships']:
            return self.shelf['ships'][player_name]
        else:
            ship = Ship(player_name)
            self.shelf['ships'][player_name] = ship
            return ship

    def add_role(self, player, role):
        if issubclass(role, Role):
            r = role.__name__
        else:
            raise TypeError("add_role requires a Role subclass to be passed as"
                            " the second argument.")
        player.roles.add(r)
        self.logger.info("Granted role %s to %s" % (r, player.name))
        for subrole in role.roles:
            s = self.get_role(subrole)
            if issubclass(s, role):
                self.add_role(player, s)

    def get_role(self, name):
        if issubclass(name, Role):
            return name
        return [x for x in Owner.roles
                if x.__name__.lower() == name.lower()][0]

    def get_player_by_name(self, name, check_logged_in=False) -> Player:
        lname = name.lower()
        for player in self.shelf['players'].values():
            if player.name.lower() == lname:
                if not check_logged_in or player.logged_in:
                    return player

    @Command("kick", role=Kick, doc="Kicks a player.",
             syntax=("[\"]player name[\"]", "[reason]"))
    def kick(self, data, protocol):
        name = data[0]
        try:
            reason = " ".join(data[1:])
        except IndexError:
            reason = "No reason given."

        p = self.get_player_by_name(" ".join(data))
        if p is not None:
            kill_packet = build_packet(packets.packets['server_disconnect'],
                                       StarString.build("You were kicked."))
            yield from p.protocol.raw_write(kill_packet)
            broadcast(self.factory,
                      "%s has kicked %s. Reason: %s" % (protocol.player.name,
                                                        p.name,
                                                        reason))

        else:
            send_message(protocol,
                         "Couldn't find a player with name %s" % name)

    @Command("ban",
             role=Ban,
             doc="Bans a user or an IP address.",
             syntax=("(ip | name)", "(reason)"))
    def ban(self, data, protocol):
        try:
            target, reason = data[0], " ".join(data[1:])
            if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", target):
                self.ban_by_ip(target, reason, protocol)
            else:
                self.ban_by_name(target, reason, protocol)
        except:
            raise SyntaxWarning

    def ban_by_ip(self, ip, reason, protocol):
        ban = IPBan(ip, reason, protocol.player.name)
        self.shelf['bans'][ip] = ban
        send_message(protocol, "Banned IP: %s with reason: %s" % (ip, reason))

    def ban_by_name(self, name, reason, protocol):
        p = self.get_player_by_name(name)
        if p is not None:
            self.ban_by_ip(p.ip, reason, protocol)
        else:
            send_message(protocol,
                         "Couldn't find a player by the name %s" % name)

    @asyncio.coroutine
    def add_or_get_planet(self, location, planet, satellite,
                          **kwargs) -> Planet:
        a, x, y = location
        loc_string = "%d:%d:%d:%d:%d" % (a, x, y, planet, satellite)
        if loc_string in self.shelf['planets']:
            self.logger.info("Returning already existing planet.")
            planet = self.shelf['planets'][loc_string]
        else:
            planet = Planet(location=location, planet=planet,
                            satellite=satellite)
            self.shelf['planets'][str(planet)] = planet
        return planet

    @Command("list_bans", role=Ban, doc="Lists all active bans.")
    def list_bans(self, data, protocol):
        if len(self.shelf['bans'].keys()) == 0:
            send_message(protocol, "There are no active bans.")
        else:
            res = ["Active bans:"]
            for ban in self.shelf['bans'].values():
                res.append("IP: %(ip)s - "
                           "Reason: %(reason)s - "
                           "Banned by: %(banned_by)s" % ban.__dict__)
            send_message(protocol, "\n".join(res))

    @Command("grant", "promote", role=Grant, doc="Grants a role to a player.",
             syntax=("(role)", "(player)"))
    def grant(self, data, protocol):
        role = data[0]
        name = " ".join(data[1:])
        p = self.get_player_by_name(name)
        try:
            if role.lower() not in (x.__name__.lower() for x in Owner.roles):
                raise LookupError("Unknown role %s" % role)
            if p is None:
                raise LookupError("Unknown player %s" % name)
            ro = [x for x in Owner.roles if
                  x.__name__.lower() == role.lower()][0]
            self.add_role(p, ro)
            send_message(protocol,
                         "Granted role %s to %s." % (ro.__name__, p.name))
            if p.protocol is not None:
                send_message(p.protocol,
                             "You've been granted the role %s by %s"
                             % (ro.__name__, protocol.player.name))
        except LookupError as e:
            send_message(protocol, str(e))

    @Command("list_players", role=Whois, doc="Lists all players.",
             syntax=("[wildcards]",))
    def list_players(self, data, protocol):
        players = [player for player in self.players.values()]
        players.sort(key=attrgetter('name'))
        send_message(protocol,
                     "%d players found:" % len(players))
        for x, player in enumerate(players):
            player_info = "  %d. %s%s"
            if player.logged_in:
                l = " (logged-in)"
            else:
                l = ""
            send_message(protocol, player_info % (x + 1, player.name, l))

    @Command("del_player", role=DeletePlayer, doc="Deletes a player",
             syntax=("(username)",
                     "[*force=forces deletion of a logged in player. NOT RECOMMENDED.]"))
    def delete_player(self, data, protocol):
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
                "Can't delete a logged-in player; please kick them first. If absolutely necessary, append *force to the command.")
        self.players.pop(player.uuid)
        del player
        send_message(protocol, "Player %s has been deleted." % name)

    def check_bans(self, protocol):
        if protocol.client_ip in self.shelf['bans']:
            self.logger.info("Banned IP (%s) tried to log in." %
                             protocol.client_ip)
            raise ValueError("You are banned!\nReason: %s"
                             % self.shelf['bans'][protocol.client_ip].reason)

    def get_storage(self, caller):
        name = caller.name
        if name not in self.plugin_shelf:
            self.plugin_shelf[name] = DotDict({})
        return self.plugin_shelf[name]
