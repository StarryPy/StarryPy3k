import asyncio
from concurrent.futures import ThreadPoolExecutor
from enum import IntEnum
import zlib
import sys

from configuration_manager import ConfigurationManager
from data_parser import ChatReceived
from packets import packets
from pparser import build_packet
from plugin_manager import PluginManager
from utilities import read_signed_vlq, path


class State(IntEnum):
    VERSION_SENT = 0
    CLIENT_CONNECT_RECEIVED = 1
    HANDSHAKE_CHALLENGE_SENT = 2
    HANDSHAKE_RESPONSE_RECEIVED = 3
    CONNECT_RESPONSE_SENT = 4
    CONNECTED = 5
    CONNECTED_WITH_HEARTBEAT = 6


@asyncio.coroutine
def read_packet(reader, direction):
    p = {}
    compressed = False

    packet_type = yield from reader.readexactly(1)

    packet_size, packet_size_data = yield from read_signed_vlq(reader)
    if packet_size < 0:
        packet_size = abs(packet_size)
        compressed = True
    data = yield from reader.read(packet_size)
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


class StarryPyServer:
    def __init__(self, reader, writer, factory):
        self._reader = reader
        self._writer = writer
        self._client_reader = None
        self._client_writer = None
        self.factory = factory
        self._client_loop_future = None
        self._server_loop_future = asyncio.Task(self.server_loop())
        self.state = None

    @asyncio.coroutine
    def server_loop(self):
        (self._client_reader,
         self._client_writer) = yield from asyncio.open_connection("127.0.0.1",
                                                                   21024)
        self._client_loop_future = asyncio.Task(self.client_loop())
        while True:
            try:
                packet = yield from read_packet(self._reader, "Client")
            except asyncio.streams.IncompleteReadError:
                if hasattr(self, 'player'):
                    print("Connection broken from player named:" % self.player)
                else:
                    print("Connection broken from unknown player.")
                break
            try:
                if (yield from self.check_plugins(packet)):
                    yield from self.write_client(packet)
            except (ConnectionResetError, ConnectionAbortedError):
                print("Returning")
                return
        self.die()
        return True

    @asyncio.coroutine
    def client_loop(self):
        while True:
            try:
                packet = yield from read_packet(self._client_reader, "Server")
            except asyncio.streams.IncompleteReadError:
                self.die()
                return
            except TypeError:
                break
            try:
                send_flag = yield from self.check_plugins(packet)
                if send_flag:
                    yield from self.write(packet)
            except (ConnectionResetError, ConnectionAbortedError):
                return

    @asyncio.coroutine
    def send_message(self, message, *, world="", client_id=0, name="",
                     channel=0):
        if self.state == State.CONNECTED_WITH_HEARTBEAT:
            chat_packet = ChatReceived.build(
                {"message": message,
                 "world": world,
                 "client_id": client_id,
                 "name": name,
                 "channel": channel})

            to_send = build_packet(4, chat_packet)
            yield from self.raw_write(to_send)

    @asyncio.coroutine
    def write(self, packet):
        self._writer.write(packet['original_data'])
        yield from self._writer.drain()

    @asyncio.coroutine
    def raw_write(self, data):
        self._writer.write(data)
        yield from self._writer.drain()

    @asyncio.coroutine
    def write_client(self, packet):
        self._client_writer.write(packet['original_data'])
        yield from self._writer.drain()

    def die(self):
        self._writer.close()
        self._client_writer.close()
        self._server_loop_future.cancel()
        self._client_loop_future.cancel()
        self.factory.remove(self)

    @asyncio.coroutine
    def check_plugins(self, packet):
        return (yield from self.factory.plugin_manager.do(
            self,
            packets[packet['type']],
            packet))

    def __del__(self):
        try:
            self.die()
        except:
            pass


class ServerFactory:
    def __init__(self):
        try:
            self.protocols = []
            self.configuration_manager = ConfigurationManager()
            self.configuration_manager.load_config(
                path / 'config' / 'config.json',
                default=True)
            self.plugin_manager = PluginManager(self.configuration_manager,
                                                factory=self)
            self.plugin_manager.load_from_path(
                path / self.configuration_manager.config.plugin_path)
            self.plugin_manager.resolve_dependencies()
            self.plugin_manager.activate_all()
            asyncio.Task(self.plugin_manager.get_overrides())
        except Exception as e:
            print("Exception encountered during server startup.")
            print(e)

            loop.stop()
            sys.exit()

    @asyncio.coroutine
    def broadcast(self, message, *, world="", name="", channel=0, client_id=0):
        for protocol in self.protocols:
            try:
                yield from protocol.send_message(message,
                                                 world=world,
                                                 name=name,
                                                 channel=channel,
                                                 client_id=client_id)
            except ConnectionError:
                continue

    def remove(self, protocol):
        self.protocols.remove(protocol)

    def __call__(self, reader, writer):
        server = StarryPyServer(reader, writer, factory=self)
        self.protocols.append(server)
        print(self.protocols)


@asyncio.coroutine
def start_server():
    server_factory = ServerFactory()
    yield from asyncio.start_server(server_factory, '0.0.0.0', 21025)
    return server_factory


if __name__ == "__main__":
    with open("commit_count") as f:
        ver = f.read()
    print("Running commit", ver)
    loop = asyncio.get_event_loop()
    #loop.set_debug(True)  # Removed in commit to avoid errors.
    loop.executor = ThreadPoolExecutor(max_workers=100)
    loop.set_default_executor(loop.executor)
    server_factory = asyncio.Task(start_server())

    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        print("Exiting")
    finally:
        server_factory.result().plugin_manager.deactivate_all()
        print("Running commit", ver)
