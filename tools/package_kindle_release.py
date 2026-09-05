#!/usr/bin/env python3
"""Build a credential-free USB package for the KOReader dashboard plugin."""

from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "device/koreader/plugins/kindleagentdashboard.koplugin"
CONFIG = ROOT / "device/koreader/config.example.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/kindle-dashboard-kindle.zip")
    args = parser.parse_args()
    if not PLUGIN.is_dir():
        parser.error(f"plugin directory not found: {PLUGIN}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PLUGIN.rglob("*")):
            if path.is_file():
                archive.write(path, Path("koreader/plugins") / PLUGIN.name / path.relative_to(PLUGIN))
        archive.write(CONFIG, "koreader/settings/kindle-agent-dashboard/config.example.json")
        readme = ROOT / "docs/INSTALL-KINDLE.md"
        archive.write(readme, "INSTALL-KINDLE.md")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
