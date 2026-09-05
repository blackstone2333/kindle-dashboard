import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from PIL import Image

from app import DEFAULT_FIXTURE, DashboardState, GRAY_LEVELS, HEIGHT, LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, WIDTH, build_landscape_timeline, get_font, make_handler, prepare_data, render_landscape, wrap_text
from http.server import ThreadingHTTPServer


class DashboardPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = DashboardState(Path(self.tmp.name) / "assets")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pages_are_pw3_16_level_pngs(self):
        for page in self.state.manifest["pages"]:
            image = Image.open(Path(self.tmp.name) / "assets" / page["path"].lstrip("/"))
            self.assertEqual(image.size, (WIDTH, HEIGHT))
            self.assertEqual(image.mode, "P")
            colors = image.convert("RGB").getcolors(maxcolors=100)
            self.assertIsNotNone(colors)
            self.assertLessEqual(len(colors), GRAY_LEVELS)
            self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
            palette = image.getpalette()[: GRAY_LEVELS * 3]
            self.assertEqual(tuple(palette[::3]), PALETTE)

    def test_landscape_mockup_is_separate_and_low_color(self):
        data, _ = prepare_data(DEFAULT_FIXTURE)
        image = render_landscape(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))

    def test_landscape_timeline_is_time_sorted_and_keeps_kinds(self):
        data, _ = prepare_data(DEFAULT_FIXTURE)
        timeline = build_landscape_timeline(data)
        self.assertEqual([item["time"] for item in timeline[:3]], ["09:30", "10:45", "14:00"])
        self.assertIn("待办", {item["kind"] for item in timeline})

    def test_manifest_contains_rotation_and_fallback_contract(self):
        self.assertEqual(self.state.manifest["manifest_version"], "1")
        self.assertEqual([page["hold_seconds"] for page in self.state.manifest["pages"]], [45, 45])
        self.assertEqual(self.state.manifest["fallback"]["long_text"], "wrap-then-ellipsis")
        self.assertIn("valid_until", self.state.manifest)

    def test_empty_payload_degrades_without_crashing(self):
        normalized, reasons = prepare_data({"events": [], "tasks": [], "news": [], "weather": {}})
        self.assertTrue(reasons)
        self.assertEqual(normalized["events"][0]["title"], "暂无日程")
        self.assertEqual(normalized["tasks"][0]["title"], "暂无待办")

    def test_long_text_is_marked_when_line_limit_is_reached(self):
        from PIL import ImageDraw

        image = Image.new("L", (1000, 200), 255)
        draw = ImageDraw.Draw(image)
        lines = wrap_text(draw, "这是一个需要在窄屏上明确截断的很长标题" * 4, get_font(30, True), 820, max_lines=1)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].endswith("…"))

    def test_http_manifest_health_and_pages(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            connection.request("GET", "/health")
            response = connection.getresponse()
            health = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(health["version"], "0.1.0")
            connection.request("GET", "/manifest.json")
            response = connection.getresponse()
            manifest = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(len(manifest["pages"]), 2)
            connection.request("GET", manifest["pages"][0]["path"])
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Content-Type"), "image/png")
            connection.request("GET", "/api/landscape/manifest")
            response = connection.getresponse()
            landscape = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(landscape["layout_version"], "v13")
            self.assertEqual(landscape["device"]["width"], LANDSCAPE_WIDTH)
            self.assertEqual(landscape["device"]["height"], LANDSCAPE_HEIGHT)
            self.assertEqual(landscape["page"]["path"], "/pages/landscape-mockup-v13.png")
            connection.request("GET", landscape["page"]["path"])
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Content-Type"), "image/png")
            connection.request("GET", "/landscape/not-found.json")
            response = connection.getresponse()
            self.assertEqual(response.status, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
