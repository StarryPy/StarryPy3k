import unittest
from plugin_manager import PluginManager


class PluginManagerTest(unittest.TestCase):
    def test_load_plugins(self):
        pm = PluginManager()
        pm.load_plugins()
