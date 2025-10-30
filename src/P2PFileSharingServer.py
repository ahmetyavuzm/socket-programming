#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BBM453 - P2P File Sharing System
Server Implementation (Final Version)

Responsibilities:
- Handle registration of peers (START SERVING)
- Track provided files (START PROVIDING)
- Respond to file search queries (START SEARCH)
- Manage concurrent access using locks
- Cleanup disconnected or dead peers
"""

import socket
import threading
import sys
import time
from collections import defaultdict
from logger import Logger


class P2PFileSharingServer:
    def __init__(self, port: int):
        self.host = "0.0.0.0"
        self.port = port
        self.logger = Logger("server")

        # file → set((ip, port))
        self.providers = defaultdict(set)
        # (ip, port) → set(filenames)
        self.peer_files = defaultdict(set)
        # all active peers
        self.active_peers = set()

        self.lock = threading.Lock()
        self.running = True

    # -------------------------------------------------------
    # 🏁 Main server loop
    # -------------------------------------------------------
    def start(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(10)
            self.logger.log(f"Server started on port {self.port}")
            print(f"🚀 Server listening on port {self.port}...")

            # Start background cleanup thread
            threading.Thread(target=self.cleanup_dead_peers, daemon=True).start()

            while self.running:
                try:
                    client_socket, addr = server_socket.accept()
                    threading.Thread(
                        target=self.handle_client, args=(client_socket, addr), daemon=True
                    ).start()
                except OSError:
                    break  # socket closed during shutdown

        except KeyboardInterrupt:
            self.shutdown()
        except Exception as e:
            self.logger.log(f"❌ Server error: {e}")
        finally:
            server_socket.close()

    # -------------------------------------------------------
    # 🧩 Handle incoming client (peer) messages
    # -------------------------------------------------------
    def handle_client(self, client_socket: socket.socket, addr):
        try:
            data = client_socket.recv(4096).decode("utf-8").strip()
            if not data:
                return

            self.logger.log(f"Received from {addr}: {data}")

            if data.startswith("START SERVING"):
                self._register_peer(data, addr)
            elif data.startswith("START PROVIDING"):
                self._update_providing(data, addr)
            elif data.startswith("START SEARCH"):
                self._handle_search(data, client_socket, addr)

        except Exception as e:
            self.logger.log(f"⚠️ Error handling {addr}: {e}")
        finally:
            client_socket.close()

    # -------------------------------------------------------
    # 🔹 Message Handlers
    # -------------------------------------------------------
    def _register_peer(self, data, addr):
        try:
            port = int(data.split()[2])
            with self.lock:
                self.active_peers.add((addr[0], port))
            self.logger.log(f"Peer registered: {addr[0]}:{port}")
            self._log_status()
        except Exception as e:
            self.logger.log(f"Error registering peer {addr}: {e}")

    def _update_providing(self, data, addr):
        try:
            parts = data.split()
            port = int(parts[2])
            filenames = parts[4:-1]
            with self.lock:
                for f in filenames:
                    self.providers[f].add((addr[0], port))
                    self.peer_files[(addr[0], port)].add(f)
            self.logger.log(f"Peer {addr[0]}:{port} provides {filenames}")
            self._log_status()
        except Exception as e:
            self.logger.log(f"Error updating provider info: {e}")

    def _handle_search(self, data, client_socket, addr):
        try:
            filename = data.split()[2]
            with self.lock:
                peers = self.providers.get(filename, set()).copy()

            # Only include alive peers
            alive_peers = []
            for ip, port in peers:
                if self._is_peer_alive(ip, port):
                    alive_peers.append(f"{ip}:{port}")
                else:
                    self._remove_peer((ip, port))

            if alive_peers:
                response = "START PROVIDERS " + " ".join(alive_peers) + " END"
            else:
                response = "START PROVIDERS END"

            client_socket.sendall(response.encode("utf-8"))
            self.logger.log(f"Sent providers for {filename}: {alive_peers}")
        except Exception as e:
            self.logger.log(f"Error in SEARCH handling from {addr}: {e}")

    # -------------------------------------------------------
    # 🔄 Peer Cleanup & Validation
    # -------------------------------------------------------
    def _is_peer_alive(self, ip, port) -> bool:
        """Check if a peer is reachable."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            result = s.connect_ex((ip, port))
            s.close()
            return result == 0
        except Exception:
            return False

    def cleanup_dead_peers(self):
        """Periodically remove dead peers from active lists."""
        while self.running:
            time.sleep(10)
            removed = 0
            with self.lock:
                for peer in list(self.active_peers):
                    if not self._is_peer_alive(*peer):
                        self._remove_peer(peer)
                        removed += 1
            if removed > 0:
                self.logger.log(f"🧹 Cleaned {removed} dead peers")

    def _remove_peer(self, peer):
        """Remove a peer and its provided files."""
        ip, port = peer
        if peer in self.active_peers:
            self.active_peers.remove(peer)
        for f, peers in list(self.providers.items()):
            if peer in peers:
                peers.remove(peer)
        if peer in self.peer_files:
            del self.peer_files[peer]
        self.logger.log(f"Removed inactive peer: {ip}:{port}")

    # -------------------------------------------------------
    # 🧾 Logging Helpers
    # -------------------------------------------------------
    def _log_status(self):
        self.logger.log(
            f"STATUS: {len(self.active_peers)} active peers, {len(self.providers)} tracked files"
        )

    # -------------------------------------------------------
    # 🧘 Graceful Shutdown
    # -------------------------------------------------------
    def shutdown(self):
        self.running = False
        self.logger.log("Server shutting down gracefully.")
        print("🛑 Server stopped.")


# -------------------------------------------------------
# 🧠 Entry Point
# -------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python P2PFileSharingServer.py <Port>")
        sys.exit(1)

    port = int(sys.argv[1])
    server = P2PFileSharingServer(port)
    server.start()
