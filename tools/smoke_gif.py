"""Real GPU export, decoded GIF timing, and live-state preservation checks."""
import sys
import time
from pathlib import Path
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image, ImageSequence
from OpenGL import GL as gl
from wifivis.app import Application
from wifivis.gif_export import export_palette


def finish(app):
    deadline = time.monotonic()+30
    while app.gif_job or app.pending_gif:
        app.frame(1/60)
        if time.monotonic() > deadline:
            raise AssertionError("GIF export timed out")
        time.sleep(.001)


def main():
    app = Application(hidden=True)
    try:
        app.paused = True
        app.markers = False
        app.gpu.step(app.scene.sources, 900)
        baseline = app.gpu.read_state()
        tick = app.gpu.tick
        app.gpu.render(app.exposure, app.mode, app.show_walls)
        expected = app.gpu.read_image().quantize(palette=export_palette(), dither=Image.Dither.NONE).convert("RGB")
        path = Path("artifacts/phase-cycle-50fps.gif").resolve()
        path.parent.mkdir(exist_ok=True)
        with patch("wifivis.app.choose_gif_file", return_value=path):
            app.browse_gif()
        finish(app)
        assert not app.gif_error, app.gif_message
        assert app.gpu.tick == tick and np.array_equal(baseline, app.gpu.read_state())
        with Image.open(path) as gif:
            assert gif.n_frames == 50, gif.n_frames
            assert gif.size == (app.gpu.width, app.gpu.height)
            assert np.array_equal(np.asarray(expected), np.asarray(gif.convert("RGB"))), "Frame zero must match live image and orientation"
            frames = [np.array(frame.convert("RGB")) for frame in ImageSequence.Iterator(gif)]
            assert not np.array_equal(frames[0], frames[20]), "Export must animate the wave field"
            gif.seek(0)
            assert [f.info["duration"] for f in ImageSequence.Iterator(gif)] == [20]*50
        app.frame(1/60)
        app.screenshot("artifacts/gif-export-preview.png")
        with tempfile.TemporaryDirectory() as directory:
            cancelled = Path(directory) / "cancelled.gif"
            assert app.start_gif(cancelled, 7.2)
            app.update_gif()
            app.gif_job.cancel()
            app.update_gif()
            assert app.gif_job is None and not cancelled.exists()
            with patch("wifivis.app.choose_gif_file", return_value=None):
                app.browse_gif()
            assert app.pending_gif is None
            missing = Path(directory) / "missing" / "cannot-write.gif"
            assert app.start_gif(missing, 180)
            finish(app)
            assert app.gif_error and not missing.exists()
        assert np.array_equal(baseline, app.gpu.read_state())
        assert gl.glGetError() == gl.GL_NO_ERROR
        print("PASS: 50-frame GPU GIF, exact 50 FPS, orientation, animation, live-state preservation, cancel, save failure")
        print(path)
    finally:
        app.close()


if __name__ == "__main__":
    main()
