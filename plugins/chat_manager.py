from base_plugin import BasePlugin
from utilities import broadcast


class ChatManager(BasePlugin):
    depends = ['player_manager']

    def on_chat_sent(self, data, protocol):
        message = data['parsed']['message']
        if message[0] == self.config.config.command_prefix:
            return True

        if data['parsed']['channel'] == 1:
            self.plugins.player_manager.planetary_broadcast(protocol.player,
                                                            message)
            return False
        elif data['parsed']['channel'] == 0:
            broadcast(self.factory,
                      data['parsed']['message'],
                      name=protocol.player.name,
                      channel=1)
            return False
        return True