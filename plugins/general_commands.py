from base_plugin import SimpleCommandPlugin
import data_parser
import packets
from plugins.player_manager import Admin
import pparser
from utilities import command


class Whois(Admin):
    pass


class GiveItem(Admin):
    pass

class GeneralCommands(SimpleCommandPlugin):
    name = "general_commands"
    depends = ["command_dispatcher", "player_manager"]

    @command("who")
    def who(self, data, protocol):
        ret_list = []
        for player in self.plugins['player_manager'].players.values():
            if player.logged_in:
                ret_list.append(player.name)
        yield from protocol.send_message(
            "%d players online: %s" % (len(ret_list),
                                       ", ".join(ret_list)))

    @command("whois", doc="Returns client data about the specified user.",
             syntax="(username)", role=Whois)
    def whois(self, data, protocol):
        if len(data) == 0:
            raise SyntaxWarning
        name = " ".join(data)
        info = self.plugins['player_manager'].get_player_by_name(name)
        if info is not None:
            if info.logged_in:
                yield from protocol.send_message(
                    "Name: %s\n"
                    "Roles: ^yellow;%s^green;\n"
                    "UUID: ^yellow;%s^green;\n"
                    "IP address: ^cyan;%s^green;\n"
                    "Current location: ^yellow;%s^green;""" % (
                        info.name, ", ".join(info.roles),
                        info.uuid, info.ip, info.location))
            else:
                yield from protocol.send_message(
                    "Name: %s ^gray;(OFFLINE)^yellow;\n"
                    "UUID: ^yellow;%s^green;\n"
                    "Last known IP: ^cyan;%s^green;""" % (
                        info.name, info.uuid, info.ip))
        else:
            yield from protocol.send_message("Player not found!")

    @command("give", "item", "give_item",
             role=GiveItem,
             doc="Gives an item to a player. "
                 "If player name is omitted, give item(s) to self.",
             syntax=("[player=self]", "(item name)", "[count=1]"))
    def give_item(self, data, protocol):
        arg_count = len(data)
        if arg_count == 1:
            target = protocol.player
            item = data[0]
            count = 1
        elif arg_count == 2:
            if data[1].isdigit():
                target = protocol.player
                item = data[0]
                count = int(data[1])
            else:
                target = self.plugins.player_manager.get_player_by_name(data[0])
                item = data[1]
                count = 1
        elif arg_count == 3:
            target = self.plugins.player_manager.get_player_by_name(data[0])
            item = data[1]
            if not data[2].isdigit():
                raise SyntaxWarning("Couldn't convert %s to an item count." %
                                    data[2])
            count = int(data[2])
        else:
            raise SyntaxWarning("Too many arguments")
        if target is None:
            raise NameError(target)
        target = target.protocol
        if count > 1000 and item != "money":
            count = 1000
        count += 1
        item_base = data_parser.GiveItem.build(dict(name=item,
                                                    count=count,
                                                    variant_type=7,
                                                    extra=0))
        item_packet = pparser.build_packet(packets.packets['give_item'],
                                           item_base)
        yield from target.raw_write(item_packet)
        yield from protocol.send_message("Gave %s (count: %d) to %s" %
                                         (item, count - 1, target.player.name))
        yield from target.send_message("%s gave you %s (count: %d)" %
                                       (protocol.player.name, item, count - 1))
