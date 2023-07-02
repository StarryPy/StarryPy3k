"""
StarryPy General Commands Plugin

Plugin for handling most of the most basic (and most useful) commands.

Original authors: AMorporkian
Updated for release: kharidiron
"""
import asyncio

import sys

import datetime

import packets
import pparser
import data_parser
from base_plugin import SimpleCommandPlugin
from utilities import send_message, Command, broadcast, link_plugin_if_available, State


###

class GeneralCommands(SimpleCommandPlugin):
    name = "general_commands"
    depends = ["command_dispatcher", "player_manager"]
    default_config = {"maintenance_message": "This server is currently in "
                                             "maintenance mode and is not "
                                             "accepting new connections."}

    def __init__(self):
        super().__init__()
        self.maintenance = False
        self.rejection_message = ""
        self.start_time = None
        self.chat_manager = None
    # Helper functions - Used by commands

    async def activate(self):
        await super().activate()
        self.maintenance = False
        self.rejection_message = self.config.get_plugin_config(self.name)[
            "maintenance_message"]
        self.start_time = datetime.datetime.now()
        if link_plugin_if_available(self, "chat_manager"):
            self.chat_manager = self.plugins["chat_manager"]

    def generate_whois(self, target):
        """
        Generate the whois data for a player, and return it as a formatted
        string.

        :param target: Player object to be looked up.
        :return: String: The data about the player.
        """
        logged_in = "(^green;Online^reset;)"
        last_seen = "Now"
        ban_status = "^green;Not banned"
        mute_line = ""
        if not target.logged_in:
            logged_in = "(^red;Offline^reset;)"
            last_seen = target.last_seen
        if target.ip in self.plugins["player_manager"].shelf["bans"]:
            ban = self.plugins["player_manager"].shelf["bans"][target.ip]
            ban_status = "^red;Banned by {} on {}\nBan Reason: ^red;{}".format(
                ban.banned_by, ban.banned_at, ban.reason)
        if self.chat_manager:
            if self.chat_manager.mute_check(target):
                mute_line = "Mute Status: ^red;Muted^green;"
            else:
                mute_line = "Mute Status: ^green;Unmuted"
        return ("Name: {} {}\n"
                "Raw Name: {}\n"
                "Ranks: ^yellow;{}^green;\n"
                "UUID: ^yellow;{}^green;\n"
                "IP address: ^cyan;{}^green;\n"
                "Team ID: ^cyan;{}^green;\n"
                "Current location: ^yellow;{}^green;\n"
                "Last seen: ^yellow;{}^green;\n"
                "Ban status: {}^green;\n"
                "{}".format(
                    target.alias, logged_in,
                    target.name,
                    ", ".join(target.ranks),
                    target.uuid,
                    target.ip,
                    target.team_id,
                    target.location,
                    last_seen,
                    ban_status,
                    mute_line))

    async def on_connect_success(self, data, connection):
        if self.maintenance and not connection.player.perm_check(
                "general_commands.maintenance_bypass"):
            fail = data_parser.ConnectFailure.build(dict(
                reason=self.rejection_message))
            pkt = pparser.build_packet(packets.packets['connect_failure'],
                                       fail)
            await connection.raw_write(pkt)
            return False
        else:
            return True

    # Commands - In-game actions that can be performed

    @Command("who",
             perm="general_commands.who",
             doc="Lists players who are currently logged in.")
    async def _who(self, data, connection):
        """
        Return a list of players currently logged in.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        ret_list = []
        for player in self.plugins['player_manager'].players_online:
            target = self.plugins['player_manager'].get_player_by_uuid(player)
            if connection.player.perm_check("general_commands.who_clientids"):
                ret_list.append(
                    "[^red;{}^reset;] {}{}^reset;".format(target.client_id,
                                                          target.chat_prefix,
                                                          target.alias))
            else:
                ret_list.append("{}{}^reset;".format(target.chat_prefix,
                                                     target.alias))
        send_message(connection,
                     "{} players online:\n{}".format(len(ret_list),
                                                     ", ".join(ret_list)))

    @Command("whois",
             perm="general_commands.whois",
             doc="Returns client data about the specified user.",
             syntax="(username)")
    async def _whois(self, data, connection):
        """
        Display information about a player.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        :raise: SyntaxWarning if no name provided.
        """
        if len(data) == 0:
            raise SyntaxWarning("No target provided.")
        name = " ".join(data)
        info = self.plugins['player_manager'].find_player(name)
        if info is not None:
            send_message(connection, self.generate_whois(info))
        else:
            send_message(connection, "Player not found!")

    @Command("give", "item", "give_item",
             perm="general_commands.give_item",
             doc="Gives an item to a player. "
                 "If player name is omitted, give item(s) to self.",
             syntax=("[player=self]", "(item name)", "[count=1]"))
    async def _give_item(self, data, connection):
        """
        Give item(s) to a player.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        :raise: SyntaxWarning if too many arguments provided or item count
                cannot be properly converted. NameError if a target player
                cannot be resolved.
        """
        arg_count = len(data)
        target = self.plugins.player_manager.find_player(data[0])
        if arg_count == 1:
            target = connection.player
            item = data[0]
            count = 1
        elif arg_count == 2:
            if data[1].isdigit():
                target = connection.player
                item = data[0]
                count = int(data[1])
            else:
                item = data[1]
                count = 1
        elif arg_count == 3:
            item = data[1]
            if not data[2].isdigit():
                raise SyntaxWarning("Couldn't convert %s to an item count." %
                                    data[2])
            count = int(data[2])
        else:
            raise SyntaxWarning("Too many arguments")
        if target is None:
            raise NameError(target)
        target = target.connection
        if count > 10000 and item != "money":
            count = 10000
        item_base = data_parser.GiveItem.build(dict(name=item,
                                                    count=count,
                                                    variant_type=7,
                                                    description=""))
        item_packet = pparser.build_packet(packets.packets['give_item'],
                                           item_base)
        await target.raw_write(item_packet)
        send_message(connection,
                     "Gave {} (count: {}) to {}".format(
                         item,
                         count,
                         target.player.alias))
        send_message(target, "{} gave you {} (count: {})".format(
            connection.player.alias, item, count))

    @Command("nick",
             perm="general_commands.nick",
             doc="Changes your nickname to another one.",
             syntax="(username)")
    async def _nick(self, data, connection):
        """
        Change your name as it is displayed in the chat window.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        if len(data) > 1 and connection.player.perm_check(
                "general_commands.nick_others"):
            target = self.plugins.player_manager.find_player(data[0])
            alias = " ".join(data[1:])
        else:
            alias = " ".join(data)
            target = connection.player
        if len(data) == 0:
            alias = connection.player.name
        conflict = self.plugins.player_manager.get_player_by_alias(alias)
        if conflict and target != conflict:
            raise ValueError("There's already a user by that name.")
        else:
            clean_alias = self.plugins['player_manager'].clean_name(alias)
            if clean_alias is None:
                send_message(connection,
                             "Nickname contains no valid characters.")
                return
            old_alias = target.alias
            target.alias = clean_alias
            broadcast(connection, "{}'s name has been changed to {}".format(
                old_alias, clean_alias))

    @Command("serverwhoami",
             perm="general_commands.whoami",
             doc="Displays your current nickname for chat.")
    async def _whoami(self, data, connection):
        """
        Displays your current nickname and connection information.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        send_message(connection,
                     self.generate_whois(connection.player))

    @Command("here",
             perm="general_commands.here",
             doc="Displays all players on the same planet as you.")
    async def _here(self, data, connection):
        """
        Displays all players on the same planet as the user.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        ret_list = []
        location = str(connection.player.location)
        for uid in self.plugins.player_manager.players_online:
            p = self.plugins.player_manager.get_player_by_uuid(uid)
            if str(p.location) == location:
                if connection.player.perm_check(
                        "general_commands.who_clientids"):
                    ret_list.append(
                        "[^red;{}^reset;] {}{}^reset;"
                            .format(p.client_id,
                                    p.chat_prefix,
                                    p.alias))
                else:
                    ret_list.append("{}{}^reset;".format(
                        p.chat_prefix, p.alias))
        send_message(connection,
                     "{} players on planet:\n{}".format(len(ret_list),
                                                        ", ".join(ret_list)))

    @Command("uptime",
             perm="general_commands.uptime",
             doc="Displays the time since the server started.")
    async def _uptime(self, data, connection):
        """
        Displays the time since the server started.
        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        current_time = datetime.datetime.now() - self.start_time
        send_message(connection, "Uptime: {}".format(current_time))

    @Command("shutdown",
             perm="general_commands.shutdown",
             doc="Shutdown the server after N seconds (default 5).",
             syntax="[time]")
    async def _shutdown(self, data, connection):
        """
        Shutdown the StarryPy server, disconnecting everyone.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        self.logger.warning("{} has called for a shutdown.".format(
            connection.player.alias))
        shutdown_time = 5
        if data:
            if data[0].isdigit():
                shutdown_time = int(data[0])

        broadcast(self, "^red;(ADMIN) The server is shutting down in {} "
                        "seconds.^reset;".format(shutdown_time))
        await asyncio.sleep(shutdown_time)
        # this is a noisy shutdown (makes a bit of errors in the logs). Not
        # sure how to make it better...
        self.logger.warning("Shutting down server now.")
        self.plugins.player_manager.sync()
        sys.exit()

    @Command("maintenance_mode",
             perm="general_commands.maintenance_mode",
             doc="Toggle maintenance mode on the server. While in "
                 "maintenance mode, the server will reject all new "
                 "connection.")
    async def _maintenance(self, data, connection):
        if self.maintenance:
            self.maintenance = False
            broadcast(self, "^red;NOTICE: Maintence mode disabled. "
                            "^reset;New connections are allowed.")
        else:
            self.maintenance = True
            broadcast(self, "^red;NOTICE: The server is now in maintenance "
                            "mode. ^reset;No additional clients can connect.")
