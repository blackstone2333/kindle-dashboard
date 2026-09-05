"""Prepare a local pairing config and vendor official Lucide device assets.

The generated config is deliberately written under ``.runtime`` and is not
part of a public release. Pass a token explicitly for a clean checkout; the
local Hub token is accepted as a developer convenience when present.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "device/koreader/plugins/kindleagentdashboard.koplugin/icons"
COMMIT = "796dad298f8d78c5da204c3e62a5ed93c2bfcd1e"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="LAN hub base URL")
    parser.add_argument("--token", help="device token; never commit the generated config")
    args = parser.parse_args()
    if not args.url.startswith(("http://", "https://")):
        parser.error("--url must use http:// or https://")
    ICONS.mkdir(exist_ok=True)
    for path in (ROOT / "assets/icons/lucide/png").glob("*.png"):
        shutil.copy2(path, ICONS / path.name)
    for name in ("wifi-off", "battery-full", "battery-low", "cloud-fog", "snowflake", "cloud-lightning"):
        target = ICONS / (name + ".svg")
        if not target.exists():
            url = f"https://raw.githubusercontent.com/lucide-icons/lucide/{COMMIT}/icons/{name}.svg"
            with urlopen(url, timeout=20) as response:
                target.write_bytes(response.read())
    license_path = ICONS / "LICENSE"
    if not license_path.exists():
        with urlopen(f"https://raw.githubusercontent.com/lucide-icons/lucide/{COMMIT}/LICENSE", timeout=20) as response:
            license_path.write_bytes(response.read())
    private = ROOT / ".runtime/device"
    private.mkdir(parents=True, exist_ok=True)
    config = private / "config.json"
    fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    token = args.token
    if not token:
        token_path = ROOT / ".runtime/hub/device-token"
        if token_path.exists():
            token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        parser.error("provide --token or create .runtime/hub/device-token locally")
    with os.fdopen(fd, "w") as out:
        json.dump({"url": args.url, "token": token}, out)
    os.chmod(config, 0o600)
    print("Device assets and private pairing config prepared; no credentials displayed.")


if __name__ == "__main__":
    main()
