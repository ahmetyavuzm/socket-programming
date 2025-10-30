#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BBM453 - P2P File Sharing System (Peer Implementation)
Final compliant version with parallel download and correct CLI usage.

Usage:
    python3 P2PFileSharingPeer.py <ServerIP:Port> <RepoPath> <ScheduleFile>
"""

import socket
import threading
import os
import sys
import time
from pathlib import Path
from logger import Logger

CHUNK_SIZE = 1024 * 128  # 128KB blocks


class P2PFileSharingPeer:
    def __init__(self, server_addr: str, repo_path: str, schedule_file: str):
        self.server_ip, self.server_port = server_addr.split(":")
        self.server_port = int(self.server_port)
        self.repo_path = Path(repo_path)
        self.schedule_file = Path(schedule_file)
        self.listen_port = self._get_free_port()
        self.running = True
        self.peer_name = f"{str(self.repo_path).split(os.sep)[-2]}-{self.listen_port}"
        self.logger = Logger(f"{self.peer_name}")

    # -----------------------------------------------------
    # Networking Utils
    # -----------------------------------------------------
    def _get_free_port(self):
        """Find an available TCP port."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def connect_to_server(self):
        """Register this peer to the server."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            msg = f"START SERVING {self.listen_port} END"
            s.sendall(msg.encode())
            s.close()
            self.logger.log(f"Registered to server as peer {self.listen_port}")
        except Exception as e:
            self.logger.log(f"❌ Failed to connect to server: {e}")
            sys.exit(1)

    def send_file_list(self):
        """Inform server about available files."""
        try:
            files = [f.name for f in self.repo_path.iterdir() if f.is_file()]
            if not files:
                self.logger.log(f"No files found in repo: {self.repo_path}")
                return
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            msg = f"START PROVIDING {self.listen_port} {len(files)} " + " ".join(files) + " END"
            s.sendall(msg.encode())
            s.close()
            self.logger.log(f"Sent PROVIDING list to server: {files}")
        except Exception as e:
            self.logger.log(f"Error sending file list: {e}")

    def notify_file_provided(self, filename: str):
        """Notify server that this peer now provides a new file."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            msg = f"START PROVIDING {self.listen_port} 1 {filename} END"
            s.sendall(msg.encode())
            s.close()
            self.logger.log(f"Updated server: now providing {filename}")
        except Exception as e:
            self.logger.log(f"Failed to notify server about {filename}: {e}")

    # -----------------------------------------------------
    # File Server (serve requests from other peers)
    # -----------------------------------------------------
    def start_file_server(self):
        """Start a background thread that serves download requests."""
        threading.Thread(target=self._file_server_thread, daemon=True).start()

    def _file_server_thread(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", self.listen_port))
        s.listen(5)
        self.logger.log(f"File server listening on port {self.listen_port}")

        while self.running:
            try:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_peer_request, args=(conn, addr), daemon=True).start()
            except Exception as e:
                self.logger.log(f"Server thread error: {e}")

    def handle_peer_request(self, conn, addr):
        """Handle a START DOWNLOAD message from another peer."""
        try:
            data = conn.recv(1024).decode().strip()
            if not data:
                return
            if data.startswith("START DOWNLOAD"):
                parts = data.split()
                filename = parts[2]
                start = int(parts[3])
                end = int(parts[4])
                filepath = self.repo_path / filename

                if not filepath.exists():
                    self.logger.log(f"File not found: {filename}")
                    return

                with open(filepath, "rb") as f:
                    f.seek(start)
                    remaining = end - start
                    while remaining > 0:
                        chunk = f.read(min(CHUNK_SIZE, remaining))
                        if not chunk:
                            break
                        conn.sendall(chunk)
                        remaining -= len(chunk)
                self.logger.log(f"Served {filename} [{start}-{end}] to {addr}")
        except Exception as e:
            self.logger.log(f"Error serving peer {addr}: {e}")
        finally:
            conn.close()

    # -----------------------------------------------------
    # File Download Logic
    # -----------------------------------------------------
    def query_server_for_file(self, filename: str):
        """Query the server to find providers for a file."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            msg = f"START SEARCH {filename} END"
            s.sendall(msg.encode())
            response = s.recv(4096).decode().strip()
            s.close()

            providers = []
            if response.startswith("START PROVIDERS"):
                tokens = response.split()[2:-1]
                for token in tokens:
                    if ":" in token:
                        ip, port = token.split(":")
                        providers.append((ip, int(port)))

            self.logger.log(f"Server response for {filename}: {response}")
            return providers
        except Exception as e:
            self.logger.log(f"Error querying server for {filename}: {e}")
            return []

    def download_part(self, ip, port, filename, start, end, part_id):
        """Download a file part from another peer."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, port))
            msg = f"START DOWNLOAD {filename} {start} {end} END"
            s.sendall(msg.encode())
            filepath = self.repo_path / f"{filename}.part{part_id}"
            with open(filepath, "wb") as f:
                total = 0
                while total < (end - start):
                    data = s.recv(CHUNK_SIZE)
                    if not data:
                        break
                    f.write(data)
                    total += len(data)
            s.close()
            self.logger.log(f"Downloaded part {part_id} of {filename} from {ip}:{port}")
        except Exception as e:
            self.logger.log(f"❌ Failed to download part {part_id} from {ip}:{port}: {e}")

    def merge_parts(self, filename, num_parts):
        """Merge all .part files into the complete file."""
        final_path = self.repo_path / filename
        with open(final_path, "wb") as out:
            for i in range(num_parts):
                part_path = self.repo_path / f"{filename}.part{i}"
                with open(part_path, "rb") as part:
                    out.write(part.read())
                os.remove(part_path)
        self.logger.log(f"File {filename} successfully downloaded and merged.")

    def download_file(self, filename, size, providers):
        """Download a file from multiple peers concurrently."""
        if not providers:
            self.logger.log(f"No providers found for {filename}")
            return

        file_size = int(size)
        num_parts = min(len(providers), 4)
        part_size = file_size // num_parts
        threads = []

        for i in range(num_parts):
            start = i * part_size
            end = (i + 1) * part_size if i < num_parts - 1 else file_size
            ip, port = providers[i % len(providers)]
            t = threading.Thread(target=self.download_part, args=(ip, port, filename, start, end, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.merge_parts(filename, num_parts)
        self.notify_file_provided(filename)

    # -----------------------------------------------------
    # Schedule Processing
    # -----------------------------------------------------
    def process_schedule(self):
        """Read and execute schedule file."""
        if not self.schedule_file.exists():
            self.logger.log(f"Schedule file not found: {self.schedule_file}")
            return

        with open(self.schedule_file, "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            return

        # wait command
        if lines[0].startswith("wait"):
            delay = int(lines[0].split()[1])
            self.logger.log(f"Waiting {delay} ms...")
            time.sleep(delay / 1000)

        for line in lines[1:]:
            if ":" in line:
                filename, size = line.split(":")
                providers = self.query_server_for_file(filename)
                self.download_file(filename, size, providers)

        done = self.repo_path / "done"
        done.touch()
        self.logger.log(f"All downloads completed. Created {done}")

    # -----------------------------------------------------
    # Shutdown
    # -----------------------------------------------------
    def shutdown(self):
        self.running = False
        self.logger.log("Peer shutting down gracefully.")

    def stay_active(self):
        """Keep the peer running to serve files."""
        self.logger.log("Waiting for incoming peer connections... (Press Ctrl+C to exit)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()


# ---------------------------------------------------------
# Entry Point
# ---------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 P2PFileSharingPeer.py <ServerIP:Port> <RepoPath> <ScheduleFile>")
        sys.exit(1)

    server_addr = sys.argv[1]
    repo_path = sys.argv[2]
    schedule_file = sys.argv[3]

    peer = P2PFileSharingPeer(server_addr, repo_path, schedule_file)
    peer.start_file_server()
    peer.connect_to_server()
    peer.send_file_list()
    peer.process_schedule()
    peer.stay_active()
