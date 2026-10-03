"""One phase cycle, deterministic sampling, and 50 FPS GIF encoding."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import math
import os
from pathlib import Path
import tempfile

import numpy as np
from PIL import Image, ImageDraw

FPS = 50


def phase_offsets(interval, frequency):
    if not math.isfinite(interval) or not 1 <= interval <= 180:
        raise ValueError("Phase step must be between 1 and 180 degrees")
    if not math.isfinite(frequency) or frequency <= 0:
        raise ValueError("Reference frequency must be positive")
    ratio = 360 / interval
    nearest = round(ratio)
    count = nearest if math.isclose(ratio, nearest, rel_tol=1e-7) else math.ceil(ratio)
    cycles_per_tick = .028 * frequency / 2.4
    return [i * interval / (360 * cycles_per_tick) for i in range(count)]


def frame_durations(count):
    # 50 FPS is exactly representable by GIF's integer-centisecond delays.
    return [20] * count


def choose_gif_file(initial_directory=None):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        result = filedialog.asksaveasfilename(
            parent=root, title="Save phase cycle as GIF", initialfile="wifi-field.gif",
            initialdir=str(initial_directory or Path.home()), defaultextension=".gif",
            filetypes=[("Animated GIF", "*.gif")], confirmoverwrite=True)
        return Path(result) if result else None
    finally:
        root.destroy()


def export_palette():
    # Shared palette prevents frame-to-frame color drift. Retain the video LUT
    # plus neutral wall shades and marker colors within GIF's 256-color limit.
    asset = Path(__file__).resolve().parent / "assets/palette.png"
    with Image.open(asset) as image:
        colors = np.asarray(image.convert("RGB"))[0]
    colors = colors[np.linspace(0, 255, 240).round().astype(int)].tolist()
    colors += [[v, v, v] for v in np.linspace(0, 255, 14).round().astype(int).tolist()]
    colors += [[77, 255, 232], [4, 6, 10]]
    palette = Image.new("P", (1, 1))
    palette.putpalette([channel for color in colors for channel in color])
    return palette


def save_gif(path, frames, interval, source_id):
    """Commit only a fully encoded file, keeping any existing file on failure."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".gif", delete=False) as file:
            temporary = Path(file.name)
        frames[0].save(
            temporary, format="GIF", save_all=True, append_images=frames[1:],
            duration=frame_durations(len(frames)), loop=0, disposal=2, optimize=False,
            comment=f"WiFi Field; target FPS={FPS}; phase step={interval:g} deg; cycle=360 deg; reference TX={source_id}".encode())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class GifExport:
    def __init__(self, gpu, scene, path, interval, *, exposure, mode, walls, show_walls,
                 loss, transmission, markers):
        self.path = Path(path)
        if self.path.suffix.lower() != ".gif":
            raise ValueError("Choose a filename ending in .gif")
        self.interval = interval
        self.selected = scene.selected
        self.offsets = phase_offsets(interval, scene.current().frequency)
        self.sources = deepcopy(scene.sources)
        self.exposure, self.mode, self.walls = exposure, mode, walls
        self.show_walls = show_walls
        self.loss, self.transmission, self.markers = loss, transmission, markers
        self.palette = export_palette()
        self.frames = []
        self.advanced = 0
        self.future = None
        self.executor = None
        self.done = False
        self.error = ""
        self.cancelled = False
        self.gpu = gpu.clone()

    @property
    def progress(self):
        return len(self.frames) / len(self.offsets)

    def advance(self):
        """Capture one frame on the GL thread; encoding runs in a worker."""
        if self.done:
            return
        try:
            if self.future is not None:
                if self.future.done():
                    self.future.result()
                    self.done = True
                return
            offset = self.offsets[len(self.frames)]
            target = math.ceil(offset)
            self.gpu.step(self.sources, target-self.advanced, self.loss, self.transmission, self.walls)
            self.advanced = target
            self.gpu.render(self.exposure, self.mode, self.show_walls, 1-(target-offset))
            frame = self.gpu.read_image()
            if self.markers:
                draw = ImageDraw.Draw(frame)
                for source in self.sources:
                    x, y = source.x*frame.width, source.y*frame.height
                    color = (77, 255, 232) if source.id == self.selected else (255, 255, 255)
                    if not source.enabled:
                        color = (140, 140, 140)
                    draw.ellipse((x-8, y-8, x+8, y+8), fill=(4, 6, 10), outline=color, width=2)
                    draw.line((x-4, y, x+4, y), fill=color)
                    draw.line((x, y-4, x, y+4), fill=color)
                    draw.text((x+12 if source.x < .7 else x-40, y-7), f"TX {source.id}", fill=color)
            self.frames.append(frame.quantize(palette=self.palette, dither=Image.Dither.NONE))
            if len(self.frames) == len(self.offsets):
                self.gpu.close()
                self.gpu = None
                self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gif-save")
                self.future = self.executor.submit(save_gif, self.path, self.frames, self.interval, self.selected)
        except Exception as error:
            self.error = str(error)
            self.done = True

    def cancel(self):
        # Once encoding starts, finish the short atomic write.
        if self.future is None:
            self.cancelled = True
            self.done = True

    def close(self):
        if self.gpu is not None:
            self.gpu.close()
            self.gpu = None
        if self.executor is not None:
            self.executor.shutdown(wait=True)
            self.executor = None
        self.frames.clear()
