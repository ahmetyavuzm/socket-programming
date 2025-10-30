#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import socket
import time
from utils.logger import SimpleLogger


class P2PFileSharingPeer:
    def __init__(self, server_ip, server_port, repo_path, schedule_path):
        self.server_ip = server_ip
        self.server_port = int(server_port)
        self.repo_path = repo_path
        self.schedule_path = schedule_path
        self.peer_port = None
        self.logger = SimpleLogger("peer.log")

    def connect_to_server(self):
        """Sunucuya bağlan ve START SERVING mesajı gönder."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            self.peer_port = 6000 + os.getpid() % 1000
            message = f"START SERVING {self.peer_port} END"
            s.sendall(message.encode("utf-8"))
            s.close()
            self.logger.log(f"Registered to server as peer {self.peer_port}")
        except Exception as e:
            self.logger.log(f"Error connecting to server: {e}")
            sys.exit(1)

    def send_file_list(self):
        """Repository içeriğini sunucuya bildir."""
        try:
            files = [f for f in os.listdir(self.repo_path) if os.path.isfile(os.path.join(self.repo_path, f))]
            if not files:
                self.logger.log(f"No files found in repository: {self.repo_path}")
                return

            message = f"START PROVIDING {self.peer_port} {len(files)} " + " ".join(files) + " END"
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            s.sendall(message.encode("utf-8"))
            s.close()
            self.logger.log(f"Sent PROVIDING list to server: {files}")
        except Exception as e:
            self.logger.log(f"Error sending file list: {e}")

    def query_server_for_file(self, filename):
        """Sunucudan dosyayı sağlayan peer listesini al."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.server_ip, self.server_port))
            message = f"START SEARCH {filename} END"
            s.sendall(message.encode("utf-8"))
            response = s.recv(4096).decode("utf-8").strip()
            s.close()

            self.logger.log(f"Server response for {filename}: {response}")
            if "START PROVIDERS" in response:
                providers = response.replace("START PROVIDERS", "").replace("END", "").strip()
                if not providers:
                    return []
                return [p for p in providers.split()]
            return []
        except Exception as e:
            self.logger.log(f"Error querying server for {filename}: {e}")
            return []

    def process_schedule(self):
        """Schedule dosyasını oku ve wait/download komutlarını sırayla işle."""
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
                self.logger.log(f"Requesting file '{filename}' of size {size} bytes")
                providers = self.query_server_for_file(filename)
                if providers:
                    self.logger.log(f"File {filename} available at: {providers}")
                else:
                    self.logger.log(f"No providers found for {filename}")

    def run(self):
        """Peer başlangıç rutini."""
        self.connect_to_server()
        self.send_file_list()
        self.logger.log("Peer initialization completed.")
        self.process_schedule()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python P2PFileSharingPeer.py <ServerIP>:<ServerPort> <RepoPath> <ScheduleFile>")
        sys.exit(1)

    server_addr = sys.argv[1]
    repo_path = sys.argv[2]
    schedule_path = sys.argv[3]

    if ":" not in server_addr:
        print("Server address must be in format <IP>:<Port>")
        sys.exit(1)

    ip, port = server_addr.split(":")
    peer = P2PFileSharingPeer(ip, port, repo_path, schedule_path)
    peer.run()
