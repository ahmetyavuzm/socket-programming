#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import threading
import sys
from logger import Logger



class P2PFileSharingServer:
    def __init__(self, port: int):
        self.host = "0.0.0.0"
        self.port = port
        self.logger = Logger("server")
        self.providers = {}  # filename -> set of (ip, port)
        self.active_peers = set()

    def start(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(10)
            self.logger.log(f"Server started on port {self.port}")
            print(f"🚀 Server listening on port {self.port}...")

            while True:
                client_socket, addr = server_socket.accept()
                self.logger.log(f"Connection from {addr}")
                threading.Thread(
                    target=self.handle_client, args=(client_socket, addr), daemon=True
                ).start()
        except Exception as e:
            self.logger.log(f"Server error: {e}")
            print(f"❌ Server error: {e}")

    def handle_client(self, client_socket: socket.socket, addr):
        try:
            data = client_socket.recv(4096).decode("utf-8").strip()
            if not data:
                return

            self.logger.log(f"Received from {addr}: {data}")

            if data.startswith("START SERVING"):
                port = int(data.split()[2])
                self.active_peers.add((addr[0], port))
                self.logger.log(f"Peer registered: {addr[0]}:{port}")

            elif data.startswith("START PROVIDING"):
                parts = data.split()
                port = int(parts[2])
                count = int(parts[3])
                filenames = parts[4:-1]
                for f in filenames:
                    self.providers.setdefault(f, set()).add((addr[0], port))
                self.logger.log(f"Peer {addr[0]}:{port} provides {filenames}")

            elif data.startswith("START SEARCH"):
                filename = data.split()[2]
                peers = self.providers.get(filename, [])
                if peers:
                    providers_str = " ".join([f"{ip}:{p}" for ip, p in peers])
                    response = f"START PROVIDERS {providers_str} END"
                else:
                    response = "START PROVIDERS END"
                client_socket.sendall(response.encode("utf-8"))
                self.logger.log(f"Sent providers for {filename}: {[f'{ip}:{p}' for ip, p in peers]}")

        except Exception as e:
            self.logger.log(f"Error handling client {addr}: {e}")
        finally:
            client_socket.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python P2PFileSharingServer.py <Port>")
        sys.exit(1)
    port = int(sys.argv[1])
    server = P2PFileSharingServer(port)
    server.start()
