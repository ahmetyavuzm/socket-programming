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

processes = []

def run_process(cmd):
    """Run a subprocess and store its PID."""
    print(f"🚀 Starting: {cmd}")
    p = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
    processes.append(p)
    return p

try:
    # Start server
    run_process("python3 generate_test_env.py --clean")
    time.sleep(1)
    run_process("python3 P2PFileSharingServer.py 5050")
    time.sleep(1.5)

    # Start peers (each in a new terminal tab or background)
    peers = [
        "python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer1/repo inputs/peer1/schedule.txt",
        "python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer2/repo inputs/peer2/schedule.txt",
        "python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer3/repo inputs/peer3/schedule.txt",
    ]

    for cmd in peers:
        run_process(cmd)
        time.sleep(0.7)  # küçük bekleme, bağlantı karışmasın

    print("\n✅ All peers and server started.")
    print("🧠 Press Ctrl+C to stop everything.\n")

    # Keep running until user interrupts
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Stopping all processes...")
    for p in processes:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    print("✅ Clean exit.")
