"""
StarryPy RCON Command Dispatcher Plugin

Author: kharidiron
"""

import asyncio
import struct

from base_plugin import BasePlugin
from utilities import extractor, get_syntax, send_message


class RConDispatcher(BasePlugin):
    name = "rcon_dispatcher"

    def __init__(self):
        super().__init__()

    def _send_command(self):
        pass