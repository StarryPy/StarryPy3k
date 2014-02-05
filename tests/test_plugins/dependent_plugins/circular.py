from base_plugin import BasePlugin


class A(BasePlugin):
    name = "a"
    depends = ["b"]


class B(BasePlugin):
    name = "b"
    depends = ["c"]


class C(BasePlugin):
    name = "c"
    depends = ["a"]
