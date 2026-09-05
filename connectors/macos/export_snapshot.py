#!/usr/bin/env python3
"""Read Calendar and Reminders into one private, atomic V13 snapshot."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.9 on macOS provides zoneinfo
    ZoneInfo = None  # type: ignore


ROOT = Path(__file__).resolve().parents[2]
HELPER_SOURCE = Path(__file__).with_name("eventkit_export.swift")
RUNTIME_DIR = ROOT / ".runtime" / "macos"
HELPER_BINARY = RUNTIME_DIR / "eventkit_export"
TIMEZONE = "Asia/Shanghai"


def export_range(today: date = None) -> Tuple[date, date]:
    """Return [first day of previous month, first day of month after next)."""
    if today is None:
        today = date.today()
    month_zero = today.year * 12 + today.month - 1
    start_zero = month_zero - 1
    end_zero = month_zero + 2
    return (
        date(start_zero // 12, start_zero % 12 + 1, 1),
        date(end_zero // 12, end_zero % 12 + 1, 1),
    )


def epoch_at_midnight(day: date) -> int:
    if ZoneInfo is None:
        raise RuntimeError("Python zoneinfo is required for the V13 exporter")
    from datetime import datetime
    return int(datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(TIMEZONE)).timestamp())


def build_helper() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if HELPER_BINARY.exists() and HELPER_BINARY.stat().st_mtime >= HELPER_SOURCE.stat().st_mtime:
        return HELPER_BINARY
    command = ["swiftc", str(HELPER_SOURCE), "-framework", "EventKit", "-o", str(HELPER_BINARY)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        detail = completed.stderr.strip() or "swiftc failed"
        raise RuntimeError("unable to build the local EventKit helper: " + detail)
    return HELPER_BINARY


def source_status(ok: bool, updated_at: int, count: int, error: Any = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"ok": bool(ok), "updated_at": updated_at, "count": count}
    if error:
        result["error"] = str(error)
    return result


def fallback_payload(error: str) -> Dict[str, Any]:
    return {"calendar": {"ok": False, "error": error, "items": []}, "reminders": {"ok": False, "error": error, "items": []}}


def read_eventkit(start: date, end: date) -> Dict[str, Any]:
    try:
        helper = build_helper()
        result = subprocess.run(
            [str(helper), "--range-start", str(epoch_at_midnight(start)), "--range-end", str(epoch_at_midnight(end))],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            return fallback_payload("EventKit helper failed: " + (result.stderr.strip() or "unknown error"))
        return json.loads(result.stdout)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return fallback_payload(str(exc))


def make_snapshot(raw: Dict[str, Any], start: date, end: date, generated_at: int = None) -> Dict[str, Any]:
    now = int(time.time()) if generated_at is None else generated_at
    calendar = raw.get("calendar") or {}
    reminders = raw.get("reminders") or {}
    events = calendar.get("items") if calendar.get("ok") else []
    tasks = reminders.get("items") if reminders.get("ok") else []
    return {
        "schema_version": 1,
        "generated_at": now,
        "timezone": TIMEZONE,
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "events": events,
        "tasks": tasks,
        "sources": {
            "calendar": source_status(calendar.get("ok", False), now, len(events), calendar.get("error")),
            "reminders": source_status(reminders.get("ok", False), now, len(tasks), reminders.get("error")),
        },
    }


def atomic_json_dump(output: Path, payload: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".snapshot-", suffix=".json", dir=str(output.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export a read-only macOS V13 snapshot")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    start, end = export_range()
    snapshot = make_snapshot(read_eventkit(start, end), start, end)
    atomic_json_dump(args.output, snapshot)
    sources = snapshot["sources"]
    print("calendar ok={0} count={1}; reminders ok={2} count={3}".format(
        sources["calendar"]["ok"], sources["calendar"]["count"],
        sources["reminders"]["ok"], sources["reminders"]["count"],
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
