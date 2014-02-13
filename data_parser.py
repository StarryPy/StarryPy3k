import asyncio
from collections import OrderedDict


class Structure:
    def __init__(self, name="default", **kwargs):
        self.name = name
        self.parsers = OrderedDict()
        self.builders = OrderedDict()
        for name, parser, builder in [(x, y[0], y[1]) for
                                      x, y in kwargs.items()]:
            self.parsers[name] = parser
            self.builders[name] = builder

    @asyncio.coroutine
    def parse(self, stream):
        results = OrderedDict()
        for name, parser in self.parsers.items():
            results[parser.name] = yield from parser.parse(stream)
        return results
