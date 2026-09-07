"""Prepare the supplied high-quality strips as fixed-canvas runtime frames."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageOps


FRAME_COUNTS = {
    "idle": ("source_strips/idle_strip.png", 6),
    "blink": ("source_strips/blink_strip.png", 4),
    "walk": ("source_strips/walk_strip.png", 8),
    "bounce": ("source_strips/bounce_strip.png", 6),
    "squish": ("source_strips/squish_strip.png", 5),
    "sleep_transition": ("source_strips/sleep_transition_strip.png", 6),
    "sleeping": ("source_strips/sleep_loop_strip.png", 3),
    "wake": ("source_strips/wake_strip.png", 6),
}
CANVAS_SIZE = 128
CONTENT_SIZE = 112


def remove_alpha_specks(image: Image.Image, minimum_area: int = 12) -> Image.Image:
    alpha = image.getchannel("A")
    pixels = alpha.load()
    visited: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for y in range(image.height):
        for x in range(image.width):
            if not pixels[x, y] or (x, y) in visited:
                continue
            component: list[tuple[int, int]] = []
            queue = deque([(x, y)])
            visited.add((x, y))
            while queue:
                point = queue.popleft()
                component.append(point)
                px, py = point
                for neighbor in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    nx, ny = neighbor
                    if (
                        0 <= nx < image.width
                        and 0 <= ny < image.height
                        and pixels[nx, ny]
                        and neighbor not in visited
                    ):
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    largest_area = max((len(component) for component in components), default=0)
    threshold = max(minimum_area, round(largest_area * 0.02))
    keep = {
        point
        for component in components
        if len(component) >= threshold
        for point in component
    }
    cleaned = Image.new("L", image.size)
    cleaned_pixels = cleaned.load()
    for x, y in keep:
        cleaned_pixels[x, y] = pixels[x, y]
    result = image.copy()
    result.putalpha(cleaned)
    return result


def recover_transparency(image: Image.Image) -> Image.Image:
    """Remove only dark background pixels connected to the image border."""
    image = image.convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            pixels[x, y] = (
                (red, green, blue, 255) if alpha >= 128 else (0, 0, 0, 0)
            )
    background: set[tuple[int, int]] = set()
    queue = deque()
    for x in range(image.width):
        queue.extend(((x, 0), (x, image.height - 1)))
    for y in range(image.height):
        queue.extend(((0, y), (image.width - 1, y)))
    while queue:
        x, y = queue.popleft()
        if (x, y) in background:
            continue
        red, green, blue, _alpha = pixels[x, y]
        if max(red, green, blue) > 20:
            continue
        background.add((x, y))
        for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= point[0] < image.width and 0 <= point[1] < image.height:
                queue.append(point)
    for x, y in background:
        pixels[x, y] = (0, 0, 0, 0)
    return image


def alpha_crop(image: Image.Image) -> Image.Image:
    image = remove_alpha_specks(image)
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Frame contains no visible pixels")
    return image.crop(bounds)


def normalize_frames(frames: list[Image.Image]) -> list[Image.Image]:
    max_width = max(frame.width for frame in frames)
    max_height = max(frame.height for frame in frames)
    scale = min(CONTENT_SIZE / max_width, CONTENT_SIZE / max_height)
    prepared = []
    for frame in frames:
        size = (max(1, round(frame.width * scale)), max(1, round(frame.height * scale)))
        sprite = frame.resize(size, Image.Resampling.NEAREST)
        resized_bounds = sprite.getchannel("A").getbbox()
        if resized_bounds is None:
            raise ValueError("Resized frame contains no visible pixels")
        sprite = sprite.crop(resized_bounds)
        size = sprite.size
        canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
        canvas.alpha_composite(sprite, ((CANVAS_SIZE - size[0]) // 2, CANVAS_SIZE - size[1]))
        prepared.append(canvas)
    return prepared


def split_strip(path: Path, count: int) -> list[Image.Image]:
    strip = recover_transparency(Image.open(path))
    frames = []
    for index in range(count):
        left = round(index * strip.width / count)
        right = round((index + 1) * strip.width / count)
        frames.append(alpha_crop(strip.crop((left, 0, right, strip.height))))
    return frames


def save_animation(source: Path, destination: Path, name: str, relative: str, count: int) -> None:
    output = destination / name
    output.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(
        normalize_frames(split_strip(source / relative, count)), start=1
    ):
        frame.save(output / f"{name}_{index:02d}.png", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    for name, (relative, count) in FRAME_COUNTS.items():
        save_animation(args.source, args.destination, name, relative, count)

    master = alpha_crop(recover_transparency(Image.open(args.source / "mochi_default.png")))
    default = normalize_frames([master])[0]
    master_directory = args.destination / "master"
    master_directory.mkdir(parents=True, exist_ok=True)
    default.save(master_directory / "mochi_default.png", optimize=True)

    walk_left = args.destination / "walk_left"
    walk_left.mkdir(parents=True, exist_ok=True)
    for index, frame_path in enumerate(sorted((args.destination / "walk").glob("*.png")), start=1):
        mirrored = ImageOps.mirror(Image.open(frame_path).convert("RGBA"))
        mirrored.save(walk_left / f"walk_left_{index:02d}.png", optimize=True)


if __name__ == "__main__":
    main()
