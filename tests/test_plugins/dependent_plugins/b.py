from base_plugin import BasePlugin


class B(BasePlugin):
    name = "b"
    depends = ["a"]