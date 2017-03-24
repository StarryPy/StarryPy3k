# StarryPy Chat Commands

On its own, StarryPy is simply a framework for inspecting (and modifying) Starbound packets, as they are transmitted between the clients and the server. It is up to StarryPy's plugins to make use of this framework, by providing its users with commands to extend the in-game experience and administration.

This document seeks to enumerate the commands that are available to the users. Section one provides a quick list off all the commands, as organized by level of user access required. Section two is organized by plugin, providing detailed usage information. Section two will be ordered by functionality and dependence.

Note: This document is likely to change often, as well as become outdated quickly, as this software develops. For that, I apologize in advance.

## Commands by User Level (Default Configuration)

***Guest Commands***

- /help
- /l
- /me
- /mel
- /motd
- /spawn
- /show_spawn
- /u
- /whisper , /w
- /reply , /r
- /ignore
- /who
- /serverwhoami
- /p
- /here
- /poi
- /report

***Registered User Commands***

- /nick
- /claim
- /unclaim
- /add_builder
- /rm_builder
- /change_owner
- /list_builders
- /list_claims
- /set_greeting
- /planet_access

***Moderator Commands***

- /ban
- /unban
- /kick
- /list_bans
- /mute
- /set_motd
- /unmute
- /modchat , /m
- /tp
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
- /set_greeting
- /user

***SuperAdmin Commands***

- /set_motd
- /set_spawn
- /del_player
- /maintenance_mode
- /shutdown

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
     - **Permission:** `motd.motd`
     - **Description:** Shows the Message of the Day.

  - /set_motd (message)
     - **Permission:** `motd.set_motd`
     - **Description:** Sets the Message of the Day.

#### Spawn

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /set_spawn
     - **Permission:** `spawn.set_spawn`
     - **Description:** Sets the planet the user is currently standing on as the "spawn" planet.

  - /show_spawn
     - **Permission:** `spawn.show_spawn`
     - **Description:** Shows the location information of the current "spawn" planet.

  - /spawn
     - **Permission:** `spawn.spawn`
     - **Description:** Move a player's ship to the spawn planet.
     - This command provides free-of-fuel-charge transit from anywhere in the universe.

Note: This is old syntax, in that each player has their own spawn planet. It would be better to describe "spawn" as being a world designated as a hub-planet where users can move their ships for meeting up with other players.

#### Points of Interest

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /poi [name]
    - **Permission:** `poi.poi`
    - **Description:** Move a player's ship to the specified POI, or list all POIs if no argument provided.
    - This command does not cost fuel to use, or even require FTL to be enabled.

  - /set_poi (name)
    - **Permission:** `poi.set_poi`
    - **Description:** Sets the planet the user is on as a POI with the specified name.

  - /del_poi (name)
    - **Permission:** `poi.set_poi`
    - **Description:** Removes the specified POI from the POI list.

#### Player Manager

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /kick (username) [reason]
     - **Permission:** `player_manager.kick`
     - **Description:** Kicks a player off the server. Fails if the user is 
     the same or lower rank than the target.

  - /ban (username) (reason)
     - **Permission:** `player_manager.ban`
     - **Description:** Bans a player from connecting to the server. Fails if 
     the user is the same or lower rank than the target.

  - /unban (username)
     - **Permission:** `player_manager.ban`
     - **Description:** Unbans a player from connecting to the server.

  - /list_bans
     - **Permission:** `player_manager.ban`
     - **Description:** Display the current bans in effect.

  - /list_players
     - **Permission:** `player_manager.list_players`
     - **Description:** Lists all players in the player database.
     
  - /user
     - **Permission:** `player_manager.user`
     - **Description:** Manage permissions and ranks.
     - /user addperm (user) (permission): Adds a permission to a player. 
     Fails if the user doesn't have the permission.
     - /user rmperm (player) (permission): Removes a permission from a 
     player. Fails if the user doesn't have the permission, or if the target's 
     priority is higher than the user's.
     - /user addrank (player) (rank): Adds a rank to a player. Fails if the 
     rank to be added is equal to or greater than the user's highest rank.
     - /user rmrank (player) (rank): Removes a rank from a player. Fails if 
     the target outranks or is equal in rank to the user.
     - /user listperms (player): Lists the permissions a player has.
     - /user listranks (player): Lists the ranks a player has.

  - /del_player (Username) [*force]
     - **Permission:** `player_manager.delete_player`
     - **Description:** Removes a player's entry from the player database. 
     Fails if the user is the same or lower rank than the target.
     - In order to remove a player who is currently connected, you must use the *force keyword as well.

#### General Commands

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /who
     - **Permission:** `general_commands.who`
     - **Description:** Lists all players currently logged in.
  - /here
     - **Permission:** `general_commands.who`
     - **Description:** Lists all players on the same planet as the user.
  - /whois (username)
     - **Permission:** `general_commands.whois`
     - **Description:** Displays detailed information about a player.

  - /serverwhoami
     - **Permission:** `general_commands.whoami`
     - **Description:** Displays detailed information about yourself.

  - /nick [user to rename](new username)
     - **Permission:** `general_commands.nick`, `general_commands.nick_others`
     - **Description:** Change your current chat nickname to something else,
      or rename another player.

  - /give (username) (item name) [quantity]
     - **Permission:** `general_commands.give_item`
     - **Description:** Give a player (an) item(s) based on asset name. If no quantity is provided, default to 1.
     - **Aliases:** /item , /give_item
     
  - /maintenance_mode
     - **Permission:** `general_commands.maintenance_mode`
     - **Description:** Toggles maintenance mode. While maintenance mode is 
     active, new connections without the `general_commands.maintenance_bypass` 
     permission will be refused.
     
  - /shutdown [time]
     - **Permission:** `general_commands.shutdown`
     - **Description:** Shuts down the server, after the given time, or five
      seconds if not specified.

#### Help

- ***Depend on:***
  - Command Dispatcher

- ***Commands Provided***
  - /help [command]
     - **Permission:** `help.help`
     - **Description:** Command for providing help with commands.
     - When run without an argument, show the player a list of all available commands to them (at their use level).

#### Chat Manager

- ***Depend on:***
  - Command Dispatcher, Player Manager

- ***Commands Provided***
  - /mute (username)
     - **Permission:** `chat_manager.mute`
     - **Description:** Mutes a player.

  - /unmute (username)
     - **Permission:** `chat_manager.mute`
     - **Description:** Unmutes a player.

#### Chat Enhancements

- ***Depend on:***
  - Command Dispatcher, Player Manager

- ***Commands Provided***
  - /l (message)
     - **Description:** Send a local message.

  - /u (message)
     - **Description:** Sends a universal message.

  - /whisper (recipient) (message)
     - **Permission:** `chat_enhancements.whisper`
     - **Description:** Sends a private message to another user.
     - **Alias:** /w

  - /p (message)
     - **Permission:** Guest
     - **Description:** Sends a message to everyone in your party. If not in a party, defaults to local chat.

  - /reply (message)
    - **Permission:** `chat_enhancements.whisper`
    - **Description:** Sends a private message to the last person to privately message you.
    - **Alias:** /r

  - /ignore (username)
    - **Permission:** `chat_enhancements.ignore`
    - **Description:** Ignores a player, preventing the user from seeing their 
    messages. Run again to remove a player from the ignore list.

#### Emotes

- ***Depend on:***
  - Command Dispatcher, Player Manager

- ***Commands Provided***
  - /me [emote]
     - **Permission:** `emotes.emote`
     - **Description:** Performs a text-emote.
     - When this command is performed with no arguments, a list of built-in actions are sent back to the player.

  - /mel [emote]
     - **Permission:** `emotes.emote`
     - **Description:** Performs a text-emote in local chat.
     - When this command is performed with no arguments, a list of built-in actions are sent back to the player.

#### Privileged Chatter

- ***Depend on:***
  - Command Dispatcher, Player Manager, Chat Enhancements

- ***Commands Provided***
  - /modchat (message)
    - **Permission:** `privileged_chatter.modchat`
    - **Description:** Sends a message visible only to other moderators.
    - **Alias:** /m
  
  - /report (message)
    - **Permission:** `privileged_chatter.report`
    - **Description:** Sends a report message to all online moderators.

  - /broadcast (message)
    - **Permission:** `privileged_chatter.broadcast`
    - **Description:** Broadcasts an admin message to the entire server.

#### New Player Greeter

- ***Depend on:***
  - Command Dispatcher, Player Manager

- ***Commands Provided***
  - None

#### Planet Protect

- ***Depend on:***
  - Command Dispatcher, Player Manager

- ***Commands Provided***
  - /protect
     - **Permission:** `planet_protect.protect`
     - **Description:** Makes a planet protected.

  - /unprotect
     - **Permission:** `planet_protect.unprotect`
     - **Description:** Removes a planet's protection.

  - /add_builder (username)
     - **Permission:** `planet_protect.manage_protection`
     - **Description:** Allow a player build-rights on a protected planet.

  - /del_builder (username)
     - **Permission:** `planet_protect.manage_protection`
     - **Description:** Disallow a player's build-rights on a protected planet.

  - /list_builders
     - **Permission:** `planet_protect.manage_protection`
     - **Description:** Show all players allowed to build on a protected planet.
  
  - Additional permissions:
     - `planet_protect.bypass`: Holders of this permission bypass all planet
      protection.

#### Claims

- ***Depend on:***
  - Command Dispatcher, Player Manager, Planet Protect

- ***Commands Provided***
  - /claim
    - **Permission:** `claims.claim`*
    - **Description:** Claim a planet to be protected.

  - /unclaim
    - **Permission:** `claims.claim`*
    - **Description:** Unclaim and unprotect the planet you're standing on.

  - /add_builder (username)
    - **Permission:** `claims.manage_claims`*
    - **Description:** Add someone to the protected list of your planet.

  - /del_builder (username)
    - **Permission:** `claims.manage_claims`*
    - **Description:** Remove someone from the protected list of your planet.

  - /list_builders
    - **Permission:** `claims.manage_claims`*
    - **Description:** List all of the people allowed to build on this planet.

  - /change_owner (username)
    - **Permission:** `claims.manage_claims`*
    - **Description:** Transfer ownership of the planet to another person.
    
  - /list_claims
    - **Permission:** `claims.claim`
    - **Description:** List all planets the player is owner of.
    
  - /planet_access (arguments...)
    - **Permission:** `claims.planet_access`
    - **Description:** Manage who is allowed or disallowed access to your claim.
    - /planet_access (Player Name) (add/remove): Adds or removes a player from the planet's access list.
    - /planet_access whitelist (true/false): Sets the access list to behave 
    like a whitelist (only players on the list can access) or a blacklist 
    (default, everyone except players on the list can access).
    - /planet_access list: Lists the players on the access list.
    - /planet_access help: Displays the help in-game.
     
  - /set_greeting (message)
    - **Permission:** `claims.manage_claims`
    - **Description:** Sets a custom greeting message that is displayed when players beam onto the planet, or clears it if unspecified.
    - Requires Planet Announcer to be installed.

  - Note: All of the commands except /claim and /list_claims require the user
   to be the owner of the planet.
   
  - Note: /add_builder, /del_builder, and /list_builders override the 
  identically-named commands in Planet Protect, and function mostly the same.

#### Warp

- ***Depend on:***
  - Command Dispatcher, Player Manager
  
- ***Commands Provided***
  - /tp [from player] (to player)
    - **Permission:** `warp.tp_player`
    - **Description:** Warps the specified from player, or self if none, to the specified to player.
    
  - /tps [from player] (to player)
    - **Permission:** `warp.tp_ship`
    - **Description:** Warps the specified from player, or self if none, to the specified to player's ship.
    
#### Planet Announcer

- ***Depend on:***
  - Command Dispatcher, Player Manager
  
- ***Commands Provided***
  - /set_greeting (message)
    - **Permission:** `planet_announcer.set_greeting`
    - **Description:** Sets a custom greeting message that is displayed when players beam onto the planet, or clears it if unspecified.

#### Planet Backups

- *NOT YET IMPLEMENTED*
