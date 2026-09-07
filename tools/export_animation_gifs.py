"""Export every runtime Mochi animation as a transparent preview GIF."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from mochi.sprites import ANIMATIONS, ASSET_SET


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "animation-gifs"


def _gif_palette(frame: Image.Image, scale: int) -> Image.Image:
    """Reserve palette index zero for hard transparency without edge halos."""
    rgba = frame.convert("RGBA").resize(
        (frame.width * scale, frame.height * scale), Image.Resampling.NEAREST
    )
    alpha = rgba.getchannel("A")
    quantized = rgba.quantize(colors=255, method=Image.Quantize.FASTOCTREE)

    result = Image.new("P", rgba.size, 0)
    palette = quantized.getpalette()[: 255 * 3]
    result.putpalette(([0, 0, 0] + palette + [0] * 768)[:768])
    result.putdata(
        [
            index + 1 if opacity else 0
            for index, opacity in zip(
                quantized.get_flattened_data(),
                alpha.get_flattened_data(),
                strict=True,
            )
        ]
    )
    result.info["transparency"] = 0
    return result


def export_animation(name: str, output: Path, scale: int) -> Path:
    animation = ANIMATIONS[name]
    frames = [
        _gif_palette(Image.open(ASSET_SET.root / frame.sprite), scale)
        for frame in animation.frames
    ]
    durations = [
        frame.duration_ms or animation.frame_duration_ms
        for frame in animation.frames
    ]
    destination = output / f"{name}.gif"
    save_options: dict[str, object] = {
        "save_all": True,
        "append_images": frames[1:],
        "duration": durations,
        "disposal": 2,
        "transparency": 0,
        "optimize": False,
    }
    if animation.looping:
        save_options["loop"] = 0
    frames[0].save(destination, **save_options)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scale", type=int, default=4)
    args = parser.parse_args()
    if args.scale < 1:
        parser.error("--scale must be at least 1")

    args.output.mkdir(parents=True, exist_ok=True)
    for name in ANIMATIONS:
        print(export_animation(name, args.output, args.scale))


if __name__ == "__main__":
    main()
