"""Build Mochi's dedicated high-energy drag sprite set from clean idle art."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "mochi" / "idle" / "idle_01.png"
TARGETS = (
    ROOT / "assets" / "mochi" / "drag",
    ROOT / "assets" / "mochi_original_set" / "frames" / "drag",
)
CANVAS_SIZE = 128
BODY_CROP = (11, 26, 116, 128)


@dataclass(frozen=True)
class Pose:
    width: int
    height: int
    top_lag: int
    middle_lag: int
    leg_sway: int
    leg_spread: int


POSES = {
    "drag_neutral": Pose(94, 100, 0, 0, 0, 0),
    "drag_left_soft": Pose(98, 97, -4, -2, -7, 1),
    "drag_left_medium": Pose(106, 91, -8, -4, -12, 3),
    "drag_left_hard": Pose(114, 84, -14, -7, -19, 6),
    "drag_right_soft": Pose(98, 97, 4, 2, 7, 1),
    "drag_right_medium": Pose(106, 91, 8, 4, 12, 3),
    "drag_right_hard": Pose(114, 84, 14, 7, 19, 6),
    "drag_settle_left": Pose(101, 94, 4, 2, 6, 2),
    "drag_settle_right": Pose(101, 94, -4, -2, -6, 2),
    "drag_settle_neutral": Pose(94, 100, 0, 0, 0, 0),
}


def _body(source: Image.Image, pose: Pose) -> Image.Image:
    return source.crop(BODY_CROP).resize(
        (pose.width, pose.height), Image.Resampling.NEAREST
    )


def _draw_feet(frame: Image.Image, pose: Pose, x: int) -> None:
    draw = ImageDraw.Draw(frame)
    outline = (1, 50, 5, 255)
    green = (55, 202, 92, 255)
    highlight = (112, 232, 124, 255)
    foot_y = 118
    centers = (
        x + pose.width // 2 - 17 + pose.leg_sway - pose.leg_spread,
        x + pose.width // 2 + 17 + pose.leg_sway + pose.leg_spread,
    )
    for index, center in enumerate(centers):
        lean = -2 if index == 0 else 2
        left = center + lean
        draw.rectangle((left - 2, foot_y - 2, left + 7, 127), fill=outline)
        draw.rectangle((left, foot_y, left + 5, 125), fill=green)
        draw.rectangle((left + 1, foot_y, left + 3, foot_y + 2), fill=highlight)


def build_pose(source: Image.Image, pose: Pose) -> Image.Image:
    sprite = _body(source, pose)
    frame = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE))
    x = (CANVAS_SIZE - pose.width) // 2
    y = CANVAS_SIZE - pose.height - 10
    bands = (
        (0, 0, pose.width, round(pose.height * 0.37), pose.top_lag),
        (
            0,
            round(pose.height * 0.32),
            pose.width,
            round(pose.height * 0.70),
            pose.middle_lag,
        ),
        (0, round(pose.height * 0.65), pose.width, pose.height, 0),
    )
    for left, top, right, bottom, offset in bands:
        frame.alpha_composite(
            sprite.crop((left, top, right, bottom)),
            (x + offset, y + top),
        )
    _draw_feet(frame, pose, x)
    return frame


def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")
    frames = {name: build_pose(source, pose) for name, pose in POSES.items()}
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for name, frame in frames.items():
            frame.save(target / f"{name}.png", optimize=True)


if __name__ == "__main__":
    main()