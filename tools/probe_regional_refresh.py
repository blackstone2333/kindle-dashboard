"""Observe one real Kindle minute boundary and a same-content sync."""
import json
import os
from pathlib import Path
import time
from PIL import Image, ImageChops
from kindle_ssh import run

DEVICE = "/mnt/us/koreader/settings/kindle-agent-dashboard"
OUT = Path(__file__).resolve().parents[1] / ".runtime/device"


def remote(command):
    return run(command, capture_output=True, text=True).stdout.strip()


def status():
    return json.loads(remote("cat " + DEVICE + "/status.json"))


def shot(name):
    remote("touch " + DEVICE + "/screenshot.request")
    for _ in range(12):
        if remote("if test -f " + DEVICE + "/screenshot.request; then echo pending; fi") != "pending":
            break
        time.sleep(0.25)
    path=OUT/name
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,"wb") as out:
        run("cat " + DEVICE + "/screen.png",stdout=out)
    return path


def main():
    before=status()
    assert before.get("active") and "refresh_batches" in before, "Updated view is not loaded"
    remote("touch " + DEVICE + "/refresh.request")
    # Wait for the marker and background fetch to finish; sync itself must not repaint.
    for _ in range(12):
        time.sleep(0.5)
        pending=remote("if test -f " + DEVICE + "/refresh.request; then echo pending; elif test -f " + DEVICE + "/request-result.json; then cat " + DEVICE + "/request-result.json; fi")
        if pending and pending != "pending":
            value=json.loads(pending)
            if value.get("ok") and value.get("at",0)>=before["rendered_at"]:
                break
    after=status()
    if before["clock"]==after["clock"]:
        assert before["renders"]==after["renders"], "Same-content sync repainted"
        print("PASS: same-content authenticated sync did not repaint",flush=True)
    first=shot("regional-before.png")
    before=status()
    for _ in range(34):
        time.sleep(2)
        after=status()
        if after["clock"]!=before["clock"]:
            break
    else:
        raise RuntimeError("No minute boundary observed")
    second=shot("regional-after.png")
    assert after["full_refreshes"]==before["full_refreshes"], "Unexpected full refresh"
    assert after["last_refresh"]["mode"]=="ui" and after["last_refresh"]["regions"]==["clock"], "Expected clock-only UI update"
    diff=ImageChops.difference(Image.open(first).convert("RGB"),Image.open(second).convert("RGB"))
    box=diff.getbbox()
    assert box and box[0]>=40 and box[1]>=20 and box[2]<=430 and box[3]<=150, f"Unexpected pixel change outside clock: {box}"
    print("PASS: real minute advanced; changed pixels confined to clock",box,flush=True)
    print("PASS: no full-screen refresh requested across the minute",flush=True)


if __name__=="__main__":
    main()
