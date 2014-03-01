import tornado.ioloop
import tornado.web
from tornado.platform.asyncio import AsyncIOMainLoop

from base_plugin import BasePlugin
from utilities import path


class WebHandler(tornado.web.RequestHandler):
    def get(self, *args, **kwargs):
        players = [player for player in
                   self.player_manager.players.values()]
        self.render("static/who.html", title="Who's online",
                    players=players)


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
    (r'/css/(.*)', tornado.web.StaticFileHandler, {'path': str(path
                                                               / "plugins"
                                                               / "static"
                                                               / "css")})])
