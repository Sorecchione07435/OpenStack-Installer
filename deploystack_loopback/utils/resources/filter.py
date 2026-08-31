from pathlib import Path
import subprocess
import re

class LVMFilter:
    def __init__(self, config):
        self.config = Path(config)

    def _parse_filter(self, output):
        devices = []

        for device in re.findall(r'a\|\^(.+?)\\?\$\|', output):
            devices.append(device)

        return devices

    def show(self):
        result = subprocess.run(["/usr/sbin/lvmconfig", "--type", "current", "devices/filter"], capture_output=True, text=True, check=True)

        return  self._parse_filter(result.stdout)