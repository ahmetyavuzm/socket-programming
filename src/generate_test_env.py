"""
Generate a ready-to-test local P2P file sharing environment.

Usage:
    python3 generate_test_env.py
    python3 generate_test_env.py --clean

This script reads template definitions from config/peers-config.json (or falls
back to example-input/) and creates a ready-to-test environment in the following
layout:

inputs/
  ├── peer1/
  │   ├── repo/             # Files available at start
  │   └── schedule.txt      # Wait + download plan (deterministic)
  ├── peer2/
  └── peer3/
"""

import os
import sys
import json
import random
import shutil
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUTS_DIR = BASE_DIR / "inputs"
CONFIG_PATH = BASE_DIR / "config" / "peers-config.json"
EXAMPLE_INPUT_DIR = (BASE_DIR / ".." / "example-input").resolve()
WAIT_TIME_MS = 5000


# HELPER FUNCTIONS
def load_peer_config():
    """Load peer configuration from peers-config.json if present."""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def create_dummy_file(filepath, size_kb=256):
    """Create a dummy .dat file with random bytes."""
    with open(filepath, "wb") as f:
        f.write(os.urandom(size_kb * 1024))


def create_schedule_file(schedule_path, wait_ms, downloads, file_config=None):
    """Generate a schedule file for a peer."""
    file_config = file_config or {}
    with open(schedule_path, "w") as f:
        f.write(f"wait {wait_ms}\n")
        for entry in downloads:
            if isinstance(entry, str):
                filename = entry
                size_hint = None
            else:
                filename = entry.get("name") or entry.get("file")
                size_hint = (
                    entry.get("size_hint")
                    or entry.get("size")
                    or entry.get("schedule_size")
                )

            size_hint = size_hint or file_config.get(filename, {}).get("schedule_size")
            if not size_hint:
                # Fallback to reproducible pseudo-random size with deterministic seed
                rng = random.Random(filename)
                size_hint = f"{rng.randint(1, 5):03d}{rng.randint(10000000, 99999999)}"

            f.write(f"{filename}:{size_hint}\n")
    print(f"Created schedule file: {schedule_path.relative_to(BASE_DIR)}")


def resolve_path(path_str, base_dir=BASE_DIR):
    """Resolve a potentially relative path against the provided base directory."""
    path = Path(path_str)
    if not path.is_absolute():
        path = base_dir / path_str
    return path.resolve()


def parse_initial_repo_template(template_path):
    """Parse initial repository tree produced by `tree -s` output."""
    if not template_path.exists():
        raise FileNotFoundError(f"Initial repo template not found: {template_path}")

    peer_files = {}
    current_peer = None
    pattern = re.compile(r"\[([\d\s]+)\]\s+([\w.\-]+)$")

    with open(template_path, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("Output"):
                continue

            match = pattern.search(line)
            if not match:
                continue

            size_bytes = int(match.group(1).replace(" ", ""))
            name = match.group(2)

            if name.endswith("-repo"):
                current_peer = name[:-5]
                peer_files.setdefault(current_peer, [])
                continue

            if current_peer is None:
                continue

            peer_files[current_peer].append(
                {
                    "name": name,
                    "size_bytes": size_bytes,
                }
            )

    return peer_files


def parse_schedule_templates(schedule_paths, default_wait_ms):
    """Parse deterministic schedules from template files."""
    schedules = {}
    for path in schedule_paths:
        peer_name = path.stem.replace("-schedule", "")
        with open(path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        wait_ms = default_wait_ms
        entries = []
        for line in lines:
            if line.startswith("wait"):
                parts = line.split()
                if len(parts) > 1 and parts[1].isdigit():
                    wait_ms = int(parts[1])
                continue

            if ":" in line:
                filename, size_hint = line.split(":", 1)
                entries.append({"name": filename.strip(), "size_hint": size_hint.strip()})

        schedules[peer_name] = {"wait": wait_ms, "entries": entries}

    return schedules


def setup_peers(clean: bool = False):
    """Create repositories and schedules for all peers."""
    print("Generating P2P test environment...\n")

    config = load_peer_config()
    template_cfg = (config or {}).get("templates", {})

    default_wait_ms = (config or {}).get("default_wait_ms", WAIT_TIME_MS)
    default_file_size_kb = (config or {}).get("default_file_size_kb", 256)
    use_template_sizes = (config or {}).get("use_template_sizes", False)
    max_file_size_kb = (config or {}).get("max_file_size_kb")

    template_dir = template_cfg.get("template_dir")
    if template_dir:
        template_dir = resolve_path(template_dir)
    else:
        template_dir = EXAMPLE_INPUT_DIR

    initial_template_path = template_cfg.get("initial_repo")
    if initial_template_path:
        initial_template_path = resolve_path(initial_template_path)
    else:
        initial_template_path = template_dir / "initial-repo-setup.txt"

    schedules_dir = template_cfg.get("schedules_dir")
    if schedules_dir:
        schedules_dir = resolve_path(schedules_dir)
    else:
        schedules_dir = template_dir

    schedule_pattern = template_cfg.get("schedule_pattern", "peer*-schedule.txt")
    schedule_paths = sorted(schedules_dir.glob(schedule_pattern))

    try:
        initial_map = parse_initial_repo_template(initial_template_path)
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)

    if not schedule_paths:
        print(f"No schedule templates found matching {schedule_pattern} in {schedules_dir}")
        sys.exit(1)

    schedule_map = parse_schedule_templates(schedule_paths, default_wait_ms)
    all_peers = sorted(set(initial_map.keys()) | set(schedule_map.keys()))

    if not all_peers:
        print("No peers discovered from templates, nothing to do.")
        return

    # Clean old environment
    if clean and INPUTS_DIR.exists():
        shutil.rmtree(INPUTS_DIR)
        print("Removed old inputs directory")

    INPUTS_DIR.mkdir(exist_ok=True)

    for name in all_peers:
        peer_initial_entries = initial_map.get(name, [])
        wait_ms = schedule_map.get(name, {}).get("wait", default_wait_ms)
        schedule_entries = schedule_map.get(name, {}).get("entries", [])

        peer_dir = INPUTS_DIR / name
        repo_path = peer_dir / "repo"
        schedule_path = peer_dir / "schedule.txt"

        os.makedirs(repo_path, exist_ok=True)

        for entry in peer_initial_entries:
            filename = entry["name"]
            size_kb = default_file_size_kb
            if use_template_sizes and entry.get("size_bytes"):
                size_kb = max(1, entry["size_bytes"] // 1024)
                if max_file_size_kb:
                    size_kb = min(size_kb, max_file_size_kb)

            create_dummy_file(repo_path / filename, size_kb)

        create_schedule_file(schedule_path, wait_ms, schedule_entries)
        print(f"Created {name}: {len(peer_initial_entries)} initial files, wait {wait_ms} ms")

    # Clear logs
    logs_dir = BASE_DIR / "logs"
    if logs_dir.exists():
        shutil.rmtree(logs_dir)
        print("Removed old logs directory")
    logs_dir.mkdir(exist_ok=True)

    print("\nTest environment successfully created!\n")
    print(f"Structure created under: {INPUTS_DIR}\n")


# MAIN ENTRY POINT
if __name__ == "__main__":
    clean_flag = "--clean" in sys.argv
    setup_peers(clean_flag)
