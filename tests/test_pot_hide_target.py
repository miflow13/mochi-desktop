from pathlib import Path
import tomllib
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.buddy import Buddy
from mochi.pot_hide_target import PotHideTarget
from mochi.state import MochiState


def test_pot_target_hitbox_includes_small_padding() -> None:
    rect = (100.0, 200.0, 80.0, 80.0)

    assert PotHideTarget._point_in_padded_rect((95.0, 240.0), rect, 12.0)
    assert PotHideTarget._point_in_padded_rect((180.0, 280.0), rect, 12.0)
    assert not PotHideTarget._point_in_padded_rect((80.0, 240.0), rect, 12.0)


def test_pot_asset_is_shipped_outside_animation_manifest() -> None:
    root = Path(__file__).resolve().parents[1]
    asset = root / "assets" / "ui" / "pot.png"
    assert asset.is_file()

    with (root / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)
    assert pyproject["tool"]["setuptools"]["data-files"]["share/mochi/ui"] == [
        "assets/ui/*.png"
    ]


def test_drop_on_highlighted_pot_hides_without_normal_drop_settle() -> None:
    target = SimpleNamespace(
        visible=True,
        update_hover=Mock(return_value=True),
        hide=Mock(),
    )
    buddy = SimpleNamespace(
        _drag_started=True,
        _drag_release_handled=False,
        _drag_end_handled=False,
        _drag_move_started=True,
        _drag_sample_position=(1, 1),
        _drag_sample_time=1.0,
        _drag_visual_key=("drag/drag_left_soft.png", 2),
        _pot_hide_target=target,
        _press=(20.0, 20.0),
        _drag_origin=SimpleNamespace(x=320, y=44),
        state=SimpleNamespace(current=MochiState.DRAGGED),
        _drag_motion=SimpleNamespace(reset=Mock()),
        _transition_to=Mock(),
        _play_animation=Mock(),
        _play_drag_settle=Mock(),
        _complete_pot_hide=Mock(return_value=False),
    )

    with patch("mochi.buddy.GLib.idle_add") as idle_add:
        assert Buddy._finish_drag_interaction(buddy)

    target.update_hover.assert_called_once_with((20.0, 20.0))
    target.hide.assert_called_once_with()
    buddy._transition_to.assert_called_once_with(MochiState.IDLE)
    buddy._play_animation.assert_called_once_with("idle")
    buddy._play_drag_settle.assert_not_called()
    buddy._drag_motion.reset.assert_called_once_with()
    assert buddy._drag_end_handled is True
    idle_add.assert_called_once_with(buddy._complete_pot_hide, 320, 44)
