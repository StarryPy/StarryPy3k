"""
StarryPy Mail Plugin

Provides a mail system that allows users to send messages to players that
are not logged in. When the recipient next logs in, they will be notified
that they have new messages.

Author: medeor413
"""
import asyncio
import datetime

from base_plugin import StorageCommandPlugin
from utilities import Command, send_message


class Mail:
    def __init__(self, message, author):
        self.message = message
        self.time = datetime.datetime.now()
        self.author = author
        self.unread = True


class MailPlugin(StorageCommandPlugin):
    name = "mail"
    depends = ["player_manager", "command_dispatcher"]
    default_config = {"max_mail_storage": 25}

    def __init__(self):
        super().__init__()
        self.max_mail = 0
        self.find_player = None

    def activate(self):
        super().activate()
        self.max_mail = self.plugin_config.max_mail_storage
        self.find_player = self.plugins.player_manager.find_player
        if 'mail' not in self.storage:
            self.storage['mail'] = {}

    def on_connect_success(self, data, connection):
        """
        Catch when a player successfully connects to the server, and send them
        a new mail message.
        :param data:
        :param connection:
        :return: True. Must always be true so the packet continues.
        """
        asyncio.ensure_future(self._display_unread(connection))
        return True

    def _display_unread(self, connection):
        await asyncio.sleep(3)
        if connection.player.uuid not in self.storage['mail']:
            self.storage['mail'][connection.player.uuid] = []
        mailbox = self.storage['mail'][connection.player.uuid]
        unread_count = len([x for x in mailbox if x.unread])
        mail_count = len(mailbox)
        if unread_count > 0:
            await send_message(connection, "You have {} unread messages."
                                    .format(unread_count))
        if mail_count >= self.max_mail * 0.8:
            await send_message(connection, "Your mailbox is almost full!")

    def send_mail(self, target, author, message):
        """
        A convenience method for sending mail so other plugins can use the
        mail system easily.

        :param target: Player: The recipient of the message.
        :param author: Player: The author of the message.
        :param message: String: The message to be sent.
        :return: None.
        """
        mail = Mail(message, author)
        self.storage['mail'][target.uuid].insert(0, mail)

    @Command("sendmail",
             perm="mail.sendmail",
             doc="Send mail to a player, to be read later.",
             syntax="(user) (message)")
    def _sendmail(self, data, connection):
        if data:
            target = self.find_player(data[0])
            if not target:
                raise SyntaxWarning("Couldn't find target.")
            if not data[1]:
                raise SyntaxWarning("No message provided.")
            uid = target.uuid
            if uid not in self.storage['mail']:
                self.storage['mail'][uid] = []
            mailbox = self.storage['mail'][uid]
            if len(mailbox) >= self.max_mail:
                await send_message(connection, "{}'s mailbox is full!"
                                        .format(target.alias))
            else:
                mail = Mail(" ".join(data[1:]), connection.player)
                mailbox.insert(0, mail)
                await send_message(connection, "Mail delivered to {}."
                                        .format(target.alias))
                if target.logged_in:
                    await send_message(target.connection, "New mail from "
                                                               "{}!"
                                            .format(connection.player.alias))
        else:
            raise SyntaxWarning("No target provided.")

    @Command("readmail",
             perm="mail.readmail",
             doc="Read mail recieved from players. Give a number for a "
                 "specific mail, or no number for all unread mails.",
             syntax="[index]")
    def _readmail(self, data, connection):
        if connection.player.uuid not in self.storage['mail']:
            self.storage['mail'][connection.player.uuid] = []
        mailbox = self.storage['mail'][connection.player.uuid]
        if data:
            try:
                index = int(data[0]) - 1
                mail = mailbox[index]
                mail.unread = False
                await send_message(connection, "From {} on {}: \n{}"
                                        .format(mail.author.alias,
                                                mail.time.strftime("%d %b "
                                                                   "%H:%M"),
                                                mail.message))
            except ValueError:
                await send_message(connection, "Specify a valid number.")
            except IndexError:
                await send_message(connection, "No mail with that "
                                                    "number.")
        else:
            unread_mail = False
            for mail in mailbox:
                if mail.unread:
                    unread_mail = True
                    mail.unread = False
                    await send_message(connection, "From {} on {}: \n{}"
                                            .format(mail.author.alias,
                                                    mail.time
                                                    .strftime("%d %b %H:%M"),
                                                    mail.message))
            if not unread_mail:
                await send_message(connection, "No unread mail to "
                                                    "display.")

    @Command("listmail",
             perm="mail.readmail",
             doc="List all mail, optionally in a specified category.",
             syntax="[category]")
    def _listmail(self, data, connection):
        if connection.player.uuid not in self.storage['mail']:
            self.storage['mail'][connection.player.uuid] = []
        mailbox = self.storage['mail'][connection.player.uuid]
        if data:
            if data[0] == "unread":
                count = 1
                for mail in mailbox:
                        if mail.unread:
                            await send_message(connection, "* {}: From "
                                                                "{} on {}"
                                                    .format(count,
                                                            mail.author.alias,
                                                            mail.time.strftime(
                                                                "%d %b ""%H:%M")))
                            count += 1
                if count == 1:
                    await send_message(connection, "No unread mail in "
                                                        "mailbox.")
            elif data[0] == "read":
                count = 1
                for mail in mailbox:
                    if not mail.unread:
                        await send_message(connection, "{}: From {} on {}"
                                                .format(count,
                                                        mail.author.alias,
                                                        mail.time.strftime(
                                                            "%d %b %H:%M")))
                    count += 1
                if count == 1:
                    await send_message(connection, "No read mail in "
                                                        "mailbox.")
            else:
                raise SyntaxWarning("Invalid category. Valid categories are "
                                    "\"read\" and \"unread\".")
        else:
            count = 1
            for mail in mailbox:
                msg = "{}: From {} on {}".format(count, mail.author.alias,
                                                        mail.time.strftime(
                                                            "%d %b %H:%M"))
                if mail.unread:
                    msg = "* {}".format(msg)
                await send_message(connection, msg)
                count += 1
            if count == 1:
                await send_message(connection, "No mail in mailbox.")

    @Command("delmail",
             perm="mail.readmail",
             doc="Delete unwanted mail, by index or category.",
             syntax="(index or category)")
    def _delmail(self, data, connection):
        uid = connection.player.uuid
        if uid not in self.storage['mail']:
            self.storage['mail'][uid] = []
        mailbox = self.storage['mail'][uid]
        if data:
            if data[0] == "all":
                self.storage['mail'][uid] = []
                await send_message(connection, "Deleted all mail.")
            elif data[0] == "unread":
                for mail in mailbox:
                    if mail.unread:
                        self.storage['mail'][uid].remove(mail)
                await send_message(connection, "Deleted all unread mail.")
            elif data[0] == "read":
                for mail in mailbox:
                    if not mail.unread:
                        self.storage['mail'][uid].remove(mail)
                await send_message(connection, "Deleted all read mail.")
            else:
                try:
                    index = int(data[0]) - 1
                    self.storage['mail'][uid].pop(index)
                    await send_message(connection, "Deleted mail {}."
                                            .format(data[0]))
                except ValueError:
                    raise SyntaxWarning("Argument must be a category or "
                                        "number. Valid categories: \"read\","
                                        " \"unread\", \"all\"")
                except IndexError:
                    await send_message(connection, "No message at "
                                                        "that index.")
        else:
            raise SyntaxWarning("No argument provided.")