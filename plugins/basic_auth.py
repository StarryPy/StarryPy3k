"""
StarryPy Basic Authentication Plugin

Blocks UUID spoofing of staff members by forcing players with Moderator roles
to log in with a whitelisted Starbound account.
Permitted accounts are defined in StarryPy3k's configuration file.

Original Authors: GermaniumSystem
"""


from base_plugin import SimpleCommandPlugin
from data_parser import ConnectFailure
from pparser import build_packet
from packets import packets


class BasicAuth(SimpleCommandPlugin):
    name = "basic_auth"
    depends = ["player_manager"]
    default_config = {"enabled": False,
                      "staff_priority": 100,
                      "staff_sb_accounts": [
                         "-- REPLACE WITH STARBOUND ACCOUNT NAME --",
                         "-- REPLACE WITH ANOTHER --",
                         "-- SO ON AND SO FORTH ---"],
                      "owner_priority": 100000,
                      "owner_sb_account": "-- REPLACE WITH OWNER ACCOUNT --"}

    def __init__(self):
        super().__init__()
        self.enabled = False

    def activate(self):
        super().activate()
        if self.config.get_plugin_config(self.name)["enabled"]:
            self.logger.debug("Enabled.")
            self.enabled = True
        else:
            self.enabled = False
            self.logger.warning("+---------------< WARNING >---------------+")
            self.logger.warning("| basic_auth plugin is disabled! You are  |")
            self.logger.warning("| vulnerable to UUID spoofing attacks!    |")
            self.logger.warning("| Consult README for enablement info.     |")
            self.logger.warning("+-----------------------------------------+")

    def on_client_connect(self, data, connection):
        """
        Catch when a the client updates the server with its connection
        details.

        :param data:
        :param connection:
        :return: Boolean: True on successful connection, False on a
                 failed connection.
        """

        if not self.enabled:
            return True
        uuid = data["parsed"]["uuid"].decode("ascii")
        account = data["parsed"]["account"]
        player = self.plugins["player_manager"].get_player_by_uuid(uuid)
        # We're only interested in players who already exist.
        if player:
            # The Owner account is quite dangerous, so it has a separate
            # password to prevent a malicious staff member from taking over.
            # Moderator thru SuperAdmin can still execute spoofing attacks on
            # eachother, but this is being allowed for the sake of usability.
            if (
                   (
                        self.plugin_config.owner_priority <= player.priority
                        and account == self.plugin_config.owner_sb_account
                   ) or (
                        self.plugin_config.owner_priority > player.priority
                        >= self.plugin_config.staff_priority
                        and account in self.plugin_config.staff_sb_accounts
                   )
            ):
                # Everything checks out.
                self.logger.info("Player with privileged UUID '{}' "
                                 "successfully authenticated as "
                                 "'{}'".format(uuid, account))
                # We don't need to worry about anything after this.
                # Starbound will take care of an incorrect password.
            elif self.plugin_config.staff_priority <= player.priority:
                # They're privileged but failed to authenticate. Kill it.
                yield from connection.raw_write(
                    self.build_rejection("^red;UNAUTHORIZED^reset;\n"
                                         "Privileged players must log in with "
                                         "an account defined in StarryPy3k's "
                                         "config."))
                connection.die()
                self.logger.warning("Player with privileged UUID '{}' FAILED "
                                    "to authenticate as '{}'"
                                    "!".format(uuid, account))
                return False
        return True

    # Helper functions - Used by hooks and commands

    def build_rejection(self, reason):
        """
        Function to build packet to reject connection for client.

        :param reason: String. Reason for rejection.
        :return: Rejection packet.
        """
        return build_packet(packets["connect_failure"],
                            ConnectFailure.build(
                                dict(reason=reason)))

