"""Extract stationary architecture and an empirical LUT from the reference clip.

Optional build tool: pip install opencv-python. The application uses baked assets.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def extract(video: Path, destination: Path):
    capture = cv2.VideoCapture(str(video))
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        # The original simulation rectangle, excluding the surrounding UI.
        frames.append(cv2.cvtColor(frame[28:565, 12:180], cv2.COLOR_BGR2RGB))
    capture.release()
    if not frames:
        raise ValueError(f"Cannot decode {video}")
    stack = np.asarray(frames, dtype=np.float32)
    low, high = stack.min(axis=-1), stack.max(axis=-1)
    neutral = ((high - low) < 38) & (low > 72)
    stationary = neutral.mean(axis=0) > 0.80
    wall = np.where(stationary, np.median(stack, axis=0).mean(axis=-1), 0)
    wall = np.clip(wall * 1.12, 0, 255).astype(np.uint8)

    # Order observed colors along the black/blue/purple/red/yellow/white path.
    # A guide curve is used only for ordering; the LUT entries are video samples.
    t = np.linspace(0, 1, 256)
    guide = np.stack((np.clip(t / .32 - .78125, 0, 1),
                      np.clip(2 * t - .84, 0, 1),
                      np.clip(np.where(t < .25, 4*t,
                               np.where(t < .42, 1, np.where(t < .92, -2*t+1.84, t/.08-11.5))), 0, 1)), axis=1) * 255
    pixels = stack[::3, :, :, :][:, ~stationary, :].reshape(-1, 3)
    pixels = pixels[::3]
    bins = [[] for _ in range(256)]
    for chunk in np.array_split(pixels, max(1, len(pixels) // 2000)):
        distance = ((chunk[:, None, :] - guide[None, :, :]) ** 2).sum(axis=2)
        nearest = distance.argmin(axis=1)
        for i in np.unique(nearest):
            bins[i].extend(chunk[nearest == i].tolist())
    known = [i for i, values in enumerate(bins) if values]
    colors = np.array([np.median(bins[i], axis=0) for i in known])
    palette = np.stack([np.interp(np.arange(256), known, colors[:, ch]) for ch in range(3)], axis=1)
    palette = np.round(palette).clip(0, 255).astype(np.uint8)
    destination.mkdir(parents=True, exist_ok=True)
    Image.fromarray(wall).save(destination / "walls.png")
    Image.fromarray(palette[None, :, :]).save(destination / "palette.png")
    (destination / "reference.json").write_text(json.dumps({
        "source": video.name, "frames": len(frames), "crop_xyxy": [12, 28, 180, 565],
        "palette": "256 empirical RGB samples, ordered by spectral color path; missing bins interpolated",
        "walls": "Achromatic pixels present in more than 80% of video frames",
        "note": "The compressed video does not expose the original numeric colormap or simulation parameters."
    }, indent=2), encoding="utf-8")
    print(f"Extracted {len(frames)} frames to {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, default=Path("wifivis/assets"))
    args = parser.parse_args()
    extract(args.video, args.output)
