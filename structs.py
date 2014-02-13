import asyncio

from construct.core import _read_stream, _write_stream


class SignedVLQ(Construct):
    def _parse(self, stream, context):
        value = 0
        while True:
            tmp = ord(_read_stream(stream, 1))
            value = (value << 7) | (tmp & 0x7f)
            if tmp & 0x80 == 0:
                break
        if (value & 1) == 0x00:
            return value >> 1
        else:
            return -((value >> 1) + 1)

    def _build(self, obj, stream, context):
        value = abs(obj * 2)
        if obj < 0:
            value -= 1
        VLQ("")._build(value, stream, context)


class VLQ(Construct):
    def _parse(self, stream, context):
        value = 0
        while True:
            tmp = ord(_read_stream(stream, 1))
            value = (value << 7) | (tmp & 0x7f)
            if tmp & 0x80 == 0:
                break
        return value

    def _build(self, obj, stream, context):
        result = bytearray()
        value = int(obj)
        if obj == 0:
            _write_stream(stream, 1, chr(0))
            return
        while value > 0:
            byte = value & 0x7f
            value >>= 7
            if value != 0:
                byte |= 0x80
            result.insert(0, byte)
        if len(result) > 1:
            result[0] |= 0x80
            result[-1] ^= 0x80
        _write_stream(stream, len(result), "".join([chr(x) for x in result]))


star_string = lambda name="star_string": StarStringAdapter(
    star_string_struct(name))


class StarStringAdapter(Adapter):
    def _encode(self, obj, context):
        return Container(length=len(obj), string=obj)

    def _decode(self, obj, context):
        return obj.string


class Joiner(Adapter):
    def _encode(self, obj, context):
        return obj

    def _decode(self, obj, context):
        return "".join(obj)


star_string_struct = lambda name="star_string": Struct(name,
                                                       VLQ("length"),
                                                       String("string", lambda
                                                           ctx: ctx.length)
)


class VariantVariant(Construct):
    def _parse(self, stream, context):
        l = VLQ("").parse_stream(stream)
        return [Variant("").parse_stream(stream) for _ in range(l)]


class DictVariant(Construct):
    def _parse(self, stream, context):
        l = VLQ("").parse_stream(stream)
        c = {}
        for x in range(l):
            key = star_string("").parse_stream(stream)
            value = Variant("").parse_stream(stream)
            c[key] = value
        return c


class Variant(Construct):
    def _parse(self, stream, context):
        x = Byte("").parse_stream(stream)
        if x == 1:
            return None
        elif x == 2:
            return BFloat64("").parse_stream(stream)
        elif x == 3:
            return Flag("").parse_stream(stream)
        elif x == 4:
            return SignedVLQ("").parse_stream(stream)
        elif x == 5:
            return star_string().parse_stream(stream)
        elif x == 6:
            return VariantVariant("").parse_stream(stream)
        elif x == 7:
            return DictVariant("").parse_stream(stream)


class StarByteArray(Construct):
    def _parse(self, stream, context):
        l = VLQ("").parse_stream(stream)
        return _read_stream(stream, l)

    def _build(self, obj, stream, context):
        _write_stream(stream, len(obj), VLQ("").build(len(obj)) + obj)


@asyncio.coroutine
def read_vlq(bytestream):
    d = b""
    v = 0
    while True:
        tmp = yield from bytestream.read(1)
        d += tmp
        tmp = ord(tmp)
        v <<= 7
        v |= tmp & 0x7f

        if tmp & 0x80 == 0:
            break
    return v, d


@asyncio.coroutine
def read_signed_vlq(reader):
    v, d = yield from read_vlq(reader)
    if (v & 1) == 0x00:
        return v >> 1, d
    else:
        return -((v >> 1) + 1), d


from construct import *
from enum import IntEnum


class Direction(IntEnum):
    CLIENT = 0
    SERVER = 1


class Packets(IntEnum):
    PROTOCOL_VERSION = 0
    CONNECT_RESPONSE = 1
    SERVER_DISCONNECT = 2
    HANDSHAKE_CHALLENGE = 3
    CHAT_RECEIVED = 4
    UNIVERSE_TIME_UPDATE = 5
    CLIENT_CONNECT = 6
    CLIENT_DISCONNECT = 7
    HANDSHAKE_RESPONSE = 8
    WARP_COMMAND = 9
    CHAT_SENT = 10
    CLIENT_CONTEXT_UPDATE = 11
    WORLD_START = 12
    WORLD_STOP = 13
    TILE_ARRAY_UPDATE = 14
    TILE_UPDATE = 15
    TILE_LIQUID_UPDATE = 16
    TILE_DAMAGE_UPDATE = 17
    TILE_MODIFICATION_FAILURE = 18
    GIVE_ITEM = 19
    SWAP_IN_CONTAINER_RESULT = 20
    ENVIRONMENT_UPDATE = 21
    ENTITY_INTERACT_RESULT = 22
    MODIFY_TILE_LIST = 23
    DAMAGE_TILE = 24
    DAMAGE_TILE_GROUP = 25
    REQUEST_DROP = 26
    SPAWN_ENTITY = 27
    ENTITY_INTERACT = 28
    CONNECT_WIRE = 29
    DISCONNECT_ALL_WIRES = 30
    OPEN_CONTAINER = 31
    CLOSE_CONTAINER = 32
    SWAP_IN_CONTAINER = 33
    ITEM_APPLY_IN_CONTAINER = 34
    START_CRAFTING_IN_CONTAINER = 35
    STOP_CRAFTING_IN_CONTAINER = 36
    BURN_CONTAINER = 37
    CLEAR_CONTAINER = 38
    WORLD_UPDATE = 39
    ENTITY_CREATE = 40
    ENTITY_UPDATE = 41
    ENTITY_DESTROY = 42
    DAMAGE_NOTIFICATION = 43
    STATUS_EFFECT_REQUEST = 44
    UPDATE_WORLD_PROPERTIES = 45
    HEARTBEAT = 46


class EntityType(IntEnum):
    END = -1
    PLAYER = 0
    MONSTER = 1
    OBJECT = 2
    ITEMDROP = 3
    PROJECTILE = 4
    PLANT = 5
    PLANTDROP = 6
    EFFECT = 7


class PacketOutOfOrder(Exception):
    pass


class HexAdapter(Adapter):
    def _encode(self, obj, context):
        return obj.decode(
            "hex")  # The code seems backward, but I assure you it's correct.

    def _decode(self, obj, context):
        return obj.encode("hex")


handshake_response = lambda name="handshake_response": Struct(name,
                                                              star_string(
                                                                  "claim_response"),
                                                              star_string(
                                                                  "hash"))

universe_time_update = lambda name="universe_time": Struct(name,
                                                           VLQ("unknown"))

packet = lambda name="base_packet": Struct(name,
                                           Byte("id"),
                                           SignedVLQ("payload_size"),
                                           Field("data", lambda ctx: abs(
                                               ctx.payload_size)))

start_packet = lambda name="interim_packet": Struct(name,
                                                    Byte("id"),
                                                    SignedVLQ("payload_size"))

protocol_version = lambda name="protocol_version": Struct(name,
                                                          UBInt32(
                                                              "server_build"))

connection = lambda name="connection": Struct(name,
                                              GreedyRange(
                                                  Byte("compressed_data")))

handshake_challenge = lambda name="handshake_challenge": Struct(name,
                                                                star_string(
                                                                    "claim_message"),
                                                                star_string(
                                                                    "salt"),
                                                                SBInt32(
                                                                    "round_count"))

connect_response = lambda name="connect_response": Struct(name,
                                                          Flag("success"),
                                                          VLQ("client_id"),
                                                          star_string(
                                                              "reject_reason"))

chat_received = lambda name="chat_received": Struct(name,
                                                    Byte("chat_channel"),
                                                    star_string("world"),
                                                    UBInt32("client_id"),
                                                    star_string("name"),
                                                    star_string("message"))

chat_sent = lambda name="chat_sent": Struct(name,
                                            star_string("message"),
                                            Padding(1))

client_connect = lambda name="client_connect": Struct(name,
                                                      VLQ(
                                                          "asset_digest_length"),
                                                      String("asset_digest",
                                                             lambda
                                                                 ctx: ctx.asset_digest_length),
                                                      Variant("claim"),
                                                      Flag("uuid_exists"),
                                                      If(lambda
                                                             ctx: ctx.uuid_exists is True,
                                                         HexAdapter(
                                                             Field("uuid", 16))
                                                      ),
                                                      star_string("name"),
                                                      star_string("species"),
                                                      VLQ("shipworld_length"),
                                                      Field("shipworld", lambda
                                                          ctx: ctx.shipworld_length),
                                                      star_string("account"))

client_disconnect = lambda name="client_disconnect": Struct(name,
                                                            Byte("data"))

world_coordinate = lambda name="world_coordinate": Struct(name,
                                                          star_string("sector"),
                                                          SBInt32("x"),
                                                          SBInt32("y"),
                                                          SBInt32("z"),
                                                          SBInt32("planet"),
                                                          SBInt32("satellite"))

warp_command = lambda name="warp_command": Struct(name,
                                                  Enum(UBInt32("warp_type"),
                                                       MOVE_SHIP=1,
                                                       WARP_UP=2,
                                                       WARP_OTHER_SHIP=3,
                                                       WARP_DOWN=4,
                                                       WARP_HOME=5),
                                                  world_coordinate(),
                                                  star_string("player"))

warp_command_write = lambda t, sector=u'', x=0, y=0, z=0, planet=0, satellite=0,
                            player=u'': warp_command().build(
    Container(
        warp_type=t,
        world_coordinate=Container(
            sector=sector,
            x=x,
            y=y,
            z=z,
            planet=planet,
            satellite=satellite
        ),
        player=player))

world_start = lambda name="world_start": Struct(name,
                                                Variant("planet"),
                                                Variant("world_structure"),
                                                StarByteArray("sky_structure"),
                                                StarByteArray("weather_data"),
                                                BFloat32("spawn_x"),
                                                BFloat32("spawn_y"),
                                                Variant("world_properties"),
                                                UBInt32("client_id"),
                                                Flag("local_interpolation"))

world_stop = lambda name="world_stop": Struct(name,
                                              star_string("status"))

give_item = lambda name="give_item": Struct(name,
                                            star_string("name"),
                                            VLQ("count"),
                                            Byte("variant_type"),
                                            star_string("description"))

give_item_write = lambda name, count: give_item().build(Container(name=name,
                                                                  count=count,
                                                                  variant_type=7,
                                                                  description=''))

update_world_properties = lambda name="world_properties": Struct(name,
                                                                 UBInt8(
                                                                     "count"),
                                                                 Array(lambda
                                                                           ctx: ctx.count,
                                                                       Struct(
                                                                           "properties",
                                                                           star_string(
                                                                               "key"),
                                                                           Variant(
                                                                               "value"))))

update_world_properties_write = lambda \
    dictionary: update_world_properties().build(
    Container(
        count=len(dictionary),
        properties=[Container(key=k, value=Container(type="SVLQ", data=v)) for
                    k, v in dictionary.items()]))

entity_create = Struct("entity_create",
                       GreedyRange(
                           Struct("entity",
                                  Byte("entity_type"),
                                  VLQ("entity_size"),
                                  String("entity", lambda ctx: ctx.entity_size),
                                  SignedVLQ("entity_id")
                           )))
projectile = DictVariant("projectile")