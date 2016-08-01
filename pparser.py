import asyncio
import traceback

from configuration_manager import ConfigurationManager
from data_parser import *

parse_map = {
    0: ProtocolRequest,
    1: ProtocolResponse,
    2: ServerDisconnect,
    3: ConnectSuccess,
    4: ConnectFailure,
    5: None,
    6: ChatReceived,
    7: None,
    8: None,
    9: PlayerWarpResult,
    10: ClientConnect,
    11: ClientDisconnectRequest,
    12: None,
    13: PlayerWarp,
    14: FlyShip,
    15: ChatSent,
    16: None,
    17: ClientContextUpdate,
    18: WorldStart,
    19: WorldStop,
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
    37: EntityInteract,
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
    48: None,
    49: None,
    50: None,
    51: StepUpdate
}


class PacketParser:
    """
    Object for handling the parsing and caching of packets.
    """
    def __init__(self, config: ConfigurationManager):
        self._cache = {}
        self._reaper = asyncio.ensure_future(self._reap())
        self.config = config
        self.loop = asyncio.get_event_loop()

    @asyncio.coroutine
    def parse(self, packet):
        """
        Given a packet preped packet from the stream, parse it down to its
        parts. First check if the packet is one we've seen before; if it is,
        pull its parsed form from the cache, and run with that. Otherwise,
        pass it to the appropriate parser for parsing.

        :param packet: Packet with header information parsed.
        :return: Fully parsed packet.
        """
        try:
            if packet["size"] >= self.config.config["min_cache_size"]:
                packet["hash"] = hash(packet["original_data"])
                if packet["hash"] in self._cache:
                    self._cache[packet["hash"]].count += 1
                    packet["parsed"] = self._cache[packet["hash"]].packet[
                        "parsed"]
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
        """
        Prune packets from the cache that are not being used, and that are
        older than the "packet_reap_time".

        :return: None.
        """
        while True:
            yield from asyncio.sleep(self.config.config["packet_reap_time"])
            for h, cached_packet in self._cache.copy().items():
                cached_packet.count -= 1
                if cached_packet.count <= 0:
                    del (self._cache[h])

    @asyncio.coroutine
    def _parse_and_cache_packet(self, packet):
        """
        Take a new packet and pass it to the parser. Once we get it back,
        make a copy of it to the cache.

        :param packet: Packet with header information parsed.
        :return: Fully parsed packet.
        """
        packet = yield from self._parse_packet(packet)
        self._cache[packet["hash"]] = CachedPacket(packet=packet)
        return packet

    @asyncio.coroutine
    def _parse_packet(self, packet):
        """
        Parse the packet by giving it to the appropriate parser.

        :param packet: Packet with header information parsed.
        :return: Fully parsed packet.
        """
        res = parse_map[packet["type"]]
        if res is None:
            packet["parsed"] = {}
        else:
            #packet["parsed"] = yield from self.loop.run_in_executor(
            #    self.loop.executor, res.parse, packet["data"])
            # Removed due to issues with testers. Need to evaluate what's going
            # on.
            packet["parsed"] = res.parse(packet["data"])
        return packet

    def __del__(self):
        self._reaper.cancel()


class CachedPacket:
    """
    Prototype for cached packets. Keep track of how often it is used,
    as well as the full packet's contents.
    """
    def __init__(self, packet):
        self.count = 1
        self.packet = packet


def build_packet(packet_id, data, compressed=False):
    """
    Convenience method for building a packet.

    :param packet_id: ID value of packet.
    :param data: Contents of packet.
    :param compressed: Whether or not to compress the packet.
    :return: Built packet object.
    """
    return BasePacket.build({"id": packet_id,
                             "data": data,
                             "compressed": compressed})
