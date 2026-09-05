from pathlib import Path
from contextlib import contextmanager

import subprocess
import re
import fcntl

class LVMFilter:
    def __init__(self, config):
        self.config = Path(config)
        self.lock_file = Path("/run/lock/deploystack-lvm-filter.lock")

    @contextmanager
    def _lock(self):

        self.lock_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with self.lock_file.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def _read_devices(self):

        content = self.config.read_text()

        match = re.search(
            r'^\s*filter\s*=\s*\[(.*?)\]',
            content,
            re.MULTILINE | re.DOTALL,
        )

        if not match:
            return []

        devices = re.findall(
            r'"a\|\^(.+?)\\?\$\|"',
            match.group(1),
        )

        return devices

    def _write_dev_loop_devices(self, devices):
        content = self.config.read_text()

        match = re.search(
            r'^\s*filter\s*=\s*\[(.*?)\]',
            content,
            re.MULTILINE | re.DOTALL,
        )

        if not match:
            raise RuntimeError(
                f"LVM filter not found in {self.config}"
            )

        current_filter = match.group(1)

        rules = re.findall(
            r'"([^"]+)"',
            current_filter,
        )

        rules = [
            rule
            for rule in rules
            if not re.match(r'a\|\^/dev/loop\d+\$\|', rule)
            and rule != "r|.*|"
        ]

        for device in devices:
            rule = f"a|^{device}$|"

            if rule not in rules:
                rules.append(rule)

        rules.append("r|.*|")

        new_filter = (
            "filter = [ "
            + ", ".join(f'"{rule}"' for rule in rules)
            + " ]"
        )
        content = re.sub(
            r'^\s*filter\s*=\s*\[.*?\]',
            new_filter,
            content,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )

        self.config.write_text(content)

    def _write_devices(self, devices, exclude_pattern=None):

        def _is_loop_device_rule(rule):
            m = re.search(r'/dev/loop\d+', rule)
            return m is not None

        content = self.config.read_text()

        match = re.search(
            r'^\s*filter\s*=\s*\[(.*?)\]',
            content,
            re.MULTILINE | re.DOTALL,
        )

        if not match:
            raise RuntimeError(
                f"LVM filter not found in {self.config}"
            )

        current_filter = match.group(1)

        rules = re.findall(
            r'"([^"]+)"',
            current_filter,
        )

        rules = [
            rule
            for rule in rules
            if not _is_loop_device_rule(rule)
            and rule != "r|.*|"
        ]

        for device in devices:
            rule = f"a|^{device}$|"
            if rule not in rules:
                rules.append(rule)

        rules.append("r|.*|")

        new_filter = (
            "filter = [ "
            + ", ".join(f'"{rule}"' for rule in rules)
            + " ]"
        )

        content = re.sub(
            r'^\s*filter\s*=\s*\[.*?\]',
            new_filter,
            content,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )

        self.config.write_text(content)

    def _parse_filter(self, output):
        devices = []

        for device in re.findall(r'a\|\^(.+?)\\?\$\|', output):
            devices.append(device)

        return devices

    def show(self):
        result = subprocess.run(["/usr/sbin/lvmconfig", "--type", "current", "devices/filter"], capture_output=True, text=True, check=True)

        return  self._parse_filter(result.stdout)

    def add(self, device):

        with self._lock():

            devices = self._read_devices()

            if device in devices:
                return False

            devices.append(device)

            self._write_devices(devices)

            return True

    def remove(self, device):
        with self._lock():
            devices = self._read_devices()

            if device not in devices:
                return False

            devices.remove(device)

            self._write_devices(devices)

            return True

    def rebuild(self, resources):

        with self._lock():
            devices = []

            for resource in resources:

                loop_dev = resource.loop_device()

                if loop_dev:
                    devices.append(loop_dev)

            self._write_dev_loop_devices(devices)