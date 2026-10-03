from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageSequence

from wifivis.gif_export import frame_durations, phase_offsets, save_gif


class GifTests(unittest.TestCase):
    def test_phase_sampling_and_float32_rounding(self):
        offsets = phase_offsets(7.2, 2.4)
        self.assertEqual(len(offsets), 50)
        self.assertEqual(offsets[0], 0)
        self.assertAlmostEqual(offsets[-1] * .028 * 360, 352.8)
        self.assertEqual(len(phase_offsets(float(np.float32(7.2)), 2.4)), 50)
        self.assertEqual(len(phase_offsets(7, 2.4)), 52)
        self.assertAlmostEqual(phase_offsets(7.2, 4.8)[1], offsets[1] / 2)
        for invalid in (0, -1, 181, float("nan")):
            with self.assertRaises(ValueError):
                phase_offsets(invalid, 2.4)

    def test_encoded_gif_has_50_frames_and_exact_20ms_delays(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "위상.gif"
            frames = [Image.new("RGB", (16, 12), (i*5, 0, 0)) for i in range(50)]
            save_gif(path, frames, 7.2, 1)
            with Image.open(path) as image:
                self.assertEqual(image.n_frames, 50)
                self.assertEqual(image.info["loop"], 0)
                durations = [frame.info["duration"] for frame in ImageSequence.Iterator(image)]
                self.assertEqual(durations, frame_durations(50))
                self.assertEqual(sum(durations), 1000)
                self.assertIn(b"FPS=50", image.info["comment"])

    def test_failed_encoding_keeps_existing_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keep.gif"
            path.write_bytes(b"Existing content")
            with self.assertRaises(IndexError):
                save_gif(path, [], 7.2, 1)
            self.assertEqual(path.read_bytes(), b"Existing content")
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
