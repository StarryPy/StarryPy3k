import asyncio
from enum import IntEnum
import io
from pathlib import Path
import collections
from types import FunctionType
import re
import zlib
#from server import logger

path = Path(__file__).parent


class State(IntEnum):
    VERSION_SENT = 0
    CLIENT_CONNECT_RECEIVED = 1
    HANDSHAKE_CHALLENGE_SENT = 2
    HANDSHAKE_RESPONSE_RECEIVED = 3
    CONNECT_RESPONSE_SENT = 4
    CONNECTED = 5
    CONNECTED_WITH_HEARTBEAT = 6


class Direction(IntEnum):
    TO_STARBOUND_CLIENT = 0
    TO_STARBOUND_SERVER = 1


def recursive_dictionary_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = recursive_dictionary_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


class DotDict(dict):
    def __init__(self, d):
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
    res = set()
    for key, value in cls.__dict__.items():
        if isinstance(value, classmethod):
            value = getattr(cls, key).__func__
        if isinstance(value, (FunctionType, classmethod)):
            meth = getattr(obj, key)
            if not meth.__func__ is value:
                res.add(key)
    return res


class BiDict(dict):
    """A case-insensitive bidirectional dictionary that supports integers."""

    def __init__(self, d, **kwargs):
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

    @asyncio.coroutine
    def read(self, *args, **kwargs):
        return super().read(*args, **kwargs)


@asyncio.coroutine
def read_vlq(bytestream):
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
    v, d = yield from read_vlq(reader)
    if (v & 1) == 0x00:
        return v >> 1, d
    else:
        return -((v >> 1) + 1), d


def extractor(*args):
    # This extracts quoted arguments and puts them as a single argument in the
    # passed iterator. It's not elegant, but it's the best way to do it
    # as far as I can tell. My regex-fu isn't strong though,
    # so if someone can come up with a better way, great.
    x = re.split(r"(?:([^\"]\S*)|\"(.+?)\")\s*", " ".join(*args))
    return [x for x in filter(None, x)]


@asyncio.coroutine
def read_packet(reader, direction):
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
        zobj = zlib.decompressobj()
        p['data'] = zobj.decompress(data)

    p['original_data'] = packet_type + packet_size_data + data
    p['direction'] = direction

    return p


def syntax(command, fn, command_prefix):
    return "Syntax: %s%s %s" % (
        command_prefix,
        command,
        fn.syntax)


def send_message(protocol, *messages):
    """
    Sends a message to a player on a protocol.
    :param protocol: The protocol to send the message to.
    :param messages: The message(s) to send.
    :return: A future for tthe message sending.
    """
    return asyncio.Task(protocol.send_message(*messages))


class Command:
    """
    Defines a decorator that encapsulates a command in StarryPy3k
    """

    def __init__(self, *aliases, role=None, roles=None, doc=None, syntax=None):
        if syntax is None:
            syntax = ()
        if isinstance(syntax, str):
            syntax = (syntax,)
        if roles is None:
            roles = set()
        elif not isinstance(roles, set):
            roles = {x for x in roles}
        if role is not None:
            roles.add(set)
        if doc is None:
            doc = ""
        self.roles = roles
        self.syntax = syntax
        self.human_syntax = " ".join(syntax)
        self.doc = doc
        self.aliases = aliases

    def __call__(self, f):
        def wrapped(s, data, protocol):
            try:
                for role in self.roles:
                    if role not in protocol.player.roles:
                        raise PermissionError
                f.syntax = self.human_syntax
                f.__doc__ = self.doc
                return f(s, data, protocol)
            except PermissionError:
                send_message(protocol,
                             "You don't have permissions to do that.")

        wrapped._command = True
        wrapped._aliases = self.aliases
        wrapped.__doc__ = self.doc
        wrapped.roles = self.roles
        return wrapped
