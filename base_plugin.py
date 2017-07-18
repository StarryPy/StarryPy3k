import asyncio
import collections

from utilities import DotDict, recursive_dictionary_update


class BaseMeta(type):
    def __new__(mcs, name, bases, clsdict):
        for key, value in clsdict.items():
            if callable(value) and (value.__name__.startswith("on_") or
                                    hasattr(value, "_command")):
                clsdict[key] = asyncio.coroutine(value)
        c = type.__new__(mcs, name, bases, clsdict)
        return c


class BasePlugin(metaclass=BaseMeta):
    """
    Defines an interface for all plugins to inherit from. Note that the init
    method should generally not be overrode; all setup work should be done in
    activate() if possible. If you do override __init__, remember to super()!

    Note that only one instance of each plugin will be instantiated for *all*
    connected clients. self.connection will be changed by the plugin
    manager to the current connection.

    You may access the factory if necessary via self.factory.connections
    to access other clients, but this "Is Not A Very Good Idea" (tm)

    `name` *must* be defined in child classes or else the plugin manager will
    complain quite thoroughly.
    """

    name = "Base Plugin"
    description = "The common class for all plugins to inherit from."
    version = ".1"
    depends = ()
    default_config = None
    plugins = DotDict({})
    auto_activate = True

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.plugin_config = self.config.get_plugin_config(self.name)
        if isinstance(self.default_config, collections.Mapping):
            temp = recursive_dictionary_update(self.default_config,
                                               self.plugin_config)
            self.plugin_config.update(temp)

        else:
            self.plugin_config = self.default_config

    def activate(self):
        pass

    def deactivate(self):
        pass

    def on_protocol_request(self, data, connection):
        """Packet type: 0 """
        return True

    def on_protocol_response(self, data, connection):
        """Packet type: 1 """
        return True

    def on_server_disconnect(self, data, connection):
        """Packet type: 2 """
        return True

    def on_connect_success(self, data, connection):
        """Packet type: 3 """
        return True

    def on_connect_failure(self, data, connection):
        """Packet type: 4 """
        return True

    def on_handshake_challenge(self, data, connection):
        """Packet type: 5 """
        return True

    def on_chat_received(self, data, connection):
        """Packet type: 6 """
        return True

    def on_universe_time_update(self, data, connection):
        """Packet type: 7 """
        return True

    def on_celestial_response(self, data, connection):
        """Packet type: 8 """
        return True

    def on_player_warp_result(self, data, connection):
        """Packet type: 9 """
        return True

    def on_planet_type_update(self, data, connection):
        """Packet type: 10 """
        return True

    def on_pause(self, data, connection):
        """Packet type: 11 """
        return True

    def on_client_connect(self, data, connection):
        """Packet type: 12 """
        return True

    def on_client_disconnect_request(self, data, connection):
        """Packet type: 13 """
        return True

    def on_handshake_response(self, data, connection):
        """Packet type: 14 """
        return True

    def on_player_warp(self, data, connection):
        """Packet type: 15 """
        return True

    def on_fly_ship(self, data, connection):
        """Packet type: 16 """
        return True

    def on_chat_sent(self, data, connection):
        """Packet type: 17 """
        return True

    def on_celestial_request(self, data, connection):
        """Packet type: 18 """
        return True

    def on_client_context_update(self, data, connection):
        """Packet type: 19 """
        return True

    def on_world_start(self, data, connection):
        """Packet type: 20 """
        return True

    def on_world_stop(self, data, connection):
        """Packet type: 21 """
        return True

    def on_world_layout_update(self, data, connection):
        """Packet type: 22 """
        return True

    def on_world_parameters_update(self, data, connection):
        """Packet type: 23 """
        return True

    def on_central_structure_update(self, data, connection):
        """Packet type: 24 """
        return True

    def on_tile_array_update(self, data, connection):
        """Packet type: 25 """
        return True

    def on_tile_update(self, data, connection):
        """Packet type: 26 """
        return True

    def on_tile_liquid_update(self, data, connection):
        """Packet type: 27 """
        return True

    def on_tile_damage_update(self, data, connection):
        """Packet type: 28 """
        return True

    def on_tile_modification_failure(self, data, connection):
        """Packet type: 29 """
        return True

    def on_give_item(self, data, connection):
        """Packet type: 30 """
        return True

    def on_environment_update(self, data, connection):
        """Packet type: 31 """
        return True

    def on_update_tile_protection(self, data, connection):
        """Packet type: 32 """
        return True

    def on_set_dungeon_gravity(self, data, connection):
        """Packet type: 33 """
        return True

    def on_set_dungeon_breathable(self, data, connection):
        """Packet type: 34 """

    def on_set_player_start(self, data, connection):
        """Packet type: 35 """
        return True

    def on_find_unique_entity_response(self, data, connection):
        """Packet type: 36"""
        return True

    def on_modify_tile_list(self, data, connection):
        """Packet type: 37 """
        return True

    def on_damage_tile_group(self, data, connection):
        """Packet type: 38 """
        return True

    def on_collect_liquid(self, data, connection):
        """Packet type: 39 """
        return True

    def on_request_drop(self, data, connection):
        """Packet type: 40 """
        return True

    def on_spawn_entity(self, data, connection):
        """Packet type: 41 """
        return True

    def on_connect_wire(self, data, connection):
        """Packet type: 42 """
        return True

    def on_disconnect_all_wires(self, data, connection):
        """Packet type: 43 """
        return True

    def on_world_client_state_update(self, data, connection):
        """Packet type: 44 """
        return True

    def on_find_unique_entity(self, data, connection):
        """Packet type: 45 """
        return True

    def on_unk(self, data, connection):
        """Packet type: 46 """
        return True

    def on_entity_create(self, data, connection):
        """Packet type: 47 """
        return True

    def on_entity_update(self, data, connection):
        """Packet type: 48 """
        return True

    def on_entity_destroy(self, data, connection):
        """Packet type: 49 """
        return True

    def on_entity_interact(self, data, connection):
        """Packet type: 50 """
        return True

    def on_entity_interact_result(self, data, connection):
        """Packet type: 51 """
        return True

    def on_hit_request(self, data, connection):
        """Packet type: 52 """
        return True

    def on_damage_request(self, data, connection):
        """Packet type: 53 """
        return True

    def on_damage_notification(self, data, connection):
        """Packet type: 54 """
        return True

    def on_entity_message(self, data, connection):
        """Packet type: 55 """
        return True

    def on_entity_message_response(self, data, connection):
        """Packet type: 56 """
        return True

    def on_update_world_properties(self, data, connection):
        """Packet type: 57 """
        return True

    def on_step_update(self, data, connection):
        """Packet type: 58 """
        return True

    def on_system_world_start(self, data, connection):
        """Packet type: 59 """
        return True

    def on_system_world_update(self, data, connection):
        """Packet type: 60 """
        return True

    def on_system_object_create(self, data, connection):
        """Packet type: 61 """
        return True

    def on_system_object_destroy(self, data, connection):
        """Packet type: 62 """
        return True

    def on_system_ship_create(self, data, connection):
        """Packet type: 63 """
        return True

    def on_system_ship_destroy(self, data, connection):
        """Packet type: 64 """
        return True

    def on_system_object_spawn(self, data, connection):
        """Packet type: 65 """
        return True

    def __repr__(self):
        return "<Plugin instance: %s (version %s)>" % (self.name, self.version)


class CommandNameError(Exception):
    """
    Raised when a command name can't be found from the `commands` list in a
    `SimpleCommandPlugin` instance.
    """


class SimpleCommandPlugin(BasePlugin):
    name = "simple_command_plugin"
    description = "Provides a simple parent class to define chat commands."
    version = "0.1"
    depends = ["command_dispatcher"]
    auto_activate = True

    def activate(self):
        super().activate()
        for name, attr in [(x, getattr(self, x)) for x in self.__dir__()]:
            if hasattr(attr, "_command"):
                for alias in attr._aliases:
                    self.plugins['command_dispatcher'].register(attr, alias)


class StoragePlugin(BasePlugin):
    name = "storage_plugin"
    depends = ['player_manager']

    def activate(self):
        super().activate()
        self.storage = self.plugins.player_manager.get_storage(self.name)


class StorageCommandPlugin(SimpleCommandPlugin):
    name = "storage_command_plugin"
    depends = ['command_dispatcher', 'player_manager']

    def activate(self):
        super().activate()
        self.storage = self.plugins.player_manager.get_storage(self)
