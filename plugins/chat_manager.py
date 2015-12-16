from base_plugin import SimpleCommandPlugin
from plugins.player_manager import Moderator
from utilities import broadcast, Command, send_message, ChatSendMode, ChatReceiveMode


class Mute(Moderator):
    pass


class Unmuteable(Moderator):
    pass


class MutePlayer(Mute):
    pass


class UnmutePlayer(Mute):
    pass


class ChatManager(SimpleCommandPlugin):
    name = "chat_manager"
    depends = ['player_manager', 'command_dispatcher']

    def activate(self):
        super().activate()
        self.storage = self.plugins.player_manager.get_storage(self)
        if "mutes" not in self.storage:
            self.storage["mutes"] = set()

    def on_chat_sent(self, data, protocol):
        message = data['parsed']['message']
        if message[
            0] == self.plugins.command_dispatcher.plugin_config.command_prefix:
            return True
        if self.mute_check(protocol.player):
            send_message(protocol, "You are muted and cannot chat.")
            return False
        if data['parsed']['send_mode'] == ChatSendMode.LOCAL:
            self.plugins.player_manager.planetary_broadcast(protocol.player,
                                                            message)
            return False
        elif data['parsed']['send_mode'] == ChatSendMode.BROADCAST:
            broadcast(self.factory,
                      data['parsed']['message'],
                      name=protocol.player.name)
            return False
        return True

    @Command("mute", doc="Mutes a user",
             syntax="(username)", role=MutePlayer)
    def mute(self, data, protocol):
        name = " ".join(data)
        player = self.plugins.player_manager.get_player_by_name(name)
        if player is None:
            raise NameError
        elif self.mute_check(player):
            send_message(protocol, "%s is already muted." % player.name)
            return
        elif player.check_role(Unmuteable):
            send_message(protocol, "%s is unmuteable." % player.name)
            return
        else:
            self.storage.mutes.add(player)
            send_message(protocol, "%s has been muted." % player.name)
            send_message(player.protocol,
                         "%s has muted you." % protocol.player.name)

    @Command("unmute",
             doc="Unmutes a player",
             syntax="(username)",
             role=UnmutePlayer)
    def unmute(self, data, protocol):
        name = " ".join(data)
        player = self.plugins.player_manager.get_player_by_name(name)
        if player is None:
            raise NameError
        elif not self.mute_check(player):
            send_message(protocol, "%s isn't muted." % player.name)
            return
        else:
            self.storage.mutes.remove(player)
            send_message(protocol, "%s has been unmuted." % player.name)
            send_message(player.protocol,
                         "%s has unmuted you." % protocol.player.name)

    def mute_check(self, player):
        return player in self.storage.mutes

