import os
import datetime

class Logger:
    def __init__(self, name: str):
        """
        Each logger writes to logs/<name>.log
        Example:
          - Logger("server") → logs/server.log
          - Logger("peer-5050") → logs/peer-5050.log
        """
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        self.log_file = os.path.join(logs_dir, f"{name}.log")

    def log(self, message: str):
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        formatted = f"{timestamp} {message}"
        print(formatted)
        with open(self.log_file, "a") as f:
            f.write(formatted + "\n")
