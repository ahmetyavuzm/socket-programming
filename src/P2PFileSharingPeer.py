import os
import sys
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple
from logger import Logger


class P2PFileSharingPeer:
    def __init__(self, server_ip, server_port, repo_path, schedule_path, working_dir=None):
        self.server_ip = server_ip
        self.server_port = int(server_port)
        self.repo_path = os.path.abspath(repo_path)
        self.schedule_path = os.path.abspath(schedule_path)
        self.peer_path = (
            os.path.abspath(working_dir)
            if working_dir
            else os.path.dirname(self.schedule_path)
        )
        self.peer_port = 6000 + os.getpid() % 1000  
        self.peer_name = os.path.basename(os.path.normpath(self.peer_path))
        self.logger = Logger(f"{self.peer_name}")
        self.download_log_path = os.path.join(self.peer_path, "download.log")
        # Reset download log on startup to ensure a clean file per run.
        os.makedirs(self.peer_path, exist_ok=True)
        with open(self.download_log_path, "w"):
            pass
        self.download_logger = Logger(
            "download",
            log_file=self.download_log_path,
            include_timestamp=False,
            echo_stdout=False,
        )
        self.download_timeout = 5
        self.max_workers = 8
        self.schedule_plan = []
        self.provider_cache = {} 

    # SERVER COMMUNICATION 
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
            files = [
                f
                for f in os.listdir(self.repo_path)
                if os.path.isfile(os.path.join(self.repo_path, f))
            ]
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
                unique = []
                seen = set()
                for entry in providers.split():
                    if entry not in seen:
                        unique.append(entry)
                        seen.add(entry)
                return unique
            return []
        except Exception as e:
            self.logger.log(f"Error querying server for {filename}: {e}")
            return []

    # FILE SERVER 
    def start_file_server(self):
        def handle_client(conn, addr):
            try:
                data = conn.recv(1024).decode("utf-8").strip()
                if not data.startswith("START GET"):
                    if data.startswith("START DOWNLOAD"):
                        parts = data.split()
                        if len(parts) < 6:
                            return
                        filename = parts[2]
                        try:
                            start_byte = int(parts[3])
                            end_byte = int(parts[4])
                        except ValueError:
                            return
                        filepath = os.path.join(self.repo_path, filename)
                        if not os.path.exists(filepath):
                            return

                        file_size = os.path.getsize(filepath)
                        start = max(0, start_byte)
                        if start >= file_size:
                            return
                        end = end_byte
                        if end < 0 or end >= file_size:
                            end = file_size - 1

                        if start > end:
                            return

                        with open(filepath, "rb") as f:
                            f.seek(start)
                            bytes_remaining = end - start + 1
                            while bytes_remaining > 0:
                                chunk = f.read(min(1024 * 1024, bytes_remaining))
                                if not chunk:
                                    break
                                conn.sendall(chunk)
                                bytes_remaining -= len(chunk)
                        self.logger.log(f"Served {filename} bytes {start}-{end} to {addr}")
                    return
                # Legacy support: START GET <filename> END
                parts = data.split()
                if len(parts) < 3:
                    return
                filename = parts[2]
                filepath = os.path.join(self.repo_path, filename)
                if not os.path.exists(filepath):
                    return
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        conn.sendall(chunk)
                self.logger.log(f"Served {filename} (legacy GET) to {addr}")
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

    # FILE DOWNLOAD 
    def download_file(self, filename, size_hint, providers):
        """Download a file by splitting ranges across available providers."""
        if not providers:
            self.logger.log(f"No providers found for {filename}")
            return

        save_path = os.path.join(self.repo_path, filename)

        try:
            size_bytes = self._parse_size_hint(size_hint)
            segments = self._build_segments(size_bytes, providers)
            if not segments:
                self.logger.log(f"No valid segments calculated for {filename}")
                return

            segment_results: List[Tuple[int, bytes]] = []
            errors = []

            with ThreadPoolExecutor(max_workers=min(len(segments), self.max_workers)) as executor:
                future_map = {
                    executor.submit(
                        self._download_segment, filename, ip, port, start, end
                    ): (ip, port, start, end)
                    for (ip, port, start, end) in segments
                }

                for future in as_completed(future_map):
                    ip, port, start, end = future_map[future]
                    try:
                        result = future.result()
                        if result is not None:
                            segment_results.append(result)
                    except Exception as exc:
                        errors.append((ip, port, start, end, exc))

            if errors:
                self.logger.log(
                    f"Segment download errors encountered for {filename}; "
                    f"falling back to sequential download."
                )
                self._download_full_file(filename, providers[0], save_path)
                return

            if not segment_results and not errors:
                self.logger.log(f"No data received for {filename}")
                return

            tmp_path = save_path + ".tmp"
            with open(tmp_path, "wb"):
                pass

            with open(tmp_path, "r+b") as output:
                for start, data in sorted(segment_results, key=lambda item: item[0]):
                    if not data:
                        continue
                    output.seek(start)
                    output.write(data)

            os.replace(tmp_path, save_path)
            self.logger.log(f"File {filename} successfully downloaded.")
            self.notify_server_of_file(filename)
        except Exception as e:
            self.logger.log(f"Error downloading {filename}: {e}")
            if os.path.exists(save_path):
                os.remove(save_path)

    # SCHEDULE 
    def process_schedule(self):
        if not os.path.exists(self.schedule_path):
            self.logger.log(f"Schedule file not found: {self.schedule_path}")
            return

        with open(self.schedule_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        parsed_schedule = []
        for line in lines:
            if line.lower().startswith("wait"):
                parts = line.split()
                delay = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                parsed_schedule.append({"type": "wait", "delay": delay})
            elif ":" in line:
                filename, size = line.split(":", 1)
                parsed_schedule.append(
                    {
                        "type": "download",
                        "filename": filename.strip(),
                        "size": size.strip(),
                    }
                )
        self.schedule_plan = parsed_schedule

        for entry in self.schedule_plan:
            if entry["type"] == "wait":
                delay = entry["delay"]
                self.logger.log(f"Waiting {delay} ms...")
                time.sleep(delay / 1000.0)
                continue

            filename = entry["filename"]
            size_hint = entry.get("size")
            self.logger.log(f"Requesting {filename} ({size_hint} bytes)")
            providers = self.query_server_for_file(filename)
            if providers:
                self.download_file(filename, size_hint, providers)
            else:
                self.logger.log(f"No providers for {filename}")

        done_path = os.path.join(self.peer_path, "done")
        open(done_path, "w").close()
        self.logger.log(f"All downloads completed. Created {done_path}")

    def stay_alive(self):
        self.logger.log("Waiting for other peers to connect...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.log("Peer shutting down gracefully.")

    def run(self):
        self.start_file_server()
        self.connect_to_server()
        self.send_file_list()

    # HELPERS 
    def _download_segment(self, filename: str, ip: str, port: str, start: int, end: int):
        """Download a single segment from a provider."""
        retries = 3
        retry_delay = 0.5

        for attempt in range(retries):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.download_timeout)
            try:
                sock.connect((ip, int(port)))
                request = f"START DOWNLOAD {filename} {start} {end} END"
                sock.sendall(request.encode("utf-8"))

                buffer = bytearray()
                while True:
                    chunk = sock.recv(1024 * 1024)
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    if end >= 0 and len(buffer) >= (end - start + 1):
                        break

                provider = f"{ip}:{port}"
                self.download_logger.log(f"{filename} {provider}")
                self.logger.log(f"{filename} {provider}")
                return start, bytes(buffer)
            except Exception as e:
                if attempt < retries - 1:
                    self.logger.log(
                        f"Retrying segment {filename} from {ip}:{port} ({attempt + 1}/"
                        f"{retries}) due to {e}"
                    )
                    time.sleep(retry_delay)
                else:
                    raise
            finally:
                sock.close()

    def _download_full_file(self, filename: str, provider: str, destination: str):
        ip, port = provider.split(":")
        _, data = self._download_segment(filename, ip, port, 0, -1)
        with open(destination, "wb") as f:
            f.write(data)
        # _download_segment already logged the provider
        self.logger.log(f"File {filename} downloaded sequentially from {provider}")
        self.notify_server_of_file(filename)

    def _parse_size_hint(self, size_hint: Optional[str]) -> Optional[int]:
        if not size_hint:
            return None
        size_hint = size_hint.strip()
        try:
            return int(size_hint)
        except ValueError:
            return None

    def _build_segments(self, size_bytes: Optional[int], providers: List[str]):
        """Return list of (ip, port, start, end) tuples."""
        normalized = []
        seen = set()
        for entry in providers:
            if entry in seen:
                continue
            seen.add(entry)
            try:
                ip, port = entry.split(":")
            except ValueError:
                continue
            normalized.append((ip, port))

        if not normalized:
            return []

        if not size_bytes or size_bytes <= 0:
            ip, port = normalized[0]
            return [(ip, port, 0, -1)]

        segments = []
        remaining = size_bytes
        start = 0
        remaining_providers = len(normalized)

        for idx, (ip, port) in enumerate(normalized):
            remaining_providers = len(normalized) - idx
            if remaining_providers <= 0 or remaining <= 0:
                break

            chunk = remaining // remaining_providers
            if chunk <= 0:
                chunk = 1 if remaining > 0 else 0
            end = start + chunk - 1
            if remaining_providers == 1:
                end = max(end, size_bytes - 1)
            segments.append((ip, port, start, end))
            consumed = max(0, end - start + 1)
            start = end + 1
            remaining -= consumed

        if segments:
            last_ip, last_port, last_start, _ = segments[-1]
            segments[-1] = (last_ip, last_port, last_start, size_bytes - 1)

        return segments

    def notify_server_of_file(self, filename: str):
        """Notify the central server that this peer now provides a new file."""
        try:
            msg = f"START PROVIDING {self.peer_port} 1 {filename} END"
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.server_ip, self.server_port))
            sock.sendall(msg.encode("utf-8"))
            sock.close()
            self.logger.log(f"Announced availability of {filename} to server.")
        except Exception as e:
            self.logger.log(f"Failed to notify server about {filename}: {e}")


    def cmd_list(self):
        """List all files in the local repository."""
        try:
            if not os.path.exists(self.repo_path):
                print(f"Repository path not found: {self.repo_path}")
                return
            files = [
                f
                for f in os.listdir(self.repo_path)
                if os.path.isfile(os.path.join(self.repo_path, f))
            ]
            if files:
                print("Local repository files:")
                for f in files:
                    print(f"  - {f}")
            else:
                print("Repository is empty.")
        except Exception as e:
            self.logger.log(f"Error listing files: {e}")
            print(f"Error listing files: {e}")

    def cmd_remove(self, filename):
        """Remove a file from the local repository."""
        try:
            path = os.path.join(self.repo_path, filename)
            if os.path.exists(path):
                os.remove(path)
                print(f"Removed {filename}")
                self.logger.log(f"Removed local file: {filename}")
            else:
                print(f"File not found: {filename}")
        except Exception as e:
            self.logger.log(f"Error removing file {filename}: {e}")
            print(f"Error removing file: {e}")

    def cmd_search(self, filename):
        """Query the central server for providers of a specific file."""
        try:
            providers = self.query_server_for_file(filename)
            if providers:
                self.provider_cache[filename] = providers
                print(f"Providers for '{filename}':")
                for p in providers:
                    print(f"  - {p}")
            else:
                print(f"No providers found for '{filename}'.")
        except Exception as e:
            self.logger.log(f"Error searching for file {filename}: {e}")
            print(f"Error searching for file: {e}")

    def cmd_providers(self):
        """Show cached provider information."""
        if not self.provider_cache:
            print("No provider information cached.")
        else:
            print("Cached provider data:")
            for fname, peers in self.provider_cache.items():
                print(f"  {fname}: {', '.join(peers)}")

    def cmd_download(self, filename):
        """Download a file manually."""
        try:
            print(f"Searching providers for '{filename}'...")
            # Önce cache'den bak
            providers = self.provider_cache.get(filename)
            if not providers:
                providers = self.query_server_for_file(filename)

            if not providers:
                print(f"No providers found for '{filename}'.")
                return

            # Dosya boyutu tahmini olmadan indir
            self.download_file(filename, None, providers)
            print(f"Download complete: {filename}")
        except Exception as e:
            self.logger.log(f"Error downloading file {filename}: {e}")
            print(f"Error downloading: {e}")

    def cmd_port(self):
        """Show the port this peer is listening on."""
        print(f"Listening on port: {self.peer_port}")

    def cmd_server(self):
        """Show the connected central server information."""
        print(f"Connected server: {self.server_ip}:{self.server_port}")

    def cmd_exit(self):
        print("Shutting down peer...")
        self.shutdown()
        
    def shutdown(self):
        self.running = False
        self.logger.log("Peer shutting down gracefully.")


    # -----------------------------------------------------
    # Interactive Mode
    # -----------------------------------------------------
    def interactive_mode(self):
        print("\nInteractive mode started. Type HELP for commands.\n")
        self.logger.log("Interactive mode started.")

        while True:
            try:
                cmd = input("> ").strip()
                if not cmd:
                    continue

                parts = cmd.split()
                command = parts[0].upper()

                if command == "HELP":
                    print("""
                        Available commands:
                        HELP              Show this help menu
                        PORT              Show peer's listening port
                        SERVER            Show connected server info
                        LIST              List local repository files
                        REMOVE <file>     Delete a local file
                        SEARCH <file>     Query server for providers
                        PROVIDERS         Show cached provider info
                        DOWNLOAD <file>   Download file manually
                        EXIT              Exit peer gracefully
                        """)
                elif command == "PORT":
                    self.cmd_port()
                elif command == "SERVER":
                    self.cmd_server()
                elif command == "LIST":
                    self.cmd_list()
                elif command == "REMOVE" and len(parts) > 1:
                    self.cmd_remove(parts[1])
                elif command == "SEARCH" and len(parts) > 1:
                    self.cmd_search(parts[1])
                elif command == "PROVIDERS":
                    self.cmd_providers()
                elif command == "DOWNLOAD" and len(parts) > 1:
                    self.cmd_download(parts[1])
                elif command == "EXIT":
                    self.cmd_exit()
                    break
                else:
                    print("Unknown command. Type HELP for options.")

            except KeyboardInterrupt:
                print("\nInterrupted by user.")
                self.shutdown()
                break
            except Exception as e:
                self.logger.log(f"Interactive error: {e}")
                print(f"Error: {e}")
if __name__ == "__main__":
    if len(sys.argv) not in (3, 4, 5):
        print(
            "Usage:\n"
            "  python P2PFileSharingPeer.py <ServerIP>:<ServerPort> <PeerPath>\n"
            "  python P2PFileSharingPeer.py <ServerIP>:<ServerPort> <RepoPath> --interactive\n"
            "  python P2PFileSharingPeer.py <ServerIP>:<ServerPort> <RepoPath> <SchedulePath>\n"
            "  python P2PFileSharingPeer.py <ServerIP>:<ServerPort> <RepoPath> <SchedulePath> --interactive"
        )
        sys.exit(1)

    # Flag check
    interactive_mode = False
    if "--interactive" in sys.argv:
        interactive_mode = True
        sys.argv.remove("--interactive")

    # Parse server info
    server = sys.argv[1]
    if ":" not in server:
        print("Server address must be in <IP>:<Port> format.")
        sys.exit(1)

    server_ip, server_port = server.split(":", 1)

    # Repo ve schedule yolları
    if len(sys.argv) == 3 and interactive_mode:
        repo_path =  os.path.abspath(sys.argv[2])
        schedule_path = ""
        working_dir = f"{os.sep}".join(sys.argv[2].split(os.sep)[:-1])
    elif len(sys.argv) == 3:
        peer_root = os.path.abspath(sys.argv[2])
        repo_path = os.path.join(peer_root, "repo")
        schedule_path = os.path.join(peer_root, "schedule.txt")  # Varsayılan
        working_dir = peer_root
    else:
        repo_path = os.path.abspath(sys.argv[2])
        schedule_path = os.path.abspath(sys.argv[3])
        working_dir = os.path.dirname(schedule_path)

    # Peer oluştur
    peer = P2PFileSharingPeer(server_ip, server_port, repo_path, schedule_path, working_dir)

    # Ortak başlatma
    peer.run()

    # 1️⃣ Eğer schedule varsa, önce otomatik işle
    if os.path.exists(schedule_path):
        peer.logger.log("Processing schedule plan before entering interactive mode (if enabled).")
        peer.process_schedule()
    else:
        peer.logger.log("No schedule file found; skipping automatic download phase.")

    # 2️⃣ Eğer interaktif mod aktifse, schedule sonrasında başlat
    if interactive_mode:
        peer.logger.log("Entering interactive mode...")
        peer.interactive_mode()
    else:
        peer.logger.log("Peer started without interactive mode; running schedule-only mode.")
        peer.stay_alive()
        
        
