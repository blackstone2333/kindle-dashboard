import unittest
from app import DEFAULT_FIXTURE, GRAY_LEVELS, LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, prepare_data, render_landscape_v13

class LandscapeV13Tests(unittest.TestCase):
    def test_v13_is_landscape_16_gray(self):
        data, degraded = prepare_data(DEFAULT_FIXTURE)
        self.assertEqual(prepare_data(DEFAULT_FIXTURE)[1], [])
        image = render_landscape_v13(data)
        self.assertEqual(image.size, (LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT))
        self.assertEqual(image.mode, "P")
        colors = image.convert("RGB").getcolors(maxcolors=100)
        self.assertIsNotNone(colors)
        self.assertLessEqual(len(colors), GRAY_LEVELS)
        self.assertTrue(all(r == g == b for _, (r, g, b) in colors))
        self.assertEqual(tuple(image.getpalette()[: GRAY_LEVELS * 3 : 3]), PALETTE)

if __name__ == "__main__":
    unittest.main()
