from __future__ import annotations

import json
from pathlib import Path

import cairo
import pytest

from mochi.dev_emote_workshop import (
    EmoteImportSpec,
    build_catalogue_snippet,
    build_preview_animation,
    inspect_source,
    promote_emote,
    slugify_animation_id,
)


def _write_png(path: Path, width: int, height: int, *, transparent: bool = True) -> None:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    context = cairo.Context(surface)
    if transparent:
        context.set_source_rgba(0, 0, 0, 0)
    else:
        context.set_source_rgba(0.2, 0.8, 0.3, 1)
    context.set_operator(cairo.OPERATOR_SOURCE)
    context.paint()
    surface.write_to_png(str(path))


def _checkout_root(tmp_path: Path) -> Path:
    root = tmp_path / "mochi"
    (root / "assets" / "mochi").mkdir(parents=True)
    (root / "src" / "mochi").mkdir(parents=True)
    (root / "src" / "mochi" / "emotes.py").write_text("# test\n", encoding="utf-8")
    (root / "assets" / "mochi" / "manifest.json").write_text(
        json.dumps(
            {
                "format": "mochi-animation-set-v1",
                "cell_size": [256, 256],
                "anchor": "bottom-center",
                "scaling": "nearest-neighbor",
                "animations": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def test_slugify_animation_id_is_manifest_safe() -> None:
    assert slugify_animation_id("Party Popper!!") == "party_popper"
    assert slugify_animation_id("  ") == "new_emote"


def test_inspect_horizontal_spritesheet_detects_frames(tmp_path: Path) -> None:
    sheet = tmp_path / "party.png"
    _write_png(sheet, 64 * 6, 64)

    inspection = inspect_source(sheet, (64, 64))

    assert inspection.source_kind == "spritesheet"
    assert inspection.frame_count == 6
    assert inspection.source_cell_size == (64, 64)


def test_inspect_rejects_non_horizontal_sheet_geometry(tmp_path: Path) -> None:
    sheet = tmp_path / "bad.png"
    _write_png(sheet, 130, 64)

    with pytest.raises(ValueError, match="horizontal sheet"):
        inspect_source(sheet, (64, 64))


def test_frame_folder_requires_consistent_dimensions(tmp_path: Path) -> None:
    folder = tmp_path / "frames"
    folder.mkdir()
    _write_png(folder / "01.png", 64, 64)
    _write_png(folder / "02.png", 32, 64)

    with pytest.raises(ValueError, match="Expected 64x64 frame"):
        inspect_source(folder, (64, 64))


def test_preview_builds_runtime_surfaces_without_touching_source(tmp_path: Path) -> None:
    sheet = tmp_path / "wave.png"
    _write_png(sheet, 64 * 3, 64)
    original = sheet.read_bytes()
    spec = EmoteImportSpec(
        source=sheet,
        animation_id="wave_test",
        label="Wave Test",
        fps=10,
        source_cell_size=(64, 64),
    )

    animation, surfaces, inspection = build_preview_animation(spec)

    assert inspection.frame_count == 3
    assert len(animation.frames) == 3
    assert animation.looping is False
    assert animation.next_state == "idle"
    assert len(surfaces) == 3
    assert all(
        (surface.get_width(), surface.get_height()) == (256, 256)
        for surface in surfaces.values()
    )
    assert sheet.read_bytes() == original


def test_promote_spritesheet_copies_art_and_updates_manifest(tmp_path: Path) -> None:
    root = _checkout_root(tmp_path)
    sheet = tmp_path / "party.png"
    _write_png(sheet, 64 * 4, 64)
    original = sheet.read_bytes()
    spec = EmoteImportSpec(
        source=sheet,
        animation_id="party_popper",
        label="Party Popper",
        fps=8.0,
        loop=False,
        source_cell_size=(64, 64),
        bond_level=3,
        rarity="rare",
        reveal_on_unlock=True,
    )

    result = promote_emote(spec, checkout_root=root)

    copied = result.asset_directory / "party_popper.png"
    assert copied.read_bytes() == original
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    entry = manifest["animations"]["party_popper"]
    assert entry == {
        "spritesheet": "party_popper/party_popper.png",
        "frame_count": 4,
        "fps": 8.0,
        "loop": False,
        "source_cell_size": [64, 64],
    }
    assert '"party-popper"' in result.catalogue_snippet
    assert 'rarity="rare"' in result.catalogue_snippet
    assert "reveal_on_unlock=True" in result.catalogue_snippet


def test_promote_refuses_existing_animation_without_overwrite(tmp_path: Path) -> None:
    root = _checkout_root(tmp_path)
    manifest_path = root / "assets" / "mochi" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["animations"]["existing"] = {
        "frames": ["existing/01.png"],
        "frame_count": 1,
        "fps": 8,
        "loop": False,
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    sheet = tmp_path / "existing.png"
    _write_png(sheet, 64, 64)
    spec = EmoteImportSpec(
        source=sheet,
        animation_id="existing",
        label="Existing",
        source_cell_size=(64, 64),
    )

    with pytest.raises(ValueError, match="already exists"):
        promote_emote(spec, checkout_root=root)


def test_catalogue_snippet_uses_expected_definition_shape(tmp_path: Path) -> None:
    source = tmp_path / "emote.png"
    _write_png(source, 64, 64)
    spec = EmoteImportSpec(
        source=source,
        animation_id="tiny_wave",
        label="Tiny Wave",
        bond_level=2,
        rarity="uncommon",
    )

    snippet = build_catalogue_snippet(spec)

    assert snippet.startswith("EmoteDefinition(")
    assert '"tiny-wave"' in snippet
    assert '"tiny_wave"' in snippet
    assert "    2," in snippet
