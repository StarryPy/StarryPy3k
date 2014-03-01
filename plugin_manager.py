import asyncio
import importlib.machinery
import inspect
import logging
import pathlib
from types import ModuleType

from base_plugin import BasePlugin
from configuration_manager import ConfigurationManager
from pparser import PacketParser
from utilities import detect_overrides


class PluginManager:
    def __init__(self, config: ConfigurationManager, *, base=BasePlugin,
                 factory=None):
        self.base = base
        self.config = config
        self.failed = {}
        self._seen_classes = set()
        self._plugins = {}
        self._activated_plugins = set()
        self._deactivated_plugins = set()
        self._resolved = False
        self._overrides = set()
        self._override_cache = set()
        self._packet_parser = PacketParser(self.config)
        self._factory = factory
        self.logger = logging.getLogger("starrypy.plugin_manager")

    def list_plugins(self):
        return self._plugins

    @asyncio.coroutine
    def do(self, protocol, action: str, packet: dict):
        """
        Calls an action on all loaded plugins
        """
        try:
            if ("on_%s" % action) in self._overrides:
                packet = yield from self._packet_parser.parse(packet)
                send_flag = True
                for plugin in self._plugins.values():
                    p = getattr(plugin, "on_%s" % action)
                    if not (yield from p(packet, protocol)):
                        send_flag = False
                return send_flag
            else:
                return True
        except:
            self.logger.exception("Exception encountered in plugin on action: "
                                  "%s", action, exc_info=True)
            return True

    def load_from_path(self, plugin_path: pathlib.Path):
        blacklist = ["__init__", "__pycache__"]
        loaded = set()
        for file in plugin_path.iterdir():
            if file.stem in blacklist:
                continue
            if (file.suffix == ".py" or file.is_dir()) and str(
                    file) not in loaded:
                try:
                    loaded.add(str(file))
                    self.load_plugin(file)
                except (SyntaxError, ImportError) as e:
                    self.failed[file.stem] = str(e)
                    print(e)
                except FileNotFoundError:
                    self.logger.warning("File not found in plugin loader.")

    @staticmethod
    def _load_module(file_path: pathlib.Path):
        """
        Attempts to load a module, either from a straight python file or from
        a python package, by appending __init__.py to the end of the path if it
        is a directory.
        """
        if file_path.is_dir():
            file_path /= '__init__.py'
        if not file_path.exists():
            raise FileNotFoundError("{0} doesn't exist.".format(file_path))
        name = "plugins.%s" % file_path.stem
        loader = importlib.machinery.SourceFileLoader(name, str(file_path))
        module = loader.load_module(name)
        return module

    def load_plugin(self, plugin_path: pathlib.Path):
        module = self._load_module(plugin_path)
        classes = self.get_classes(module)
        for candidate in classes:
            candidate.factory = self._factory
            self._seen_classes.add(candidate)

    def get_classes(self, module: ModuleType):
        """
        Uses the inspect module to find all classes in a given module that
        are subclassed from `self.base`, but are not actually `self.base`.
        """
        class_list = []
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                if issubclass(obj, self.base) and obj is not self.base:
                    obj.config = self.config
                    obj.logger = logging.getLogger("starrypy.plugin.%s" %
                                                   obj.name)
                    class_list.append(obj)

        return class_list

    def load_plugins(self, plugins: list):
        for plugin in plugins:
            self.load_plugin(plugin)

    def resolve_dependencies(self):
        """
        Resolves dependencies from self._seen_classes through a very simple
        topological sort. Raises ImportError if there is an unresolvable
        dependency, otherwise it instantiates the class and puts it in
        self._plugins.
        """
        deps = {x.name: set(x.depends) for x in self._seen_classes}
        classes = {x.name: x for x in self._seen_classes}
        while len(deps) > 0:
            ready = [x for x, d in deps.items() if len(d) == 0]
            for name in ready:
                self._plugins[name] = classes[name]()
                del deps[name]
            for name, depends in deps.items():
                to_load = depends & set(self._plugins.keys())
                deps[name] = deps[name].difference(set(self._plugins.keys()))
                for plugin in to_load:
                    classes[name].plugins[plugin] = self._plugins[plugin]
            if len(ready) == 0:
                raise ImportError("Unresolved dependencies found.")
        self._resolved = True

    @asyncio.coroutine
    def get_overrides(self):
        if self._override_cache is self._activated_plugins:
            return self._overrides
        else:
            overrides = set()
            for plugin in self._activated_plugins:
                override = yield from detect_overrides(BasePlugin, plugin)
                overrides.update({x for x in override})
            self._overrides = overrides
            self._override_cache = self._activated_plugins
            return overrides

    def activate_all(self):
        self.logger.info("Activating plugins:")
        for plugin in self._plugins.values():
            self.logger.info(plugin.name)
            plugin.activate()
            self._activated_plugins.add(plugin)

    def deactivate_all(self):
        for plugin in self._plugins.values():
            self.logger.info("Deactivating %s", plugin.name)
            plugin.deactivate()
