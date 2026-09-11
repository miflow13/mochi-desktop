from __future__ import annotations

import inspect

from mochi.presence.click_dialogue import PresenceBuddy, PresenceX11Buddy
from mochi.quick_start import (
    QUICK_START_FOOTER,
    QUICK_START_SECTIONS,
    QuickStartMixin,
    QuickStartWindow,
)


def _section(title: str):
    return next(section for section in QUICK_START_SECTIONS if section.title == title)


def test_quick_start_is_part_of_both_runtime_buddies() -> None:
    assert QuickStartMixin in PresenceBuddy.__mro__
    assert QuickStartMixin in PresenceX11Buddy.__mro__


def test_context_menu_entry_closes_menu_before_presenting_help() -> None:
    menu_source = inspect.getsource(QuickStartMixin._make_quick_start_menu_button)
    action_source = inspect.getsource(
        QuickStartMixin._show_quick_start_from_context_menu
    )

    assert "What can Mochi do?" in menu_source
    assert "_close_context_menu_then(self._show_quick_start)" in action_source


def test_quick_start_is_lazy_reusable_and_does_not_touch_buddy_state() -> None:
    source = inspect.getsource(QuickStartMixin._show_quick_start)

    assert "if self._quick_start_window is None" in source
    assert "self._quick_start_window.present()" in source
    assert "_transition_to" not in source
    assert "_play_animation" not in source
    assert "_mark_interaction" not in source


def test_quick_start_window_is_non_modal_transient_and_reopenable() -> None:
    init_source = inspect.getsource(QuickStartWindow.__init__)

    assert "set_transient_for(owner)" in init_source
    assert "set_modal(False)" in init_source
    assert "set_hide_on_close(True)" in init_source
    assert "Gtk.ScrolledWindow" in init_source


def test_quick_start_copy_matches_current_capabilities() -> None:
    titles = {section.title for section in QUICK_START_SECTIONS}
    assert titles == {
        "Meet Mochi",
        "Ambient Reactions",
        "Play With Mochi",
        "Little Thoughts",
        "You’re in Control",
        "Try This",
    }

    ambient = " ".join(_section("Ambient Reactions").bullets)
    assert "Typing" in ambient
    assert "VS Code" in ambient
    assert "Terminal" in ambient
    assert "Music" in ambient
    assert "YouTube" in ambient
    assert "file browsing" in ambient

    interactions = " ".join(_section("Play With Mochi").bullets)
    assert "Hover" in interactions
    assert "Left-click" in interactions
    assert "Double-click" in interactions
    assert "Drag" in interactions
    assert "Right-click" in interactions

    controls = _section("You’re in Control").body
    assert "Edge roam" in controls
    assert "Stay put" in controls
    assert "speech bubbles" in controls
    assert "ambient reactions" in controls
    assert "quiet mode" in controls
    assert "Mochi Lab" in controls


def test_quick_start_ends_with_requested_playful_line() -> None:
    assert QUICK_START_FOOTER == "That’s enough reading. Go bother Mochi. 🌱"
