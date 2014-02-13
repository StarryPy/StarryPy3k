import asyncio

from server import ServerFactory


def start_server():
    serverf = ServerFactory()
    yield from asyncio.start_server(serverf, '127.0.0.1', 21025)


class TestServer:
    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        self.loop.stop()

    def testTest(self):
        asyncio.Task(self.beep())

    @asyncio.coroutine
    def beep(self):
        x = yield from (lambda _: True)("")
        return x