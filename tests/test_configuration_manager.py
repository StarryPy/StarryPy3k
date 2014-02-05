import json
import unittest
from configuration_manager import ConfigurationManager
import utilities


class ConfigurationManagerTests(unittest.TestCase):
    def setUp(self):
        self.config = ConfigurationManager()
        self.base_path = utilities.path / 'tests' / 'test_config'
        self.output_path = self.base_path / 'test_outputs' / 'out.json'
        self.trivial_config_path = self.base_path / 'trivial_config.json'
        self.complex_config_path = self.base_path / 'complex_config.json'
        self.merged_path = self.base_path / 'complex_merged_config.json'
        self.config_with_utf_8_path = self.base_path / 'unicode_config.json'

    def test_config_manager_loads_correct_path(self):
        with open(str(str(self.trivial_config_path))) as f:
            raw = f.read()
        self.config.load_config(str(self.trivial_config_path))
        self.assertEquals(raw, self.config._raw_config)

    def test_config_manager_path_set_on_load(self):
        self.config.load_config(self.trivial_config_path)
        self.assertEqual(self.config._path, str(self.trivial_config_path))

    def test_config_manager_load_complex_with_default(self):
        with open(str(self.merged_path)) as f:
            merged = json.load(f)
        self.config.load_config(str(self.complex_config_path), default=True)
        self.assertEquals(merged, self.config.config)

    def test_config_manager_dot_notation(self):
        complex_config_path = str((self.base_path / 'complex_config.json'))
        self.config.load_config(str(complex_config_path))
        self.assertEqual(self.config.config.test1.test5.test7.test8,
                         ["test9", "test10"])
        with self.assertRaises(AttributeError):
            self.config.config.borp

    def test_config_manager_add_dictionary_with_dot_notation(self):
        complex_config_path = str((self.base_path / 'complex_config.json'))
        self.config.load_config(str(complex_config_path))
        self.config.config.testx = {"testy": "testz"}
        self.assertEqual(self.config.config.testx.testy, "testz")

    def test_config_manager_save_to_path(self):
        self.config.load_config(str(self.complex_config_path))
        self.config.save_config(path=str(self.output_path))
        self.assertTrue(self.output_path.exists(),
                        msg="Output file does not exist.")

    def test_config_manager_save_utf_8(self):
        self.config.load_config(str(self.config_with_utf_8_path))
        self.config.save_config(path=str(self.output_path))
        with self.config_with_utf_8_path.open() as f:
            original = f.read()
        with self.output_path.open() as f:
            saved = f.read()
        self.assertEqual(original, saved)

    def test_config_manager_with_path_object(self):
        try:
            self.config.load_config(self.trivial_config_path)
        except TypeError:
            self.fail("Didn't load from Path() object.")


if __name__ == "__main__":
    unittest.main()