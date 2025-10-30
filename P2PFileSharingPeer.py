#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import socket
import threading
import time
from logger import Logger


class P2PFileSharingPeer:
    def __init__(self, server_ip, server_port, repo_path, schedule_path):
        self.server_ip = server_ip
        self.server_port = int(server_port)
        self.repo_path = repo_path
        self.schedule_path = schedule_path
        self.peer_port = 6000 + os.getpid() % 1000  # unique-ish
        self.peer_name = repo_path.split(os.sep)[-2]
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
            files = [f for f in os.listdir(self.repo_path) if os.path.isfile(os.path.join(self.repo_path, f))]
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
                if not data.startswith("START DOWNLOAD"):
                    return
                parts = data.split()
                filename, start_b, end_b = parts[2], int(parts[3]), int(parts[4])
                filepath = os.path.join(self.repo_path, filename)
                with open(filepath, "rb") as f:
                    f.seek(start_b)
                    chunk = f.read(end_b - start_b + 1)
                    conn.sendall(chunk)
                self.logger.log(f"Served {filename} bytes {start_b}-{end_b} to {addr}")
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
        """Diğer peer’lardan paralel dosya indir."""
        if not providers:
            self.logger.log(f"No providers found for {filename}")
            return

        save_path = os.path.join(self.repo_path, filename)
        temp_parts = []

        def download_part(provider, start_b, end_b, idx):
            ip, port = provider.split(":")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, int(port)))
            msg = f"START DOWNLOAD {filename} {start_b} {end_b} END"
            s.sendall(msg.encode("utf-8"))
            data = s.recv(1024 * 1024)
            s.close()
            part_path = f"{save_path}.part{idx}"
            with open(part_path, "wb") as f:
                f.write(data)
            temp_parts.append(part_path)
            self.logger.log(f"Downloaded part {idx} ({start_b}-{end_b}) from {provider}")

        # (Şimdilik tüm dosya tek parça olarak indiriliyor)
        threads = []
        for i, provider in enumerate(providers):
            t = threading.Thread(target=download_part, args=(provider, 0, 1024 * 1024 - 1, i))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        # Parçaları birleştir
        with open(save_path, "wb") as out:
            for part in sorted(temp_parts):
                with open(part, "rb") as p:
                    out.write(p.read())
                os.remove(part)
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

        done_path = os.path.join(self.repo_path, "done")
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
    if len(sys.argv) != 4:
        print("Usage: python P2PFileSharingPeer.py <ServerIP>:<ServerPort> <RepoPath> <ScheduleFile>")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    peer = P2PFileSharingPeer(ip, int(port), sys.argv[2], sys.argv[3])
    peer.run()
