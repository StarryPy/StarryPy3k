"""
StarryPy species whitelist plugin

Prevents players with unknown species from joining the server.
This is necessary due to a year+ old "bug" detailed here:
https://community.playstarbound.com/threads/119569/

Original Authors: GermaniumSystem
"""

from base_plugin import BasePlugin
from data_parser import ConnectFailure
from packets import packets
from pparser import build_packet



class SpeciesWhitelist(BasePlugin):
    name = "species_whitelist"
    depends = ["player_manager"]
    default_config = {"enabled": False,
                      "allowed_species": [
                          "apex",
                          "avian",
                          "glitch",
                          "floran",
                          "human",
                          "hylotl",
                          "penguin",
                          "novakid"
                      ]}


    def activate(self):
        super().activate()
        self.enabled = self.config.get_plugin_config(self.name)["enabled"]
        self.allowed_species = self.config.get_plugin_config(self.name)["allowed_species"]


    def on_client_connect(self, data, connection):
        if not self.enabled:
            return True
        species = data['parsed']['species']
        if species not in self.allowed_species:
            self.logger.warn("Aborting connection - player's species ({}) "
                    "is not in whitelist.".format(species))
            rejection_packet = build_packet(packets['connect_failure'],
                    ConnectFailure.build(dict(reason="^red;Connection "
                            "aborted!\n\n^orange;Your species ({}) is not "
                            "allowed on this server.\n^green;Please use a "
                            "different character.".format(species))))
            yield from connection.raw_write(rejection_packet)
            connection.die()
            return False
        return True

