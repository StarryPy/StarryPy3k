from collections import OrderedDict
import functools
from io import BytesIO
import io
import struct

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
            if self.retrieve_count % 1000 == 0:
                print(self.set_count, self.retrieve_count)
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
        print("Preparing", name)
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
            k = cacher.get_key(d)
            _c = cacher.retrieve(cls, d)
            if _c is not None:
                #print("Returning cached item")
                return _c
        if ctx is None:
            ctx = OrderedDotDict()
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
    def build(cls, obj):
        fake_stream = BytesIO()
        ctx = OrderedDotDict()
        if cls._struct_fields:
            for name, struct in cls._struct_fields:
                ctx[name] = struct._build(obj, ctx)
            res = ctx
        else:
            res = cls._build(obj, fake_stream, ctx)
        fake_stream.seek(0)
        return fake_stream.read()

    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        raise NotImplementedError

    @classmethod
    def _build(cls, obj, stream: BytesIO, ctx: OrderedDict):
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
    def _build(cls, obj, stream: BytesIO, ctx: OrderedDict):
        result = bytearray()
        value = int(obj)
        if obj == 0:
            result = [b'\x00']
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
        return stream.write(result)


class SignedVLQ(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        v = VLQ.parse(stream, ctx)
        if (v & 1) == 0x00:
            return v >> 1
        else:
            return -((v >> 1) + 1)


class UBInt32(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">L", stream.read(4))


class SBInt32(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">l", stream.read(4))


class BFloat32(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">f", stream.read(4))


class StarByteArray(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        length = VLQ.parse(stream, ctx)
        return stream.read(length)


class StarString(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        data = StarByteArray.parse(stream, ctx)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data


class Byte(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return int.from_bytes(stream.read(1), byteorder="big", signed=False)


class Flag(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return bool(stream.read(1))


class BDouble(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        return struct.unpack(">d", stream.read(8))


class UUID(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        if Flag.parse(stream, ctx):
            return stream.read(16)
        else:
            return None


class VariantVariant(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        l = VLQ.parse(stream, ctx)
        return [Variant.parse_stream(stream, ctx) for _ in range(l)]


class DictVariant(Struct):
    @classmethod
    def _parse(cls, stream: BytesIO, ctx: OrderedDict):
        l = VLQ.parse(stream, ctx)
        c = OrderedDotDict()
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


class WorldCoordinate(Struct):
    sector = StarString
    x = SBInt32
    y = SBInt32
    z = SBInt32
    planet = SBInt32
    satellite = SBInt32


class WarpCommand(Struct):
    warp_type = UBInt32
    coordinates = WorldCoordinate
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
    description = StarString


class ConnectResponse(Struct):
    success = Flag
    client_id = VLQ


class ChatSent(Struct):
    message = StarString


class GreedyArray(Struct):
    @classmethod
    def parse_stream(cls, stream, ctx=None):
        bcls = cls.mro()[0]
        res = []
        _l = -1
        while True:
            l = len(stream.peek())
            if l == 0 or _l == l: break
            res.append(super().parse_stream(stream, ctx))
            _l = l
        return res


class EntityCreate(GreedyArray):
    entity_type = Byte
    entity = StarString
    entity_id = SignedVLQ