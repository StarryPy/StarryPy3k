import asyncio
from configuration_manager import ConfigurationManager
from packets import packets
from plugin_manager import PluginManager
from utilities import path


@asyncio.coroutine
def read_packet(reader, direction):
    p = {}
    compressed = False

    packet_type = yield from reader.readexactly(1)

    packet_size, packet_size_data = yield from read_svlq(reader)
    if packet_size < 0:
        packet_size = abs(packet_size)
        compressed = True
    data = yield from reader.read(packet_size)
    p['type'] = ord(packet_type)
    p['size'] = packet_size
    p['compressed'] = compressed
    p['data'] = data
    p['original_data'] = packet_type + packet_size_data + data
    p['direction'] = direction

    return p


@asyncio.coroutine
def read_vlq(reader):
    d = b""
    v = 0
    while True:
        tmp = yield from reader.read(1)
        d += tmp
        tmp = ord(tmp)
        v <<= 7
        v |= tmp & 0x7f

        if tmp & 0x80 == 0:
            break
    return v, d


@asyncio.coroutine
def read_svlq(reader):
    v, d = yield from read_vlq(reader)
    if (v & 1) == 0x00:
        return v >> 1, d
    else:
        return -((v >> 1) + 1), d


class StarboundClient:
    def __init__(self, server):
        self._server = server
        self.reader = None
        self.writer = None
        self.connected = asyncio.Task(self.connect_to_server())
        self.is_connected = False

    @asyncio.coroutine
    def connect_to_server(self):
        self.reader, self.writer = yield from asyncio.open_connection(
            "localhost", 21024)
        asyncio.Task(self._loop())
        self.is_connected = True

    @asyncio.coroutine
    def _loop(self):
        while True:
            try:
                packet = yield from read_packet(self.reader, "Server")
            except asyncio.streams.IncompleteReadError:
                self._server.die()
                return
            except TypeError:
                break
            try:
                yield from self._server.write(packet)
            except (ConnectionResetError, ConnectionAbortedError):
                return

    @asyncio.coroutine
    def write(self, data):
        self.writer.write(data['original_data'])
        yield from self.writer.drain()

    def die(self):
        if self.is_connected:
            self.writer.close()
            print("Closed connection to Starbound server.")


class StarryPyServer:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.factory = None
        self._client = StarboundClient(self)
        asyncio.Task(self._loop())

    @asyncio.coroutine
    def _loop(self):
        yield from self._client.connected
        while True:
            try:
                packet = yield from read_packet(self.reader, "Client")
            except asyncio.streams.IncompleteReadError:
                print("Connection broken")
                break
            try:
                send_flag = yield from self.check_plugins(packet)
                if send_flag:
                    yield from self._client.write(packet)
            except (ConnectionResetError, ConnectionAbortedError):
                return
        self._client.die()
        return True

    @asyncio.coroutine
    def write(self, packet):
        self.writer.write(packet['original_data'])
        yield from self.writer.drain()

    def die(self):
        self.writer.close()
        self.factory.remove(self)

    @asyncio.coroutine
    def check_plugins(self, packet):
        results = yield from self.factory.plugin_manager.do(
            packets[packet['type']],
            packet)
        return results


class ServerFactory:
    def __init__(self):
        self.protocols = []
        self.configuration_manager = ConfigurationManager()
        self.configuration_manager.load_config(path / 'config' / 'config.json',
                                               default=True)
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_from_path(
            path / self.configuration_manager.config.plugin_path)
        self.plugin_manager.resolve_dependencies()
        self.plugin_manager.activate_all()
        asyncio.Task(self.plugin_manager.get_overrides())

    def remove(self, protocol):
        self.protocols.remove(protocol)

    def __call__(self, reader, writer, *args, **kwargs):
        server = StarryPyServer(reader, writer)
        server.factory = self
        self.protocols.append(server)
        print(self.protocols)


@asyncio.coroutine
def start_server():
    serverf = ServerFactory()
    yield from asyncio.start_server(serverf, '127.0.0.1', 21025)


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        asyncio.Task(start_server())
        loop.run_forever()
    finally:
        print("Done")