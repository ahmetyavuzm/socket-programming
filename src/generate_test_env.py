#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate a ready-to-test local P2P file sharing environment.

Usage:
    python3 generate_test_env.py
    python3 generate_test_env.py --clean

This script reads peer configurations from peer-config.json and creates
example peer repositories and schedules in a structured layout:

inputs/
  ├── peer1/
  │   ├── repo/
  │   └── schedule.txt
  ├── peer2/
  └── peer3/
"""

import os
import sys
import json
import random
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUTS_DIR = BASE_DIR / "inputs"
CONFIG_PATH = BASE_DIR / "config" / "peers-config.json"
WAIT_TIME_MS = 5000


# -------------------------------------------------------
# 🔧 HELPER FUNCTIONS
# -------------------------------------------------------
def load_peer_config():
    """Load peer configuration from peer-config.json"""
    if not CONFIG_PATH.exists():
        print(f"❌ Config file not found: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def create_dummy_file(filepath, size_kb=256):
    """Create a dummy .dat file with random bytes."""
    with open(filepath, "wb") as f:
        f.write(os.urandom(size_kb * 1024))


def create_schedule_file(schedule_path, downloads):
    """Generate a schedule file for a peer."""
    with open(schedule_path, "w") as f:
        f.write(f"wait {WAIT_TIME_MS}\n")
        for file in downloads:
            size_str = f"{random.randint(1, 5):03d}{random.randint(10000000, 99999999)}"
            f.write(f"{file}:{size_str}\n")
    print(f"🗓️  Created schedule file: {schedule_path.relative_to(BASE_DIR)}")


def setup_peers(clean: bool = False):
    """Create repositories and schedules for all peers."""
    print("🔧 Generating P2P test environment...\n")

    peers = load_peer_config()

    # Clean old environment
    if clean and INPUTS_DIR.exists():
        shutil.rmtree(INPUTS_DIR)
        print("🧹 Removed old inputs directory")

    INPUTS_DIR.mkdir(exist_ok=True)

    for name, data in peers.items():
        peer_dir = INPUTS_DIR / name
        repo_path = peer_dir / "repo"
        schedule_path = peer_dir / "schedule.txt"

        os.makedirs(repo_path, exist_ok=True)

        for file in data.get("files", []):
            create_dummy_file(repo_path / file)

        create_schedule_file(schedule_path, data.get("downloads", []))
        print(f"📁 Created {name}: {len(data.get('files', []))} initial files")

    # Clear logs
    logs_dir = BASE_DIR / "logs"
    if logs_dir.exists():
        shutil.rmtree(logs_dir)
        print("🧹 Removed old logs directory")
    logs_dir.mkdir(exist_ok=True)

    print("\n✅ Test environment successfully created!\n")
    print(f"📂 Structure created under: {INPUTS_DIR}\n")


# -------------------------------------------------------
# 🏁 MAIN ENTRY POINT
# -------------------------------------------------------
if __name__ == "__main__":
    clean_flag = "--clean" in sys.argv
    setup_peers(clean_flag)
