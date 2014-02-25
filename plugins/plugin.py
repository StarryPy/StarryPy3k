import tornado.ioloop
import tornado.web
from tornado.platform.asyncio import AsyncIOMainLoop

from base_plugin import BasePlugin


class WebHandler(tornado.web.RequestHandler):
    def get(self, *args, **kwargs):
        players = [player.name for player in
                   self.player_manager.players.values()]
        self.render("static/who.html", title="Who's online",
                    items=players, count=len(players))


class WebManager(BasePlugin):
    name = "web_manager"
    depends = ['player_manager']

    def activate(self):
        WebHandler.web_manager = self
        WebHandler.factory = self.factory
        WebHandler.player_manager = self.plugins.player_manager

        AsyncIOMainLoop().install()
        application.listen(8888)


application = tornado.web.Application([
    (r"/", WebHandler),
])