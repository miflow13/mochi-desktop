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
    source_cell_size: tuple[int, int]
    spritesheet_path: str | None = None


class AnimationAssetSet:
    """Reads one animation manifest and lazily caches requested frame surfaces."""

    FORMAT = "mochi-animation-set-v1"
    CELL_SIZE = (256, 256)

    def __init__(self, manifest_path: Path | None = None) -> None:
        self.manifest_path = manifest_path or self._find_manifest()
        self.root = self.manifest_path.parent.resolve()
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") != self.FORMAT:
            raise ValueError("Unsupported Mochi animation manifest format")

        cell_size = manifest.get("cell_size")
        if cell_size != list(self.CELL_SIZE):
            raise ValueError(
                f"Expected {self.CELL_SIZE[0]}x{self.CELL_SIZE[1]} "
                f"animation cells, got {cell_size}"
            )
        self.cell_size = self.CELL_SIZE
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
        if metadata.spritesheet_path is not None:
            self._load_spritesheet(metadata)
        else:
            for relative_path in metadata.frame_paths:
                if relative_path in self.surfaces:
                    continue
                path = self._safe_frame_path(relative_path)
                source = cairo.ImageSurface.create_from_png(str(path))
                actual_size = (source.get_width(), source.get_height())
                if actual_size != metadata.source_cell_size:
                    raise ValueError(
                        f"Expected {metadata.source_cell_size} frame {relative_path}, "
                        f"got {actual_size}"
                    )
                self.surfaces[relative_path] = self._scale_to_runtime_cell(source)
        return {path: self.surfaces[path] for path in metadata.frame_paths}

    def _load_spritesheet(self, metadata: AnimationMetadata) -> None:
        if all(path in self.surfaces for path in metadata.frame_paths):
            return

        sheet_path = self._safe_frame_path(metadata.spritesheet_path or "")
        sheet = cairo.ImageSurface.create_from_png(str(sheet_path))
        cell_width, cell_height = metadata.source_cell_size
        expected_size = (cell_width * len(metadata.frame_paths), cell_height)
        actual_size = (sheet.get_width(), sheet.get_height())
        if actual_size != expected_size:
            raise ValueError(
                f"Expected spritesheet {metadata.spritesheet_path} size "
                f"{expected_size}, got {actual_size}"
            )

        for index, frame_key in enumerate(metadata.frame_paths):
            source = cairo.ImageSurface(
                cairo.FORMAT_ARGB32,
                cell_width,
                cell_height,
            )
            context = cairo.Context(source)
            context.set_operator(cairo.OPERATOR_SOURCE)
            context.set_source_surface(sheet, -(index * cell_width), 0)
            context.paint()
            source.flush()
            self.surfaces[frame_key] = self._scale_to_runtime_cell(source)

    def _scale_to_runtime_cell(
        self,
        source: cairo.ImageSurface,
    ) -> cairo.ImageSurface:
        actual_size = (source.get_width(), source.get_height())
        if actual_size == self.cell_size:
            return source

        surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32,
            self.cell_size[0],
            self.cell_size[1],
        )
        context = cairo.Context(surface)
        context.scale(
            self.cell_size[0] / actual_size[0],
            self.cell_size[1] / actual_size[1],
        )
        context.set_source_surface(source, 0, 0)
        context.get_source().set_filter(cairo.FILTER_NEAREST)
        context.paint()
        surface.flush()
        return surface

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
            frame_count = raw_metadata.get("frame_count")
            fps = raw_metadata.get("fps")
            looping = raw_metadata.get("loop")
            if spritesheet is not None:
                if frames is not None:
                    raise ValueError(
                        f"Animation {name} cannot define both frames and spritesheet"
                    )
                if not isinstance(spritesheet, str) or not spritesheet:
                    raise ValueError(f"Animation {name} has an invalid spritesheet")
                if not isinstance(frame_count, int) or frame_count <= 0:
                    raise ValueError(f"Animation {name} has an invalid frame count")
                frame_paths = tuple(
                    f"{spritesheet}#{index + 1:04d}"
                    for index in range(frame_count)
                )
            else:
                if not isinstance(frames, list) or not frames:
                    raise ValueError(f"Animation {name} needs frames")
                if not all(isinstance(path, str) for path in frames):
                    raise ValueError(f"Animation {name} has an invalid frame path")
                if frame_count != len(frames):
                    raise ValueError(f"Animation {name} frame count does not match")
                frame_paths = tuple(frames)
            if not isinstance(fps, (int, float)) or fps <= 0:
                raise ValueError(f"Animation {name} has an invalid FPS")
            if not isinstance(looping, bool):
                raise ValueError(f"Animation {name} has an invalid loop value")
            raw_source_cell_size = raw_metadata.get(
                "source_cell_size", list(self.cell_size)
            )
            if (
                not isinstance(raw_source_cell_size, list)
                or len(raw_source_cell_size) != 2
                or not all(
                    isinstance(value, int) and value > 0
                    for value in raw_source_cell_size
                )
            ):
                raise ValueError(
                    f"Animation {name} has an invalid source cell size"
                )
            animations[name] = AnimationMetadata(
                name=name,
                frame_paths=frame_paths,
                fps=float(fps),
                looping=looping,
                source_cell_size=tuple(raw_source_cell_size),
                spritesheet_path=spritesheet,
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
