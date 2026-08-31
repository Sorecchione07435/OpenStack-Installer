from pathlib import Path
import subprocess

class Loopback:
    def __init__(self, config):
        self.image = Path(config["image"])
        self.vg = config["vg"]
        self.state_file = Path(config["state_file"])

    def attach(self):

        if not self.image.is_file():
            raise FileNotFoundError(f"Image not found: {self.image}")

        loop_dev = self._find_loop_device()

        if loop_dev:
            return loop_dev

        result = subprocess.run(["/sbin/losetup", "--find", "--show", str(self.image)], capture_output=True, text=True, check=True)

        loop_dev = result.stdout.strip()
        self._save_state(loop_dev)

        return loop_dev

    def detach(self):

        loop_dev = self._find_loop_device()

        if not loop_dev:
            return

        subprocess.run(["/sbin/losetup", "--detach", loop_dev], check=True)

        self.state_file.unlink(missing_ok=True)

    def check(self):
        result = {
            "image": str(self.image),
            "image_exists": self.image.is_file(),
            "loop_device": None,
            "attached": False,
        }

        if not result["image_exists"]:
            return result

        loop_dev = self._find_loop_device()

        if loop_dev:
            result["loop_device"] = loop_dev
            result["attached"] = True

        return result

    def _find_loop_device(self):
        result = subprocess.run(["/sbin/losetup", "--associated", str(self.image)], capture_output=True, text=True, check=True)

        if not result.stdout.strip():
            return None

        return result.stdout.split(":", 1)[0]

    def _save_state(self, loop_dev):
        self.state_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.state_file.write_text(
            f"{loop_dev}\n"
        )