import json

from nose.tools import assert_equals, assert_true, assert_raises

from configuration_manager import ConfigurationManager
import utilities


class TestConfigurationManager:

    def setup(self):
        self.base_path = utilities.path / 'tests' / 'test_config'
        self.output_path = self.base_path / 'test_outputs' / 'out.json'
        self.trivial_config_path = self.base_path / 'trivial_config.json'
        self.complex_config_path = self.base_path / 'complex_config.json'
        self.merged_path = self.base_path / 'complex_merged_config.json'
        self.config_with_utf_8_path = self.base_path / 'unicode_config.json'
        self.config = ConfigurationManager()

    def test_config_manager_loads_correct_path(self):
        with open(str(str(self.trivial_config_path))) as f:
            raw = f.read()
        self.config.load_config(str(self.trivial_config_path))
        assert_equals(raw, self.config._raw_config)

    def test_config_manager_path_set_on_load(self):
        self.config.load_config(self.trivial_config_path)
        assert_equals(self.config._path, self.trivial_config_path)

    def test_config_manager_load_complex_with_default(self):
        with open(str(self.merged_path)) as f:
            merged = json.load(f)
        self.config.load_config(str(self.complex_config_path), default=True)
        assert_equals(merged, self.config.config)

    def test_config_manager_dot_notation(self):
        complex_config_path = str((self.base_path / 'complex_config.json'))
        self.config.load_config(str(complex_config_path))
        assert_equals(self.config.config.test1.test5.test7.test8,
                      ["test9", "test10"])
        with assert_raises(AttributeError):
            self.config.config.borp

    def test_config_manager_add_dictionary_with_dot_notation(self):
        complex_config_path = str((self.base_path / 'complex_config.json'))
        self.config.load_config(str(complex_config_path))
        self.config.config.testx = {"testy": "testz"}
        assert_equals(self.config.config.testx.testy, "testz")

    def test_config_manager_save_to_path(self):
        self.config.load_config(str(self.complex_config_path))
        self.config.save_config(path=str(self.output_path))
        assert_true(self.output_path.exists(),
                    msg="Output file does not exist.")

    def test_config_manager_save_utf_8(self):
        self.config.load_config(str(self.config_with_utf_8_path))
        self.config.save_config(path=str(self.output_path))
        with self.config_with_utf_8_path.open() as f:
            original = f.read()
        with self.output_path.open() as f:
            saved = f.read()
        assert_equals(original, saved)

    def test_config_manager_with_path_object(self):
        self.config.load_config(self.trivial_config_path)


if __name__ == "__main__":
    unittest.main()