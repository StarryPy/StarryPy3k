import asyncio
import unittest
from plugin_manager import PluginManager
from utilities import path


class PluginManagerTest(unittest.TestCase):
    def setUp(self):
        self.plugin_path = path / 'tests' / 'test_plugins'
        self.good_plugin = self.plugin_path / 'test_plugin_2.py'
        self.good_plugin_package = self.plugin_path / 'test_plugin_package'
        self.bad_plugin = self.plugin_path / 'bad_plugin'
        self.bad_path = self.plugin_path / 'bad_path.py'
        self.dependent_plugins = self.plugin_path / "dependent_plugins"
        self.plugin_manager = PluginManager()
        self.loop = asyncio.new_event_loop()


    def test_bad_paths(self):
        self.assertRaises(FileNotFoundError,
                          self.plugin_manager._load_module, self.bad_path)

    def test_load_good_plugins(self):
        self.plugin_manager.load_plugin(self.good_plugin)
        self.plugin_manager.load_plugin(self.good_plugin_package)
        self.plugin_manager.resolve_dependencies()
        self.assertIn("test_plugin_2",
                      self.plugin_manager.list_plugins().keys())
        self.assertIn("test_plugin_1",
                      self.plugin_manager.list_plugins().keys())

    def test_load_bad_plugin(self):
        with self.assertRaises(SyntaxError):
            self.plugin_manager.load_plugin(self.bad_plugin)
            self.plugin_manager.resolve_dependencies()

    def test_load_plugin_dir(self):
        self.plugin_manager.load_from_path(self.plugin_path)
        self.plugin_manager.resolve_dependencies()
        self.assertIn("test_plugin_2",
                      self.plugin_manager.list_plugins())
        self.assertIn("test_plugin_1",
                      self.plugin_manager.list_plugins())
        self.assertIn("bad_plugin",
                      self.plugin_manager.failed)

    def test_do(self):
        self.plugin_manager.load_plugin(self.good_plugin)
        self.plugin_manager.load_plugin(self.good_plugin_package)
        self.plugin_manager.resolve_dependencies()
        result = self.loop.run_until_complete(
            self.plugin_manager.do("chat_sent", b""))
        self.assertEquals(result,
                          [True, True])

    def test_dependency_check(self):
        with self.assertRaises(ImportError):
            self.plugin_manager.load_plugin(self.dependent_plugins / 'b.py')
            self.plugin_manager.resolve_dependencies()

    def test_dependency_resolution(self):
        try:
            self.plugin_manager.load_plugins([
                self.dependent_plugins / 'a.py',
                self.dependent_plugins / 'b.py'
            ])

            self.plugin_manager.resolve_dependencies()
        except:
            self.fail("Dependency resolution test failed.")

    def test_circular_dependency_error(self):
        with self.assertRaises(ImportError):
            self.plugin_manager.load_plugin(
                self.dependent_plugins / 'circular.py')
            self.plugin_manager.resolve_dependencies()