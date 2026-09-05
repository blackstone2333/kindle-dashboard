#!/usr/bin/env python3
"""Publish one structured Agent card to a running local Hub."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


CARD_TYPES = ("briefing", "news", "english", "divination", "photo", "quote", "horoscope", "question", "task")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card_id")
    parser.add_argument("--type", choices=CARD_TYPES, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--expires-at", type=int)
    parser.add_argument("--url", default="http://127.0.0.1:18501")
    parser.add_argument("--data-dir", type=Path, default=Path(".runtime/hub"))
    args = parser.parse_args()
    token = (args.data_dir / "agent-token").read_text(encoding="utf-8").strip()
    document = {"type": args.type, "title": args.title, "body": args.body}
    if args.expires_at is not None:
        document["expires_at"] = args.expires_at
    payload = json.dumps(document, ensure_ascii=False).encode("utf-8")
    request = Request(args.url.rstrip("/") + "/api/v1/cards/" + quote(args.card_id, safe=""),
                      data=payload, method="PUT",
                      headers={"Authorization": "Bearer " + token,
                               "Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        print(response.read().decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
