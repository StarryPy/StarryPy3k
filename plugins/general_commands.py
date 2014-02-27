from base_plugin import SimpleCommandPlugin, command
from plugins.player_manager import Moderator


class Whois(Moderator):
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
