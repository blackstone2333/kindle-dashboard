import unittest
from pathlib import Path

from app import GRAY_LEVELS, LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, prepare_data, render_landscape_v9, DEFAULT_FIXTURE


class LandscapeV9Tests(unittest.TestCase):
    def test_v9_weather_alignment_surface_is_low_color(self):
        data, degraded = prepare_data(DEFAULT_FIXTURE)
        self.assertEqual(degraded, [])
        image = render_landscape_v9(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertIsNotNone(colors)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
        self.assertEqual(tuple(image.getpalette()[: GRAY_LEVELS * 3 : 3]), PALETTE)
        self.assertTrue((Path(__file__).parents[1] / "public/pages/landscape-mockup-v8.png").exists())


if __name__ == "__main__":
    unittest.main()
