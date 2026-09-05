import datetime as dt
import json
import os
from pathlib import Path
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from tempfile import TemporaryDirectory
from unittest.mock import patch

from hub.server import SHANGHAI, SnapshotHandler, SnapshotHub, _date_range, _calendar_day


def export_document(calendar_ok=True, reminders_ok=True, events=None, tasks=None):
    return {"schema_version": 1, "generated_at": 123, "timezone": "Asia/Shanghai",
            "range_start": "2026-08-01", "range_end": "2026-11-01", "events": events if events is not None else [],
            "tasks": tasks if tasks is not None else [], "sources": {
              "calendar": {"ok": calendar_ok, "updated_at": 123, "count": len(events or [])},
              "reminders": {"ok": reminders_ok, "updated_at": 123, "count": len(tasks or [])}}}


class HubTests(unittest.TestCase):
    def test_location_configuration_invalidates_other_city_cache(self):
        self.hub.state["weather"].update(location="上海", temperature=31, updated_at=123, ok=True)
        self.hub.location_path.write_text(json.dumps({"city":"Test City", "latitude":12.3456, "longitude":78.9012}))
        self.assertTrue(self.hub._load_location())
        self.assertEqual(self.hub.city, "Test City")
        self.assertEqual(self.hub.latitude, 12.3456)
        self.assertIsNone(self.hub.state["weather"]["temperature"])
        self.assertFalse(self.hub.state["weather"]["ok"])

    def test_snapshot_remains_available_during_export(self):
        import time
        self.hub.exporter.write_text("import time; time.sleep(0.4)")
        worker = threading.Thread(target=self.hub.refresh_export)
        worker.start()
        time.sleep(0.05)
        acquired = self.hub.lock.acquire(timeout=0.1)
        if acquired:
            self.hub.lock.release()
        worker.join()
        self.assertTrue(acquired)

    def test_device_contract_and_weather_units(self):
        self.hub.state["weather"].update(wind_level=19.8, ok=True, updated_at=123)
        doc = self.hub.build_snapshot()
        self.assertEqual(doc["schema_version"], 1)
        self.assertIsInstance(doc["generated_at"], int)
        self.assertIn("range_start", doc)
        self.assertIn("range_end", doc)
        self.assertTrue(doc["sources"]["weather"]["ok"])
        self.assertEqual(doc["weather"]["wind_level"], 3)
        self.assertEqual(doc["weather"]["location"], "上海")

    def test_agent_card_is_cached_exposed_and_expired(self):
        card = self.hub.put_card("divination-2026-09-05", {
            "type": "divination", "title": "今日一签", "body": "宜静心读书，娱乐内容。",
            "generated_at": 100, "expires_at": 200, "symbol": "中签",
        })
        self.assertEqual(card["id"], "divination-2026-09-05")
        self.hub.now = lambda: 150
        self.assertEqual(self.hub.build_snapshot()["cards"][0]["type"], "divination")
        self.hub.now = lambda: 201
        self.assertEqual(self.hub.build_snapshot()["cards"], [])

    def test_agent_card_endpoint_uses_separate_token(self):
        SnapshotHandler.hub = self.hub
        server = ThreadingHTTPServer(("127.0.0.1", 0), SnapshotHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_port)
            body = json.dumps({"type": "divination", "title": "今日一卦", "body": "宜静心"})
            conn.request("PUT", "/api/v1/cards/today", body=body,
                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.hub.agent_token})
            self.assertEqual(conn.getresponse().status, 200)
            conn.request("GET", "/api/v1/snapshot", headers={"Authorization": "Bearer " + self.hub.token})
            snapshot = json.loads(conn.getresponse().read())
            self.assertEqual(snapshot["cards"][0]["type"], "divination")
        finally:
            server.shutdown(); server.server_close()

    def test_lunar_label_and_current_solar_term(self):
        day = _calendar_day(dt.date(2026, 9, 5))
        self.assertTrue(day["lunar"].startswith("农历七月"))
        self.assertIn("丙午马年", day["lunar"])
        self.assertEqual(day["solar_term"], "处暑")
        self.assertEqual(day["solar_term_date"], "8月23日")
        self.assertEqual(day["next_solar_term"], "白露")
        self.assertEqual(day["next_solar_term_date"], "9月7日")

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.hub = SnapshotHub(self.root / "hub", exporter=self.root / "missing.py")

    def tearDown(self):
        self.temp.cleanup()

    def test_token_is_private_and_auth_is_required(self):
        token_file = self.root / "hub" / "device-token"
        self.assertEqual(os.stat(token_file).st_mode & 0o777, 0o600)
        SnapshotHandler.hub = self.hub
        server = ThreadingHTTPServer(("127.0.0.1", 0), SnapshotHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_port)
            conn.request("GET", "/api/v1/snapshot")
            self.assertEqual(conn.getresponse().status, 401)
            conn.request("GET", "/health")
            health = json.loads(conn.getresponse().read())
            self.assertNotIn("token", json.dumps(health))
            conn.request("GET", "/api/v1/snapshot", headers={"Authorization": "Bearer " + self.hub.token})
            self.assertEqual(conn.getresponse().status, 200)
        finally:
            server.shutdown(); server.server_close()

    def test_per_source_failure_keeps_last_good_data_and_full_counts(self):
        events = [{"id": str(i), "title": "private", "calendar": "c"} for i in range(101)]
        tasks = [{"id": str(i), "title": "private"} for i in range(103)]
        self.hub._merge_export(export_document(events=events, tasks=tasks))
        self.hub._merge_export(export_document(calendar_ok=False, reminders_ok=True, events=[], tasks=[{"id": "new"}]))
        snapshot = self.hub.build_snapshot()
        self.assertEqual(len(snapshot["events"]), 101)
        self.assertEqual(len(snapshot["tasks"]), 1)
        self.assertFalse(snapshot["sources"]["calendar"]["ok"])
        self.assertEqual(snapshot["sources"]["calendar"]["count"], 101)

    def test_current_day_metadata_and_timezone_range(self):
        snapshot = self.hub.build_snapshot()
        today = dt.datetime.now(SHANGHAI).date().isoformat()
        self.assertEqual(snapshot["utc_offset"], 28800)
        self.assertIn(today, snapshot["days"])
        self.assertEqual(snapshot["days"][today]["almanac"].keys(), {"yi", "ji"})
        self.assertIn("2026-07-01", snapshot["days"])
        self.assertIn("2026-11-30", snapshot["days"])
        self.assertNotIn("2026-12-01", snapshot["days"])

    def test_month_range_crosses_year_boundary_in_shanghai_calendar(self):
        start, end = _date_range(dt.date(2026, 1, 1))
        self.assertEqual(start.isoformat(), "2025-11-01")
        self.assertEqual(end.isoformat(), "2026-04-01")

    def test_missing_exporter_and_weather_failure_do_not_destroy_cache(self):
        self.hub._merge_export(export_document(events=[{"id": "e"}], tasks=[{"id": "t"}]))
        self.assertFalse(self.hub.refresh_export())
        self.assertEqual(len(self.hub.build_snapshot()["events"]), 1)
        with patch("hub.server.urlopen", side_effect=OSError("offline")):
            self.assertFalse(self.hub.refresh_weather())
        self.assertEqual(len(self.hub.build_snapshot()["tasks"]), 1)


if __name__ == "__main__":
    unittest.main()
