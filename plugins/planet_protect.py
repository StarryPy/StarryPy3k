import asyncio

from base_plugin import SimpleCommandPlugin, command
from plugins.player_manager import Admin, Ship
from utilities import Direction


class Protect(Admin):
    pass


class Unprotect(Admin):
    pass


class PlanetProtect(SimpleCommandPlugin):
    name = "planet_protect"
    depends = ['command_dispatcher', 'player_manager']

    def on_world_start(self, data, protocol):
        asyncio.Task(self.protect_ship(protocol))
        return True

    @asyncio.coroutine
    def protect_ship(self, protocol):
        yield from asyncio.sleep(.5)
        if isinstance(protocol.player.location, Ship):
            if not hasattr(protocol.player.location, "protected"):
                if protocol.player.location.player == protocol.player.name:
                    protocol.player.location.protected = True
                    protocol.player.location.allowed_builders = {
                        protocol.player.name}
                    yield from protocol.send_message(
                        "Your ship has been auto-protected.")


    @command("protect", doc="Protects a planet", syntax="", role=Protect)
    def protect(self, data, protocol):
        location = protocol.player.location
        location.protected = True
        location.allowed_builders = {protocol.player.name}
        yield from protocol.send_message("Protected planet %s" % location)

    @command("unprotect", doc="Unprotects a planet", syntax="", role=Unprotect)
    def unprotect(self, data, protocol):
        location = protocol.player.location
        location.protected = False
        yield from protocol.send_message("Unprotected planet %s" % location)

    @command("add_builder",
             doc="Adds a player to the current location's build list.",
             syntax="[\"](player name)[\"]",
             role=Protect)
    def add_builder(self, data, protocol):
        if not hasattr(protocol.player.location, "protected"):
            yield from protocol.send_message(
                "Planet is not protected. Protecting.")
            yield from self.protect(data, protocol)
        p = self.plugins.player_manager.get_player_by_name(" ".join(data))
        if p is not None:
            protocol.player.location.allowed_builders.add(p.name)
            yield from protocol.send_message(
                "Added %s to allowed list for %s" % (
                p.name, protocol.player.location))
            try:
                yield from p.protocol.send_message(
                    "You've been granted build access on %s by %s" % (
                    protocol.player.location, protocol.player.name))
            except AttributeError:
                yield from protocol.send_message(
                    "%s isn't online, so we can't send them a notification."
                    % p.name)
        else:
            yield from protocol.send_message(
                "Couldn't find a player with name %s" %
                " ".join(data))

    @command("del_builder",
             doc="Deletes a player from the current location's build list",
             syntax="[\"](player name)[\"]")
    def del_builder(self, data, protocol):
        if not hasattr(protocol.player.location, "protected"):
            yield from protocol.send_message(
                "Location is not protected.")
            return
        p = self.plugins.player_manager.get_player_by_name(" ".join(data))
        if p is not None:
            try:
                protocol.player.location.allowed_builders.remove(p.name)
            except KeyError:
                yield from protocol.send_message("Player isn't in the allowed"
                                                 "builders list for this."
                                                 "location.")
        else:
            yield from protocol.send_message("Couldn't find a player with name "
                                             "%s" % " ".join(data))

    @command("list_builders",
             doc="Lists all players granted build permissions "
                 "at current location",
             syntax="")
    def list_builders(self, data, protocol):
        if not hasattr(protocol.player.location, 'protected'):
            yield from protocol.send_message("This location has never been"
                                             "protected.")
            return
        players = ", ".join(sorted(protocol.player.location.allowed_builders))
        yield from protocol.send_message("Players allowed to build at location "
                                         "'%s': %s" % (protocol.player.location,
                                                       players))

    def on_entity_interact(self, data, protocol):
        if data['direction'] == Direction.TO_STARBOUND_CLIENT:
            return True
        try:
            if not getattr(protocol.player.location, "protected", False):
                return True
            else:
                if Admin.__name__ in protocol.player.roles:
                    return True
                elif protocol.player.name in protocol.player.location.allowed_builders:
                    return True
                else:
                    return False
        except AttributeError as e:
            print(e)
            return True

    def on_entity_create(self, data, protocol):
        if data['direction'] == Direction.TO_STARBOUND_SERVER and data['data'][
            0] == 0x00:
            return True  # A player is being sent, let's let it through.
        return (yield from self.on_entity_interact(data, protocol))

    on_damage_tile = on_entity_interact
    on_damage_tile_group = on_entity_interact
    #on_entity_create = on_entity_interact
    on_spawn_entity = on_entity_interact
    on_modify_tile_list = on_entity_interact
    on_tile_update = on_entity_interact
    on_tile_array_update = on_entity_interact