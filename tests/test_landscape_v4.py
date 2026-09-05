import hashlib
import unittest
from pathlib import Path

from PIL import Image

from app import DEFAULT_FIXTURE, GRAY_LEVELS, LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, prepare_data, render_landscape_v4


class LandscapeV4Tests(unittest.TestCase):
    def test_v4_uses_vendored_lucide_assets(self):
        root = Path(__file__).parents[1] / "assets/icons/lucide"
        for name in ("cloud-sun", "cloud", "cloud-rain", "sun", "settings", "wifi", "battery"):
            self.assertTrue((root / f"{name}.svg").is_file())
            self.assertTrue((root / "png" / f"{name}.png").is_file())
        self.assertIn("ISC", (root / "NOTICE.md").read_text(encoding="utf-8"))

    def test_v4_is_landscape_16_level_grayscale(self):
        data, degraded = prepare_data(DEFAULT_FIXTURE)
        self.assertEqual(degraded, [])
        image = render_landscape_v4(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertIsNotNone(colors)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
        self.assertEqual(tuple(image.getpalette()[: GRAY_LEVELS * 3 : 3]), PALETTE)

    def test_previous_landscape_previews_are_unchanged(self):
        root = Path(__file__).parents[1] / "public/pages"
        expected = {
            "landscape-mockup.png": "a36ebbf1535e7ac9212092a4d4a3a1427f641e20de266032d28043b1240457c1",
            "landscape-mockup-v2.png": "fe4189360943789c376449d9bc848592c2282e96b934aba6ec50a15260563483",
            "landscape-mockup-v3.png": "f723c9e58952d000898cb4675b960d0596b7499d9f9a4186a905f4b1d11a5535",
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
