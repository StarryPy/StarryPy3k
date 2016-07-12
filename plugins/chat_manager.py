"""
StarryPy Chat Manager Plugin

Provides core chat management features, such as mute... and that's it right now.

Original authors: AMorporkian
Updated for release: kharidiron
"""

from base_plugin import SimpleCommandPlugin
from plugins.player_manager import Moderator
from utilities import Command, send_message


# Roles

class Mute(Moderator):
    pass


class Unmuteable(Moderator):
    pass


class MutePlayer(Mute):
    pass


class UnmutePlayer(Mute):
    pass


###

class ChatManager(SimpleCommandPlugin):
    name = "chat_manager"
    depends = ["player_manager", "command_dispatcher"]

    def __init__(self):
        super().__init__()
        self.storage = None

    def activate(self):
        super().activate()
        self.storage = self.plugins.player_manager.get_storage(self)
        if "mutes" not in self.storage:
            self.storage["mutes"] = set()

    def on_chat_sent(self, data, connection):
        """
        Catch when someone sends a message.
        :param data: The packet containing the message.
        :param connection: The connection from which the packet came.
        :return: Boolean. True if we're done with the packet here, False if the
                 player is muted (preventing packet from being passed along.
                 Commands are treated as truthy values.
        """
        message = data["parsed"]["message"]
        if message.startswith(
                self.plugins.command_dispatcher.plugin_config.command_prefix):
            return True
        if self.mute_check(connection.player):
            send_message(connection, "You are muted and cannot chat.")
            return False
        return True

    @Command("mute",
             role=MutePlayer,
             doc="Mutes a user",
             syntax="(username)")
    def mute(self, data, connection):
        """
        Mute command.
        Pulls target's name from data stream. Check if valid player. Also check
        if player can be muted, or is already muted. Otherwise, mute target.
        """
        name = " ".join(data)
        player = self.plugins.player_manager.get_player_by_name(name)
        if player is None:
            raise NameError
        elif self.mute_check(player):
            send_message(connection, "{} is already muted.".format(player.name))
            return
        elif player.check_role(Unmuteable):
            send_message(connection, "{} is unmuteable.".format(player.name))
            return
        else:
            self.storage.mutes.add(player)
            send_message(connection, "{} has been muted.".format(player.name))
            send_message(player.connection,
                         "{} has muted you.".format(connection.player.name))

    @Command("unmute",
             role=UnmutePlayer,
             doc="Unmutes a player",
             syntax="(username)")
    def unmute(self, data, connection):
        """
        Unmute command.
        Pulls target's name from data stream. Check if valid player. Check that
        player is actually muted. Otherwise, unmute target.
        """
        name = " ".join(data)
        player = self.plugins.player_manager.get_player_by_name(name)
        if player is None:
            raise NameError
        elif not self.mute_check(player):
            send_message(connection, "{} isn't muted.".format(player.name))
            return
        else:
            self.storage.mutes.remove(player)
            send_message(connection, "{} has been unmuted.".format(player.name))
            send_message(player.connection,
                         "{} has unmuted you.".format(connection.player.name))

    def mute_check(self, player):
        """
        Utility function for verifying target player's mute status.
        :param player: Target player to check.
        :return: Boolean. True if player is mutes, False if they are not.
        """
        return player in self.storage.mutes
