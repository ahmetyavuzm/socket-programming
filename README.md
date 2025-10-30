# P2P File Sharing System

This project is a simple **Peer-to-Peer (P2P)** file sharing system implemented in Python.
Each peer registers its available files with a central **Server** and can download files from other peers.
All communication happens over **TCP sockets**.

---

## Features

* Multi-peer file sharing
* Central server for file provider lookup
* Parallel, ranged downloads between peers (`START DOWNLOAD`)
* Separate runtime logs (`logs/`) and submission-ready `download.log` per peer
* Easy environment setup and cleanup

---

## Directory Structure

```
.
├── P2PFileSharingServer.py
├── P2PFileSharingPeer.py
├── logger.py
├── generate_test_env.py         # Test environment generator
├── setup_env.sh                 # Shell script for environment setup
├── logs/                      # Runtime traces for debugging
│   ├── server.log
│   ├── peer1.log
│   ├── peer2.log
│   └── peer3.log
└── inputs/
    ├── peer1/
    │   ├── repo/               # Files owned by peer 1
    │   ├── schedule.txt        # Files peer 1 will request
    │   └── download.log        # Lines: "<filename> <peer_ip>:<port>"
    ├── peer2/
    │   ├── repo/
    │   ├── schedule.txt
    │   └── download.log
    ├── peer3/
    │   ├── repo/
    │   ├── schedule.txt
    │   └── download.log
```

---

## Setup

### 1. Automatic Environment Setup (Recommended)

Run the provided shell script to prepare your environment automatically:

```bash
bash setup_env.sh
```

This script:

* Checks for **Python 3.9**, installs it if missing (via `brew`, `apt`, or `yum`)
* Creates a virtual environment under `env/`
* Activates it and installs dependencies (`rich`, `colorama`)

To manually activate the environment later:

```bash
source env/bin/activate
```

---

### 2. Manual Setup (Optional)

If you prefer manual setup:

```bash
python3 -m venv env
source env/bin/activate   # macOS / Linux
env\\Scripts\\activate      # Windows
```

(Optional) Install dependencies:

```bash
pip install -r requirements.txt
```

---

### 3. Generate the Test Environment (Requires Templates Below)

Automatically create peer directories, repositories, and schedule files:

```bash
python3 generate_test_env.py
```

Or reset everything from scratch:

```bash
python3 generate_test_env.py --clean
```

---

### 4. Start the Server

```bash
python3 P2PFileSharingServer.py 5050
```

The server starts listening on **port 5050**.
Logs are written to `logs/server.log`.

---

### 5. Start Peers

Each peer should be started in its own terminal.
Assignment CLI expects both repository and schedule paths:

```bash
python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer1/repo inputs/peer1/schedule.txt
python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer2/repo inputs/peer2/schedule.txt
python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer3/repo inputs/peer3/schedule.txt
```

Tip: Start peers simultaneously (or with short delays). Otherwise, the first peer may not find providers and show “No providers found”.

Shortcut: You can still pass the peer folder (`inputs/peer1`) and the script will derive repo/schedule automatically.

---

## 🔄 Running Everything Automatically

### 6. Run the Whole System at Once (Server + All Peers)

If you want to launch the entire system automatically, use the provided `run_peers.py` script.
It dynamically detects your current working directory — no need for static `src/` paths.

```bash
python3 run_peers.py
```

This will:

1. Clean and regenerate the test environment (`generate_test_env.py --clean`)
2. Start the central server on port `5050`
3. Launch all peers (`peer1`, `peer2`, `peer3`) with their respective `repo` and `schedule.txt`

You’ll see output like:

```
🚀 Starting: python3 src/generate_test_env.py --clean
🚀 Starting: python3 src/P2PFileSharingServer.py 5050
🚀 Starting: python3 src/P2PFileSharingPeer.py 127.0.0.1:5050 src/inputs/peer1/repo src/inputs/peer1/schedule.txt
🚀 Starting: python3 src/P2PFileSharingPeer.py 127.0.0.1:5050 src/inputs/peer2/repo src/inputs/peer2/schedule.txt
🚀 Starting: python3 src/P2PFileSharingPeer.py 127.0.0.1:5050 src/inputs/peer3/repo src/inputs/peer3/schedule.txt

✅ All peers and server started.
🧠 Press Ctrl+C to stop everything.
```

Press **Ctrl+C** to stop all processes at once — the script will terminate all peers and the server cleanly.

---

## 💬 Interactive Mode

Each peer can also be started in **interactive mode**, where you can issue commands manually after it connects to the server.

### Example:

```bash
python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer1/repo inputs/peer1/schedule.txt --interactive
```

If you omit the schedule path:

```bash
python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer1 --interactive
```

the peer will still start its file server, register to the central server, and open the interactive shell.

---

### Available Commands

Once the peer starts, you’ll see:

```
🌐 Interactive mode started. Type HELP for commands.
```

Then you can use:

| Command           | Description                               |
| ----------------- | ----------------------------------------- |
| `HELP`            | Show command list                         |
| `PORT`            | Show peer’s listening port                |
| `SERVER`          | Show connected server info                |
| `LIST`            | List local repository files               |
| `REMOVE <file>`   | Delete a local file                       |
| `SEARCH <file>`   | Ask the server which peers have that file |
| `PROVIDERS`       | Show cached provider info                 |
| `DOWNLOAD <file>` | Download file manually                    |
| `EXIT`            | Shut down the peer gracefully             |

Example session:

```
> LIST
📁 Local repository files:
  - a.dat
  - b.dat

> SEARCH g.dat
🌍 Providers for 'g.dat':
  - 127.0.0.1:6005
  - 127.0.0.1:6006

> DOWNLOAD g.dat
⬇️ Searching providers for 'g.dat'...
✅ Download complete: g.dat

> EXIT
👋 Shutting down peer...
```

---

## ⚙️ Combined Operation (Schedule + Interactive)

You can also **combine scheduled downloads and interactive mode** in one peer:

```bash
python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer1/repo inputs/peer1/schedule.txt --interactive
```

Behavior:

1. The peer runs all downloads in `schedule.txt`
2. Once done, it enters interactive mode automatically
   allowing you to search or download more files manually.

This hybrid mode is ideal for debugging and live demonstrations.

---

## 🧹 Cleanup Reminder

After tests, you can safely clean up with:

```bash
rm -rf logs/*
find inputs/ -name "done" -delete
```
