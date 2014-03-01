import datetime
from enum import IntEnum
import pprint
import shelve
import asyncio
import re

from base_plugin import Role, SimpleCommandPlugin
from data_parser import StarString
import packets
from pparser import build_packet
from server import StarryPyServer
from utilities import Command, send_message


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


class State(IntEnum):
    VERSION_SENT = 0
    CLIENT_CONNECT_RECEIVED = 1
    HANDSHAKE_CHALLENGE_SENT = 2
    HANDSHAKE_RESPONSE_RECEIVED = 3
    CONNECT_RESPONSE_SENT = 4
    CONNECTED = 5
    CONNECTED_WITH_HEARTBEAT = 6


class Player:
    def __init__(self, uuid, name='', last_seen=None, roles=None,
                 logged_in=True, protocol=None, client_id=-1, ip="0.0.0.0",
                 planet='', muted=False, state=None):
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
        return pprint.pformat(self.__dict__)

    def check_role(self, role):
        for r in self.roles:
            if r.lower() == role.__name__.lower():
                return True
        return False


class Ship:
    def __init__(self, player):
        self.player = player

    def __str__(self):
        return "%s's ship" % self.player


class Planet:
    def __init__(self, sector='alpha', location=(0, 0, 0), planet=0,
                 satellite=0):
        self.sector = sector
        self.a, self.x, self.y = location
        self.planet = planet
        self.satellite = satellite

    def __str__(self):
        return "%s:%d:%d:%d:%d:%d" % (self.sector, self.a, self.x, self.y,
                                      self.planet, self.satellite)


class IPBan:
    def __init__(self, ip, reason, banned_by, timeout=None):
        self.ip = ip
        self.reason = reason
        self.timeout = timeout
        self.banned_by = banned_by
        self.banned_at = datetime.datetime.now()


class PlayerManager(SimpleCommandPlugin):
    name = "player_manager"

    def activate(self):
        super().activate()
        self.shelf = shelve.open(self.config.config.player_db, writeback=True)
        self.sync()
        self.players = self.shelf['players']
        self.planets = self.shelf['planets']
        self.plugin_shelf = self.shelf['plugins']

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

    def on_protocol_version(self, data, protocol):
        if protocol.client_ip in self.shelf['bans']:
            self.logger.info("Banned IP (%s) tried to log in." %
                             protocol.client_ip)
            return False
        else:
            protocol.state = State.VERSION_SENT
            return True

    def on_handshake_challenge(self, data, protocol):
        protocol.state = State.HANDSHAKE_CHALLENGE_SENT
        return True

    def on_handshake_response(self, data, protocol):
        protocol.state = State.HANDSHAKE_RESPONSE_RECEIVED
        return True

    def on_connect_response(self, data, protocol):
        response = data['parsed']
        if response['success']:
            protocol.player.logged_in = True
            protocol.player.client_id = response['client_id']
            protocol.player.protocol = protocol
            protocol.player.location = yield from self.add_or_get_ship(
                protocol.player.name)
            protocol.state = State.CONNECTED
        else:
            protocol.player.logged_in = False
            protocol.player.client_id = -1
        return True

    def on_client_connect(self, data, protocol: StarryPyServer):
        player = yield from self.add_or_get_player(**data['parsed'])
        player.ip = protocol.client_ip
        protocol.player = player
        return True

    def on_client_disconnect(self, data, protocol):
        protocol.player.protocol = None
        protocol.player.logged_in = False
        protocol.player.location = None
        return True

    def on_server_disconnect(self, data, protocol):
        protocol.player.protocol = None
        protocol.player.logged_in = False
        return True

    def on_warp_command(self, data, protocol):
        if data['parsed']['warp_type'] == 3:
            protocol.player.location = yield from \
                self.add_or_get_ship(data['parsed']['player'])
        elif data['parsed']['warp_type'] == 2:
            protocol.player.location = self.add_or_get_ship(
                protocol.player.name)
        return True

    def on_world_start(self, data, protocol: StarryPyServer):
        planet = data['parsed']['planet']
        if planet['celestialParameters'] is not None:
            location = yield from self.add_or_get_planet(
                **planet['celestialParameters']['coordinate'])
            protocol.player.location = location
        else:
            if not isinstance(protocol.player.location, Ship):
                protocol.player.location = yield from self.add_or_get_ship(
                    protocol.player.name)
        self.logger.info("Player %s is now at location: %s",
                         protocol.player.name,
                         protocol.player.location)
        return True

    def on_heartbeat(self, data, protocol):
        protocol.state = 6
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
            name = name.decode("utf-8")
        if uuid in self.shelf['players']:
            self.logger.info("Returning existing player.")
            p = self.shelf['players'][uuid]
            if uuid == self.config.config.owner_uuid:
                p.roles = {x.__name__ for x in Owner.roles}
            return p
        else:
            self.logger.info("Creating new player with UUID %s and name %s",
                             uuid, name)
            if uuid == self.config.config.owner_uuid:
                roles = {x.__name__ for x in Owner.roles}
            else:
                roles = {x.__name__ for x in Guest.roles}
            self.logger.debug("Matches owner UUID: ",
                              uuid == self.config.config.owner_uuid)
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
            yield from self.factory.broadcast("%s has kicked %s. Reason: %s" %
                                              (protocol.player.name,
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
    def add_or_get_planet(self, sector, location, planet, satellite,
                          **kwargs) -> Planet:
        a, x, y = location
        loc_string = "%s:%d:%d:%d:%d:%d" % (sector, a, x, y, planet, satellite)
        if loc_string in self.shelf['planets']:
            self.logger.info("Returning already existing planet.")
            planet = self.shelf['planets'][loc_string]
        else:
            planet = Planet(sector=sector, location=location, planet=planet,
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
