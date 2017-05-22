"""
StarryPy Privileged Chatter Plugin

Add a number of chat commands that leverage the roles system:
 - Mod Chatter: lets Mods,Admins and SuperAdmins talk privately in-game
 - Admin Announce: command for admins to make alert-style announcements to all
                   players
 - Notify Mod : Lets players send a message to Mods+, in case something needs
                their attention.

Original authors: medeor413
"""

from base_plugin import SimpleCommandPlugin
from utilities import Command, send_message, ChatReceiveMode, broadcast,\
    link_plugin_if_available


class PrivilegedChatter(SimpleCommandPlugin):
    name = "privileged_chatter"
    depends = ["command_dispatcher", "player_manager"]
    default_config = {"modchat_color": "^violet;",
                      "report_prefix": "^magenta;(REPORT): ",
                      "broadcast_prefix": "^red;(ADMIN): "}

    def __init__(self):
        super().__init__()
        self.modchat_color = None
        self.report_prefix = None
        self.broadcast_prefix = None
        self.mail = None
        self.chat_enhancements = None

    def activate(self):
        super().activate()
        self.modchat_color = self.config.get_plugin_config(self.name)[
            "modchat_color"]
        self.report_prefix = self.config.get_plugin_config(self.name)[
            "report_prefix"]
        self.broadcast_prefix = self.config.get_plugin_config(self.name)[
            "broadcast_prefix"]
        if link_plugin_if_available(self, 'mail'):
            self.mail = self.plugins.mail
        if link_plugin_if_available(self, 'chat_enhancements'):
            self.chat_enhancements = self.plugins.chat_enhancements

    # Commands - In-game actions that can be performed

    @Command("modchat", "m",
             perm="privileged_chatter.modchat",
             doc="Send a message that can only be seen by other moderators.",
             syntax="(message)")
    def _moderatorchat(self, data, connection):
        """
        Command to send private messages between moderators.

        :param data: The packet containing the command.
        :param connection: The connection which sent the command.
        :return: Null.
        """
        if data:
            message = " ".join(data)
            if self.chat_enhancements:
                sender = self.chat_enhancements.decorate_line(connection)
            else:
                sender = connection.player.name
            send_mode = ChatReceiveMode.BROADCAST
            channel = ""
            for uuid in self.plugins["player_manager"].players_online:
                p = self.plugins["player_manager"].get_player_by_uuid(uuid)
                if p.perm_check("privileged_chatter.modchat"):
                    yield from send_message(p.connection,
                                            "{}{}^reset;".format(
                                                self.modchat_color, message),
                                            client_id=p.client_id,
                                            name=sender,
                                            mode=send_mode,
                                            channel=channel)

    @Command("report",
             perm="privileged_chatter.report",
             doc="Privately make a report to all online moderators.",
             syntax="(message)")
    def _report(self, data, connection):
        """
        Command to send reports to moderators.

        :param data: The packet containing the command.
        :param connection: The connection which sent the command.
        :return: Null.
        """
        if data:
            message = " ".join(data)
            if self.chat_enhancements:
                sender = self.chat_enhancements.decorate_line(connection)
            else:
                sender = connection.player.name
            send_mode = ChatReceiveMode.BROADCAST
            channel = ""
            mods_online = False
            yield from send_message(connection,
                                    "{}{}^reset;".format(
                                        self.report_prefix, message),
                                    client_id=connection.player.client_id,
                                    name=sender,
                                    mode=send_mode,
                                    channel=channel)
            for uuid in self.plugins["player_manager"].players_online:
                p = self.plugins["player_manager"].get_player_by_uuid(uuid)
                if p.perm_check("privileged_chatter.modchat"):
                    mods_online = True
                    yield from send_message(p.connection,
                                            "{}{}^reset;".format(
                                                self.report_prefix, message),
                                            client_id=p.client_id,
                                            name=sender,
                                            mode=send_mode,
                                            channel=channel)
            # if not mods_online and self.report_mail:
            #     self.mail.send_mail()

    @Command("broadcast",
             perm="privileged_chatter.broadcast",
             doc="Sends a message to everyone on the server.",
             syntax="(message)")
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
            message = self.broadcast_prefix + " ".join(data)
            broadcast(self, message)
