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

    def activate(self):
        super().activate()
        self.blocked_messages = [
            "applyStatusEffect",
            "warp",
            "playAltMusic",
            "stopAltMusic",
            "playCinematic"
        ]

    def on_entity_message(self, data, connection):
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
                else:
                    return True
            else:
                return True
