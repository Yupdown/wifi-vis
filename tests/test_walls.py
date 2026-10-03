from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from wifivis.walls import load_wall_map


class WallImageTests(unittest.TestCase):
    def test_light_and_dark_backgrounds_produce_same_obstacles(self):
        with tempfile.TemporaryDirectory() as directory:
            ink = np.zeros((80, 120), np.uint8)
            ink[20:60, 50:60] = 255
            light = Path(directory) / "밝은 평면도.png"
            dark = Path(directory) / "dark.png"
            Image.fromarray(255-ink).save(light)
            Image.fromarray(ink).save(dark)
            first, second = load_wall_map(light), load_wall_map(dark)
            self.assertTrue(first.inverted)
            self.assertFalse(second.inverted)
            self.assertLessEqual(np.abs(first.pixels.astype(int)-second.pixels).max(), 1)
            self.assertGreater(first.pixels[80, 110], 240)
            self.assertEqual(first.pixels[0, 0], 0)
            manual = load_wall_map(light, invert=False)
            self.assertEqual(manual.pixels[0, 0], 255)

    def test_transparent_background_is_empty_for_both_ink_colors(self):
        with tempfile.TemporaryDirectory() as directory:
            for color in (0, 255):
                rgba = np.zeros((80, 120, 4), np.uint8)
                rgba[20:60, 50:60, :3] = color
                rgba[20:60, 50:60, 3] = 255
                path = Path(directory) / f"alpha-{color}.png"
                Image.fromarray(rgba).save(path)
                result = load_wall_map(path)
                self.assertEqual(result.pixels[0, 0], 0)
                self.assertGreater(result.pixels[80, 110], 240)

    def test_large_image_retains_aspect_ratio_with_bounded_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.png"
            Image.new("L", (3200, 1600)).save(path)
            result = load_wall_map(path)
            h, w = result.pixels.shape
            self.assertAlmostEqual(w/h, 2, delta=.01)
            self.assertLessEqual(max(w, h), 1074)
            self.assertLessEqual(w*h, 362000)


if __name__ == "__main__":
    unittest.main()
