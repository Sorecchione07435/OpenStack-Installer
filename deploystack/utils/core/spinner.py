import sys
import termios
import threading
import tty
import time

class Spinner:
    def __init__(self, message="Processing"):
        self.spinner = ["|", "/", "-", "\\"]
        self.idx = 0
        self.running = False
        self.thread = None
        self.message = message
        self._lock = threading.Lock()
        self._stdin_fd = sys.stdin.fileno()
        self._old_term = None

    def start(self):
        self.running = True
        self.idx = 0

        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        self._old_term = termios.tcgetattr(self._stdin_fd)
        tty.setcbreak(self._stdin_fd)
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def _spin(self):
        while self.running:
            with self._lock:
                sys.stdout.write(f"\r{self.message} {self.spinner[self.idx]}")
                sys.stdout.flush()
                self.idx = (self.idx + 1) % len(self.spinner)
            time.sleep(0.5)

    def stop(self, done_message="DONE", color="yellow", width=80):
        self.running = False
        if self.thread:
            self.thread.join()

        if self._old_term:
            termios.tcsetattr(self._stdin_fd, termios.TCSADRAIN, self._old_term)

        color_codes = {
            "yellow": "\033[33m",
            "red": "\033[31m",
            "green": "\033[32m",
            "reset": "\033[0m"
        }
        color_code = color_codes.get(color, "")
        reset_code = color_codes["reset"]
        message_aligned = self.message.ljust(width)

        sys.stdout.write(f"\r{message_aligned}[ {color_code}{done_message}{reset_code} ]\n\033[?25h")
        sys.stdout.flush()