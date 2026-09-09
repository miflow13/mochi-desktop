"""Manifest-driven loading and caching for Mochi's fixed-canvas PNG frames."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

import cairo

from mochi.animation import Animation, AnimationFrame


@dataclass(frozen=True)
class AnimationMetadata:
    name: str
    frame_paths: tuple[str, ...]
    fps: float
    looping: bool
    spritesheet: str | None = None
    frame_size: tuple[int, int] | None = None
    source_frame_count: int | None = None


class AnimationAssetSet:
    """Reads one animation manifest and lazily caches requested frame surfaces."""

    FORMAT = "mochi-animation-set-v1"

    def __init__(self, manifest_path: Path | None = None) -> None:
        self.manifest_path = manifest_path or self._find_manifest()
        self.root = self.manifest_path.parent.resolve()
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") != self.FORMAT:
            raise ValueError("Unsupported Mochi animation manifest format")

        cell_size = manifest.get("cell_size")
        if cell_size != [128, 128]:
            raise ValueError(f"Expected 128x128 animation cells, got {cell_size}")
        self.cell_size = (128, 128)
        self.animations = self._parse_animations(manifest.get("animations"))
        self.surfaces: dict[str, cairo.ImageSurface] = {}

    def animation(self, name: str) -> Animation:
        metadata = self.animations[name]
        return Animation(
            name=name,
            frames=tuple(AnimationFrame(path) for path in metadata.frame_paths),
            frame_duration_ms=round(1_000 / metadata.fps),
            looping=metadata.looping,
            next_state=None if metadata.looping else "idle",
        )

    def load_frames(self, name: str) -> dict[str, cairo.ImageSurface]:
        metadata = self.animations[name]
        if metadata.spritesheet is not None:
            self._load_spritesheet(metadata)
            return {path: self.surfaces[path] for path in metadata.frame_paths}
        for relative_path in metadata.frame_paths:
            if relative_path in self.surfaces:
                continue
            path = self._safe_frame_path(relative_path)
            surface = cairo.ImageSurface.create_from_png(str(path))
            actual_size = (surface.get_width(), surface.get_height())
            if actual_size != self.cell_size:
                raise ValueError(
                    f"Expected {self.cell_size} frame {relative_path}, got {actual_size}"
                )
            self.surfaces[relative_path] = surface
        return {
            path: self.surfaces[path]
            for path in metadata.frame_paths
        }

    def _load_spritesheet(self, metadata: AnimationMetadata) -> None:
        if all(path in self.surfaces for path in metadata.frame_paths):
            return
        assert metadata.spritesheet is not None
        assert metadata.frame_size is not None
        assert metadata.source_frame_count is not None
        path = self._safe_frame_path(metadata.spritesheet)
        sheet = cairo.ImageSurface.create_from_png(str(path))
        frame_width, frame_height = metadata.frame_size
        expected_size = (frame_width * metadata.source_frame_count, frame_height)
        actual_size = (sheet.get_width(), sheet.get_height())
        if actual_size != expected_size:
            raise ValueError(
                f"Expected spritesheet {metadata.spritesheet} to be "
                f"{expected_size}, got {actual_size}"
            )
        scale = min(
            self.cell_size[0] // frame_width,
            self.cell_size[1] // frame_height,
        )
        draw_width = frame_width * scale
        draw_height = frame_height * scale
        offset_x = (self.cell_size[0] - draw_width) // 2
        offset_y = self.cell_size[1] - draw_height
        for index in range(metadata.source_frame_count):
            frame_path = f"{metadata.spritesheet}#{index}"
            surface = cairo.ImageSurface(
                cairo.FORMAT_ARGB32, self.cell_size[0], self.cell_size[1]
            )
            context = cairo.Context(surface)
            context.translate(offset_x, offset_y)
            context.scale(scale, scale)
            context.rectangle(0, 0, frame_width, frame_height)
            context.clip()
            context.set_source_surface(sheet, -index * frame_width, 0)
            context.get_source().set_filter(cairo.FILTER_NEAREST)
            context.paint()
            self.surfaces[frame_path] = surface

    def _parse_animations(
        self, raw_animations: object
    ) -> dict[str, AnimationMetadata]:
        if not isinstance(raw_animations, dict):
            raise ValueError("Animation manifest needs an animations object")

        animations: dict[str, AnimationMetadata] = {}
        for name, raw_metadata in raw_animations.items():
            if not isinstance(name, str) or not isinstance(raw_metadata, dict):
                raise ValueError("Invalid animation metadata")
            frames = raw_metadata.get("frames")
            spritesheet = raw_metadata.get("spritesheet")
            fps = raw_metadata.get("fps")
            looping = raw_metadata.get("loop")
            frame_count = raw_metadata.get("frame_count")
            frame_size = None
            if spritesheet is not None:
                width = raw_metadata.get("frame_width")
                height = raw_metadata.get("frame_height")
                if not isinstance(spritesheet, str):
                    raise ValueError(f"Animation {name} has an invalid spritesheet")
                if not isinstance(frame_count, int) or frame_count <= 0:
                    raise ValueError(f"Animation {name} has an invalid frame count")
                if not isinstance(width, int) or not isinstance(height, int):
                    raise ValueError(f"Animation {name} has an invalid frame size")
                if width <= 0 or height <= 0 or width > 128 or height > 128:
                    raise ValueError(f"Animation {name} exceeds the logical canvas")
                frames = [f"{spritesheet}#{index}" for index in range(frame_count)]
                frame_size = (width, height)
            else:
                if not isinstance(frames, list) or not frames:
                    raise ValueError(f"Animation {name} needs frames")
                if not all(isinstance(path, str) for path in frames):
                    raise ValueError(f"Animation {name} has an invalid frame path")
                if frame_count != len(frames):
                    raise ValueError(f"Animation {name} frame count does not match")
            if not isinstance(fps, (int, float)) or fps <= 0:
                raise ValueError(f"Animation {name} has an invalid FPS")
            if not isinstance(looping, bool):
                raise ValueError(f"Animation {name} has an invalid loop value")
            animations[name] = AnimationMetadata(
                name=name,
                frame_paths=tuple(frames),
                fps=float(fps),
                looping=looping,
                spritesheet=spritesheet,
                frame_size=frame_size,
                source_frame_count=frame_count if spritesheet is not None else None,
            )
        return animations

    def _safe_frame_path(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Frame path escapes the asset directory: {relative_path}")
        if not path.is_file():
            raise FileNotFoundError(f"Animation frame was not found: {relative_path}")
        return path

    @staticmethod
    def _find_manifest() -> Path:
        candidates = (
            Path(__file__).resolve().parents[2] / "assets" / "mochi" / "manifest.json",
            Path(sys.prefix) / "share" / "mochi" / "manifest.json",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise FileNotFoundError("Mochi animation manifest was not found")
