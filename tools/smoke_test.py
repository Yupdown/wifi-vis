"""Exercise the real GL solver, UI renderer and pointer handling in a hidden window."""
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from OpenGL import GL as gl
from PIL import Image, ImageDraw
from wifivis.app import Application


def main():
    app = Application(hidden=True)
    try:
        print("GPU:", gl.glGetString(gl.GL_RENDERER).decode())
        app.frame(1/60)
        before = app.gpu.read_state()
        assert np.isfinite(before).all() and np.max(np.abs(before[:, :, 0])) > .01
        # Feed mouse events through the actual ImGui canvas (not just the model).
        left, top, width, height = app.canvas_rect
        original_inputs = app.ui.process_inputs
        mouse = [left + .8 * width, top + .45 * height, False]
        def inputs():
            import imgui
            original_inputs()
            io = imgui.get_io()
            io.mouse_pos = (mouse[0], mouse[1])
            io.mouse_down[0] = mouse[2]
        app.ui.process_inputs = inputs
        app.frame(1/60)
        mouse[2] = True
        app.frame(1/60)
        mouse[:2] = [left + .7 * width, top + .4 * height]
        app.frame(1/60)
        mouse[2] = False
        app.frame(1/60)
        assert abs(app.scene.current().x-.7) < .01, "ImGui marker dragging must move the source"
        app.ui.process_inputs = original_inputs
        app.adding = True
        app.pointer(.4, .3, 300, 900, True, True, False, True)
        assert len(app.scene.sources) == 2
        added = app.scene.current()
        app.pointer(.6, .2, 300, 900, True, False, False, True)
        app.pointer(.6, .2, 300, 900, True, False, False, False)
        assert abs(added.x-.6) < 1e-6 and abs(added.y-.2) < 1e-6
        for _ in range(50):
            app.frame(1/60)
        after = app.gpu.read_state()
        assert np.isfinite(after).all() and not np.allclose(before, after)
        app.paused = True
        app.frame(1/60)
        assert np.array_equal(after, app.gpu.read_state()), "Pause must freeze simulation"
        app.paused = False
        app.gpu.clear()
        assert not np.any(app.gpu.read_state()[:, :, :3])
        for source in app.scene.sources:
            source.enabled = False
        app.gpu.step(app.scene.sources, 30)
        assert not np.any(app.gpu.read_state()[:, :, :3]), "Disabled sources must not emit"
        for source in app.scene.sources:
            source.enabled = True
        app.gpu.clear()
        app.gpu.step(app.scene.sources, 700, walls=True)
        with_walls = app.gpu.read_state()
        app.gpu.clear()
        app.gpu.step(app.scene.sources, 700, walls=False)
        without_walls = app.gpu.read_state()
        assert not np.allclose(with_walls, without_walls), "Walls must change propagation"
        app.gpu.clear()
        app.gpu.step(app.scene.sources, 1600)
        app.frame(1/60)
        assert np.isfinite(app.gpu.read_state()).all()
        app.screenshot("artifacts/app-preview.png")
        app.mode = 1
        app.frame(1/60)
        app.screenshot("artifacts/app-mean-intensity.png")
        # Replacing maps must resize the solver, preserve sources, and survive
        # invalid files/cancellation without losing the current working map.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "사용자 평면도.png"
            plan = Image.new("L", (600, 360), 255)
            drawing = ImageDraw.Draw(plan)
            drawing.rectangle((40, 40, 560, 320), outline=0, width=4)
            drawing.line((300, 40, 300, 220), fill=0, width=5)
            plan.save(path)
            positions = [(s.x, s.y) for s in app.scene.sources]
            with patch("wifivis.app.choose_wall_file", return_value=path):
                app.browse_wall()
            app.paused = True
            app.frame(1/60)
            assert app.wall_path == path.resolve() and app.wall_inverted
            assert abs(app.gpu.width/app.gpu.height-600/360) < .01
            assert positions == [(s.x, s.y) for s in app.scene.sources]
            assert not np.any(app.gpu.read_state()[:, :, :3])
            current_texture = app.gpu.output
            with patch("wifivis.app.choose_wall_file", return_value=None):
                app.browse_wall()
            assert app.pending_wall is None and app.gpu.output == current_texture
            bad = Path(directory) / "broken.png"
            bad.write_text("This is not an image", encoding="utf-8")
            assert not app.load_wall(bad)
            assert app.gpu.output == current_texture and app.wall_path == path.resolve()
            app.frame(1/60)
            app.wall_error = ""
            app.paused = False
            app.gpu.step(app.scene.sources, 600)
            app.frame(1/60)
            field = app.gpu.read_state()
            assert np.isfinite(field).all() and np.max(np.abs(field[:, :, 0])) > .01
            app.screenshot("artifacts/custom-wall-preview.png")
            assert app.load_wall(path, invert=False) and not app.wall_inverted
            assert app.load_wall() and app.wall_path is None
            assert (app.gpu.width, app.gpu.height) == (336, 1074)
            app.frame(1/60)
        assert gl.glGetError() == gl.GL_NO_ERROR
        print("PASS: shaders, propagation, add/drag, pause, clear, disable, walls, import/resize, cancel/error, restore, screenshot")
    finally:
        app.close()


if __name__ == "__main__":
    main()
