# StarryPy3k

##About
StarryPy3k is the successor to StarryPy. StarryPy is a plugin-driven Starbound
server wrapper that adds a great deal of functionality to Starbound. StarryPy3k
 is written using asyncio is Python 3.

***Please note this is still in very active development and is not ready to be
used on general purpose servers. It should mostly work, but you have been
forewarned.***

## Requirements
Python **3.4.4** or greater is required. Test are only conducted on Python
versions 3.4 and 3.5.

While StarryPy3k **may** work with earlier version of Python, it is not
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

### StarryPy Proxy Configuration
Unfortunately, the example `config.json` file included in the repository is
not comprehensive.  Fortunately, StarryPy will write its runtime configuration
to disk periodically.  Go ahead and start the Starbound server and StarryPy,
and make sure you can connect to your server.  Then disconnect, and open up
`config/config.json`.  Also, open up your Starbound server log, and make a
note of the UUID you were assigned when you connected to your server.  Edit
the obvious things in the configuration file (the Message of the Day, for
example).  Look in particular for the `player_manager` section, and replace
the text telling you to replace it with your UUID.  This will accord you the
privileges of the server owner within StarryPy.  Restart it, and you should be
up and running.

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
StarryPy3k was originally developed by [CarrotsAreMediocre](https://github
.com/CarrotsAreMediocre), who set all the groundwork for AsyncIO and packet
interpreting. Due to personal circumstances, Carrots stepped away from the
project.

After roughly 2 years of laying dormant, Kharidiron, having spent some time
learning the ropes of StarryPy, decided to take the reigns on StarryPy3k.
After many months of staring at the code (and many emails to
CarrotsAreMediocre requesting assistance in understanding just what it is
doing), is feeling a modicum more confident in handling this project and
keeping it running.
