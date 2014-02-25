from base_plugin import SimpleCommandPlugin, command


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