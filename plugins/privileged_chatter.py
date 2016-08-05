"""
StarryPy Privileged Chatter Plugin

Add a number of chat commands that leverage the roles system:
 - Mod Chatter: lets Mods,Admins and SuperAdmins talk privately in-game
 - Admin Announce: command for admins to make alert-style announcements to all
                   players
 - Notify Mod : Lets players send a message to Mods+, in case something needs
                their attention.

Original authors: kharidiron
"""

from base_plugin import SimpleCommandPlugin
from plugins.player_manager import Admin, Moderator
from utilities import get_syntax, Command, send_message, ChatReceiveMode, broadcast

class ModeratorChat(Moderator):
    pass


class Broadcast(Admin):
    pass


class PrivilegedChatter(SimpleCommandPlugin):
    name = "privileged_chatter"
    depends = ["command_dispatcher", "chat_enhancements", "player_manager"]
    default_config = {"modchat_color": "^violet;",
                      "report_prefix": "^magenta;(REPORT): ",
                      "broadcast_prefix": "^red;(ADMIN): "}

    def __init__(self):
        super().__init__()
        self.command_prefix = None
        self.commands = None

    def activate(self):
        super().activate()
        cd = self.plugins.command_dispatcher
        self.command_prefix = cd.plugin_config.command_prefix
        self.commands = cd.commands
        self.modchat_color = self.config.get_plugin_config(self.name)["modchat_color"]
        self.report_prefix = self.config.get_plugin_config(self.name)["report_prefix"]
        self.broadcast_prefix = self.config.get_plugin_config(self.name)["broadcast_prefix"]

    # Commands - In-game actions that can be performed

    @Command("modchat", "m",
              role=ModeratorChat,
              doc="Send a message that can only be seen by other moderators.")
    def _moderatorchat(self, data, connection):
         """
         Command to send private messages between moderators.

         :param data: The packet containing the command.
         :param connection: The connection which sent the command.
         :return: Null.
         """
         if data:
             message = " ".join(data)
             sender = self.plugins['chat_enhancements']._decorate_line(connection)
             send_mode = ChatReceiveMode.BROADCAST
             channel = ""
             for p in self.factory.connections:
                 if "ModeratorChat" in p.player.roles:
                     yield from send_message(p,
                                             "{}{}^reset;".format(self.modchat_color, message),
                                             client_id=p.player.client_id,
                                             name=sender,
                                             mode=send_mode,
                                             channel=channel)

    @Command("report",
          doc="Privately make a report to all online moderators.")
    def _report(self, data, connection):
         """
         Command to send reports to moderators.

         :param data: The packet containing the command.
         :param connection: The connection which sent the command.
         :return: Null.
         """
         if data:
             message = " ".join(data)
             sender = self.plugins['chat_enhancements']._decorate_line(connection)
             send_mode = ChatReceiveMode.BROADCAST
             channel = ""
             for p in self.factory.connections:
                 if "ModeratorChat" in p.player.roles or p == connection:
                     yield from send_message(p,
                                             "{}{}^reset;".format(self.report_prefix, message),
                                             client_id=p.player.client_id,
                                             name=sender,
                                             mode=send_mode,
                                             channel=channel)


    @Command("broadcast",
         role=Broadcast,
         doc="Sends a message to everyone on the server.")
    def _broadcast(self, data, connection):
        """
        Broadcast a message to everyone on the server. Currently, this is
        actually redundant, as sending a message regularly is already a
        broadcast.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        if data:
            message = " ".join(data)
            broadcast(self,
                  "{}{}^reset;".format(self.broadcast_prefix, message))