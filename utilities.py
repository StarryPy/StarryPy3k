"""
StarryPy Utilities

Provides a collection of commonly used utility objects, functions and classes
that can be utilized. Boilerplate = bad.

Original authors: AMorporkian
Updated for release: kharidiron
"""

import asyncio
import collections
import io
import re
import zlib
import dbm
from enum import IntEnum
from pathlib import Path
from types import FunctionType
from shelve import Shelf, _ClosedDict
from pickle import Pickler, Unpickler

path = Path(__file__).parent


# Enums

class State(IntEnum):
    DISCONNECTED = 0
    VERSION_SENT = 1
    CLIENT_CONNECT_RECEIVED = 2
    HANDSHAKE_CHALLENGE_SENT = 3
    HANDSHAKE_RESPONSE_RECEIVED = 4
    CONNECT_RESPONSE_SENT = 5
    CONNECTED = 6
    CONNECTED_WITH_HEARTBEAT = 7


class Direction(IntEnum):
    TO_CLIENT = 0
    TO_SERVER = 1


class WarpType(IntEnum):
    TO_WORLD = 1
    TO_PLAYER = 2
    TO_ALIAS = 3


class WarpWorldType(IntEnum):
    CELESTIAL_WORLD = 1
    PLAYER_WORLD = 2
    UNIQUE_WORLD = 3
    MISSION_WORLD = 4


class WarpAliasType(IntEnum):
    RETURN = 0
    ORBITED = 1
    SHIP = 2


class ChatSendMode(IntEnum):
    UNIVERSE = 0
    LOCAL = 1
    PARTY = 2


class ChatReceiveMode(IntEnum):
    LOCAL = 0
    PARTY = 1
    BROADCAST = 2
    WHISPER = 3
    COMMAND_RESULT = 4
    RADIO_MESSAGE = 5
    WORLD = 6


class SystemLocationType(IntEnum):
    SYSTEM = 0
    COORDINATE = 1
    ORBIT = 2
    UUID = 3
    LOCATION = 4


class DamageType(IntEnum):
    NO_DAMAGE = 0 # Assumed
    DAMAGE = 1
    IGNORES_DEF = 2
    KNOCKBACK = 3
    ENVIRONMENT = 4


class DamageHitType(IntEnum):
    NORMAL = 0
    STRONG = 1
    WEAK = 2
    SHIELD = 3
    KILL = 4

class EntityInteractionType(IntEnum):
    NOMINAL = 0
    OPEN_CONTAINER_UI = 1
    GO_PRONE = 2
    OPEN_CRAFTING_UI = 3
    OPEN_NPC_UI = 6
    OPEN_SAIL_UI = 7
    OPEN_TELEPORTER_UI = 8
    OPEN_SCRIPTED_UI = 10
    OPEN_SPECIAL_UI = 11
    OPEN_CREW_UI = 12


class EntitySpawnType(IntEnum):
    PLANT = 0
    OBJECT = 1
    VEHICLE = 2
    ITEM_DROP = 3
    PLANT_DROP = 4
    PROJECTILE = 5
    STAGEHAND = 6
    MONSTER = 7
    NPC = 8
    PLAYER = 9


# Useful things

def recursive_dictionary_update(d, u):
    """
    Given two dictionaries, update the first one with new values provided by
    the second. Works for nested dictionary sets.

    :param d: First Dictionary, to base off of.
    :param u: Second Dictionary, to provide updated values.
    :return: Dictionary. Merged dictionary with bias towards the second.
    """
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = recursive_dictionary_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


class DotDict(dict):
    """
    Custom dictionary format that allows member access by using dot notation:
    eg - dict.key.subkey
    """

    def __init__(self, d, **kwargs):
        super().__init__(**kwargs)
        for k, v in d.items():
            if isinstance(v, collections.Mapping):
                v = DotDict(v)
            self[k] = v

    def __getattr__(self, item):
        try:
            return super().__getitem__(item)
        except KeyError as e:
            raise AttributeError(str(e)) from None

    def __setattr__(self, key, value):
        if isinstance(value, collections.Mapping):
            value = DotDict(value)
        super().__setitem__(key, value)

    __delattr__ = dict.__delitem__


@asyncio.coroutine
def detect_overrides(cls, obj):
    """
    For each active plugin, check if it wield a packet hook. If it does, add
    make a not of it. Hand back all hooks for a specific packet type when done.
    """
    res = set()
    for key, value in cls.__dict__.items():
        if isinstance(value, classmethod):
            value = getattr(cls, key).__func__
        if isinstance(value, (FunctionType, classmethod)):
            meth = getattr(obj, key)
            if meth.__func__ is not value:
                res.add(key)
    return res


class BiDict(dict):
    """
    A case-insensitive bidirectional dictionary that supports integers.
    """
    def __init__(self, d, **kwargs):
        super().__init__(**kwargs)
        for k, v in d.items():
            self[k] = v

    def __setitem__(self, key, value):
        if key in self:
            del self[key]
        if value in self:
            del self[value]
        super().__setitem__(str(key), str(value))
        super().__setitem__(str(value), str(key))

    def __getitem__(self, item):
        if isinstance(item, int):
            key = str(item)
        else:
            key = item
        res = super().__getitem__(key)
        if res.isdigit():
            res = int(res)
        return res

    def __delitem__(self, key):
        super().__delitem__(self[key])
        super().__delitem__(key)


class AsyncBytesIO(io.BytesIO):
    """
    This class just wraps a normal BytesIO.read() in a coroutine to make it
    easier to interface with functions designed to work on coroutines without
    having to monkey around with a type check and extra futures.
    """
    @asyncio.coroutine
    def read(self, *args, **kwargs):
        return super().read(*args, **kwargs)


class Cupboard(Shelf):
    """
    Custom Shelf implementation that only pickles values at save-time.
    Increases save/load times, decreases get/set item times.
    More suitable for use as a savable dictionary.
    """
    def __init__(self, filename, flag='c', protocol=None, keyencoding='utf-8'):
        self.db = filename
        self.flag = flag
        self.dict = {}
        with dbm.open(self.db, self.flag) as db:
            for k in db.keys():
                v = io.BytesIO(db[k])
                self.dict[k] = Unpickler(v).load()
        Shelf.__init__(self, self.dict, protocol, False, keyencoding)

    def __getitem__(self, key):
        return self.dict[key.encode(self.keyencoding)]

    def __setitem__(self, key, value):
        self.dict[key.encode(self.keyencoding)] = value

    def __delitem__(self, key):
        del self.dict[key.encode(self.keyencoding)]

    def sync(self):
        res = {}
        with dbm.open(self.db, self.flag) as db:
            for k, v in self.dict.items():
                f = io.BytesIO()
                p = Pickler(f, protocol=self._protocol)
                p.dump(v)
                db[k] = f.getvalue()
            try:
                db.sync()
            except AttributeError:
                pass

    def close(self):
        try:
            self.sync()
        finally:
            try:
                self.dict = _ClosedDict()
            except:
                self.dict = None


@asyncio.coroutine
def read_vlq(bytestream):
    """
    Give a bytestream, extract the leading Variable Length Quantity (VLQ).

    We have to do this as a stream, since we don't know how long a VLQ is
    until we observe its end.
    """
    d = b""
    v = 0
    while True:
        tmp = yield from bytestream.readexactly(1)
        d += tmp
        tmp = ord(tmp)
        v <<= 7
        v |= tmp & 0x7f

        if tmp & 0x80 == 0:
            break
    return v, d


@asyncio.coroutine
def read_signed_vlq(reader):
    """
    Manipulate the read-in VLQ to account for signed-ness.
    """
    v, d = yield from read_vlq(reader)
    if (v & 1) == 0x00:
        return v >> 1, d
    else:
        return -((v >> 1) + 1), d


def extractor(*args):
    """
    Extracts quoted arguments and puts them as a single argument in the
    passed iterator.
    """
    # It's not elegant, but it's the best way to do it as far as I can tell.
    # My regex-fu isn't strong though, so if someone can come up with a
    # better way, great.
    x = re.split(r"(?:([^\"]\S*)|\"(.+?)(?<!\\)\")\s*", " ".join(*args))
    x = [word.replace("\\\"", "\"") if word is not None else None for word in x]
    return [x for x in filter(None, x)]


@asyncio.coroutine
def read_packet(reader, direction):
    """
    Given an interface to read from (reader) read the next packet that comes
    in. Determine the packet's type, decode its contents, and track the
    direction it is flowing. Store this all in a packet object, and return it
    for further processing down the line.

    :param reader: Stream from which to read the packet.
    :param direction: Destination for the packet (SERVER or CLIENT).
    :return: Dictionary. Contains both raw and decoded versions of the packet.
    """
    p = {}
    compressed = False

    packet_type = (yield from reader.readexactly(1))
    packet_size, packet_size_data = yield from read_signed_vlq(reader)
    if packet_size < 0:
        packet_size = abs(packet_size)
        compressed = True

    data = yield from reader.readexactly(packet_size)
    p['type'] = ord(packet_type)
    p['size'] = packet_size
    p['compressed'] = compressed
    if not compressed:
        p['data'] = data
    else:
        try:
            zobj = zlib.decompressobj()
            p['data'] = zobj.decompress(data)
        except zlib.error as e:
            raise asyncio.IncompleteReadError

    p['original_data'] = packet_type + packet_size_data + data
    p['direction'] = direction

    return p


def get_syntax(command, fn, command_prefix):
    """
    Read back the syntax argument provided in a command's wrapper. Return it
    in a printable format.

    :param command: Command being called.
    :param fn: Function which the command is wrapped around.
    :param command_prefix: Prefix used for commands in chat.
    :return: String. Syntax details of the target command.
    """
    return "Syntax: {}{} {!s}".format(
        command_prefix,
        command,
        fn.syntax)


def send_message(connection, *messages, **kwargs):
    """
    Sends a message to a connected player.

    :param connection: The connection to send the message to.
    :param messages: The message(s) to send.
    :return: A Future for the message(s) being sent.
    """
    return asyncio.ensure_future(connection.send_message(*messages, **kwargs))


def broadcast(connection, *messages, **kwargs):
    """
    Sends a message to all connected players.

    :param connection: The connection from which the message came.
    :param messages: The message(s) to send.
    :return: A Future for the message(s) being sent.
    """
    return asyncio.ensure_future(
        connection.factory.broadcast(*messages, **kwargs))


def link_plugin_if_available(self, plugin):
    if plugin in self.factory.plugin_manager.list_plugins().keys():
        self.logger.debug("{} available.".format(plugin))
        self.plugins[plugin] = \
            self.factory.plugin_manager.list_plugins()[plugin]
        return True
    else:
        return False


class Command:
    """
    Defines a decorator that encapsulates a chat command. Provides a common
    interface for all commands, including roles, documentation, usage syntax,
    and aliases.
    """
    def __init__(self, *aliases, role=None, roles=None, perm=None, doc=None,
                 syntax=None, priority=0):
        if syntax is None:
            syntax = ()
        if isinstance(syntax, str):
            syntax = (syntax,)
        if doc is None:
            doc = ""
        self.perm = perm
        self.syntax = syntax
        self.human_syntax = " ".join(syntax)
        self.doc = doc
        self.aliases = aliases
        self.priority = priority

    def __call__(self, f):
        """
        Whenever a command is called, its handling gets done here.

        :param f: The function the Command decorator is wrapping.
        :return: The now-wrapped command, with all the trappings.
        """
        def wrapped(s, data, connection):
            try:
                if self.perm is not None:
                    if not connection.player.perm_check(self.perm):
                        raise PermissionError
                return f(s, data, connection)
            except PermissionError:
                send_message(connection,
                             "You don't have permissions to do that.")

        wrapped._command = True
        wrapped._aliases = self.aliases
        wrapped.__doc__ = self.doc
        wrapped.perm = self.perm
        wrapped.syntax = self.human_syntax
        wrapped.priority = self.priority
        # f.roles = self.roles
        # f.syntax = self.human_syntax
        # f.__doc__ = self.doc
        return wrapped


class StorageMixin:
    """
    Convenience class for adding access to a player's server-based storage.
    """
    def __init__(self):
        self.storage = self.plugins.player_manager.get_storage(self)
