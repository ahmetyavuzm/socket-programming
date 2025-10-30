# utils/logger.py
import threading
from datetime import datetime
from colorama import Fore, Style


class SimpleLogger:
    """Thread-safe file logger used by both Server and Peer."""

    _lock = threading.Lock()

    def __init__(self, logfile: str):
        self.logfile = logfile

    def log(self, message: str, console: bool = True):
        """Write a message to log file and optionally to console."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}"
        with self._lock:
            with open(self.logfile, "a") as f:
                f.write(entry + "\n")
        if console:
            print(Fore.CYAN + entry + Style.RESET_ALL)
