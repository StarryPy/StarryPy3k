import asyncio
from random import randrange, choice
from base_plugin import SimpleCommandPlugin, command

__author__ = 'teihoo'

class Emotes(SimpleCommandPlugin):
    name = "Emotes"
    depends = ["colored_names"]

    #activate is main entry point for plugin
    def activate(self):
        super().activate()
#        asyncio.Task(self.load_config())

    #idea: you might be able to replace doc="my function help" with doc=print_emote_list(), might work
    @command("me", doc="Creates a player emote message.\nPredefined emotes: ^yellow;beckon^green;, ^yellow;bow^green;, ^yellow;cheer^green;, ^yellow;cower^green;, ^yellow;cry^green;, ^yellow;dance^green;, ^yellow;hug^green;, ^yellow;hugs^green;, ^yellow;kiss^green;, ^yellow;kneel^green;, ^yellow;laugh^green;, ^yellow;lol^green;, ^yellow;no^green;, ^yellow;point^green;, ^yellow;ponder^green;, ^yellow;rofl^green;, ^yellow;salute^green;, ^yellow;shrug^green;, ^yellow;sit^green;, ^yellow;sleep^green;, ^yellow;surprised^green;, ^yellow;threaten^green;, ^yellow;wave^green;, ^yellow;yes^green;\nUtility emotes: ^yellow;flip^green;, ^yellow;roll^green;",
             syntax="(emote)")
    def me(self, data, protocol):
        """
        Creates a player emote message. Syntax: /me <emote>
        """
        if len(data) == 0:
            asyncio.Task(protocol.send_message(self.me.__doc__))
            return
#        if protocol.player.muted:
#            asyncio.Task(protocol.send_message(
#                "You are currently muted and cannot emote. You are limited to commands and admin chat (prefix your lines with %s for admin chat." % (config.chat_prefix*2))
#            return False
        emote = " ".join(data)
        spec_prefix = "" #we'll use this for random rolls, to prevent faking
        if emote == "beckon":
            emote = "beckons you to come over"
        elif emote == "bow":
            emote = "bows before you"
        elif emote == "cheer":
            emote = "cheers at you! Yay!"
        elif emote == "cower":
            emote = "cowers at the sight of your weapons!"
        elif emote == "cry":
            emote = "bursts out in tears... sob sob"
        elif emote == "dance":
            emote = "is busting out some moves, some sweet dance moves"
        elif emote == "flip":
            flipdata = ["HEADS!", "TAILS!"]
            spec_prefix = "^cyan;!^orange;"  #add cyan color ! infront of name or player can /me rolled ^cyan;100
            emote = "flips a coin and its... ^cyan;%s" % choice(flipdata)
        elif emote == "hug":
            emote = "needs a hug!"
        elif emote == "hugs":
            emote = "needs a hug! Many MANY hugs!"
        elif emote == "kiss":
            emote = "blows you a kiss <3"
        elif emote == "kneel":
            emote = "kneels down before you"
        elif emote == "laugh":
            emote = "suddenly laughs and just as suddenly stops"
        elif emote == "lol":
            emote = "laughs out loud -LOL-"
        elif emote == "no":
            emote = "disagrees"
        elif emote == "point":
            emote = "points somewhere in the distance"
        elif emote == "ponder":
            emote = "ponders if this is worth it"
        elif emote == "rofl":
            emote = "rolls on the floor laughing"
        elif emote == "roll":
            rollx=str(randrange(1,101))
            spec_prefix = "^cyan;!^orange;"  #add cyan color ! infront of name or player can /me rolled ^cyan;100
            emote = "rolled ^cyan;%s" % rollx
        elif emote == "salute":
            emote = "salutes you"
        elif emote == "shrug":
            emote = "shrugs at you"
        elif emote == "sit":
            emote = "sits down. Oh, boy..."
        elif emote == "sleep":
            emote = "falls asleep. Zzz"
        elif emote == "surprised":
            emote = "is surprised beyond belief"
        elif emote == "threaten":
            emote = "is threatening you with a butter knife!"
        elif emote == "wave":
            emote = "waves... Helloooo there!"
        elif emote == "yes":
            emote = "agrees"

        timestamp = self.plugins.colored_names.timestamps()
        yield from self.factory.broadcast("^orange;%s%s%s %s" % (timestamp, spec_prefix, protocol.player.name, emote), world='planet')
        return False
