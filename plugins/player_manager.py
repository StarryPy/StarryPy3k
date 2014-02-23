import datetime
from enum import IntEnum
import pprint
import shelve
import asyncio

from base_plugin import BasePlugin
from server import StarryPyServer


class State(IntEnum):
    VERSION_SENT = 0
    CLIENT_CONNECT_RECEIVED = 1
    HANDSHAKE_CHALLENGE_SENT = 2
    HANDSHAKE_RESPONSE_RECEIVED = 3
    CONNECT_RESPONSE_SENT = 4
    CONNECTED = 5


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


class PlayerManager(BasePlugin):
    name = "player_manager"

    def activate(self):
        super().activate()
        self.shelf = shelve.open(self.config.config.player_db, writeback=True)
        self.sync()

    def sync(self):
        if 'players' not in self.shelf:
            self.shelf['players'] = {}
        if 'plugins' not in self.shelf:
            self.shelf['plugins'] = {}
        if 'planets' not in self.shelf:
            self.shelf['planets'] = {}

    def on_protocol_version(self, data, protocol):
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
            protocol.state = State.CONNECTED
        else:
            protocol.player.logged_in = False
            protocol.player.client_id = -1
        return True

    def on_client_connect(self, data, protocol: StarryPyServer):
        player = yield from self.add_or_get_player(**data['parsed'])
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
        else:
            protocol.player.on_ship = True
            location = "on ship"
        print(location)
        return True

    def deactivate(self):
        for player in self.shelf['players'].values():
            player.protocol = None
            player.logged_in = False
        print(self.shelf['players'])
        self.shelf.close()
        print("Closed the shelf")

    @asyncio.coroutine
    def add_or_get_player(self, uuid, name='', last_seen=None, roles=None,
                          logged_in=True, protocol=None, client_id=-1,
                          ip="0.0.0.0",
                          planet='', on_ship=True, muted=False,
                          **kwargs) -> Player:
        if str(uuid) in self.shelf:
            return self.shelf['players'][str(uuid)]
        else:
            new_player = Player(uuid, name, last_seen, roles, logged_in,
                                protocol, client_id, ip, planet, on_ship, muted)
            self.shelf['players'][str(uuid)] = new_player
            return new_player

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

