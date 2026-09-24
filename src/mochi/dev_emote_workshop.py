"""Developer-only helpers for previewing and promoting Mochi emote artwork."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import sys

import cairo

from mochi.animation import Animation, AnimationFrame


RARITIES = ("common", "uncommon", "rare", "epic", "legendary")
_ID_RE = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True, slots=True)
class EmoteInspection:
    frame_count: int
    source_cell_size: tuple[int, int]
    source_kind: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EmoteImportSpec:
    source: Path
    animation_id: str
    label: str
    fps: float = 8.333333333333334
    loop: bool = False
    source_cell_size: tuple[int, int] = (64, 64)
    bond_level: int = 1
    rarity: str = "common"
    reveal_on_unlock: bool = False

    def validate(self) -> None:
        if not self.source.exists():
            raise ValueError(f"Source does not exist: {self.source}")
        if not _ID_RE.fullmatch(self.animation_id):
            raise ValueError("Animation ID must use lowercase letters, numbers, and underscores")
        if not self.label.strip():
            raise ValueError("Emote label cannot be empty")
        if self.fps <= 0:
            raise ValueError("FPS must be greater than zero")
        if self.bond_level < 1:
            raise ValueError("Bond level must be at least 1")
        if self.rarity not in RARITIES:
            raise ValueError(f"Unsupported rarity: {self.rarity}")
        width, height = self.source_cell_size
        if width <= 0 or height <= 0:
            raise ValueError("Source cell size must be positive")


@dataclass(frozen=True, slots=True)
class PromotionResult:
    asset_directory: Path
    manifest_path: Path
    pyproject_path: Path
    catalogue_snippet: str
    frame_count: int


def slugify_animation_id(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return value.strip("_") or "new_emote"


def development_checkout_root() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    if (
        (root / "assets" / "mochi" / "manifest.json").is_file()
        and (root / "src" / "mochi" / "emotes.py").is_file()
        and (root / ".git").exists()
    ):
        return root
    return None


def inspect_source(source: Path, source_cell_size: tuple[int, int]) -> EmoteInspection:
    source = source.expanduser().resolve()
    cell_width, cell_height = source_cell_size
    if cell_width <= 0 or cell_height <= 0:
        raise ValueError("Source cell size must be positive")

    warnings: list[str] = []
    if source.is_file():
        if source.suffix.lower() != ".png":
            raise ValueError("Spritesheet must be a PNG file")
        sheet = cairo.ImageSurface.create_from_png(str(source))
        width, height = sheet.get_width(), sheet.get_height()
        if height != cell_height or width % cell_width:
            raise ValueError(
                f"Expected a horizontal sheet using {cell_width}x{cell_height} cells; "
                f"got {width}x{height}"
            )
        frame_count = width // cell_width
        if not _surface_has_transparency(sheet):
            warnings.append("No transparent pixels detected in the spritesheet")
        return EmoteInspection(
            frame_count=frame_count,
            source_cell_size=source_cell_size,
            source_kind="spritesheet",
            warnings=tuple(warnings),
        )

    if source.is_dir():
        frames = _frame_files(source)
        if not frames:
            raise ValueError("Frame folder does not contain PNG files")
        opaque_frames = 0
        for frame_path in frames:
            frame = cairo.ImageSurface.create_from_png(str(frame_path))
            actual = (frame.get_width(), frame.get_height())
            if actual != source_cell_size:
                raise ValueError(
                    f"Expected {source_cell_size[0]}x{source_cell_size[1]} frame "
                    f"{frame_path.name}, got {actual[0]}x{actual[1]}"
                )
            if not _surface_has_transparency(frame):
                opaque_frames += 1
        if opaque_frames:
            warnings.append(
                f"{opaque_frames} frame(s) have no transparent pixels detected"
            )
        return EmoteInspection(
            frame_count=len(frames),
            source_cell_size=source_cell_size,
            source_kind="frames",
            warnings=tuple(warnings),
        )

    raise ValueError("Choose a PNG spritesheet or a folder of PNG frames")


def build_preview_animation(
    spec: EmoteImportSpec,
) -> tuple[Animation, dict[str, cairo.ImageSurface], EmoteInspection]:
    spec.validate()
    inspection = inspect_source(spec.source, spec.source_cell_size)
    frame_duration_ms = max(1, round(1_000 / spec.fps))
    surfaces: dict[str, cairo.ImageSurface] = {}
    frames: list[AnimationFrame] = []

    if inspection.source_kind == "spritesheet":
        sheet = cairo.ImageSurface.create_from_png(str(spec.source))
        cell_width, cell_height = spec.source_cell_size
        for index in range(inspection.frame_count):
            source = cairo.ImageSurface(cairo.FORMAT_ARGB32, cell_width, cell_height)
            context = cairo.Context(source)
            context.set_operator(cairo.OPERATOR_SOURCE)
            context.set_source_surface(sheet, -(index * cell_width), 0)
            context.paint()
            source.flush()
            key = f"__dev_emote__/{spec.animation_id}/{index + 1:04d}"
            surfaces[key] = _scale_to_runtime_cell(source)
            frames.append(AnimationFrame(key))
    else:
        for index, frame_path in enumerate(_frame_files(spec.source)):
            source = cairo.ImageSurface.create_from_png(str(frame_path))
            key = f"__dev_emote__/{spec.animation_id}/{index + 1:04d}"
            surfaces[key] = _scale_to_runtime_cell(source)
            frames.append(AnimationFrame(key))

    animation = Animation(
        name=f"__dev_emote__{spec.animation_id}",
        frames=tuple(frames),
        frame_duration_ms=frame_duration_ms,
        looping=False,
        next_state="idle",
    )
    return animation, surfaces, inspection


def promote_emote(
    spec: EmoteImportSpec,
    *,
    checkout_root: Path | None = None,
) -> PromotionResult:
    spec.validate()
    inspection = inspect_source(spec.source, spec.source_cell_size)
    root = checkout_root or development_checkout_root()
    if root is None:
        raise RuntimeError("Promotion is only available from a Mochi source checkout")

    manifest_path = root / "assets" / "mochi" / "manifest.json"
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        raise RuntimeError("Mochi pyproject.toml was not found in the source checkout")

    original_manifest = manifest_path.read_text(encoding="utf-8")
    original_pyproject = pyproject_path.read_text(encoding="utf-8")
    manifest = json.loads(original_manifest)
    animations = manifest.get("animations")
    if not isinstance(animations, dict):
        raise ValueError("Mochi manifest is missing its animations object")
    if spec.animation_id in animations:
        raise ValueError(f"Animation already exists: {spec.animation_id}")

    asset_directory = root / "assets" / "mochi" / spec.animation_id
    if asset_directory.exists():
        raise ValueError(f"Asset directory already exists: {asset_directory}")
    packaging_entry = (
        f'"share/mochi/{spec.animation_id}" = '
        f'["assets/mochi/{spec.animation_id}/*.png"]'
    )
    updated_pyproject = original_pyproject
    if packaging_entry not in updated_pyproject:
        marker = "\n[tool.pytest.ini_options]"
        if marker not in updated_pyproject:
            shutil.rmtree(asset_directory, ignore_errors=True)
            raise RuntimeError("Could not locate the setuptools data-files section boundary")
        updated_pyproject = updated_pyproject.replace(
            marker,
            f"\n{packaging_entry}\n{marker}",
            1,
        )

    try:
        if inspection.source_kind == "spritesheet":
            destination = asset_directory / f"{spec.animation_id}.png"
            shutil.copy2(spec.source, destination)
            entry: dict[str, object] = {
                "spritesheet": f"{spec.animation_id}/{destination.name}",
                "frame_count": inspection.frame_count,
                "fps": spec.fps,
                "loop": spec.loop,
                "source_cell_size": list(spec.source_cell_size),
            }
        else:
            destination_frames: list[str] = []
            for source_frame in _frame_files(spec.source):
                destination = asset_directory / source_frame.name
                shutil.copy2(source_frame, destination)
                destination_frames.append(
                    f"{spec.animation_id}/{destination.name}"
                )
            entry = {
                "frames": destination_frames,
                "frame_count": inspection.frame_count,
                "fps": spec.fps,
                "loop": spec.loop,
                "source_cell_size": list(spec.source_cell_size),
            }

        animations[spec.animation_id] = entry
        temporary = manifest_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(manifest_path)

        pyproject_temporary = pyproject_path.with_suffix(".toml.tmp")
        pyproject_temporary.write_text(updated_pyproject, encoding="utf-8")
        pyproject_temporary.replace(pyproject_path)
    except Exception:
        shutil.rmtree(asset_directory, ignore_errors=True)
        manifest_path.write_text(original_manifest, encoding="utf-8")
        pyproject_path.write_text(original_pyproject, encoding="utf-8")
        raise

    return PromotionResult(
        asset_directory=asset_directory,
        manifest_path=manifest_path,
        pyproject_path=pyproject_path,
        catalogue_snippet=build_catalogue_snippet(spec),
        frame_count=inspection.frame_count,
    )


def build_catalogue_snippet(spec: EmoteImportSpec) -> str:
    emote_id = spec.animation_id.replace("_", "-")
    reveal = ",\n    reveal_on_unlock=True" if spec.reveal_on_unlock else ""
    return (
        "EmoteDefinition(\n"
        f'    "{emote_id}",\n'
        f'    "{spec.label.strip()}",\n'
        f'    "{spec.animation_id}",\n'
        f"    {spec.bond_level},\n"
        f'    rarity="{spec.rarity}"'
        f"{reveal},\n"
        "),"
    )


def _frame_files(directory: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                path
                for path in directory.iterdir()
                if path.is_file() and path.suffix.lower() == ".png"
            ),
            key=lambda path: path.name.casefold(),
        )
    )


def _scale_to_runtime_cell(source: cairo.ImageSurface) -> cairo.ImageSurface:
    runtime_width = runtime_height = 256
    if source.get_width() == runtime_width and source.get_height() == runtime_height:
        return source

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, runtime_width, runtime_height)
    context = cairo.Context(surface)
    context.scale(
        runtime_width / source.get_width(),
        runtime_height / source.get_height(),
    )
    context.set_source_surface(source, 0, 0)
    context.get_source().set_filter(cairo.FILTER_NEAREST)
    context.paint()
    surface.flush()
    return surface


def _surface_has_transparency(surface: cairo.ImageSurface) -> bool:
    if surface.get_format() != cairo.FORMAT_ARGB32:
        return False
    surface.flush()
    data = memoryview(surface.get_data())
    alpha_offset = 3 if sys.byteorder == "little" else 0
    stride = surface.get_stride()
    for y in range(surface.get_height()):
        row = y * stride
        for x in range(surface.get_width()):
            if data[row + x * 4 + alpha_offset] < 255:
                return True
    return False
