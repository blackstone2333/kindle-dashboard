import hashlib
import unittest
from pathlib import Path

from app import DEFAULT_FIXTURE, GRAY_LEVELS, LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, prepare_data, render_landscape_v8


class LandscapeV8Tests(unittest.TestCase):
    def test_v8_is_low_color_landscape_and_keeps_v7(self):
        data, degraded = prepare_data(DEFAULT_FIXTURE)
        self.assertEqual(degraded, [])
        image = render_landscape_v8(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertIsNotNone(colors)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
        self.assertEqual(tuple(image.getpalette()[: GRAY_LEVELS * 3 : 3]), PALETTE)
        root = Path(__file__).parents[1] / "public/pages"
        self.assertEqual(hashlib.sha256((root / "landscape-mockup-v7.png").read_bytes()).hexdigest(), "f2dd1f65d4a7a945e03d31fcbcc43c9cf90d680f3cfe6fe6efadb732a400e39a")


if __name__ == "__main__":
    unittest.main()
