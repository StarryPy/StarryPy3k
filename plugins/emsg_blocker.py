"""
StarryPy Entity Message Blocker Plugin

Filter out harmful or malicious entity messages from players.

Original authors: medeor413
"""

from base_plugin import BasePlugin
from utilities import Direction


class ChatLogger(BasePlugin):
    name = "emsg_blocker"

    def __init__(self):
        super().__init__()
        self.blocked_messages = []
        self.in_transit_players = set()

    async def activate(self):
        await super().activate()
        self.in_transit_players = set()
        self.blocked_messages = [
            "applyStatusEffect",
            "warp",
            "playAltMusic",
            "stopAltMusic",
            "playCinematic"
        ]
        self.blocked_world_properties = [
            "nonCombat",
            "invinciblePlayers"
        ]

    async def on_world_stop(self, data, connection):
        self.in_transit_players.add(connection)
        return True

    async def on_world_start(self, data, connection):
        if connection in self.in_transit_players:
            self.in_transit_players.remove(connection)
        return True

    async def on_entity_message(self, data, connection):
        """
        Catch when an entity message is sent and block it, depending on its
        contents.

        :param data: The packet containing the message.
        :param connection: The connection from which the packet came.
        :return: Boolean; True if the message is allowed, false if it's
        blocked.
        """
        if data['direction'] == Direction.TO_CLIENT:
            # The server probably isn't sending malicious messages
            return True
        else:
            if data['parsed']['message_name'] in self.blocked_messages:
                if not connection.player.perm_check("emsg_blocker.bypass"):
                    self.logger.debug("Blocked message {} from player {}."
                                      .format(data['parsed']['message_name'],
                                              connection.player.alias))
                    return False
            return True

    async def on_entity_message_response(self, data, connection):
        if connection in self.in_transit_players and data['direction'] == \
                Direction.TO_CLIENT:
            return False
        else:
            return True

    async def on_update_world_properties(self, data, connection):
        """
        Catch when world properties are modified and block it, depending on
        its contents.
        :param data:
        :param connection:
        :return: Boolean: True if the change is allowed, false otherwise
        """
        if data['direction'] == Direction.TO_CLIENT:
            # The server is just informing the clients of changes.
            return True
        else:
            for key in data['parsed'].keys():
                if key in self.blocked_world_properties:
                    if not connection.player.perm_check("emsg_blocker.bypass"):
                        self.logger.debug("Blocked change of world property "
                                          "{} from player {}.".format(
                            key, connection.player.alias))
                        return False
            return True