"""
StarryPy OpenSB Detector Plugin

Detects zstd compression for the stream and sets server configuration accordingly
"""

import asyncio

from base_plugin import SimpleCommandPlugin
from utilities import send_message, Command


class OpenSBDetector(SimpleCommandPlugin):
    name = "opensb_detector"

    def __init__(self):
        super().__init__()

    async def activate(self):
        await super().activate()

    async def on_protocol_response(self, data, connection):
        # self.logger.debug("Received protocol response: {} from connection {}".format(data, connection))
        info = data["parsed"].get("info")
        if info != None and info["compression"] == "Zstd":
            self.logger.info("Detected Zstd compression. Setting server configuration.")
            connection.start_zstd()
        return True
