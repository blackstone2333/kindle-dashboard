import hashlib
import unittest
from pathlib import Path

from app import DEFAULT_FIXTURE, GRAY_LEVELS, LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, prepare_data, render_landscape_v6


class LandscapeV6Tests(unittest.TestCase):
    def test_v6_is_low_color_landscape_and_keeps_v5(self):
        data, degraded = prepare_data(DEFAULT_FIXTURE)
        self.assertEqual(degraded, [])
        image = render_landscape_v6(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertIsNotNone(colors)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
        self.assertEqual(tuple(image.getpalette()[: GRAY_LEVELS * 3 : 3]), PALETTE)
        root = Path(__file__).parents[1] / "public/pages"
        self.assertEqual(hashlib.sha256((root / "landscape-mockup-v5.png").read_bytes()).hexdigest(), "acb27f521dd5df3b78711f5344d0aafa34785e7ca137c91364c41d7f171ce085")

    def test_battery_medium_asset_exists(self):
        root = Path(__file__).parents[1] / "assets/icons/lucide"
        self.assertTrue((root / "battery-medium.svg").is_file())
        self.assertTrue((root / "png/battery-medium.png").is_file())


if __name__ == "__main__":
    unittest.main()
