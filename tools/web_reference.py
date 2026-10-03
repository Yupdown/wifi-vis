"""Generate a reproducible desktop-GPU fixture for WebGL parity tests."""
from pathlib import Path
import base64
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import glfw
from PIL import Image, ImageDraw
from wifivis.gpu import WaveGPU
from wifivis.model import Transmitter


def main():
    destination = Path(__file__).resolve().parents[1] / "web-tests/fixtures"
    destination.mkdir(parents=True, exist_ok=True)
    assert glfw.init()
    glfw.window_hint(glfw.VISIBLE, False)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    window = glfw.create_window(64, 64, "Web reference", None, None)
    assert window
    glfw.make_context_current(window)
    gpu = WaveGPU(48, 64)
    try:
        sources = [Transmitter(1, .35, .4), Transmitter(2, .7, .65, .7, 3.2, 75)]
        gpu.step(sources, 240)
        gpu.render()
        data = {
            "width": 48, "height": 64, "ticks": 240,
            "sources": [vars(s) for s in sources],
            "stateFloat32LE": base64.b64encode(gpu.read_state().tobytes()).decode(),
            "rgba": base64.b64encode(gpu.read_image().convert("RGBA").tobytes()).decode(),
        }
        (destination / "desktop-wave.json").write_text(json.dumps(data), encoding="utf-8")
    finally:
        gpu.close()
        glfw.destroy_window(window)
        glfw.terminate()
    wall = Image.new("RGB", (120, 80), "white")
    ImageDraw.Draw(wall).rectangle((55, 10, 65, 70), fill="black")
    wall.save(destination / "wall.png")
    wall.save(destination / "wall.tiff")
    print(destination)


if __name__ == "__main__":
    main()
