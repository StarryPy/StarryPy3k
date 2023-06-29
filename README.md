# StarryPy3k

## About
StarryPy3k is the successor to StarryPy. StarryPy is a plugin-driven Starbound
server wrapper that adds a great deal of functionality to Starbound. StarryPy3k
 is written using asyncio in Python 3.11.

***Please note this is still in very active development and is not ready to be
used on general purpose servers. It should mostly work, but you have been
forewarned.***

## Requirements
Due to an upgrade of the Discord API, Python **3.8** or greater is required. 
Tests are only conducted on Python version 3.11.

While StarryPy3k **may** work with earlier or later versions of Python, it is not
recommended and will not be readily supported.

## Installation
If you are installing during the development phase, please clone the repository
 with git. While it is not strictly necessary, it is highly encouraged to
 run your StarryPy3k instance from a virtual environment, as future plugins
 may require more Python modules than are currently listed (eg - IRC3), and
 using a virtual environment helps to keep a clean namespace and reduce the
 chance of bugs.

### Starbound Server Configuration
StarryPy works as a benevolent "man in the middle" between the Starbound game
client and the Starbound dedicated server, in effect acting as a proxy server.
As such, for easiest transition from a "Vanilla" server to one enhanced by
StarryPy, you need to set your Starbound server to accept incoming connections
on a new TCP port.  By default, this will be the port one lower than standard,
to wit: 21024.  To accomplish this, edit your `starbound_server.config`.  Look
for the lines below, and change them to specify port 21024:

```
  "gameServerPort" : 21025,
  [...]
  "queryServerPort" : 21025,
```

While editing your `starbound_server.config`, you should also add some accounts
for your server's staff, if you have not done so already. StarryPy3k's
basic_auth plugin uses Starbound's account system to authenticate privileged
users (moderator and up), so you will need at least one account before your
staff can join the server. Look for the lines below:

```
  "serverUsers" : {
  },
```

And add some accounts (preferably one per staff member) using the format below.
Note: you do **not** need to set "admin" to "false". Set it to "true" if you
would like this account to have administrator privileges on the underlying
Starbound dedicated server.

```
  "serverUsers" : {
    "repalceWithAccountName" : {
      "admin" : false,
      "password" : "replaceWithAccountPassword"
    },
    "repalceWithAnotherAccountName" : {
      "admin" : false,
      "password" : "replaceWithAnotherAccountPassword"
    }
  },
```

### StarryPy Proxy Configuration
An example configuration file, `config.json.default`, is provided in the
`config` directory.  Copy that file to a new one named `config.json` in the
same location.  Open it in your text editor of choice.  The following are the
most likely changes you will have to make:

```
        "basic_auth": {
            "enabled": true,
            "owner_sb_account": "-- REPLACE WITH OWNER ACCOUNT --",
            "staff_sb_accounts": [
                "-- REPLACE WITH STARBOUND ACCOUNT NAME --",
                "-- REPLACE WITH ANOTHER --",
                "-- SO ON AND SO FORTH --"
            ]
        },
```

The section above is used by StarryPy3k's basic_auth plugin to define
Starbound accounts that staff members can use to authenticate. Edit the example
above to use **only** the account **names** (no passwords) that you just set up
in your `starbound_server.config` file.

```
        "irc_bot": {
            "channel": "#YourChannel",
            "log_irc": false,
            "server": "irc.example.com",
            "strip_colors": true,
            "username": "Replace With Valid IRC Nick"
        },
```

This section controls the built-in IRC-to-Starbound bridge.  It will be active
if you have the `irc3` Python module installed on your system.  Edit the sample
values here to match your preferred IRC server, bot nick, et cetera.  Chat in
the Starbound server will be relayed to the specified IRC channel, and vice
versa.  You can also see who is on the server from IRC by saying `.who` in the
IRC channel (we cannot use `/` as the command leader in IRC for obvious reasons.

```
        "motd": {
            "message": "Insert your MOTD message here. ^red;Note^reset; color codes work."
        },
        "new_player_greeters": {
            "gifts": {},
            "greeting": "This message will be displayed to players the first time StarryPy sees them connect."
        },
```

The MOTD, or Message Of The Day, will be displayed to all players when they
connect to the Starbound server.  You can update this in-game by using the
`/set_motd` command.  The next section allows you to specify a message to be
displayed to any players the first time they connect to the server.  You can
also have StarryPy give items to new players by enumarating them in the `gifts`
property.  Use Starbound's names for items as specified in its `.json` files.

```
        "player_manager": {
            "owner_uuid": "!--REPLACE WITH YOUR UUID--!",
            "player_db": "config/player"
        },
```

Replace the obvious value here with your UUID.  This is how StarryPy will
recognize you as the owner of the server and accord you the relevant rights
and privileges.  You can find your UUID by watching the Starbound server log
as you connect, by using the `list` RCON command, or by observing the names
of your save files on the computer you use to play Starbound.

Once you have finished editing `config.json`, copy the `permissions.json.default`
 file to `permissions.json` and edit it to your liking. Example of 
 permissions format is provided below:
 ```
"Role Name": {
  "priority": 100000, // This determines the role heirarchy for administrative commands such as /kick, /ban, and /user
  "prefix": "^#F7434C;", // This role's chat prefix, typically a color
  "inherits": [ // Roles to inherit permissions from
    "Another Role"
  ],
  "permissions": [ // An array of permissions; see permissions.json.default for all the permissions included
    "special.allperms"
  ]
}
```

### Starting the proxy
Starting StarryPy is as simple as issueing the command `python3 ./server.py`
once you have finised editing `config/config.json` and `config/permissions
.json`.  To terminate the proxy, either press `^C` in an interactive 
terminal session, or send it an `INT` signal.

### Running under Docker
StarryPy now includes a basic Docker configuration.  To run this image, 
all you need to do is run:

```bash
  docker run -p 21025:21025 starrypy/starrypy:1.0.0
```

StarryPy exports a volume at /app/config which stores your configuration file and 
the various databases.  You can create your own data container for this volume to persist
your configuration and data even if you rebuild or upgrade StarryPy, or use volume 
mount points to share a directory from your host server into the container.

To use a storage volume, create a volume with:

```bash
docker volume create --name sb-data
```

Then provide it as part of your startup command:

```bash
docker run -d --name starry -p 20125:21025 -v sb-data:/app/config starrypy/starrypy:1.0.0
```

You can edit the config by mounting the volume into another container with your favorite text editor:
```bash
docker run --rm -v sb-data:/app/config -ti thinca/vim /app/config/config.json
```

If you'd rather map a directory on your host, just provide that as an argument to -v instead:

```bash
docker run -d --name starry -p 20125:21025 -v /opt/wherever/you/want/it:/app/config starrypy/starrypy:1.0.0
```

You can also run as a low-privileges user, with starry only having access to write to its config volume:
```bash 
docker run -d --name starry -p 20125:21025 -v /opt/wherever/you/want/it:/app/config --user 1002 starrypy/starrypy:1.0.0
```


Please note that this is a Linux-based docker container, so it won't work properly on Docker
for Windows in Windows Container mode.

## Contributing
Contributions are highly encouraged and always welcome. Please feel free to
open an issue on GitHub if you are having an error, or wish to make a
suggestion. If you're feeling really motivated, fork the repo and contribute
 some code.

In addition, plugin development is encouraged. There are still a few features
missing from the core (particularly in the role system). A more comprehensive
guide on plugin development is in the works. Please note that plugins will not
work without modification from the original version of StarryPy.

If you would like to talk with other contributors/ask questions about
development, please join #StarryPy on irc.freenode.net, or chat with us on
[gitter](https://gitter.im/StarryPy).

## History
StarryPy3k was originally developed by [CarrotsAreMediocre](https://github.com/CarrotsAreMediocre), who set all the groundwork for AsyncIO and packet
interpreting. Due to personal circumstances, Carrots stepped away from the
project.

After roughly 2 years of laying dormant, Kharidiron, having spent some time
learning the ropes of StarryPy, decided to take the reigns on StarryPy3k.
After many months of staring at the code (and many emails to
CarrotsAreMediocre requesting assistance in understanding just what it is
doing), is feeling a modicum more confident in handling this project and
keeping it running.