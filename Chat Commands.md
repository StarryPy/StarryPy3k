# StarryPy Chat Commands

On its own, StarryPy is simply a framework for inspecting (and modifying) Starbound packets, as they are transmitted between the clients and the server. It is up to StarryPy's plugins to make use of this framework, by providing its users with commands to extend the in-game experience and administration.

This document seeks to enumerate the commands that are available to the users. Section one provides a quick list off all the commands, as organized by level of user access required. Section two is organized by plugin, providing detailed usage information. Section two will be ordered by functionality and dependence.

Note: This document is likely to change often, as well as become outdated quickly, as this software develops. For that, I apologize in advance.

## Commands by User Level

***Guest Commands***

- /help
- /l
- /me
- /mel
- /motd
- /spawn
- /u
- /whisper , /w
- /who
- /whoami
- /p
- /here , /planet
- /poi
- /report

***Registered User Commands***

- /nick
- /claim
- /unclaim
- /add_helper
- /rm_helper
- /change_owner
- /helper_list
- /list_claims

***Moderator Commands***

- /ban
- /unban
- /kick
- /list_bans
- /mute
- /set_motd
- /show_spawn
- /unmute
- /modchat , /m
- /warp , /tp
- /tps

***Admin Commands***

- /protect
- /unprotect
- /add_builder
- /del_builder
- /list_builders
- /list_players
- /whois
- /broadcast
- /give , /item , /give_item
- /set_poi
- /del_poi
- /grant , /promote , /revoke , /demote

***SuperAdmin Commands***

- /set_spawn
- /del_player

## Commands by Plugin

#### Chat Logger

- ***Depend on:***
  - None

- ***Commands Provided***
  - None

Chat logger does nothing more than echo chat messages sent by clients to the logging system. Thus, all messages sent to the server, be the chats, whispers, or user commands will be shown in the console log and saved in the debug.log file.

#### Command Dispatcher

- ***Depend on:***
  - None

- ***Commands Provided***
  - None

Command Dispatcher is part of the core plugin framework, as it provides the mechanism through which plugins are able to provide commands.

#### IRC Bot

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - None

In-game, the IRC bot does not provide any commands. Instead, it provides a means of echo chatter between the game chat and an IRC chat instance.

#### Message of the Day

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /motd
     - **Role:** Guest
     - **Description:** Shows the Message of the Day.

  - /set_motd (message)
     - **Role:** Moderator
     - **Description:** Sets the Message of the Day.

#### Spawn

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /set_spawn
     - **Role:** SuperAdmin
     - **Description:** Sets the planet the user is currently standing on as the "spawn" planet.

  - /show_spawn
     - **Role:** Moderator
     - **Description:** Shows the location information of the current "spawn" planet.

  - /spawn
     - **Role:** Guest
     - **Description:** Move a player's ship to the spawn planet.
     - This command provides free-of-fuel-charge transit from anywhere in the universe.

Note: This is old syntax, in that each player has their own spawn planet. It would be better to describe "spawn" as being a world designated as a hub-planet where users can move their ships for meeting up with other players.

#### Points of Interest

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /poi [name]
    - **Role:** Guest
    - **Description:** Move a player's ship to the specified POI, or list all POIs if no argument provided.
    - This command does not cost fuel to use, or even require FTL to be enabled.

  - /set_poi (name)
    - **Role:** Admin
    - **Description:** Sets the planet the user is on as a POI with the specified name.

  - /del_poi (name)
    - **Role:** Admin
    - **Description:** Removes the specified POI from the POI list.

#### Player Manager

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /kick (username) [reason]
     - **Role:** Moderator
     - **Description:** Kicks a player off the server.

  - /ban (username) (reason)
     - **Role:** Moderator
     - **Description:** Bans a player from connecting to the server.

  - /unban (username)
     - **Role:** Moderator
     - **Description:** Unbans a player from connecting to the server.

  - /list_bans
     - **Role:** Moderator
     - **Description:** Display the current bans in effect.

  - /list_players
     - **Role:** Admin
     - **Description:** Lists all players in the player database.

  - /grant (Role) (Username)
     - **Role:** Admin
     - **Description:** Grant a role to a player.
     - **Alias:** /promote
     - Roles can be either part of the hierarchy (moderator, admin, etc...) or command-specific (/kick, /set_motd, etc...)

  - /del_player (Username) [*force]
     - **Role:** SuperAdmin
     - **Description:** Removed a player's entry from the player database.
     - In order to remove a player who is currently connected, you must use the *force keyword as well.

#### General Commands

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /who
     - **Role:** Guest
     - **Description:** Lists all players currently logged in.
  - /here
     - **Role:** Guest
     - **Description:** Lists all players on the same planet as the user.
     - **Alias:** /planet
  - /whois (username)
     - **Role:** Admin
     - **Description:** Displays detailed information about a player.

  - /whoami
     - **Role:** Guest
     - **Description:** Displays your current chat nickname.

  - /nick (new username)
     - **Role:** Registered
     - **Description:** Change your current chate nickname to something else.

  - /give (username) (item name) [quantity]
     - **Role:** Admin
     - **Description:** Give a player (an) item(s) based on asset name. If no quantity is provided, default to 1.
     - **Aliases:** /item , /give_item

#### Help

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /help [command]
     - **Role:** Guest
     - **Description:** Command for providing help with commands.
     - When run without an argument, show the player a list of all available commands to them (at their use level).

#### Chat Manager

- ***Depend on:***
  - Command Dispatcher, Player Manger

- ***Commands Provided***
  - /mute (username)
     - **Role:** Moderator
     - **Description:** Mutes a player.

  - /unmute (username)
     - **Role:** Moderator
     - **Description:** Unmutes a player.

#### Chat Enhancements

- ***Depend on:***
  - Command Dispatcher, Player Manger

- ***Commands Provided***
  - /l (message)
     - **Role:** Guest
     - **Description:** Send a local message.

  - /u (message)
     - **Role:** Guest
     - **Description:** Sends a universal message.

  - /whisper (recipient) (message)
     - **Role:** Guest
     - **Description:** Sends a private message to another user.
     - **Alias:** /w

  - /p (message)
     - **Role:** Guest
     - **Description:** Sends a message to everyone in your party. If not in a party, defaults to local chat.

#### Emotes

- ***Depend on:***
  - Command Dispatcher, Player Manger

- ***Commands Provided***
  - /me [emote]
     - **Role:** Guest
     - **Description:** Performs a text-emote.
     - When this command is performed with no arguments, a list of built-in actions are sent back to the player.

  - /mel [emote]
     - **Role:** Guest
     - **Description:** Performs a text-emote in local chat.
     - When this command is performed with no arguments, a list of built-in actions are sent back to the player.

#### Privileged Chatter

- ***Depend on:***
  - Command Dispatcher, Player Manager, Chat Enhancements

- ***Commands Provided***
  - /modchat (message)
    - **Role:** Moderator
    - **Description:** Sends a message visible only to other moderators.
    - **Alias:** /m
  
  - /report (message)
    - **Role:** Guest
    - **Description:** Sends a report message to all online moderators.

  - /broadcast (message)
    - **Role:** Admin
    - **Description:** Broadcasts an admin message to the entire server.

#### New Player Greeter

- ***Depend on:***
  - Command Dispatcher, Player Manger

- ***Commands Provided***
  - None

#### Planet Protect

- ***Depend on:***
  - Command Dispatcher, Player Manger

- ***Commands Provided***
  - /protect
     - **Role:** Admin
     - **Description:** Makes a planet protected.

  - /unprotect
     - **Role:** Admin
     - **Description:** Removes a planet's protection.

  - /add_builder (username)
     - **Role:** Admin
     - **Description:** Allow a player build-rights on a protected planet.

  - /del_builder (username)
     - **Role:** Admin
     - **Description:** Disallow a player's build-rights on a protected planet.

  - /list_builders
     - **Role:** Admin
     - **Description:** Show all players allowed to build on a protected planet.

#### Claims

- ***Depend on:***
  - Command Dispatcher, Player Manager, Planet Protect

- ***Commands Provided***
  - /claim
    - **Role:** Registered
    - **Description:** Claim a planet to be protected.

  - /unclaim
    - **Role:** Registered*
    - **Description:** Unclaim and unprotect the planet you're standing on.

  - /add_helper (username)
    - **Role:** Registered*
    - **Description:** Add someone to the protected list of your planet.

  - /rm_helper (username)
    - **Role:** Registered*
    - **Description:** Remove someone from the protected list of your planet.

  - /helper_list
    - **Role:** Registered*
    - **Description:** List all of the people allowed to build on this planet.

  - /change_owner (username)
    - **Role:** Registered*
    - **Description:** Transfer ownership of the planet to another person.
    
  - /list_claims
    - **Role:** Registered
    - **Description:** List all planets the player is owner of.

  - Note: All of the commands except /claim and /list_helper require the user to be the owner of the planet.

#### Warp

- ***Depend on:***
  - Command Dispatcher, Player Manager
  
- ***Commands Provided***
  - /tp [from player] (to player)
    - **Role:** Moderator
    - **Description:** Warps the specified from player, or self if none, to the specified to player.
    
  - /tps [from player] (to player)
    - **Role:** Moderator
    - **Description:** Warps the specified from player, or self if none, to the specified to player's ship.

#### Planet Backups

- *NOT YET IMPLEMENTED*
