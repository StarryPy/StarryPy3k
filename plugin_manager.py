import asyncio
import importlib.machinery
import inspect

from base_plugin import BasePlugin
from utilities import detect_overrides


class PluginManager:
    def __init__(self, base=BasePlugin):
        self.base = base
        self._seen_classes = set()
        self._plugins = {}
        self._activated_plugins = set()
        self._deactivated_plugins = set()
        self.failed = {}
        self._resolved = False
        self._overrides = set()
        self._override_cache = set()

    def list_plugins(self):
        return self._plugins

    @asyncio.coroutine
    def do(self, action, packet):
        """
        Calls an action on all loaded plugins
        """
        if ("on_%s" % action) in self._overrides:
            results = []
            for plugin in self._plugins.values():
                p = getattr(plugin, "on_%s" % action)
                print(p)
                result = yield from p(packet)
                print(result)
                results.append(result)
            print(results)
            return results
        else:
            return True

    def load_from_path(self, plugin_path):
        blacklist = ["__init__", "__pycache__"]
        loaded = set()
        for file in plugin_path.iterdir():
            if file.stem in blacklist:
                continue
            if (file.suffix == ".py" or file.is_dir()) and str(
                    file) not in loaded:
                try:
                    loaded.add(str(file))
                    print(file)
                    self.load_plugin(file)
                except (SyntaxError, ImportError) as e:
                    self.failed[file.stem] = str(e)
                    print(e)
                except FileNotFoundError:
                    print("File not found")

    @staticmethod
    def _load_module(file_path):
        """
        Attempts to load a module, either from a straight python file or from
        a python package, by appending __init__.py to the end of the path if it
        is a directory.
        """
        if file_path.is_dir():
            file_path /= '__init__.py'
        if not file_path.exists():
            raise FileNotFoundError("{0} doesn't exist.".format(str(file_path)))
        name = "starrypy3.%s" % file_path.stem
        loader = importlib.machinery.SourceFileLoader(name, str(file_path))
        module = loader.load_module(name)
        return module

    def load_plugin(self, plugin_path):
        print(str(plugin_path))
        print(plugin_path)
        module = self._load_module(plugin_path)
        classes = self.get_classes(module)
        for candidate in classes:
            self._seen_classes.add(candidate)

    def get_classes(self, module):
        """
        Uses the inspect module to find all classes in a given module that
        are subclassed from `self.base`, but are not actually `self.base`.
        """
        class_list = []
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                if issubclass(obj, self.base) and obj is not self.base:
                    class_list.append(obj)
        return class_list

    def load_plugins(self, plugins):
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
        for plugin in self._plugins.values():
            print(plugin)
            plugin.activate()
            self._activated_plugins.add(plugin)




