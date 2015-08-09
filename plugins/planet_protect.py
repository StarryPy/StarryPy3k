import asyncio

from base_plugin import StorageCommandPlugin
from plugins.player_manager import Admin, Ship
from utilities import Direction, Command, send_message


class Protect(Admin):
    pass


class Unprotect(Admin):
    pass


class ProtectedLocation:
    def __init__(self, location, allowed_builder):
        self.protected = True
        self.location = location
        self.allowed_builders = {allowed_builder.name}

    def unprotect(self):
        self.protected = False

    def protect(self):
        self.protected = True

    def add_builder(self, builder):
        self.allowed_builders.add(builder.name)

    def del_builder(self, builder):
        self.allowed_builders.remove(builder.name)

    def check_builder(self, builder):
        return builder.name in self.allowed_builders

    def get_builders(self):
        return self.allowed_builders


class PlanetProtect(StorageCommandPlugin):
    name = "planet_protect"

    def activate(self):
        super().activate()
        if "locations" not in self.storage:
            self.storage['locations'] = {}

    def on_world_start(self, data, protocol):
        asyncio.Task(self.protect_ship(protocol))
        return True

    def check_protection(self, location):
        return str(location) in self.storage['locations']

    def get_protection(self, location) -> ProtectedLocation:
        return self.storage['locations'][str(location)]

    def add_protection(self, location, player):
        if str(location) not in self.storage['locations']:
            protection = ProtectedLocation(location, player)
            self.storage['locations'][str(location)] = protection
        else:
            protection = self.storage['locations'][str(location)]
            protection.protect()
            protection.add_builder(player)
        return protection

    def disable_protection(self, location):
        self.storage['locations'][str(location)].unprotect()

    @asyncio.coroutine
    def protect_ship(self, protocol):
        yield from asyncio.sleep(.5)
        if isinstance(protocol.player.location, Ship):
            ship = protocol.player.location
            if not self.check_protection(ship):
                if ship.player == protocol.player.name:
                    self.add_protection(ship, protocol.player)
                    send_message(protocol,
                                 "Your ship has been auto-protected.")

    @Command("protect", doc="Protects a planet", syntax="", role=Protect)
    def protect(self, data, protocol):
        location = protocol.player.location
        self.add_protection(location, protocol.player)
        send_message(protocol, "Protected location: %s" % location)

    @Command("unprotect", doc="Unprotects a planet", syntax="", role=Unprotect)
    def unprotect(self, data, protocol):
        location = protocol.player.location
        self.disable_protection(location)
        send_message(protocol, "Unprotected planet %s" % location)

    @Command("add_builder",
             doc="Adds a player to the current location's build list.",
             syntax="[\"](player name)[\"]",
             role=Protect)
    def add_builder(self, data, protocol):
        location = protocol.player.location
        p = self.plugins.player_manager.get_player_by_name(" ".join(data))
        if p is not None:
            protection = self.get_protection(location)
            protection.add_builder(p)
            send_message(protocol,
                         "Added %s to allowed list for %s" % (
                             p.name, protocol.player.location))
            try:
                yield from p.protocol.send_message(
                    "You've been granted build access on %s by %s" % (
                        protocol.player.location, protocol.player.name))
            except AttributeError:
                send_message(protocol,
                             "%s isn't online, granted anyways." % p.name)
        else:
            send_message(protocol,
                         "Couldn't find a player with name %s" %
                         " ".join(data))

    @Command("del_builder",
             doc="Deletes a player from the current location's build list",
             syntax="[\"](player name)[\"]")
    def del_builder(self, data, protocol):
        p = self.plugins.player_manager.get_player_by_name(" ".join(data))
        if p is not None:
            protection = self.get_protection(protocol.player.location)
            protection.del_builder(p)
            send_message(protocol,
                         "Removed player from build list for this location.")
        else:
            send_message(protocol, "Couldn't find a player with name "
                                   "%s" % " ".join(data))

    @Command("list_builders",
             doc="Lists all players granted build permissions "
                 "at current location",
             syntax="")
    def list_builders(self, data, protocol):
        if not self.check_protection(protocol.player.location):
            send_message(protocol, "This location has never been"
                                   "protected.")
        else:
            protection = self.get_protection(protocol.player.location)
            players = ", ".join(protection.get_builders())
            send_message(protocol, "Players allowed to build at location "
                                   "'%s': %s" % (protocol.player.location,
                                                 players))

    def on_entity_interact(self, data, protocol):
        if data['direction'] == Direction.TO_CLIENT:
            return True
        if not self.check_protection(protocol.player.location):
            return True
        protection = self.get_protection(protocol.player.location)
        if not protection.protected:
            return True
        if protocol.player.check_role(Admin):
            return True
        elif protocol.player.name in protection.get_builders():
            return True
        else:
            return False

    def on_entity_create(self, data, protocol):
        if data['direction'] == Direction.TO_SERVER:
            if data['data'][0] == 0x00:
                return True  # A player is being sent, let's let it through.
        return (yield from self.on_entity_interact(data, protocol))

    on_damage_tile = on_entity_interact
    on_damage_tile_group = on_entity_interact
    #on_entity_create = on_entity_interact
    on_spawn_entity = on_entity_interact
    on_modify_tile_list = on_entity_interact
    on_tile_update = on_entity_interact
    on_tile_array_update = on_entity_interact
