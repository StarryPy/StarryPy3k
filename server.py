import asyncio
import logging
import sys

from configuration_manager import ConfigurationManager
from data_parser import ChatReceived
from packets import packets
from pparser import build_packet
from plugin_manager import PluginManager
from utilities import path, read_packet, State, Direction


class StarryPyServer:
    def __init__(self, reader, writer, factory):
        logger.warning("Initializing protocol.")
        self._reader = reader
        self._writer = writer
        self._client_reader = None
        self._client_writer = None
        self.factory = factory
        self._client_loop_future = None
        self._server_loop_future = asyncio.Task(self.server_loop())
        self.state = None
        self._alive = True
        self.client_ip = reader._transport.get_extra_info('peername')[0]
        self._server_read_future = None
        self._client_read_future = None
        self._server_write_future = None
        self._client_write_future = None
        logger.info("Received connection from %s", self.client_ip)

    @asyncio.coroutine
    def server_loop(self):
        (self._client_reader,
         self._client_writer) = yield from asyncio.open_connection("127.0.0.1",
                                                                   21024)
        self._client_loop_future = asyncio.Task(self.client_loop())
        try:
            while True:
                packet = yield from read_packet(self._reader,
                                                Direction.TO_STARBOUND_SERVER)
                if (yield from self.check_plugins(packet)):
                    yield from self.write_client(packet)
        finally:
            self.die()

    @asyncio.coroutine
    def client_loop(self):
        try:
            while True:
                packet = yield from read_packet(self._client_reader,
                                                Direction.TO_STARBOUND_CLIENT)
                send_flag = yield from self.check_plugins(packet)
                if send_flag:
                    yield from self.write(packet)
        finally:
            self.die()

    @asyncio.coroutine
    def send_message(self, message, *messages, world="", client_id=0, name="",
                     channel=0):
        if messages:
            for m in messages:
                yield from self.send_message(m,
                                             world=world,
                                             client_id=client_id,
                                             name=name,
                                             channel=channel)
        if "\n" in message:
            for m in message.splitlines():
                yield from self.send_message(m,
                                             world=world,
                                             client_id=client_id,
                                             name=name,
                                             channel=channel)
            return

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
    def client_raw_write(self, data):
        self._client_writer.write(data)
        yield from self._client_writer.drain()

    @asyncio.coroutine
    def write_client(self, packet):
        yield from self.client_raw_write(packet['original_data'])

    def die(self):
        if self._alive:
            if hasattr(self, "player"):
                logger.info("Removing player %s.", self.player.name)
            else:
                logger.info("Removing unknown player.")
            self._writer.close()
            self._client_writer.close()
            self._server_loop_future.cancel()
            self._client_loop_future.cancel()
            self.factory.remove(self)
            self._alive = False

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
            logger.exception("Error during server startup.", exc_info=True)

            loop.stop()
            sys.exit()

    @asyncio.coroutine
    def broadcast(self, messages, *, world="", name="", channel=0,
                  client_id=0):
        for protocol in self.protocols:
            try:
                yield from protocol.send_message(messages,
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

    def kill_all(self):
        for protocol in self.protocols:
            protocol.die()


@asyncio.coroutine
def start_server():
    server_factory = ServerFactory()
    try:
        yield from asyncio.start_server(server_factory, '0.0.0.0', 21025)
    except OSError as e:
        logger.exception("Error while trying to start server.")
        logger.exception(e)
        sys.exit(1)
    return server_factory


if __name__ == "__main__":
    DEBUG = False
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    aiologger = logging.getLogger("asyncio")
    aiologger.setLevel(logging.DEBUG)
    logger = logging.getLogger('starrypy')
    logger.setLevel(logging.DEBUG)
    if DEBUG:
        fh_d = logging.FileHandler("debug.log")
        fh_d.setLevel(logging.DEBUG)
        fh_d.setFormatter(formatter)
        aiologger.addHandler(fh_d)
        logger.addHandler(fh_d)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    aiologger.addHandler(ch)
    logger.addHandler(ch)
    with open("commit_count") as f:
        ver = f.read()
    logger.info("Running commit %s", ver)
    loop = asyncio.get_event_loop()
    #loop.set_debug(True)  # Removed in commit to avoid errors.
    #loop.executor = ThreadPoolExecutor(max_workers=100)
    #loop.set_default_executor(loop.executor)
    logger.info("Starting server")
    server_factory = asyncio.Task(start_server())

    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.warning("Exiting")
    finally:
        server_factory.result().kill_all()
        server_factory.result().plugin_manager.deactivate_all()
        loop.stop()
        loop.close()
        logger.warning("Running commit %s", ver)
