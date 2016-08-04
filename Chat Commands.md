# StarryPy Chat Commands

On its own, StarryPy is simply a framework for inspecting (and modifying) Starbound packets, as they are transmitted between the clients and the server. It is up to StarryPy's plugins to make use of this framework, by providing its users with commands to extend the in-game experience and administration.

This document seeks to enumerate the commands that are available to the users. Section one provides a quick list off all the commands, as organized by level of user access required. Section two is organized by plugin, providing detailed usage information. Section two will be ordered by functionality and dependence.

Note: This document is likely to change often, as well as become outdated quickly, as this software develops. For that, I apologize in advance.

## Commands by User Level

***Guest Commands***

- /help
- /local , /l
- /me , /em
- /motd
- /spawn
- /universe , /u
- /whisper , /w
- /who
- /whoami

***Registered User Commands***

- /nick

***Moderator Commands***

- /ban
- /kick
- /list_bans
- /mute
- /set_motd
- /show_spawn
- /unmute

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

***SuperAdmin Commands***

- /set_spawn
- /del_player

***Owner Commands***

- /grant , /promote

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

  - /list_bans
     - **Role:** Moderator
     - **Description:** Display the current bans in effect.

  - /list_players
     - **Role:** Admin
     - **Description:** Lists all players in the player database.

  - /grant (Role) (Username)
     - **Role:** Owner
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

  - broadcast (message)
     - **Role:** Admin
     - **Description:** Send a message to everyone on the server. Text is dispalyed in red, to act as an alert.

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
  - /mute
     - **Role:** Moderator
     - **Description:** Mutes a player.

  - /unmute
     - **Role:** Moderator
     - **Description:** Unmutes a player.

#### Chat Enhancements

- ***Depend on:***
  - Command Dispatcher, Player Manger

- ***Commands Provided***
  - /local (message)
     - **Role:** Guest
     - **Description:** Send a local message.
     - **Alias:** /l

  - /universe (message)
     - **Role:** Guest
     - **Description:** Sends a universal message.
     - **Alias:** /u

  - /whisper (recipient) (message)
     - **Role:** Guest
     - **Description:** Sends a private message to another user.
     - **Alias:** /w

#### Emotes

- ***Depend on:***
  - Command Dispatcher, Player Manger

- ***Commands Provided***
  - /me [emote]
     - **Role:** Guest
     - **Description:** Performs a text-emote.
     - **Alias:** /em
     - When this command is performed with no arguments, a list of built-in actions are sent back to the player.

#### Privileged Chatter

- *NOT YET IMPLEMENTED*

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
     - **Description:** 

  - /unprotect
     - **Role:** Admin
     - **Description:** 

  - /add_builder
     - **Role:** Admin
     - **Description:** 

  - /del_builder
     - **Role:** Admin
     - **Description:** 

  - /list_builders
     - **Role:** Admin
     - **Description:** 

#### Planet Backups

- *NOT YET IMPLEMENTED*