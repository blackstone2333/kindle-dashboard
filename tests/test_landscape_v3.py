import hashlib
import unittest
from pathlib import Path

from PIL import Image

from app import DEFAULT_FIXTURE, GRAY_LEVELS, LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, prepare_data, render_landscape_v3


class LandscapeV3Tests(unittest.TestCase):
    def test_v3_is_16_level_grayscale_landscape(self):
        data, degraded = prepare_data(DEFAULT_FIXTURE)
        self.assertEqual(degraded, [])
        image = render_landscape_v3(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertIsNotNone(colors)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
        self.assertEqual(tuple(image.getpalette()[: GRAY_LEVELS * 3 : 3]), PALETTE)

    def test_v3_keeps_v1_and_v2_files_unchanged(self):
        root = Path(__file__).parents[1] / "public/pages"
        self.assertEqual(hashlib.sha256((root / "landscape-mockup.png").read_bytes()).hexdigest(), "a36ebbf1535e7ac9212092a4d4a3a1427f641e20de266032d28043b1240457c1")
        self.assertEqual(hashlib.sha256((root / "landscape-mockup-v2.png").read_bytes()).hexdigest(), "fe4189360943789c376449d9bc848592c2282e96b934aba6ec50a15260563483")


if __name__ == "__main__":
    unittest.main()
