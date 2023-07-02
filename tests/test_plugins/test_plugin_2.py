import asyncio

from base_plugin import BasePlugin


class TestPlugin(BasePlugin):
    name = "test_plugin_2"

    async def on_chat_sent(self, data):
        return True