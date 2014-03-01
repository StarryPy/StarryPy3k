from collections import OrderedDict
import functools
from io import BytesIO
import io
import struct
import binascii

from utilities import DotDict


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


import copy


def make_hash(o):
    """
    Makes a hash from a dictionary, list, tuple or set to any level, that contains
    only other hashable types (including any lists, tuples, sets, and
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
        d = string.peek()
        big_enough = len(d) > 1
        if big_enough:
            _c = cacher.retrieve(cls, d)
            if _c is not None:
                return _c
        if ctx is None:
            ctx = {}
        res = cls.parse_stream(string, ctx)
        if big_enough:
            cacher.set(cls, res, d)
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
    def _parse(cls, stream: BytesIO, ctx: OrderedDict) -> int:
        value = 0
        while True:
            try:
                tmp = ord(stream.read(1))
                value = (value << 7) | (tmp & 0x7f)
                if tmp & 0x80 == 0:
                    break
            except TypeError:  # If the stream is empty.
                break
        return value

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
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        v = VLQ.parse(stream, ctx)
        if (v & 1) == 0x00:
            return v >> 1
        else:
            return -((v >> 1) + 1)

    @classmethod
    def _build(cls, obj, ctx):
        value = abs(obj * 2)
        if obj < 0:
            value -= 1
        return VLQ.build(value, ctx)


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
        length = VLQ.parse(stream, ctx)
        return stream.read(length)

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return VLQ.build(len(obj), ctx) + obj


class StarString(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        data = StarByteArray.parse(stream, ctx)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data

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
        return bool(stream.read(1))

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return int(obj)


class BDouble(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">d", stream.read(8))

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        return struct.pack(">d", obj)


class UUID(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        if Flag.parse(stream, ctx):
            return binascii.hexlify(stream.read(16))
        else:
            return None

    @classmethod
    def _build(cls, obj, ctx: OrderedDotDict):
        res = b''
        if obj:
            res += Flag.build(True)
            res += obj
        else:
            res += Flag.build(False)
        return res


class VariantVariant(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        l = VLQ.parse(stream, ctx)
        return [Variant.parse(stream, ctx) for _ in range(l)]


class DictVariant(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        l = VLQ.parse(stream, ctx)
        c = {}
        for _ in range(l):
            key = StarString.parse(stream, ctx)
            value = Variant.parse(stream, ctx)
            if isinstance(value, bytes):
                value = value.decode('ascii')
            c[key] = value
        return c


class Variant(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        x = Byte.parse(stream, ctx)
        if x == 1:
            return None
        elif x == 2:
            return BDouble.parse(stream, ctx)
        elif x == 3:
            return Flag.parse(stream, ctx)
        elif x == 4:
            return SignedVLQ.parse(stream, ctx)
        elif x == 5:
            return StarString.parse(stream, ctx)
        elif x == 6:
            return VariantVariant.parse(stream, ctx)
        elif x == 7:
            return DictVariant.parse(stream, ctx)


class ClientConnect(Struct):
    asset_digest = StarByteArray
    claim = Variant
    uuid = UUID
    name = StarString
    species = StarString
    shipworld = StarByteArray
    account = StarString


class ChatReceived(Struct):
    channel = Byte
    world = StarString
    client_id = UBInt32
    name = StarString
    message = StarString


class WarpCommand(Struct):
    warp_type = UBInt32
    sector = StarString
    x = SBInt32
    y = SBInt32
    z = SBInt32
    planet = SBInt32
    satellite = SBInt32
    player = StarString


class SpawnCoordinates(Struct):
    x = BFloat32
    y = BFloat32


class WorldStart(Struct):
    planet = Variant
    world_structure = Variant
    sky_structure = StarByteArray
    weather_data = StarByteArray
    spawn = SpawnCoordinates
    world_properties = Variant
    client_id = UBInt32
    local_interpolation = Flag


class GiveItem(Struct):
    name = StarString
    count = VLQ
    variant_type = Byte
    extra = Byte
    #description = StarString


class ConnectResponse(Struct):
    success = Flag
    client_id = VLQ


class ChatSent(Struct):
    message = StarString
    channel = Byte


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


class EntityCreate(GreedyArray):
    entity_type = Byte
    entity = StarString
    entity_id = SignedVLQ


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

