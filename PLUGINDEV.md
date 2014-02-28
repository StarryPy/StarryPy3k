# StarryPy3k

##About
StarryPy3k is the successor to StarryPy. StarryPy is a plugin-driven Starbound server wrapper that adds a great deal of functionality to Starbound. StarryPy3k is written using asyncio is Python 3.

***Please note this is still in very active development and is not ready to be used on general purpose servers. It should mostly work, but you have been forewarned.***

## Requirements
Requirements can be found in README.md. The version of Python used as of time of writing is 3.4.0 RC2.

## Quick-Start Guide
Looking to add features to your own flavor of StarryPy? This guide will give you a brief overview of the basic code structure of a plugin, and how you can suscribe to certain events to give functionality to your plugin.

### Imports
>In a standard installation, StarryPy comes with 2 base plugin classes that you can use; BasePlugin and SimpleCommandPlugin. Do note that you can only extend off one class at a time, for a single plugin class.
#### BasePlugin
BasePlugin is the parent of all StarryPy plugins and contains all the event hooks that StarryPy provides, from which you can suscribe to by overriding the same function name in your plugin body:
```python
from base_plugin import BasePlugin
```
#### SimpleCommandPlugin
SimpleCommandPlugin provides an extension to handle commands sent via chat (e.g "/help", "/kick"). It also provides a command decorator from which you can set details such as a help/syntax string. More on this will be explained in a later portion of the guide.
```python
from base_plugin import SimpleCommandPlugin, command
```

### Plugin Class
>The plugin class body is where the actual functionality of your plugin takes place. For simplicity, BasePlugin will be used as an example. The structure of the plugin class is as follows:
```python
class MyPlugin(BasePlugin):
	name = "my_plugin"
	depends = ["some_plugin"]
	def activate(self):
		super().activate()
```
* **name** is the identifier for your plugin, so other plugins will be able to find your plugin through the dictionary by using your identifier as a key.
* **depends** holds a list of plugins (by name) to load BEFORE your plugin loads. This is to ensure the required dependencies for your plugin are loaded.
* **activate()** is the entry point for all plugins. When the plugin loader goes through the list of plugins to load, it will call activate() for each plugin. super().activate() is required as it tells the parent class to load first so your plugin is able to suscribe to events.

### Events
>StarryPy has many events that your plugin can suscribe to and perform an action. Such events include on_chat_sent, on_client_connect, on_give_item, to name a few. More can be found in **base_plugin.py**

>To suscribe to an event, just create a definition with the same signature in your plugin class like so:
```python
def on_chat_sent(self, data, protocol):
	print("on_chat_sent got triggered!")
```
* **data** contains a parsed list of values in the data packet that StarryPy intercepted. You can access the values in this list by accessing it via a key (e.g data['parsed']['message'])
* **protocol** contains the handle of the player/entity that triggered the event. Inside this there are many useful properties that you can use, such as "protocol.player.name" and "protocol.player.roles", giving you the name and permissions respectively. 

### Configuration & Logging
>StarryPy uses a centralized JSON configuration to save/load plugin configuration data. The config object can be accessed very simply in the plugin class by the following:
```python
self.my_config_value = self.config.config.my_plugin["my_config_value"]
```

>Similarly, logging functionality has been built into StarryPy and can be accessed easily. There are 3 main loggers that StarryPy includes, one for logging, one for debugging and one for errors and warnings. They can be accessed like so:
```python
self.logger.info("This is a regular msg")	#this will log a timestamped message with the plugin name that called in server.log
self.logger.debug("This is a debug msg")	#same as above, but it goes into debug.log and is prefixed with DEBUG
self.logger.warning("This is a warning msg")	#same as above, but it goes into server.log and is prefixed with WARN or ERROR
```
 
