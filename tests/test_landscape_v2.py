import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app import (
    DEFAULT_FIXTURE,
    DashboardState,
    GRAY_LEVELS,
    LANDSCAPE_HEIGHT,
    LANDSCAPE_WIDTH,
    PALETTE,
    _landscape_future_events,
    prepare_data,
    render_landscape_v2,
)


class LandscapeV2Tests(unittest.TestCase):
    def test_v2_render_is_pw3_landscape_low_color(self):
        data, degraded = prepare_data(DEFAULT_FIXTURE)
        self.assertEqual(degraded, [])
        image = render_landscape_v2(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertIsNotNone(colors)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
        self.assertEqual(tuple(image.getpalette()[: GRAY_LEVELS * 3 : 3]), PALETTE)

    def test_future_strip_is_bounded_and_has_required_fields(self):
        data, _ = prepare_data(DEFAULT_FIXTURE)
        items = _landscape_future_events(data)
        self.assertGreaterEqual(len(items), 3)
        self.assertLessEqual(len(items), 5)
        self.assertTrue(all({"date", "weekday", "time", "title", "kind"} <= set(item) for item in items))

    def test_empty_payload_keeps_v2_safe_fallback(self):
        data, reasons = prepare_data({"events": [], "tasks": [], "news": [], "weather": {}, "future_events": []})
        self.assertIn("future_events_empty", reasons)
        image = render_landscape_v2(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))

    def test_v2_is_not_added_to_portrait_manifest_and_v1_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            state = DashboardState(Path(directory) / "assets")
            self.assertNotIn("landscape-mockup-v2", {page["id"] for page in state.manifest["pages"]})
        v1 = Path(__file__).parents[1] / "public/pages/landscape-mockup.png"
        digest = hashlib.sha256(v1.read_bytes()).hexdigest()
        self.assertEqual(digest, "a36ebbf1535e7ac9212092a4d4a3a1427f641e20de266032d28043b1240457c1")


if __name__ == "__main__":
    unittest.main()
