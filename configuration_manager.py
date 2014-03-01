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
        with path.open() as f:
            self._raw_config = f.read()
        self._path = path
        recursive_dictionary_update(self._config, json.loads(self._raw_config))

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
