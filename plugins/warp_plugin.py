"""
StarryPy Warp Plugin

Allows Moderators to teleport to other players and their ships.

Original author: ?
Updated for 1.0 by medeor413
"""

import asyncio

import packets
from plugins.player_manager import Moderator
from base_plugin import SimpleCommandPlugin
from data_parser import PlayerWarp
from pparser import build_packet
from utilities import Command, send_message


class Warp(Moderator):
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
        self.get_by_alias = self.plugins.player_manager.get_player_by_alias

    @Command("warp", "tp",
             role=Warp,
             doc="Warps a player to another player.",
             syntax=("[from player=self]", "(to player)"))
    def warp(self, data, connection):
        if len(data) == 1:
            from_player = connection.player
            to_player = self.get_by_alias(data[0], check_logged_in=True)
        elif len(data) == 2:
            from_player = self.get_by_alias(data[0], check_logged_in=True)
            to_player = self.get_by_alias(data[1], check_logged_in=True)
        else:
            raise SyntaxWarning
        if from_player is None or to_player is None:
            send_message(connection, "Target is not logged in or does not "
                                     "exist.")
            return
        yield from self.warp_player_to_player(from_player, to_player)
        if from_player.alias != connection.player.alias:
            send_message(from_player.connection, "You've been warped to {}."
                         .format(to_player.alias))
            send_message(connection, "Warped {} to {}.".format(
                from_player.alias, to_player.alias))
        else:
            send_message(connection, "Warped to {}.".format(to_player.alias))

    @asyncio.coroutine
    def warp_player_to_player(self, from_player, to_player):
        """
        Warps a player to another player.
        :param from_player: Player: The player being warped.
        :param to_player: Player: The player being warped to.
        :return: None
        """
        wp = PlayerWarp.build(dict(warp_action=dict(warp_type=2,
                                                    player_id=to_player.uuid)))
        full = build_packet(packets.packets['player_warp'], wp)
        yield from from_player.connection.client_raw_write(full)
