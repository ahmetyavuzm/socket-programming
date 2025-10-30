# 🧩 P2P File Sharing System

This project is a simple **Peer-to-Peer (P2P)** file sharing system implemented in Python.  
Each peer registers its available files with a central **Server** and can download files from other peers.  
All communication happens over **TCP sockets**.

---

## 🚀 Features
- Multi-peer file sharing  
- Central server for file provider lookup  
- Direct peer-to-peer file transfer  
- Separate log file for each peer and the server  
- Easy environment setup and cleanup

---

## 📁 Directory Structure
```
.
├── P2PFileSharingServer.py
├── P2PFileSharingPeer.py
├── logger.py
├── generate_test_env.py         # Test environment generator
├── setup_env.sh                 # Shell script for environment setup
├── logs/
│   ├── server.log
│   ├── peer1.log
│   ├── peer2.log
│   └── peer3.log
└── inputs/
    ├── peer1/
    │   ├── repo/               # Files owned by peer 1
    │   └── schedule.txt        # Files peer 1 will request
    ├── peer2/
    │   ├── repo/
    │   └── schedule.txt
    ├── peer3/
    │   ├── repo/
    │   └── schedule.txt
```

---

## ⚙️ Setup

### 1. Automatic Environment Setup (Recommended)
Run the provided shell script to prepare your environment automatically:
```bash
bash setup_env.sh
```
This script:
- Checks for **Python 3.9**, installs it if missing (via `brew`, `apt`, or `yum`)
- Creates a virtual environment under `env/`
- Activates it and installs dependencies (`rich`, `colorama`)

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

### 3. Generate the Test Environment
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
Now you only need to pass the peer folder (e.g., `inputs/peer1`):

```bash
python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer1
python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer2
python3 P2PFileSharingPeer.py 127.0.0.1:5050 inputs/peer3
```

> 💡 **Tip:**  
> Start peers simultaneously (or with small delays).  
> Otherwise, the first peer may not find providers and show “No providers found”.

---

## 🧾 Logging
All logs are stored in the `logs/` directory:
```
logs/
├── server.log
├── peer1.log
├── peer2.log
└── peer3.log
```
Logs include connection info, file requests, transfers, and errors.  
Each entry has a timestamp in the format `[YYYY-MM-DD HH:MM:SS]`.

---

## 🧠 Common Issues & Fixes

| Error | Description | Fix |
|-------|--------------|-----|
| `ConnectionRefusedError` | A peer tried connecting before the target peer started | Start peers sequentially with small delays |
| `OSError: [Errno 22] Invalid argument` | Server was expected to send provider as `ip:port` format | Fixed in current implementation ✅ |
| `No providers for <file>` | Other peers have not yet registered with the server | Ensure all peers are running |

---

## 🧹 Cleanup
After tests, remove logs and temporary files:
```bash
rm -rf logs/*
find inputs/ -name "done" -delete
```

