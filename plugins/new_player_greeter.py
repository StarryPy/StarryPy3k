"""
StarryPy New Player Greeter Plugin

Plugin for greeting players who are new to the server. Greets can include:
 - private greet message
 - starter items disbursement
 - public announcement

Original authors: kharidiron
"""

import asyncio

import packets
import pparser
from base_plugin import SimpleCommandPlugin
from data_parser import GiveItem
from utilities import send_message, ChatReceiveMode, DotDict


###

class NewPlayerGreeter(SimpleCommandPlugin):
    name = "new_player_greeters"
    depends = ["player_manager"]
    default_config = {"greeting": "Why hello there. You look like you're "
                                  "new here. Here, take this. It should "
                                  "help you on your way.",
                      "gifts": DotDict({
                      })}

    def __init__(self):
        super().__init__()
        self.greeting = None
        self.gifts = DotDict({})

    async def activate(self):
        await super().activate()
        self.greeting = self.config.get_plugin_config(self.name)["greeting"]
        self.gifts = self.config.get_plugin_config(self.name)["gifts"]

    async def on_world_start(self, data, connection):
        """
        Client on world hook. After a client connects, when their world
        first loads, check if they are new to the server (never been seen
        before). If they're new, send them a nice message and give them some
        starter items.

        :param data: The packet saying the client connected.
        :param connection: The connection from which the packet came.
        :return: Boolean: True. Anything else stops the client from being able
                 to connect.
        """
        player = self.plugins['player_manager'].get_player_by_name(
            connection.player.name)
        if hasattr(player, 'seen_before'):
            return True
        else:
            self.background(self._new_player_greeter(connection))
            self.background(self._new_player_gifter(connection))
            player.seen_before = True
        return True

    # Helper functions - Used by commands

    async def _new_player_greeter(self, connection):
        """
        Helper routine for greeting new players.

        :param connection: The connection we're showing the message to.
        :return: Null.
        """
        await asyncio.sleep(1.3)
        await send_message(connection,
                                "{}".format(self.greeting),
                                mode=ChatReceiveMode.RADIO_MESSAGE)
        return

    async def _new_player_gifter(self, connection):
        """
        Helper routine for giving items to new players.

        :param connection: The connection we're showing the message to.
        :return: Null.
        """
        await asyncio.sleep(2)
        for item, count in self.gifts.items():
            count = int(count)
            if count > 10000 and item != "money":
                count = 10000
            item_base = GiveItem.build(dict(name=item,
                                            count=count,
                                            variant_type=7,
                                            description=""))
            item_packet = pparser.build_packet(packets.packets['give_item'],
                                               item_base)
            await asyncio.sleep(.1)
            await connection.raw_write(item_packet)
            send_message(connection,
                         "You have been given {} {}".format(str(count), item),
                         mode=ChatReceiveMode.COMMAND_RESULT)
        return
