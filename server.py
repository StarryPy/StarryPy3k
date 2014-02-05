import asyncio
import binascii


class Packet(object):
    def __init__(self):
        self.packets = []



class Client(asyncio.Protocol):
    def __init__(self, server):
        self.transport = None
        self.server = server
        self.packet = Packet()

    def connection_made(self, transport):
        print("connection made to client")
        self.transport = transport

    def data_received(self, data):
        asyncio.Task(self.server.consume(self, data))

    @asyncio.coroutine
    def consume(self, data):
        pass


class Server(asyncio.Protocol):
    def __init__(self, factory):
        self.factory = factory
        self.loop = asyncio.get_event_loop()
        self.transport = None
        self.client = Client(self)

    def connection_made(self, transport):
        print("connection made to server")
        self.transport = transport
        asyncio.Task(self.connect_to_client())


    def data_received(self, data):
        self.consume(data)

    @asyncio.coroutine
    def connect_to_client(self):
        print("in connect_to_client")
        protocol, self.client = yield from self.loop.create_connection(Client(self), "starbound.end-ga.me", 21025)

    @asyncio.coroutine
    def consume(self, data):
        print(len(data))
        self.transport.write(data)

class ServerFactory():
    def __init__(self):
        self.protocols = []

    def __call__(self, *args, **kwargs):
        protocol = Server(self)
        self.protocols.append(protocol)
        print(self.protocols)
        return protocol

@asyncio.coroutine
def init(loop):
    yield from loop.create_server(ServerFactory(), '127.0.0.1', 21025)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    asyncio.Task(init(loop))
    loop.run_forever()