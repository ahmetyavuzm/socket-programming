#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import socket
import threading
import time
from logger import Logger


class P2PFileSharingPeer:
    def __init__(self, server_ip, server_port, peer_path):
        self.server_ip = server_ip
        self.server_port = int(server_port)
        self.peer_path = peer_path
        self.repo_path =  os.path.join(peer_path, "repo")
        self.schedule_path = os.path.join(peer_path, "schedule.txt")
        self.peer_port = 6000 + os.getpid() % 1000  # unique-ish
        self.peer_name = peer_path.split(os.sep)[-1]
        self.logger = Logger(f"{self.peer_name}")

    # ---------- SERVER COMMUNICATION ---------- #
    def connect_to_server(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            msg = f"START SERVING {self.peer_port} END"
            s.sendall(msg.encode("utf-8"))
            s.close()
            self.logger.log(f"Registered to server as peer {self.peer_port}")
        except Exception as e:
            self.logger.log(f"Error connecting to server: {e}")
            sys.exit(1)

    def send_file_list(self):
        try:
            files = [f for f in os.listdir(self.repo_path)
                     if os.path.isfile(os.path.join(self.repo_path, f))]
            if not files:
                self.logger.log(f"No files found in repository: {self.repo_path}")
                return

            msg = f"START PROVIDING {self.peer_port} {len(files)} " + " ".join(files) + " END"
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            s.sendall(msg.encode("utf-8"))
            s.close()
            self.logger.log(f"Sent PROVIDING list to server: {files}")
        except Exception as e:
            self.logger.log(f"Error sending file list: {e}")

    def query_server_for_file(self, filename):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            msg = f"START SEARCH {filename} END"
            s.sendall(msg.encode("utf-8"))
            response = s.recv(4096).decode("utf-8").strip()
            s.close()
            self.logger.log(f"Server response for {filename}: {response}")
            providers = response.replace("START PROVIDERS", "").replace("END", "").strip()
            if providers:
                return [p for p in providers.split()]
            return []
        except Exception as e:
            self.logger.log(f"Error querying server for {filename}: {e}")
            return []

    # ---------- FILE SERVER (UPLOAD SIDE) ---------- #
    def start_file_server(self):
        """Peer diğer peer’lardan gelen dosya indirme isteklerini dinler."""
        def handle_client(conn, addr):
            try:
                data = conn.recv(1024).decode("utf-8").strip()
                if not data.startswith("START GET"):
                    return
                parts = data.split()
                filename = parts[2]
                filepath = os.path.join(self.repo_path, filename)
                with open(filepath, "rb") as f:
                    chunk = f.read()
                    conn.sendall(chunk)
                self.logger.log(f"Served {filename} to {addr}")
            except Exception as e:
                self.logger.log(f"Error serving file to {addr}: {e}")
            finally:
                conn.close()

        def server_thread():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", self.peer_port))
            srv.listen(5)
            self.logger.log(f"File server listening on port {self.peer_port}")
            while True:
                conn, addr = srv.accept()
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

        threading.Thread(target=server_thread, daemon=True).start()

    # ---------- FILE DOWNLOAD (CLIENT SIDE) ---------- #
    def download_file(self, filename, providers):
        """Basit (tek parça) dosya indirimi."""
        if not providers:
            self.logger.log(f"No providers found for {filename}")
            return

        save_path = os.path.join(self.repo_path, filename)

        def download_part(ip, port, filename):
            """Download a file from a peer with retry mechanism."""
            retries = 3
            retry_delay = 0.5
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)

            for attempt in range(retries):
                try:
                    s.connect((ip, int(port)))
                    break
                except (ConnectionRefusedError, TimeoutError) as e:
                    if attempt < retries - 1:
                        self.logger.log(f"Peer {ip}:{port} not ready ({e}), retrying {attempt + 1}/{retries}...")
                        time.sleep(retry_delay)
                    else:
                        self.logger.log(f"❌ Connection to {ip}:{port} failed after {retries} retries.")
                        s.close()
                        return

            try:
                request = f"START GET {filename} END"
                s.sendall(request.encode())
                with open(save_path, "wb") as f:
                    while True:
                        data = s.recv(1024 * 1024)
                        if not data:
                            break
                        f.write(data)
                self.logger.log(f"Downloaded {filename} from {ip}:{port}")
            except Exception as e:
                self.logger.log(f"❌ Error downloading {filename} from {ip}:{port}: {e}")
            finally:
                s.close()

        threads = []
        for provider in providers:
            ip, port = provider.split(":")
            t = threading.Thread(target=download_part, args=(ip, port, filename))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        self.logger.log(f"File {filename} successfully downloaded and merged.")

    # ---------- SCHEDULE ---------- #
    def process_schedule(self):
        if not os.path.exists(self.schedule_path):
            self.logger.log(f"Schedule file not found: {self.schedule_path}")
            return

        with open(self.schedule_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        for line in lines:
            if line.startswith("wait"):
                delay = int(line.split()[1])
                self.logger.log(f"Waiting {delay} ms...")
                time.sleep(delay / 1000.0)
            elif ":" in line:
                filename, size = line.split(":")
                self.logger.log(f"Requesting {filename} ({size} bytes)")
                providers = self.query_server_for_file(filename)
                if providers:
                    self.download_file(filename, providers)
                else:
                    self.logger.log(f"No providers for {filename}")

        done_path = os.path.join(self.peer_path, "done")
        open(done_path, "w").close()
        self.logger.log(f"All downloads completed. Created {done_path}")
        self.logger.log("All downloads completed. Waiting for other peers to connect...")
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            self.logger.log("Peer shutting down gracefully.")

    def run(self):
        self.start_file_server()
        self.connect_to_server()
        self.send_file_list()
        self.process_schedule()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python P2PFileSharingPeer.py <ServerIP>:<ServerPort> <PeerPath>")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    peer = P2PFileSharingPeer(ip, int(port), sys.argv[2])
    peer.run()
