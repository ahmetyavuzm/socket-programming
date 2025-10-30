import socket
import threading
import sys
from typing import Dict, Set, Tuple, Iterable
from logger import Logger


class P2PFileSharingServer:
    def __init__(self, port: int):
        self.host = "0.0.0.0"
        self.port = port
        self.logger = Logger("server")
        self.providers: Dict[str, Set[Tuple[str, int]]] = {}
        self.active_peers: Set[Tuple[str, int]] = set()
        self.lock = threading.Lock()

    def start(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(32)
            self.logger.log(f"Server started on port {self.port}")
            print(f"Server listening on port {self.port}...")

            while True:
                client_socket, addr = server_socket.accept()
                self.logger.log(f"Connection from {addr}")
                threading.Thread(
                    target=self.handle_client, args=(client_socket, addr), daemon=True
                ).start()
        except Exception as e:
            self.logger.log(f"Server error: {e}")
            print(f"Server error: {e}")

    def handle_client(self, client_socket: socket.socket, addr):
        try:
            data = client_socket.recv(4096).decode("utf-8").strip()
            if not data:
                return

            self.logger.log(f"Received from {addr}: {data}")

            if data.startswith("START SERVING"):
                tokens = data.split()
                if len(tokens) < 3:
                    self.logger.log(f"Malformed SERVING message from {addr}: {data}")
                    return
                port = int(tokens[2])
                with self.lock:
                    self.active_peers.add((addr[0], port))
                self.logger.log(f"Peer registered: {addr[0]}:{port}")

            elif data.startswith("START PROVIDING"):
                self._handle_providing(addr, data)

            elif data.startswith("START SEARCH"):
                tokens = data.split()
                if len(tokens) < 3:
                    self.logger.log(f"Malformed SEARCH message from {addr}: {data}")
                    return
                filename = tokens[2]
                peers = self._get_providers(filename)
                if peers:
                    providers_str = " ".join([f"{ip}:{p}" for ip, p in peers])
                    response = f"START PROVIDERS {providers_str} END"
                else:
                    response = "START PROVIDERS END"
                client_socket.sendall(response.encode("utf-8"))
                self.logger.log(
                    f"Sent providers for {filename}: {[f'{ip}:{p}' for ip, p in peers]}"
                )
            else:
                self.logger.log(f"Unknown command from {addr}: {data}")

        except Exception as e:
            self.logger.log(f"Error handling client {addr}: {e}")
        finally:
            client_socket.close()

    def _handle_providing(self, addr: Tuple[str, int], data: str):
        tokens = data.split()
        if len(tokens) < 5:
            self.logger.log(f"Malformed PROVIDING message from {addr}: {data}")
            return

        try:
            port = int(tokens[2])
            count = int(tokens[3])
        except ValueError:
            self.logger.log(f"Invalid PROVIDING numbers from {addr}: {data}")
            return

        filenames = [name for name in tokens[4:] if name != "END"]
        if len(filenames) < count:
            self.logger.log(
                f"Expected {count} filenames but received {len(filenames)} from {addr}"
            )

        filenames = filenames[:count] if count > 0 else []
        if not filenames:
            return

        with self.lock:
            for filename in filenames:
                providers = self.providers.setdefault(filename, set())
                providers.add((addr[0], port))

        self.logger.log(f"Peer {addr[0]}:{port} provides {filenames}")

    def _get_providers(self, filename: str) -> Iterable[Tuple[str, int]]:
        with self.lock:
            providers = self.providers.get(filename)
            if not providers:
                return []
            return list(providers)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python P2PFileSharingServer.py <Port>")
        sys.exit(1)
    port = int(sys.argv[1])
    server = P2PFileSharingServer(port)
    server.start()
