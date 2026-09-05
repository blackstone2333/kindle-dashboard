import hashlib
import unittest
from pathlib import Path

from app import DEFAULT_FIXTURE, GRAY_LEVELS, LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, prepare_data, render_landscape_v7


class LandscapeV7Tests(unittest.TestCase):
    def test_v7_is_low_color_landscape_and_keeps_v6(self):
        data, degraded = prepare_data(DEFAULT_FIXTURE)
        self.assertEqual(degraded, [])
        image = render_landscape_v7(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertIsNotNone(colors)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
        self.assertEqual(tuple(image.getpalette()[: GRAY_LEVELS * 3 : 3]), PALETTE)
        root = Path(__file__).parents[1] / "public/pages"
        self.assertEqual(hashlib.sha256((root / "landscape-mockup-v6.png").read_bytes()).hexdigest(), "504455e6e27e98b65d0346c1ee35a2601e3ea14cd9410350f76c061777ffecb9")


if __name__ == "__main__":
    unittest.main()
