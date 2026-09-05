import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from connectors.macos import export_snapshot


class MacOSExportTests(unittest.TestCase):
    def test_range_covers_previous_month_through_month_after_next(self):
        self.assertEqual(
            export_snapshot.export_range(date(2026, 9, 5)),
            (date(2026, 8, 1), date(2026, 11, 1)),
        )

    def test_snapshot_keeps_successful_source_when_other_source_fails(self):
        start, end = date(2026, 8, 1), date(2026, 11, 1)
        raw = {
            "calendar": {"ok": False, "error": "not authorized", "items": []},
            "reminders": {"ok": True, "items": [{"id": "r1", "title": "private", "due": None}]},
        }
        snapshot = export_snapshot.make_snapshot(raw, start, end, generated_at=42)
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["events"], [])
        self.assertEqual(snapshot["tasks"], raw["reminders"]["items"])
        self.assertEqual(snapshot["sources"]["calendar"], {"ok": False, "updated_at": 42, "count": 0, "error": "not authorized"})
        self.assertEqual(snapshot["sources"]["reminders"], {"ok": True, "updated_at": 42, "count": 1})

    def test_atomic_writer_leaves_valid_final_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "apple.json"
            export_snapshot.atomic_json_dump(output, {"schema_version": 1, "events": []})
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"schema_version": 1, "events": []})
            self.assertFalse(list(output.parent.glob(".snapshot-*.json")))


if __name__ == "__main__":
    unittest.main()
