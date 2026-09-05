"""Verify real-device cache retention and recovery, without changing Wi-Fi or data."""
import json
from pathlib import Path
import subprocess
import sys
import time

from kindle_ssh import run

ROOT = Path(__file__).resolve().parents[1]
DEVICE = "/mnt/us/koreader/settings/kindle-agent-dashboard"


def remote(command):
    return run(command, capture_output=True, text=True).stdout.strip()


def result():
    # A request removes the previous result before writing its new atomic result.
    value = remote("if test -f " + DEVICE + "/request-result.json; then cat " + DEVICE + "/request-result.json; fi")
    return json.loads(value) if value else {}


def poll(after, success):
    for _ in range(20):
        item = result()
        if item.get("at", 0) > after and item.get("ok") == success:
            return item
        time.sleep(1)
    raise RuntimeError("Expected device sync result did not arrive")


def main():
    before = remote("sha256sum " + DEVICE + "/snapshot.json").split()[0]
    at = result()["at"]
    try:
        subprocess.run([sys.executable, "tools/live_hub.py", "stop"], cwd=ROOT, check=True)
        remote("touch " + DEVICE + "/refresh.request")
        failed = poll(at, False)
        after = remote("sha256sum " + DEVICE + "/snapshot.json").split()[0]
        assert before == after, "Last good device cache changed during failed sync"
        state = json.loads(remote("cat " + DEVICE + "/status.json"))
        assert state["active"] and state["events"] > 0
        print("PASS: service unavailable; Kindle remains open and cache unchanged")
    finally:
        subprocess.run([sys.executable, "tools/live_hub.py", "start"], cwd=ROOT, check=True)
    time.sleep(2)
    remote("touch " + DEVICE + "/refresh.request")
    poll(failed["at"], True)
    print("PASS: authenticated sync recovered on the same open Kindle view")


if __name__ == "__main__":
    main()
