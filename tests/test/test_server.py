import asyncio

from server import ServerFactory


async def start_server():
    serverf = ServerFactory()
    await asyncio.start_server(serverf, '127.0.0.1', 21025)


class TestServer:
    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        self.loop.stop()

    def testTest(self):
        asyncio.ensure_future(self.beep())

    async def beep(self):
        x = await (lambda _: True)("")
        return x