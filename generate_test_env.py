#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate a ready-to-test local P2P file sharing environment.

Usage:
    python3 generate_test_env.py
    python3 generate_test_env.py --clean

Creates example peer repositories and schedules in a structured layout:
example-input/
  ├── peer1/
  │   ├── repo/
  │   └── schedule.txt
  ├── peer2/
  └── peer3/
"""

import os
import random
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EXAMPLE_INPUT_DIR = BASE_DIR / "inputs"

# -------------------------------------------------------
# ✅ CONFIGURATION BASED ON example-input STRUCTURE
# -------------------------------------------------------
PEERS = {
    "peer1": {
        "files": ["a.dat", "b.dat", "c.dat", "d.dat"],
        "downloads": ["e.dat", "f.dat", "g.dat", "h.dat"]
    },
    "peer2": {
        "files": ["e.dat", "f.dat"],
        "downloads": ["a.dat", "b.dat", "c.dat", "d.dat", "g.dat", "h.dat"]
    },
    "peer3": {
        "files": ["g.dat", "h.dat"],
        "downloads": ["a.dat", "b.dat", "c.dat", "d.dat", "e.dat", "f.dat"]
    },
}

# -------------------------------------------------------
# 🔧 HELPER FUNCTIONS
# -------------------------------------------------------
def create_dummy_file(filepath, size_kb=256):
    """Create a dummy .dat file with random bytes."""
    with open(filepath, "wb") as f:
        f.write(os.urandom(size_kb * 1024))


def create_schedule_file(schedule_path, downloads):
    """Generate a schedule file for a peer."""
    with open(schedule_path, "w") as f:
        f.write("wait 500\n")
        for file in downloads:
            size_str = f"{random.randint(1, 5):03d}{random.randint(10000000, 99999999)}"
            f.write(f"{file}:{size_str}\n")
    print(f"🗓️  Created schedule file: {schedule_path.relative_to(BASE_DIR)}")


def setup_peers(clean: bool = False):
    """Create repositories and schedules for all peers."""
    print("🔧 Generating P2P test environment...\n")

    # Clean old environment
    if clean and EXAMPLE_INPUT_DIR.exists():
        shutil.rmtree(EXAMPLE_INPUT_DIR)
        print(f"🧹 Removed old example-input directory")

    EXAMPLE_INPUT_DIR.mkdir(exist_ok=True)

    for name, data in PEERS.items():
        peer_dir = EXAMPLE_INPUT_DIR / name
        repo_path = peer_dir / "repo"
        schedule_path = peer_dir / "schedule.txt"

        os.makedirs(repo_path, exist_ok=True)

        for file in data["files"]:
            create_dummy_file(repo_path / file)

        create_schedule_file(schedule_path, data["downloads"])
        print(f"📁 Created {name}: {len(data['files'])} initial files")

    # Clear logs
    logs_dir = BASE_DIR / "logs"
    if logs_dir.exists():
        shutil.rmtree(logs_dir)
        print("🧹 Removed old logs directory")
    logs_dir.mkdir(exist_ok=True)

    print("\n✅ Test environment successfully created!\n")
    print(f"📂 Structure created under: {EXAMPLE_INPUT_DIR}\n")


# -------------------------------------------------------
# 🏁 MAIN ENTRY POINT
# -------------------------------------------------------
if __name__ == "__main__":
    clean_flag = "--clean" in sys.argv
    setup_peers(clean_flag)
