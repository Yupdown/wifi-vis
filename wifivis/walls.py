"""Image decoding and the native file chooser for wall maps."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


@dataclass
class WallMap:
    path: Path
    pixels: np.ndarray
    inverted: bool


def load_wall_map(path, invert=None):
    """Convert image ink to wall strength; transparent pixels are always empty."""
    path = Path(path).resolve()
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    w, h = image.size
    scale = min(2.0, 1074 / max(w, h), (360864 / (w*h)) ** .5)
    image = image.resize((max(2, round(w*scale)), max(2, round(h*scale))), Image.Resampling.LANCZOS)
    rgba = np.asarray(image)
    gray = np.asarray(image.convert("L"))
    alpha = rgba[:, :, 3].astype(np.float32) / 255
    if invert is None:
        if np.any(alpha < .5):
            visible = gray[alpha > .5]
            invert = bool(visible.size and np.median(visible) < 128)
        else:
            border = np.concatenate((gray[0], gray[-1], gray[:, 0], gray[:, -1]))
            invert = bool(np.median(border) >= 128)
    strength = 255-gray if invert else gray
    pixels = np.ascontiguousarray(np.round(strength * alpha).astype(np.uint8))
    return WallMap(path, pixels, bool(invert))


def choose_wall_file(initial_directory=None):
    # Tk uses the native Windows Explorer open dialog; no extra pip package.
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        result = filedialog.askopenfilename(
            parent=root, title="Select a wall / floor plan image",
            initialdir=str(initial_directory or Path.home()),
            filetypes=[("Wall images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"),
                       ("All files", "*.*")])
        return Path(result) if result else None
    finally:
        root.destroy()
