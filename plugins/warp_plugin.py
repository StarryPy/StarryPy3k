import asyncio
import re

from base_plugin import SimpleCommandPlugin
from data_parser import WarpCommand
import packets
import plugins.player_manager as player_manager
from pparser import build_packet
from utilities import command


class Warp(player_manager.Owner):
    pass


class WarpPlayer(Warp):
    pass


class WarpShip(Warp):
    pass


class WarpPlugin(SimpleCommandPlugin):
    """Plugin which provides commands related to warping."""
    name = "warp_plugin"
    depends = ["player_manager", "command_dispatcher"]

    def activate(self):
        super().activate()
        self.get_by_name = self.plugins.player_manager.get_player_by_name

    @command("warp", role=Warp, doc="Warps a player to another player.",
             syntax=("[from player=self]", "(to player)"))
    def warp(self, data, protocol):
        if len(data) == 1:
            from_player = protocol.player
            to_player = self.get_by_name(data[0], check_logged_in=True)
        elif len(data) == 2:
            from_player = self.get_by_name(data[0], check_logged_in=True)
            to_player = self.get_by_name(data[1], check_logged_in=True)
        else:
            raise SyntaxWarning
        if (from_player is None) or (to_player is None):
            raise NameError("Couldn't find name.")
        yield from self.warp_player_to_player(from_player, to_player)
        yield from protocol.send_message("Warped %s to %s." % (from_player.name,
                                                               to_player.name))
        yield from from_player.protocol.send_message("%s has warped to you %s's"
                                                     "ship." %
                                                     (protocol.player.name,
                                                      to_player.name))
        yield from to_player.protocol.send_message("%s has been warped to "
                                                   "your ship by %s." %
                                                   (from_player.name,
                                                    protocol.player.name))

    @asyncio.coroutine
    def warp_player_to_player(self, from_player, to_player):
        """
        Warps a player to another player's ship.
        :param from_player: Player
        :param to_player: Player
        :return: None
        """
        coords = dict(sector="", x=0, y=0, z=0, planet=0, satellite=0)
        wp = WarpCommand.build(dict(warp_type=3, coordinate=coords,
                                    player=to_player.name, sector="", x=0, y=0,
                                    z=0, planet=0, satellite=0))
        full = build_packet(id=packets.packets['warp_command'], data=wp)
        yield from from_player.protocol.client_raw_write(full)

    @asyncio.coroutine
    def warp_ship_to_planet(self, from_player, to):
        planet_regex = r"(?:(?P<sector>[a-z]+):(?P<a>-?[0-9]+):(?P<x>-?[0-9]+):(?P<y>-?[0-9]+):(?P<planet>[0-9]+):(?P<satellite>[0-9]+)?)"
        warp_match = re.match(planet_regex, to)
        if warp_match is not None:
            warp_coords = warp_match.groupdict()
        else:
            raise NotImplementedError
