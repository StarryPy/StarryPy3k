"""
StarryPy Emotes Plugin

Simple plugin to provide in-game text emotes, with both generic /me
functionality (a la IRC) and predefined actions.

Original authors: kharidiron
"""

import asyncio

import data_parser
import packets
import pparser
from base_plugin import SimpleCommandPlugin
from utilities import Command, send_message, StorageMixin, broadcast, \
    link_plugin_if_available, ChatSendMode


class Emotes(StorageMixin, SimpleCommandPlugin):
    name = "emotes"
    depends = ["command_dispatcher", "player_manager", "chat_manager"]
    set_emotes = {"beckon": "beckons you to come over",
                  "bow": "bows before you",
                  "cheer": "cheers at you! Yay!",
                  "cower": "cowers at the sight of your weapons!",
                  "cry": "bursts out in tears... sob sob",
                  "dance": "is busting out some moves, some sweet dance moves",
                  "hug": "needs a hug!",
                  "hugs": "needs a hug! Many MANY hugs!",
                  "kiss": "blows you a kiss <3",
                  "kneel": "kneels down before you",
                  "laugh": "suddenly laughs and just as suddenly stops",
                  "lol": "laughs out loud -LOL-",
                  "no": "disagrees",
                  "point": "points somewhere in the distance",
                  "ponder": "ponders if this is worth it",
                  "rofl": "rolls on the floor laughing",
                  "salute": "salutes you",
                  "shrug": "shrugs at you",
                  "sit": "sits down. Oh, boy...",
                  "sleep": "falls asleep. Zzz",
                  "surprised": "is surprised beyond belief",
                  "threaten": "is threatening you with a butter knife!",
                  "wave": "waves... Helloooo there!",
                  "yes": "agrees"}

    def __init__(self):
        super().__init__()

    def activate(self):
        super().activate()
        link_plugin_if_available(self, "irc_bot")
        link_plugin_if_available(self, "chat_enhancements")

    # Helper functions - Used by commands

    @asyncio.coroutine
    def _send_to_server(self, message, mode, connection):
        msg_base = data_parser.ChatSent.build(dict(message="".join(message),
                                                   send_mode=mode))
        msg_packet = pparser.build_packet(packets.packets['chat_sent'],
                                          msg_base)
        yield from connection.client_raw_write(msg_packet)

    # Commands - In-game actions that can be performed

    @Command("me",
             doc="Perform emote actions.")
    def _emote(self, data, connection):
        """
        Command to provide in-game text emotes.

        :param data: The packet containing the command.
        :param connection: The connection which sent the command.
        :return: Null.
        """
        if not data:
            emotes = ", ".join(sorted(self.set_emotes))
            send_message(connection,
                         "Available emotes are:\n {}".format(emotes))
            send_message(connection,
                         "...or, just type your own: `/me can do anything`")
            return False
        else:
            if self.plugins['chat_manager'].mute_check(connection.player):
                send_message(connection, "You are muted and cannot emote.")
                return False

            emote = " ".join(data)
            try:
                emote = self.set_emotes[emote]
            except KeyError:
                pass
            finally:
                try:
                    asyncio.ensure_future(
                        self.plugins["irc_bot"].bot_write(" -*- {} {}".format(
                            connection.player.alias, emote)))
                except KeyError:
                    pass
                message = "^orange;{} {}".format(connection.player.alias,
                                                 emote)
                try:
                    yield from (
                        self._send_to_server(message,
                                             ChatSendMode.UNIVERSE,
                                             connection))
                except (KeyError, AttributeError):
                    self.logger.debug("using fallback broadcast")
                    broadcast(connection, message)

    @Command("mel",
             doc="Perform emote actions in local chat.")
    def _emote_local(self, data, connection):
        """
        Command to provide in-game text emotes for local chat.

        :param data: The packet containing the command.
        :param connection: The connection which sent the command.
        :return: Null.
        """
        if not data:
            emotes = ", ".join(sorted(self.set_emotes))
            send_message(connection,
                         "Available emotes are:\n {}".format(emotes))
            send_message(connection,
                         "...or, just type your own: `/me can do anything`")
            return False
        else:
            if self.plugins['chat_manager'].mute_check(connection.player):
                send_message(connection, "You are muted and cannot emote.")
                return False

            emote = " ".join(data)
            try:
                emote = self.set_emotes[emote]
            except KeyError:
                pass
            finally:
                message = "^orange;{} {}".format(connection.player.alias,
                                                 emote)
                try:
                    yield from (
                        self._send_to_server(message,
                                             ChatSendMode.LOCAL,
                                             connection))
                except (KeyError, AttributeError):
                    self.logger.debug("using fallback broadcast")
                    broadcast(connection, message)
