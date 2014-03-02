import json
from pathlib import Path

from utilities import recursive_dictionary_update, DotDict


class ConfigurationManager:
    def __init__(self):
        self._raw_config = None
        self._raw_default_config = None
        self._config = {}
        self._dot_dict = None
        self._path = None

    @property
    def config(self):
        if self._dot_dict is None:
            self._dot_dict = DotDict(self._config)
        return self._dot_dict

    def load_config(self, path, default=False):
        if not isinstance(path, Path):
            path = Path(path)
        if default:
            self.load_defaults(path)
        try:
            with path.open() as f:
                self._raw_config = f.read()
        except FileNotFoundError:
            path.touch()
            with path.open("w") as f:
                f.write("{}")
            self._raw_config = "{}"
        self._path = path
        recursive_dictionary_update(self._config, json.loads(self._raw_config))
        if "plugins" not in self._config:
            self._config['plugins'] = DotDict({})

    def load_defaults(self, path):
        path = Path(str(path) + ".default")
        with path.open() as f:
            self._raw_default_config = f.read()
        recursive_dictionary_update(self._config,
                                    json.loads(self._raw_default_config))

    def save_config(self, path=None):
        if path is None:
            path = self._path
        temp_path = Path(str(path) + "_")
        with temp_path.open("w") as f:
            json.dump(self.config, f, sort_keys=True, indent=4,
                      separators=(',', ': '), ensure_ascii=False)
        path.unlink()
        temp_path.rename(path)

    def get_plugin_config(self, plugin_name):
        if plugin_name not in self.config:
            storage = DotDict({})
            self.config.plugins[plugin_name] = storage
        else:
            storage = self.config.plugins[plugin_name]
        return storage
