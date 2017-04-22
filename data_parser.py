import binascii
import copy
import functools
import io
import struct
import _parser
from collections import OrderedDict
from io import BytesIO

from utilities import DotDict, WarpType, WarpWorldType


#
## Packet Helpers
#

class NotFound:
    pass


class StructCacher:
    def __init__(self):
        self.cache = {}
        self.set_count = 0
        self.retrieve_count = 0

    def get_key(self, string, *args, **kwargs):
        return hash(string)

    def retrieve(self, cls, string, *args, **kwargs):
        key = self.get_key(string)
        try:
            c = self.cache[cls.__name__][key]
            self.retrieve_count += 1
            return c
        except KeyError:
            return None

    def set(self, cls, result, string):
        key = self.get_key(string)
        self.set_key(cls.__name__, key, result)

    def set_key(self, cls, key, result):
        self.set_count += 1
        self.cache[cls][key] = result


cacher = StructCacher()


def composed(*decs):
    def deco(f):
        for dec in reversed(decs):
            f = dec(f)
        return f

    return deco


def make_hash(o):
    """
    Makes a hash from a dictionary, list, tuple or set to any level, that
    contains only other hashable types (including any lists, tuples, sets, and
    dictionaries).
    """

    if isinstance(o, (set, tuple, list)):
        return tuple([make_hash(e) for e in o])
    elif not isinstance(o, dict):
        return hash(o)

    new_o = copy.deepcopy(o)
    for k, v in new_o.items():
        new_o[k] = make_hash(v)

    return hash(tuple(frozenset(sorted(new_o.items()))))


class OrderedDotDict(OrderedDict, DotDict):
    def __hash__(self):
        return make_hash(self)


cm = composed(classmethod, functools.lru_cache())


class MetaStruct(type):
    @classmethod
    def __prepare__(mcs, name, bases):
        return OrderedDict({'_struct_fields': [], '_cache': {}})

    def __new__(mcs, name, bases, clsdict):
        for key, value in clsdict.items():
            if isinstance(value, mcs):
                clsdict['_struct_fields'].append((key, value))
        c = type.__new__(mcs, name, bases, clsdict)
        cacher.cache[c.__name__] = {}
        return c


class Struct(metaclass=MetaStruct):
    @classmethod
    def parse(cls, string, ctx=None):
        if not isinstance(string, io.BufferedReader):
            if not isinstance(string, BytesIO):
                if isinstance(string, str):
                    string = bytes(string, encoding="utf-8")
                string = BytesIO(string)
            string = io.BufferedReader(string)

        # FIXME: Stream caching appears to be causing a parsing issue.
        # Disabling for now...
        # d = string.peek()
        # big_enough = len(d) > 1
        # if big_enough:
        #     _c = cacher.retrieve(cls, d)
        #     if _c is not None:
        #         return _c

        if ctx is None:
            ctx = {}
        res = cls.parse_stream(string, ctx)
        # if big_enough:
        #     cacher.set(cls, res, d)
        return res

    @classmethod
    def parse_stream(cls, stream, ctx=None):
        if cls._struct_fields:
            for name, struct in cls._struct_fields:
                try:
                    ctx[name] = struct.parse(stream, ctx=ctx)
                except:
                    print("Context at time of failure:", ctx)
                    raise
            res = ctx
        else:
            res = cls._parse(stream, ctx=ctx)

        return res

    @classmethod
    def build(cls, obj, res=None, ctx=None):
        if res is None:
            res = b''
        if ctx is None:
            ctx = {}
        if cls._struct_fields:
            for name, struct in cls._struct_fields:
                try:
                    if name in obj:
                        res += struct.build(obj[name], ctx=ctx)
                    else:
                        res += struct.build(None, ctx=ctx)
                except:
                    print("Context at time of failure:", ctx)
                    raise
        else:
            res = cls._build(obj, ctx=ctx)
        return res

    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        raise NotImplementedError

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        raise NotImplementedError


class VLQ(Struct):
    @classmethod
    # def _parse(cls, stream: BytesIO, ctx: OrderedDict) -> int:
    #     value = 0
    #     while True:
    #         try:
    #             tmp = ord(stream.read(1))
    #             value = (value << 7) | (tmp & 0x7f)
    #             if tmp & 0x80 == 0:
    #                 break
    #         except TypeError:  # If the stream is empty.
    #             break
    #     return value
    def _parse(cls, stream: BytesIO, ctx: OrderedDict) -> int:
        return _parser.parse_vlq(stream)

    @classmethod
    def _build(cls, obj, ctx):
        result = bytearray()
        value = int(obj)
        if obj == 0:
            result = bytearray(b'\x00')
        else:
            while value > 0:
                byte = value & 0x7f
                value >>= 7
                if value != 0:
                    byte |= 0x80
                result.insert(0, byte)
            if len(result) > 1:
                result[0] |= 0x80
                result[-1] ^= 0x80
        return bytes(result)


class SignedVLQ(Struct):
    @classmethod
    # def _parse(cls, stream: BytesIO, ctx: OrderedDict):
    #     v = VLQ.parse(stream, ctx)
    #     if (v & 1) == 0x00:
    #         return v >> 1
    #     else:
    #         return -((v >> 1) + 1)
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return _parser.parse_svlq(stream)

    @classmethod
    def _build(cls, obj, ctx):
        value = abs(obj * 2)
        if obj < 0:
            value -= 1
        return VLQ.build(value, ctx)


class UBInt16(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">H", stream.read(2))[0]

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">H", obj)


class SBInt16(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">h", stream.read(2))[0]

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">h", obj)


class UBInt32(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">L", stream.read(4))[0]

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">L", obj)


class SBInt32(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">l", stream.read(4))[0]

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">l", obj)

class UBInt64(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">Q", stream.read(8))[0]

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">Q", obj)


class SBInt64(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">q", stream.read(8))[0]

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">q", obj)


class BFloat32(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">f", stream.read(4))[0]

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">f", obj)


class StarByteArray(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        # length = VLQ.parse(stream, ctx)
        # return stream.read(length)
        return _parser.parse_starbytearray(stream)

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return VLQ.build(len(obj), ctx) + obj


class StarString(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        # data = StarByteArray.parse(stream, ctx)
        # try:
        #     return data.decode("utf-8")
        # except UnicodeDecodeError:
        #     return data
        return _parser.parse_starstring(stream)

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return StarByteArray.build(obj.encode("utf-8"), ctx)


class Byte(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return int.from_bytes(stream.read(1), byteorder="big", signed=False)

    @classmethod
    def _build(cls, obj: int, ctx: OrderedDotDict):
        return obj.to_bytes(1, byteorder="big", signed=False)


class Flag(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">?", stream.read(1))[0]

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">?", obj)


class BDouble(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">d", stream.read(8))[0]

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">d", obj)


class UUID(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return binascii.hexlify(stream.read(16))

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        res = b''
        res += obj
        return res


class VariantVariant(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        # l = VLQ.parse(stream, ctx)
        # return [Variant.parse(stream, ctx) for _ in range(l)]
        return _parser.parse_variant_variant(stream)


class DictVariant(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        # l = VLQ.parse(stream, ctx)
        # c = {}
        # for _ in range(l):
        #     key = StarString.parse(stream, ctx)
        #     value = Variant.parse(stream, ctx)
        #     if isinstance(value, bytes):
        #         try:
        #             value = value.decode('utf-8')
        #         except UnicodeDecodeError:
        #             pass
        #     c[key] = value
        # return c
        return _parser.parse_dict_variant(stream)


class Variant(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        # x = Byte.parse(stream, ctx)
        # if x == 1:
        #     return None
        # elif x == 2:
        #     return BDouble.parse(stream, ctx)
        # elif x == 3:
        #     return Flag.parse(stream, ctx)
        # elif x == 4:
        #     return SignedVLQ.parse(stream, ctx)
        # elif x == 5:
        #     return StarString.parse(stream, ctx)
        # elif x == 6:
        #     return VariantVariant.parse(stream, ctx)
        # elif x == 7:
        #     return DictVariant.parse(stream, ctx)
        return _parser.parse_variant(stream)


class StringSet(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        l = VLQ.parse(stream, ctx)
        c = []
        for _ in range(l):
            value = StarString.parse(stream, ctx)
            if isinstance(value, bytes):
                try:
                    value = value.decode('utf-8')
                except UnicodeDecodeError:
                    pass
            c.append(value)
        return c


class CelestialCoordinates(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        world_x = SBInt32.parse(stream, ctx)
        world_y = SBInt32.parse(stream, ctx)
        world_z = SBInt32.parse(stream, ctx)
        world_planet = SBInt32.parse(stream, ctx)
        world_satellite = SBInt32.parse(stream, ctx)
        return {"x": world_x,
                "y": world_y,
                "z": world_z,
                "planet": world_planet,
                "satellite": world_satellite}


class WarpAction(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        warp_type = Byte.parse(stream, ctx)
        d = {"warp_type": warp_type}

        if warp_type == WarpType.TO_WORLD:
            # warp_type 1
            world_id = Byte.parse(stream, ctx)
            d["world_id"] = world_id

            if world_id == WarpWorldType.CELESTIAL_WORLD:
                # world_id 1
                d["celestial_coordinates"] = CelestialCoordinates.parse(stream,
                                                                        ctx)
                flag = Byte.parse(stream, ctx)
                if flag == 1:
                    d["teleporter"] = StarString.parse(stream, ctx)
            elif world_id == WarpWorldType.PLAYER_WORLD:
                # world_id 2
                d["ship_id"] = UUID.parse(stream, ctx)
                flag = Byte.parse(stream, ctx)
                if flag == 2:
                    d["pos_x"] = UBInt32.parse(stream, ctx)
                    d["pos_y"] = UBInt32.parse(stream, ctx)
            elif world_id == WarpWorldType.UNIQUE_WORLD:
                # world_id 3
                d["world_name"] = StarString.parse(stream, ctx)
                d["instance_flag"] = Byte.parse(stream, ctx)
                d["instance_id"] = UUID.parse(stream, ctx)
                d["teleporter_flag"] = Byte.parse(stream, ctx)
                d["teleporter"] = StarString.parse(stream, ctx)
            elif world_id == WarpWorldType.MISSION_WORLD:
                # world_id 4
                d["world_name"] = StarString.parse(stream, ctx)

        elif warp_type == WarpType.TO_PLAYER:
            # warp_type 2
            d["player_id"] = UUID.parse(stream, ctx)

        elif warp_type == WarpType.TO_ALIAS:
            # warp_type 3
            d["alias_id"] = SBInt32.parse(stream, ctx)

        return d

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        res = b''
        res += Byte.build(obj["warp_type"])

        if obj["warp_type"] == WarpType.TO_WORLD:
            res += Byte.build(obj["world_id"])

            if obj["world_id"] == WarpWorldType.CELESTIAL_WORLD:
                res += CelestialCoordinates.build(obj["celestial_coordinates"])
                if obj["flag"] == 1:
                    res += Byte.build(1)
                    res += StarString.build(obj["teleporter"])
            elif obj["world_id"] == WarpWorldType.PLAYER_WORLD:
                res += UUID.build(binascii.unhexlify(obj["ship_id"]))
                if obj["flag"] == 2:
                    res += UBInt32.build(obj["pos_x"])
                    res += UBInt32.build(obj["pos_y"])
                res += Byte.build(0)
            elif obj["world_id"] == WarpWorldType.UNIQUE_WORLD:
                res += StarString.build(obj["world_name"])
                res += Byte.build(obj["instance_flag"])
                res += UUID.build(binascii.unhexlify(obj["instance_id"]))
                res += Byte.build(obj["teleporter_flag"])
                res += StarString.build(obj["teleporter"])
                res += Byte.build(0)
            elif obj["world_id"] == WarpWorldType.MISSION_WORLD:
                res += StarString.build(obj["world_name"])
                res += Byte.build(0)

        elif obj["warp_type"] == WarpType.TO_PLAYER:
            res += UUID.build(binascii.unhexlify(obj["player_id"]))

        elif obj["warp_type"] == WarpType.TO_ALIAS:
            res += SBInt32.build(obj["alias_id"])

        return res


class ChatHeader(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        mode = Byte.parse(stream, ctx)
        if mode == 0 or mode == 1:
            channel = StarString.parse(stream, ctx)
            client_id = UBInt16.parse(stream, ctx)
        else:
            channel = ""
            _ = Byte.parse(stream, ctx)
            client_id = UBInt16.parse(stream, ctx)
        return {"mode": mode,
                "channel": channel,
                "client_id": client_id}

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        res = b''
        res += Byte.build(obj["mode"])
        if obj["mode"] == 0:
            res += StarString.build(obj["channel"])
            res += UBInt16.build(obj["client_id"])
        else:
            res += Byte.build(0)
            res += UBInt16.build(obj["client_id"])
        return res


class ClientContextSet(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        d = {}
        total_length = VLQ.parse(stream, ctx)
        d["total_length"] = total_length
        if total_length < 100:
            sub_length = VLQ.parse(stream, ctx)
        l = VLQ.parse(stream, ctx)
        d["number_of_sets"] = l
        for i in range(l):
            d[i] = Variant.parse(stream, ctx)
        return d


class WorldChunks(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        l = VLQ.parse(stream, ctx)
        d = {}
        c = []
        n = 0
        for _ in range(l):
            v1 = VLQ.parse(stream, ctx)
            c1 = stream.read(v1)
            sep = Byte.parse(stream, ctx)
            v2 = VLQ.parse(stream, ctx)
            c2 = stream.read(v2)
            c.append((n, v1, c1, sep, v2, c2))
            n += 1
        d['length'] = l
        d['content'] = c
        return d


class GreedyArray(Struct):
    @classmethod
    def parse_stream(cls, stream, ctx=None):
        bcls = cls.mro()[0]
        res = []
        _l = -1
        try:
            while True:
                l = len(stream.peek())
                if l == 0 or _l == l:
                    break
                res.append(super().parse(stream, ctx))
                _l = l
        finally:
            return res


class SpawnCoordinates(Struct):
    x = BFloat32
    y = BFloat32

#
## Packet implementations
#

class ProtocolRequest(Struct):
    """packet type: 0 """
    client_build = UBInt32


class ProtocolResponse(Struct):
    """packet type 1 """
    server_response = Byte


class ServerDisconnect(Struct):
    """packet type: 2 """
    reason = StarString


class ConnectSuccess(Struct):
    """packet type: 3 """
    client_id = VLQ
    server_uuid = UUID
    planet_orbital_levels = SBInt32
    satellite_orbital_levels = SBInt32
    chunk_size = SBInt32
    xy_min = SBInt32
    xy_max = SBInt32
    z_min = SBInt32
    z_max = SBInt32


class ConnectFailure(Struct):
    """packet type: 4 """
    reason = StarString


class HandshakeChallenge(Struct):
    """packet type: 5 """
    salt = StarByteArray


class ChatReceived(Struct):
    """packet type: 6 """
    header = ChatHeader
    name = StarString
    junk = Byte
    message = StarString


class UniverseTimeUpdate(Struct):
    """packet type: 7 """
    timestamp = VLQ
    # Questionable implementation... upstream says 'double'


class PlayerWarpResult(Struct):
    """packet type: 9 """
    warp_success = Flag
    warp_action = WarpAction


class ClientConnect(Struct):
    """packet type: 11 """
    asset_digest = StarByteArray
    allow_mismatch = Flag
    uuid = UUID
    name = StarString
    species = StarString
    shipdata = WorldChunks
    ship_level = UBInt32
    max_fuel = UBInt32
    crew_size = UBInt32
    # Junk means, I don't know what this value represents... <_<
    junk2 = UBInt32
    ship_upgrades = StringSet
    # account really does appear to be a StringSet despite always being a single string.
    account = StringSet


class ClientDisconnectRequest(Struct):
    """packet type: 12 """
    request = Byte


class PlayerWarp(Struct):
    """packet type: 14 """
    warp_action = WarpAction


class FlyShip(Struct):
    """packet type: 15 """
    world_x = SBInt32
    world_y = SBInt32
    world_z = SBInt32
    world_planet = SBInt32
    world_satellite = SBInt32


class ChatSent(Struct):
    """packet type: 16 """
    message = StarString
    send_mode = Byte


class ClientContextUpdate(Struct):
    """packet type: 18 """
    contexts = ClientContextSet
    # Incomplete implementation


class WorldStart(Struct):
    """packet type: 19 """
    template_data = Variant
    sky_data = StarByteArray
    weather_data = StarByteArray
    spawn = SpawnCoordinates
    respawn = SpawnCoordinates
    respawn_in_world = Flag
    #dungeonid = StarString
    world_properties = Variant
    client_id = UBInt16
    local_interpolation = Flag
    # Incomplete implementation


class WorldStop(Struct):
    """packet type: 20 """
    reason = StarString


class GiveItem(Struct):
    """packet type: 29 """
    name = StarString
    count = VLQ
    variant_type = Byte
    description = StarString


class EntityInteractResult(Struct):
    """packet type: 31 """
    interaction_type = UBInt32
    target_id = UBInt32
    entity_data = Variant
    request_id = UUID


class ModifyTileList(Struct):
    """packet type: 35 """
    brush_size = VLQ
    # Incomplete implementation


class SpawnEntity(Struct):
    """packet type: 39 """
    spawn_type = Byte
    payload_size = VLQ
    payload = StarString
    payload_value = VLQ
    # Incomplete implementation


class EntityInteract(Struct):
    """packet type: 40 """
    source_id = UBInt32
    source_x = BFloat32
    source_y = BFloat32
    target_id = UBInt32
    target_x = BFloat32
    target_y = BFloat32
    request_id = UUID


class EntityMessage(Struct):
    """packet type: 51"""
    @classmethod
    def _parse(cls, stream, ctx=None):
        res = {}
        res['target_unique'] = Flag.parse(stream, ctx)
        if res['target_unique']:
            res['unique_id'] = StarString.parse(stream, ctx)
        else:
            res['target_id'] = SBInt32.parse(stream, ctx)
        res['message_name'] = StarString.parse(stream, ctx)
        res['message_args'] = VariantVariant.parse(stream, ctx)
        res['message_uuid'] = UUID.parse(stream, ctx)
        res['unknown'] = UBInt16.parse(stream, ctx) # Appears to always be 0
        return res

    def _build(cls, obj, ctx=None):
        res = b''
        res += Flag.build(obj['target_unique'])
        if obj['target_unique']:
            res += StarString.build(obj['unique_id'])
        else:
            res += SBInt32.build(obj['target_id'])
        res += StarString.build(obj['message_name'])
        res += VariantVariant.build(obj['message_args'])
        res += UUID.build(obj['message_uuid'])
        res += UBInt16.build(obj['unknown'])
        return res


class EntityMessageResponse(Struct):
    success_level = Byte # 1 is a failure, 2 is a success
    response = Variant
    message_uuid = UUID

class StepUpdate(Struct):
    """packet type: 54"""
    heartbeat = VLQ



class BasePacket(Struct):
    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        res = b''
        res += Byte.build(obj['id'], ctx)
        v = len(obj['data'])
        if 'compressed' in ctx and ctx['compressed']:
            v = -abs(v)
        res += SignedVLQ.build(v)
        if not isinstance(obj['data'], bytes):
            obj['data'] = bytes(obj['data'].encode("utf-8"))
        res += obj['data']
        return res
