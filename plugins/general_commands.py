from base_plugin import SimpleCommandPlugin, command
import data_parser
import packets
from plugins.player_manager import Moderator, Admin, SuperAdmin
import pparser


class Whois(Moderator):
    pass


class GiveItem(Admin):
    pass


class GeneralCommands(SimpleCommandPlugin):
    name = "general_commands"
    depends = ["command_dispatcher", "player_manager", "colored_names"]

    @command("who", "players",
             doc="Shows players online.",
             syntax="")
    def who(self, data, protocol):
        ret_list = []
        for player in self.plugins['player_manager'].players.values():
            if player.logged_in:
                ret_list.append(self.plugins.colored_names.colored_name(player))
        yield from protocol.send_message(
            "^cyan;%d^green; players online: %s" % (len(ret_list),
                                       "^green;, ".join(ret_list)))

    @command("whois",
             doc="Returns client data about the specified user.",
             syntax="(username)",
             role=Whois)
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
                        self.plugins.colored_names.colored_name(info), ", ".join(info.roles),
                        info.uuid, info.ip, info.location))
            else:
                yield from protocol.send_message(
                    "Name: %s ^gray;(OFFLINE)^yellow;\n"
                    "UUID: ^yellow;%s^green;\n"
                    "Last known IP: ^cyan;%s^green;""" % (
                        self.plugins.colored_names.colored_name(info), info.uuid, info.ip))
        else:
            yield from protocol.send_message("Player not found!")

    @command("give", "item", "give_item",
             role=GiveItem,
             doc="Gives an item to a player. "
                 "If player name is omitted, give item(s) to self.",
             syntax=("[player=self]", "(item name)", "[count=1]"))
    def give_item(self, data, protocol):
        print(data)
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
        if count > 1000:
            count = 1000
        count += 1
        item_base = data_parser.GiveItem.build(dict(name=item,
                                                    count=count,
                                                    variant_type=0,
                                                    description=""))
        item_packet = pparser.build_packet(packets.packets['give_item'],
                                           item_base)
        yield from target.raw_write(item_packet)
        yield from protocol.send_message("Gave ^yellow;%s^green; (count: ^cyan;%d^green;) to %s" %
                                         (item, count, self.plugins.colored_names.colored_name(target.player)))
        yield from target.send_message("%s gave you ^yellow;%s^green; (count: ^cyan;%d^green;)" %
                                       (self.plugins.colored_names.colored_name(protocol.player), item, count))

    def on_give_item(self, data, protocol):
        print(data['data'])
        return True

    @command("chattimestamps",
             doc="Toggles chat time stamps.",
             syntax="",
             role=SuperAdmin)
    def chattimestamps(self, data, protocol):
        try:
            if self.config.config.chattimestamps:
                self.config.config.chattimestamps = False
                yield from self.factory.broadcast("Chat timestamps are now: ^red;HIDDEN")

            else:
                self.config.config.chattimestamps = True
                yield from self.factory.broadcast("Chat timestamps are now: ^yellow;SHOWN")
        except:
            self.config.config.chattimestamps=True
            yield from self.factory.broadcast("Chat timestamps are now: ^yellow;SHOWN")

