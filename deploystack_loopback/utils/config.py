from pathlib import Path
import tomllib

class Config:

    DEFAULT_PATH = Path("/etc/deploystack-loopback.conf")

    def __init__(self, path=None):
        self.path = Path(path or self.DEFAULT_PATH)

        with self.path.open("rb") as f:
            self.data = tomllib.load(f)

    def resource(self, name):
        return self.data[name]

    def resource_names(self):
        return [
            name for name in self.data if name != "lvm"
        ]

    @property
    def lvm_config(self):
        return self.data["lvm"]["config"]