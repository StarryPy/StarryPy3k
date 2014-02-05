import asyncio

from nose.tools import *

from plugin_manager import PluginManager
from utilities import path


class TestPluginManager:
    def __init__(self):
        self.plugin_path = path / 'tests' / 'test_plugins'
        self.good_plugin = self.plugin_path / 'test_plugin_2.py'
        self.good_plugin_package = self.plugin_path / 'test_plugin_package'
        self.bad_plugin = self.plugin_path / 'bad_plugin'
        self.bad_path = self.plugin_path / 'bad_path.py'
        self.dependent_plugins = self.plugin_path / "dependent_plugins"
        self.plugin_manager = PluginManager()
        self.loop = None

    def setup(self):
        self.plugin_manager = PluginManager()
        self.loop = asyncio.new_event_loop()

    def test_bad_paths(self):
        assert_raises(FileNotFoundError,
                      self.plugin_manager._load_module, self.bad_path)

    def test_load_good_plugins(self):
        self.plugin_manager.load_plugin(self.good_plugin)
        self.plugin_manager.load_plugin(self.good_plugin_package)
        self.plugin_manager.resolve_dependencies()
        assert_in("test_plugin_2",
                  self.plugin_manager.list_plugins().keys())
        assert_in("test_plugin_1",
                  self.plugin_manager.list_plugins().keys())

    def test_load_bad_plugin(self):
        with assert_raises(SyntaxError):
            self.plugin_manager.load_plugin(self.bad_plugin)
            self.plugin_manager.resolve_dependencies()

    def test_load_plugin_dir(self):
        self.plugin_manager.load_from_path(self.plugin_path)
        self.plugin_manager.resolve_dependencies()
        assert_in("test_plugin_2",
                  self.plugin_manager.list_plugins())
        assert_in("test_plugin_1",
                  self.plugin_manager.list_plugins())
        assert_in("bad_plugin",
                  self.plugin_manager.failed)

    def test_the_do_method(self):
        self.plugin_manager.load_plugin(self.good_plugin)
        self.plugin_manager.load_plugin(self.good_plugin_package)
        self.plugin_manager.resolve_dependencies()
        result = self.loop.run_until_complete(
            self.plugin_manager.do("chat_sent", b""))
        assert_equals(result, True)

    def test_dependency_check(self):
        with assert_raises(ImportError):
            self.plugin_manager.load_plugin(self.dependent_plugins / 'b.py')
            self.plugin_manager.resolve_dependencies()

    def test_dependency_resolution(self):
        self.plugin_manager.load_plugins([
            self.dependent_plugins / 'a.py',
            self.dependent_plugins / 'b.py'
        ])

        self.plugin_manager.resolve_dependencies()

    def test_circular_dependency_error(self):
        with assert_raises(ImportError):
            self.plugin_manager.load_plugin(
                self.dependent_plugins / 'circular.py')
            self.plugin_manager.resolve_dependencies()

    def test_empty_overrides(self):
        self.plugin_manager.resolve_dependencies()
        owners = self.loop.run_until_complete(
            self.plugin_manager.get_overrides())
        assert_equal(owners, set())

    def test_override(self):
        self.plugin_manager.load_plugin(
            self.plugin_path / 'test_plugin_package')
        self.plugin_manager.load_plugin(self.plugin_path / 'test_plugin_2.py')
        self.plugin_manager.resolve_dependencies()
        self.plugin_manager.activate_all()
        overrides = self.loop.run_until_complete(
            self.plugin_manager.get_overrides())
        assert_equal(overrides, {'on_chat_sent'})

    def test_override_caching(self):
        self.plugin_manager.load_plugin(self.plugin_path / 'test_plugin_2.py')
        assert_equal(self.plugin_manager._overrides, set())
        assert_equal(self.plugin_manager._override_cache, set())
        self.plugin_manager.activate_all()
        self.loop.run_until_complete(self.plugin_manager.get_overrides())
        assert_is(self.plugin_manager._override_cache,
                  self.plugin_manager._activated_plugins)
        cache = self.plugin_manager._override_cache
        self.loop.run_until_complete(self.plugin_manager.get_overrides())
        assert_is(self.plugin_manager._override_cache, cache)


    def test_activate(self):
        self.plugin_manager.load_plugin(
            self.plugin_path / 'test_plugin_package')
        self.plugin_manager.load_plugin(self.plugin_path / 'test_plugin_2.py')
        self.plugin_manager.resolve_dependencies()
        self.plugin_manager.activate_all()
        assert_equal({x.name for x in self.plugin_manager._activated_plugins},
                     {'test_plugin_1', 'test_plugin_2'})


