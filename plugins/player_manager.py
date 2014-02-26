import datetime
from enum import IntEnum
import pprint
import shelve
import asyncio
import re
import traceback

from base_plugin import Role, command, SimpleCommandPlugin
from server import StarryPyServer


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
                 planet='', on_ship=True, muted=False, state=None):
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
        self.planet = planet
        self.on_ship = on_ship
        self.muted = muted

    def __str__(self):
        return pprint.pformat(self.__dict__)


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
        if response.success:
            protocol.player.logged_in = True
            protocol.player.client_id = response.client_id
            protocol.player.protocol = protocol
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
        return True

    def on_server_disconnect(self, data, protocol):
        protocol.player.protocol = None
        protocol.player.logged_in = False
        return True

    def on_warp_command(self, data, protocol):
        return True

    def on_world_start(self, data, protocol: StarryPyServer):
        planet = data['parsed'].planet
        if planet.celestialParameters is not None:
            location = yield from self.add_or_get_planet(
                **planet.celestialParameters.coordinate)
            protocol.player.planet = location
        else:
            protocol.player.on_ship = True
            location = "on ship"
        self.logger.info("Player %s is now at location: %s",
                         protocol.player.name,
                         location)
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
                          planet='', on_ship=True, muted=False,
                          **kwargs) -> Player:
        if str(uuid) in self.shelf['players']:
            self.logger.info("Returning existing player.")
            p = self.shelf['players'][str(uuid)]
            if uuid.decode("ascii") == self.config.config.owner_uuid:
                p.roles = {x.__name__ for x in Owner.roles}
            return p
        else:
            self.logger.info("Creating new player with UUID %s and name %s",
                             uuid, name)
            if uuid.decode("ascii") == self.config.config.owner_uuid:
                roles = {x.__name__ for x in Owner.roles}
            else:
                roles = {x.__name__ for x in Guest.roles}
            self.logger.debug("Matches owner UUID: ",
                              uuid.decode(
                                  "ascii") == self.config.config.owner_uuid)
            new_player = Player(uuid, name, last_seen, roles, logged_in,
                                protocol, client_id, ip, planet, on_ship, muted)
            self.shelf['players'][str(uuid)] = new_player
            return new_player

    def add_role(self, player, role):
        if issubclass(role, Role):
            role = role.__name__
        player.roles.add(role)

    def get_player_by_name(self, name, check_logged_in=False) -> Player:
        lname = name.lower()
        for player in self.shelf['players'].values():
            if player.name.lower() == lname:
                if not check_logged_in or player.logged_in:
                    return player

    @command("kick", role=Kick, doc="Kicks a player.",
             syntax=("[\"]player name[\"]", "[reason]"))
    def kick(self, data, protocol):
        name = data[0]
        try:
            reason = " ".join(data[1:])
        except IndexError:
            reason = "No reason given."

        p = self.get_player_by_name(" ".join(data))
        if p is not None:
            p.protocol.die()
            yield from self.factory.broadcast("%s has kicked %s. Reason: %s" % (
                protocol.player.name,
                p.name,
                reason))
        else:
            yield from protocol.send_message(
                "Couldn't find a player with name %s" % name)

    @command("ban", role=Ban, doc="Bans a user or an IP address.",
             syntax=("(ip | name)", "(reason)"))
    def ban(self, data, protocol):
        try:
            target, reason = data[0], " ".join(data[1:])
            if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", target):
                self.ban_by_ip(target, reason, protocol)
            else:
                self.ban_by_name(target, reason, protocol)
        except Exception as e:
            print(e)
            traceback.print_exc()
            yield from protocol.send_message("You must provide a name "
                                             "and a reason for banning.")

    def ban_by_ip(self, ip, reason, protocol):
        ban = IPBan(ip, reason, protocol.player.name)
        self.shelf['bans'][ip] = ban
        asyncio.Task(protocol.send_message("Banned IP: %s with reason: %s" % (
            ip, reason
        )))

    def ban_by_name(self, name, reason, protocol):
        p = self.get_player_by_name(name)
        if p is not None:
            self.ban_by_ip(p.ip, reason, protocol)
        else:
            asyncio.Task(protocol.send_message("Couldn't find a player by the "
                                               "name %s" % name))

    @asyncio.coroutine
    def add_or_get_planet(self, sector, location, planet, satellite,
                          **kwargs) -> Planet:
        a, x, y = location
        loc_string = "%s:%d:%d:%d:%d:%d" % (sector, a, x, y, planet, satellite)
        if loc_string in self.shelf['planets']:
            print("Returning already existing planet.")
            planet = self.shelf['planets'][loc_string]
        else:
            planet = Planet(sector=sector, location=location, planet=planet,
                            satellite=satellite)
            self.shelf['planets'][str(planet)] = planet
        return planet

    @command("list_bans", role=Ban, doc="Lists all active bans.")
    def list_bans(self, data, protocol):
        if len(self.shelf['bans'].keys()) == 0:
            yield from protocol.send_message("There are no active bans.")
        else:
            res = ["Active bans:"]
            for ban in self.shelf['bans'].values():
                res.append("IP: %(ip)s - "
                           "Reason: %(reason)s - "
                           "Banned by: %(banned_by)s" % ban.__dict__)
            yield from protocol.send_message("\n".join(res))