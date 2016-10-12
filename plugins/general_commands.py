"""
StarryPy General Commands Plugin

Plugin for handling most of the most basic (and most useful) commands.

Original authors: AMorporkian
Updated for release: kharidiron
"""
import asyncio

import sys

import packets
import pparser
import data_parser
from base_plugin import SimpleCommandPlugin
from plugins.player_manager import SuperAdmin, Admin, Moderator, Registered,\
    Guest
from utilities import send_message, Command, broadcast


# Roles

class Whois(Admin):
    pass


class GiveItem(Admin):
    pass


class Nick(Registered):
    pass


class Whoami(Guest):
    pass


class Shutdown(SuperAdmin):
    pass


###

class GeneralCommands(SimpleCommandPlugin):
    name = "general_commands"
    depends = ["command_dispatcher", "player_manager"]
    default_config = {"maintenance_message": "This server is currently in "
                                             "maintenance mode and is not "
                                             "accepting new connections."}
    # Helper functions - Used by commands
    def activate(self):
        super().activate()
        self.maintenance = False
        self.rejection_message = self.config.get_plugin_config(self.name)[
            "maintenance_message"]

    def generate_whois(self, target):
        """
        Generate the whois data for a player, and return it as a formatted
        string.

        :param target: Player object to be looked up.
        :return: String: The data about the player.
        """
        l = ""
        if not target.logged_in:
            l = "(^red;Offline^reset;)"
        return ("Name: {} {}\n"
                "Raw Name: {}\n"
                "Roles: ^yellow;{}^green;\n"
                "UUID: ^yellow;{}^green;\n"
                "IP address: ^cyan;{}^green;\n"
                "Team ID: ^cyan;{}^green;\n"
                "Current location: ^yellow;{}^green;\n"
                "Last seen: ^yellow;{}^green;".format(
                    target.alias, l,
                    target.name,
                    ", ".join(target.roles),
                    target.uuid,
                    target.ip,
                    target.team_id,
                    target.location,
                    target.last_seen))

    def on_connect_success(self, data, connection):
        if self.maintenance and "SuperAdmin" not in connection.player.roles:
            fail = data_parser.ConnectFailure.build(dict(
                reason=self.rejection_message))
            pkt = pparser.build_packet(packets.packets['connect_failure'],
                                       fail)
            yield from connection.raw_write(pkt)
            print("Rejection message sent. Pkt: {}".format(fail))
            return False
        else:
            return True

    # Commands - In-game actions that can be performed

    @Command("who",
             doc="Lists players who are currently logged in.")
    def _who(self, data, connection):
        """
        Return a list of players currently logged in.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        ret_list = []
        for player in self.plugins['player_manager'].players_online:
            target = self.plugins['player_manager'].get_player_by_uuid(player)
            if connection.player.check_role(Moderator):
                ret_list.append(
                    "[^red;{}^reset;] {}".format(target.client_id,
                                                 target.alias))
            else:
                ret_list.append("{}".format(target.alias))
        send_message(connection,
                     "{} players online:\n{}".format(len(ret_list),
                                                     ", ".join(ret_list)))

    @Command("whois",
             role=Whois,
             doc="Returns client data about the specified user.",
             syntax="(username)")
    def _whois(self, data, connection):
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
        info = self.plugins['player_manager'].get_player_by_alias(name)
        if info is not None:
            send_message(connection, self.generate_whois(info))
        else:
            send_message(connection, "Player not found!")

    @Command("give", "item", "give_item",
             role=GiveItem,
             doc="Gives an item to a player. "
                 "If player name is omitted, give item(s) to self.",
             syntax=("[player=self]", "(item name)", "[count=1]"))
    def _give_item(self, data, connection):
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
        target = self.plugins.player_manager.get_player_by_alias(data[0])
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
        yield from target.raw_write(item_packet)
        send_message(connection,
                     "Gave {} (count: {}) to {}".format(
                         item,
                         count,
                         target.player.alias))
        send_message(target, "{} gave you {} (count: {})".format(
            connection.player.alias, item, count))

    @Command("nick",
             role=Nick,
             doc="Changes your nickname to another one.",
             syntax="(username)")
    def _nick(self, data, connection):
        """
        Change your name as it is displayed in the chat window.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        alias = " ".join(data)
        if self.plugins.player_manager.get_player_by_alias(alias):
            raise ValueError("There's already a user by that name.")
        else:
            clean_alias = self.plugins['player_manager'].clean_name(alias)
            if clean_alias is None:
                send_message(connection,
                             "Nickname contains no valid characters.")
                return
            old_alias = connection.player.alias
            connection.player.alias = clean_alias
            broadcast(self.factory,
                      "{}'s name has been changed to {}".format(old_alias,
                                                                clean_alias))

    @Command("whoami",
             role=Whoami,
             doc="Displays your current nickname for chat.")
    def _whoami(self, data, connection):
        """
        Displays your current nickname and connection information.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        # TODO: currently this is buggy, and will sometime not work...
        # instead, the Starbound version of /whoami will take over.
        send_message(connection,
                     self.generate_whois(connection.player))

    @Command("here", "planet",
             role=Whoami,
             doc="Displays all players on the same planet as you.")
    def _here(self, data, connection):
        """
        Displays all players on the same planet as the user.

        :param data: The packet containing the command.
        :param connection: The connection from which the packet came.
        :return: Null.
        """
        ret_list = []
        location = str(connection.player.location)
        for p in self.factory.connections:
            if str(p.player.location) == location:
                if connection.player.check_role(Moderator):
                    ret_list.append(
                        "[^red;{}^reset;] {}".format(p.player.client_id,
                                                     p.player.alias))
                else:
                    ret_list.append("{}".format(p.player.alias))
        send_message(connection,
                     "{} players on planet:\n{}".format(len(ret_list),
                                                        ", ".join(ret_list)))

    @Command("shutdown",
             role=Shutdown,
             doc="Shutdown the server after N seconds (default 5).",
             syntax="[time]")
    def _shutdown(self, data, connection):
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
                self.logger.debug("We think it is an int, lets use it.")
                shutdown_time = int(data[0])

        broadcast(self, "^red;(ADMIN) The server is shutting down in {} "
                        "seconds.^reset;".format(shutdown_time))
        yield from asyncio.sleep(shutdown_time)
        # this is a noisy shutdown (makes a bit of errors in the logs). Not
        # sure how to make it better...
        self.logger.warning("Shutting down server now.")
        sys.exit()

    @Command("maintenance_mode",
             role=SuperAdmin,
             doc="Toggle maintenance mode on the server. While in "
                 "maintenance mode, the server will reject all new "
                 "connection.")
    def _maintenance(self, data, connection):
        if self.maintenance:
            self.maintenance = False
            broadcast(self, "^red;NOTICE: Maintence mode disabled. "
                            "^reset;New connections are allowed.")
        else:
            self.maintenance = True
            broadcast(self, "^red;NOTICE: The server is now in maintenance "
                            "mode. ^reset;No additional clients can connect.")