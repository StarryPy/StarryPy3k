import asyncio
import subprocess
import sys
import pathlib

from base_plugin import SimpleCommandPlugin
from plugins.player_manager import SuperAdmin


class ServerRestart(SuperAdmin):
    """Role to restart the underlying Starbound server."""


class StarboundWatchdog(SimpleCommandPlugin):
    name = "starbound_watchdog"
    """ Provides a watchdog to automatically start a server, restart it should
    it die, and (in the future) detect hangs."""

    def activate(self):
        self.is_64bits = sys.maxsize > 2 ** 32  # Check if it's 64 bits
        self.platform = sys.platform.lower()  # Linux, Windows, Darwin.
        self.starbound_path = pathlib.Path(self.config.config.starbound_folder)
        self.executable = self.find_executable()
        self.watchdog = asyncio.Task(self.start_watchdog())


    def find_executable(self):
        if self.platform == "win32":
            p = self.starbound_path / "win32/starbound_server.exe"
            self.logger.info("Detected windows. Trying path %s", str(p))
        elif self.platform == "linux":
            if self.is_64bits:
                p = self.starbound_path / "linux64/starbound_server"
            else:
                p = self.starbound_path / "linux32/starbound_server"
        else:
            raise ValueError("Unknown server operating system.")
        if not p.exists():
            raise FileNotFoundError("Couldn't find starbound executable.")
        return str(p)

    @asyncio.coroutine
    def start_watchdog(self):
        subproc = subprocess.Popen(self.executable, shell=True)
        self.logger.info("Started Starbound server with PID: %d", subproc.pid)
        while True:
            if subproc.poll():
                self.logger.warning("Starbound has exited. "
                                    "Restarting in 5 seconds...")
                for protocol in self.factory.protocols:
                    protocol.die()
                yield from asyncio.sleep(5)
                self.watchdog = asyncio.Task(
                    self.start_watchdog())
                break
            yield from asyncio.sleep(1)
        try:
            subproc.terminate()
        except ProcessLookupError:
            self.logger.debug("Process already dead.")