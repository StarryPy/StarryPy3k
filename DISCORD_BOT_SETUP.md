# StarryPy Discord Bot

StarryPy includes a plugin that allows you to connect a bot to a Discord 
server that will relay messages between the Starbound and Discord servers. 
If the IRC bot also included with StarryPy is enabled, the Discord and IRC 
plugins will also relay messages between each other.

## Using the Discord Bot
The Discord bot plugin uses the [discord.py](https://github.com/Rapptz/discord.py)
library, and will not work without it.

To use the Discord bot, you will need to create a Discord application. Go to 
[this page](https://discordapp.com/developers/applications/me) and click the
 "New Application" button.
 Give your bot a descriptive name; giving it an avatar or description is optional.
 
 Once you have created your application, you must create a bot user by clicking the "Create a Bot User" option on 
 the application's page.
 
 To add the bot to your server, go to `https://discordapp.com/oauth2/authorize?&client_id=CLIENT_ID&scope=bot&permissions=0`
 (replacing `CLIENT_ID` with your application's client ID) and add the 
 bot to your server.
 
 Once the bot is added to your server, copy the token 
 and client id from the application to the fields in config.json. Get the 
 channel id for a given channel by enabling Developer Mode in 
 Discord, right-clicking a channel, and clicking "Copy ID," then paste this 
 ID into the "channel" field in config.json. Your bot should now be fully 
 configured and ready to use.