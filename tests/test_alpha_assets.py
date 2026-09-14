"""Release inventory and supported-size rendering checks."""
from pathlib import Path
import tomllib

import cairo
import pytest

from mochi import __version__
from mochi.sprites import ANIMATIONS, SpriteAtlas


@pytest.mark.parametrize('size', [64, 128, 192, 256])
def test_every_runtime_frame_fits_supported_canvas(size):
    atlas = SpriteAtlas()
    for animation in ANIMATIONS.values():
        for frame in animation.frames:
            x, y, width, height = atlas.visible_bounds(frame, size, size)
            assert 0 <= x <= x + width <= size, (animation.name, frame.sprite)
            assert 0 <= y <= y + height <= size, (animation.name, frame.sprite)
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
            atlas.draw(cairo.Context(surface), frame, size, size)
            assert any(surface.get_data()), frame.sprite


def test_runtime_and_package_versions_agree():
    project = Path(__file__).resolve().parents[1] / 'pyproject.toml'
    assert tomllib.loads(project.read_text())['project']['version'] == __version__
