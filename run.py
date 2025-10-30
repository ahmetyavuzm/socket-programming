#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run all components (Server + Peers) for BBM453 P2P project.

Usage:
    python3 run_peers.py
"""

import subprocess
import time
import os
import signal
import sys

processes = []


def run_process(cmd):
    """Run a subprocess and store its PID."""
    print(f"🚀 Starting: {cmd}")
    p = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
    processes.append(p)
    return p


def main():
    # 🔹 Determine project root dynamically
    script_dir = os.path.dirname(os.path.abspath(__file__))        # current file directory
    src_dir = os.path.join(script_dir, "src")                      # src directory
    inputs_dir = os.path.join(script_dir, "src", "inputs")         # peers' input directory

    # Ensure src directory exists
    if not os.path.exists(src_dir):
        print(f"Error: src directory not found at {src_dir}")
        sys.exit(1)

    try:
        run_process(f"python3 {os.path.join(src_dir, 'generate_test_env.py')} --clean")
        time.sleep(1)

        run_process(f"python3 {os.path.join(src_dir, 'P2PFileSharingServer.py')} 5050")
        time.sleep(1.5)

        peers = [
            os.path.join(inputs_dir, "peer1"),
            os.path.join(inputs_dir, "peer2"),
            os.path.join(inputs_dir, "peer3"),
        ]

        for peer_path in peers:
            repo_path = os.path.join(peer_path, "repo")
            schedule_path = os.path.join(peer_path, "schedule.txt")
            cmd = (
                f"python3 {os.path.join(src_dir, 'P2PFileSharingPeer.py')} "
                f"127.0.0.1:5050 {repo_path} {schedule_path}"
            )
            run_process(cmd)
            # time.sleep(0.7)  # optional delay between peers

        print("\nAll peers and server started.")
        print("Press Ctrl+C to stop everything.\n")

        # Keep running until user interrupts
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping all processes...")
        for p in processes:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        print("Clean exit.")


if __name__ == "__main__":
    main()
