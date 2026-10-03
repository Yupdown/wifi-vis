"""Screen-composite a nearest-sampled, jiggling foreground onto an animated GIF."""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence


def jiggle_foreground(foreground, size, rng, amplitude):
    """Smooth random displacement field, nearest-neighbor BITMAP sampling."""
    width, height = size
    source = np.asarray(foreground.convert("RGBA"))
    source_h, source_w = source.shape[:2]
    grid_size = (max(3, math.ceil(width/64)+1), max(3, math.ceil(height/64)+1))
    displacements = []
    for _ in range(2):
        noise = rng.uniform(-1, 1, (grid_size[1], grid_size[0])).astype(np.float32)
        # Interpolate the motion field only. Color/alpha bitmap samples below
        # are rounded to one source pixel, never blurred or interpolated.
        field = np.asarray(Image.fromarray(noise).resize(size, Image.Resampling.BICUBIC))
        displacements.append(np.clip(field, -1, 1) * amplitude)
    yy, xx = np.mgrid[:height, :width]
    sx = np.rint((xx+displacements[0]+.5)*source_w/width-.5).astype(int)
    sy = np.rint((yy+displacements[1]+.5)*source_h/height-.5).astype(int)
    inside = (sx >= 0) & (sx < source_w) & (sy >= 0) & (sy < source_h)
    result = np.zeros((height, width, 4), dtype=np.uint8)
    result[inside] = source[sy[inside], sx[inside]]
    return result


def screen(background, foreground):
    back = background.astype(np.uint32)
    front = foreground[:, :, :3].astype(np.uint32)
    alpha = foreground[:, :, 3:4].astype(np.uint32)
    blended = 255 - ((255-back)*(255-front)+127)//255
    return ((blended*alpha + back*(255-alpha)+127)//255).astype(np.uint8)


def composite(background_path, foreground_path, output_path, amplitude=2.0, hold=5, seed=20261001):
    background_path, foreground_path, output_path = map(Path, (background_path, foreground_path, output_path))
    if output_path.resolve() in (background_path.resolve(), foreground_path.resolve()):
        raise ValueError("Output must differ from both source files")
    if output_path.exists():
        raise FileExistsError(f"Output already exists: {output_path}")
    if hold < 1 or not math.isfinite(amplitude) or amplitude < 0:
        raise ValueError("Hold must be positive and amplitude must be nonnegative")
    with Image.open(background_path) as gif:
        size = gif.size
        loop = gif.info.get("loop")
        backgrounds, durations = [], []
        for frame in ImageSequence.Iterator(gif):
            duration = frame.info.get("duration", 0)
            if duration <= 0:
                raise ValueError("Source GIF must specify a positive frame duration")
            durations.append(duration)
            backgrounds.append(np.asarray(frame.convert("RGB")))
    with Image.open(foreground_path) as image:
        foreground = image.convert("RGBA")
    # Match both background phase and the foreground hold at the loop seam.
    count = math.lcm(len(backgrounds), hold)
    rng = np.random.default_rng(seed)
    composites = []
    for index in range(count):
        if index % hold == 0:
            moving_wall = jiggle_foreground(foreground, size, rng, amplitude)
        rgb = screen(backgrounds[index % len(backgrounds)], moving_wall)
        composites.append(Image.fromarray(rgb))

    # A common palette learned from every output frame prevents palette flicker.
    # Source pixels still use nearest-neighbor sampling before GIF quantization.
    tile = 96
    columns = min(10, count)
    contact = Image.new("RGB", (columns*tile, math.ceil(count/columns)*tile))
    for index, frame in enumerate(composites):
        contact.paste(frame.resize((tile, tile), Image.Resampling.NEAREST),
                      ((index % columns)*tile, (index // columns)*tile))
    palette = contact.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in composites]
    output_durations = [durations[i % len(durations)] for i in range(count)]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    options = dict(format="GIF", save_all=True, append_images=encoded[1:],
                   duration=output_durations, disposal=2, optimize=False,
                   comment=f"Screen; foreground jiggle every {hold} frames; nearest neighbor; amplitude {amplitude:g}px; seed {seed}".encode())
    if loop is not None:
        options["loop"] = loop
    encoded[0].save(output_path, **options)
    with Image.open(output_path) as result:
        actual_durations = [f.info["duration"] for f in ImageSequence.Iterator(result)]
        if result.n_frames != count or actual_durations != output_durations or result.size != size:
            raise RuntimeError("Encoded GIF does not preserve the requested frames, timing, or dimensions")
    report = {
        "background": str(background_path.resolve()), "foreground": str(foreground_path.resolve()),
        "output": str(output_path.resolve()), "size": list(size), "source_frames": len(backgrounds),
        "output_frames": count, "duration_ms": sum(output_durations),
        "frame_durations_ms": sorted(set(output_durations)), "blend": "screen",
        "jiggle_amplitude_output_pixels": amplitude, "jiggle_update_frames": hold,
        "jiggle_groups": count//hold, "bitmap_sampling": "nearest neighbor", "seed": seed,
    }
    output_path.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("background", type=Path)
    parser.add_argument("foreground", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--amplitude", type=float, default=2.0, help="Maximum displacement per axis in output pixels")
    parser.add_argument("--hold", type=int, default=5, help="Update jiggle once every N frames")
    parser.add_argument("--seed", type=int, default=20261001)
    args = parser.parse_args()
    composite(args.background, args.foreground, args.output, args.amplitude, args.hold, args.seed)
