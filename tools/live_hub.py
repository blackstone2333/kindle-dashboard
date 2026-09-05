"""Start/status/stop the local hub, detached from the development terminal."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".runtime/hub"


def running_pid():
    try:
        pid = int((DATA / "server.pid").read_text())
        command = subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True)
        if "-m hub.server" in command:
            return pid
    except (OSError, ValueError, subprocess.CalledProcessError):
        pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "restart", "status"])
    args = parser.parse_args()
    pid = running_pid()
    if args.action in ("stop", "restart") and pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if not running_pid():
                break
            time.sleep(0.1)
        else:
            raise SystemExit("Hub did not stop; not starting a duplicate.")
        pid = None
    if args.action in ("start", "restart") and not pid:
        DATA.mkdir(parents=True, exist_ok=True)
        fd = os.open(DATA / "process.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "ab", buffering=0) as log:
            child = subprocess.Popen(
                [sys.executable, "-m", "hub.server", "--host", "0.0.0.0", "--port", "18501", "--data-dir", str(DATA)],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                start_new_session=True, close_fds=True,
            )
        print("Hub started in background:", child.pid)
        return
    if args.action == "status":
        with urlopen("http://127.0.0.1:18501/health", timeout=5) as response:
            print(json.dumps(json.load(response)))
    elif args.action == "stop":
        print("Hub stopped.")
    elif pid:
        print("Hub already running:", pid)


if __name__ == "__main__":
    main()
