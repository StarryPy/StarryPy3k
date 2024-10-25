import asyncio
import logging
import sys
import signal
import traceback

from configuration_manager import ConfigurationManager
from data_parser import ChatReceived
from packets import packets
from pparser import build_packet
from plugin_manager import PluginManager
from utilities import path, read_packet, State, Direction, ChatReceiveMode
from zstd_reader import ZstdFrameReader
from zstd_writer import ZstdFrameWriter


DEBUG = True

if DEBUG:
    loglevel = logging.DEBUG
else:
    loglevel = logging.INFO

logger = logging.getLogger('starrypy')
logger.setLevel(loglevel)

class SwitchToZstdException(Exception):
    pass

class StarryPyServer:
    """
    Primary server class. Handles all the things.
    """
    def __init__(self, reader, writer, config, factory):
        logger.debug("Initializing connection.")
        self._reader = ZstdFrameReader(reader, Direction.TO_SERVER) # read packets from client
        self._writer = ZstdFrameWriter(writer) # writes packets to client
        self._client_reader = None # read packets from server (acting as client)
        self._client_writer = None # write packets to server
        self.factory = factory
        self._client_loop_future = asyncio.create_task(self.client_loop())
        self._server_loop_future = asyncio.create_task(self.server_loop())
        self.state = None
        self._alive = True
        self.config = config.config
        self.client_ip = reader._transport.get_extra_info('peername')[0]
        self._server_read_future = None
        self._client_read_future = None
        self._server_write_future = None
        self._client_write_future = None
        logger.info("Received connection from {}".format(self.client_ip))

    def start_zstd(self):
        self._reader.enable_zstd()
        self._client_reader.enable_zstd()
        self._writer.enable_zstd(skip_packets=1) # skip this packet
        self._client_writer.enable_zstd()
        logger.info("Switched to zstd")


    async def server_loop(self):
        """
        Main server loop. As clients connect to the proxy, pass the
        connection on to the upstream server and bind it to a 'connection'.
        Start sniffing all packets as they fly by.

        :return:
        """

        # wait until client is available
        while self._client_writer is None:
            await asyncio.sleep(0.1)

        try:
            while True:
                packet = await read_packet(self._reader,
                                            Direction.TO_SERVER)
                # Break in case of emergencies:
                # if packet['type'] not in [17, 40, 41, 43, 48, 51]:
                #    logger.debug('c->s  {}'.format(packet['type']))

                if (await self.check_plugins(packet)):
                    await self.write_client(packet)
        except asyncio.IncompleteReadError:
            # Pass on these errors. These occur when a player disconnects badly
            pass
        except asyncio.CancelledError:
            logger.warning("Connection ended abruptly.")
        except Exception as err:
            logger.error("Server loop exception occurred:"
                         "{}: {}".format(err.__class__.__name__, err))
            logger.error("Error details and traceback: {}".format(traceback.format_exc()))
        finally:
            logger.info("Server loop ended.")
            self.die()

    async def client_loop(self):
        """
        Main client loop. Sniff packets originating from the server and bound
        for the clients.

        :return:
        """
        (reader, writer) = await asyncio.open_connection(self.config['upstream_host'],
                                               self.config['upstream_port'])
        
        self._client_reader = ZstdFrameReader(reader, Direction.TO_CLIENT)
        self._client_writer = ZstdFrameWriter(writer)

        try:
            while True:
                packet = await read_packet(self._client_reader,
                                                Direction.TO_CLIENT)
                # Break in case of emergencies:
                # if packet['type'] not in [7, 17, 23, 27, 31, 43, 49, 51]:
                #     logger.debug('s->c  {}'.format(packet['type']))

                send_flag = await self.check_plugins(packet)
                if send_flag:
                    await self.write(packet)
        except asyncio.IncompleteReadError:
            logger.error("IncompleteReadError: Connection ended abruptly.")
        finally:
            self.die()

    async def send_message(self, message, *messages, mode=ChatReceiveMode.BROADCAST,
                     client_id=0, name="", channel=""):
        """
        Convenience function to send chat messages to the client. Note that
        this does *not* send messages to the server at large; broadcast
        should be used for messages to all clients, or manually constructed
        chat messages otherwise.

        :param message: message text
        :param messages: used if there are more that one message to be sent
        :param client_id: who sent the message
        :param name:
        :param channel:
        :param mode:
        :return:
        """
        header = {"mode": mode, "channel": channel, "client_id": client_id}
        try:
            if messages:
                for m in messages:
                    await self.send_message(m,
                                                 mode=mode,
                                                 client_id=client_id,
                                                 name=name,
                                                 channel=channel)
            if "\n" in message:
                for m in message.splitlines():
                    await self.send_message(m,
                                                 mode=mode,
                                                 client_id=client_id,
                                                 name=name,
                                                 channel=channel)
                return

            if self.state is not None and self.state >= State.CONNECTED:
                chat_packet = ChatReceived.build({"message": message,
                                                  "name": name,
                                                  "junk": 0,
                                                  "header": header})
                to_send = build_packet(packets['chat_received'], chat_packet)
                await self.raw_write(to_send)
        except Exception as err:
            logger.exception("Error while trying to send message.")
            logger.exception(err)

    async def raw_write(self, data):
        self._writer.write(data)
        await self._writer.drain()

    async def client_raw_write(self, data):
        self._client_writer.write(data)
        await self._client_writer.drain()

    async def write(self, packet):
        self._writer.write(packet['original_data'])
        await self._writer.drain()

    async def write_client(self, packet):
        await self.client_raw_write(packet['original_data'])

    def die(self):
        """
        Handle closeout from player disconnecting.

        :return: Null.
        """
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
            self.state = State.DISCONNECTED
            self._alive = False

    async def check_plugins(self, packet):
        return (await self.factory.plugin_manager.do(
            self,
            packets[packet['type']],
            packet))

    def __del__(self):
        try:
            self.die()
        except Exception:
            logger.error("An error occurred while a player was disconnecting.")


class ServerFactory:
    def __init__(self):
        try:
            self.connections = []
            self.configuration_manager = ConfigurationManager()
            self.configuration_manager.load_config(
                path / 'config' / 'config.json',
                default=True)
            self.plugin_manager = PluginManager(self.configuration_manager,
                                                factory=self)
            self.plugin_manager.load_from_path(
                path / self.configuration_manager.config.plugin_path)
            self.plugin_manager.resolve_dependencies()
        except Exception as err:
            logger.exception("Error during server startup.", exc_info=True)
            raise err
        
    async def start_plugins(self):
        await self.plugin_manager.activate_all()

    async def broadcast(self, messages, *, mode=ChatReceiveMode.RADIO_MESSAGE,
                  **kwargs):
        """
        Send a message to all connected clients.

        :param messages: Message(s) to be sent.
        :param mode: Mode bit of message.
        :return: Null.
        """
        for connection in self.connections:
            try:
                await connection.send_message(
                    messages,
                    mode=mode
                )
            except Exception as err:
                logger.exception("Error while trying to broadcast.")
                logger.exception(err)
                continue

    def remove(self, connection):
        """
        Remove a single connection.

        :param connection: Connection to be removed.
        :return: Null.
        """
        self.connections.remove(connection)

    def __call__(self, reader, writer):
        """
        Whenever a client connects, ping the server factory to start
        handling it.

        :param reader: Reader transport socket.
        :param writer: Writer transport socket.
        :return: Null.
        """
        server = StarryPyServer(reader, writer, self.configuration_manager,
                                factory=self)
        self.connections.append(server)
        logger.debug("New connection established.")

    def kill_all(self):
        """
        Drop all connections.

        :return: Null.
        """
        logger.debug("Dropping all connections.")
        for connection in self.connections:
            connection.die()


async def start_server() -> tuple[ServerFactory, asyncio.AbstractServer]:
    """
    Main function for kicking off the server factory.

    :return: Server factory object.
    """
    _server_factory = ServerFactory()
    await _server_factory.start_plugins()
    config = _server_factory.configuration_manager.config
    try:
        srv = await asyncio.start_server(_server_factory,
                                        port=config['listen_port'])
    except OSError as err:
        logger.error("Error while trying to start server.")
        logger.error("{}".format(str(err)))
        sys.exit(1)
    return (_server_factory, srv)


async def main():
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s # %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    aiologger = logging.getLogger("asyncio")
    aiologger.setLevel(loglevel)
    if DEBUG:
        fh_d = logging.FileHandler("config/debug.log")
        fh_d.setLevel(loglevel)
        fh_d.setFormatter(formatter)
        aiologger.addHandler(fh_d)
        logger.addHandler(fh_d)
    ch = logging.StreamHandler()
    ch.setLevel(loglevel)
    ch.setFormatter(formatter)
    aiologger.addHandler(ch)
    logger.addHandler(ch)

    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    loop = asyncio.get_event_loop()
    loop.set_debug(False)  # Removed in commit to avoid errors.

    logger.info("Starting server")

    (server_factory, srv) = await start_server()

    try:
        await srv.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.warning("Exiting")
    except Exception as e:
        logger.warning('An exception occurred, exiting: {}'.format(e))
    finally:
        logger.info("Exiting StarryPy. Shutting down all plugins.")
        server_factory.kill_all()
        await server_factory.plugin_manager.deactivate_all()
        #_factory.configuration_manager.save_config() # this causes changes to the config while the server is running to be overwritten.  Very annoying and makes quick restart cycles impossible.
        aiologger.removeHandler(fh_d)
        aiologger.removeHandler(ch)
        logger.info("Finished.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exited due to interrupt.")