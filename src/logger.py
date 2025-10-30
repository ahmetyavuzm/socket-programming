import os
import datetime
from pathlib import Path


class Logger:
    def __init__(
        self,
        name: str,
        *,
        log_file: str = None,
        include_timestamp: bool = True,
        echo_stdout: bool = True,
    ):
        if log_file:
            self.log_file = Path(log_file).resolve()
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            logs_dir = Path(__file__).resolve().parent / "logs"
            logs_dir.mkdir(exist_ok=True)
            self.log_file = logs_dir / f"{name}.log"

        self.include_timestamp = include_timestamp
        self.echo_stdout = echo_stdout

    def log(self, message: str):
        formatted = self._format(message)
        if self.echo_stdout:
            print(formatted)
        with open(self.log_file, "a") as f:
            f.write(formatted + "\n")

    def _format(self, message: str) -> str:
        if not self.include_timestamp:
            return message
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        return f"{timestamp} {message}"
