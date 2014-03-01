import asyncio
import traceback

from configuration_manager import ConfigurationManager
from data_parser import *


parse_map = {
    0: None,
    1: ConnectResponse,
    2: None,
    3: None,
    4: ChatReceived,
    5: None,
    6: None,
    7: ClientConnect,
    8: None,
    9: None,
    10: WarpCommand,
    11: ChatSent,
    12: None,
    13: None,
    14: WorldStart,
    15: None,
    16: None,
    17: None,
    18: None,
    19: None,
    20: None,
    21: None,
    22: None,
    23: None,
    24: None,
    25: None,
    26: None,
    27: None,
    28: None,
    29: None,
    30: None,
    31: None,
    32: None,
    33: None,
    34: None,
    35: None,
    36: None,
    37: None,
    38: None,
    39: None,
    40: None,
    41: None,
    42: None,
    43: None,
    44: None,
    45: None,
    46: None,
    47: None,
    48: None
}


class PacketParser:
    def __init__(self, config: ConfigurationManager):
        self._cache = {}
        self._reaper = asyncio.Task(self._reap())
        self._debug = asyncio.Task(self._debug_counter())
        self.config = config
        self.loop = asyncio.get_event_loop()

    @asyncio.coroutine
    def parse(self, packet):
        try:
            if packet['size'] >= self.config.config['min_cache_size']:
                packet['hash'] = hash(packet['original_data'])
                if packet['hash'] in self._cache:
                    packet['parsed'] = self._cache[packet['hash']]['parsed']
                else:
                    packet = yield from self._parse_and_cache_packet(packet)
            else:
                packet = yield from self._parse_packet(packet)
        except Exception as e:
            print("Error during parsing.")
            print(traceback.print_exc())
        finally:
            return packet

    @asyncio.coroutine
    def _reap(self):
        while True:
            yield from asyncio.sleep(self.config.config['packet_reap_time'])
            for h, cached_packet in self._cache.items():
                cached_packet.count -= 1
                if cached_packet.count <= 0:
                    del (self._cache[h])

    @asyncio.coroutine
    def _debug_counter(self):
        while True:
            yield from asyncio.sleep(60)

    @asyncio.coroutine
    def _parse_and_cache_packet(self, packet):
        packet = yield from self._parse_packet(packet)
        self._cache[packet['hash']] = packet
        return packet

    @asyncio.coroutine
    def _parse_packet(self, packet):
        res = parse_map[packet['type']]
        if res is None:
            packet['parsed'] = {}
        else:
            #packet['parsed'] = yield from self.loop.run_in_executor(
            #    self.loop.executor, res.parse, packet['data'])
            # Removed due to issues with testers. Need to evaluate what's going
            # on.
            packet['parsed'] = res.parse(packet['data'])
        return packet

    def __del__(self):
        self._reaper.cancel()


class CachedPacket:
    def __init__(self, packet):
        self.count = 1
        self.packet = packet


def build_packet(id, data, compressed=False):
    return BasePacket.build({"id": id, "data": data,
                             "compressed": compressed})
