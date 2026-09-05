import hashlib
import unittest
from pathlib import Path

from PIL import Image

from app import DEFAULT_FIXTURE, GRAY_LEVELS, LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, prepare_data, render_landscape_v5


class LandscapeV5Tests(unittest.TestCase):
    def test_v5_is_landscape_low_color_and_previous_versions_stay_fixed(self):
        data, degraded = prepare_data(DEFAULT_FIXTURE)
        self.assertEqual(degraded, [])
        image = render_landscape_v5(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertIsNotNone(colors)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
        self.assertEqual(tuple(image.getpalette()[: GRAY_LEVELS * 3 : 3]), PALETTE)
        root = Path(__file__).parents[1] / "public/pages"
        self.assertEqual(hashlib.sha256((root / "landscape-mockup-v4.png").read_bytes()).hexdigest(), "df71bc9c31748802e4b8b0c9202a55a93bde0f18d56530e81ed3bd6f0598096b")


if __name__ == "__main__":
    unittest.main()
