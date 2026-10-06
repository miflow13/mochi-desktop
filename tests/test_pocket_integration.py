"""Pocket composition, menu, and lifecycle integration coverage."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest

from mochi.pocket_hover import DwellPhase
from mochi.pocket_integration import PocketBuddyMixin
from mochi.presence.click_dialogue import PresenceBuddy, PresenceX11Buddy
from mochi.presence.integration import PresenceBuddyMixin
from mochi.state import MochiState, PresentationState


class _MenuBase:
    def _build_context_menu(self):
        return "menu"

    def _make_menu_button(self, label, icon, callback):
        self.button_args = (label, icon, callback)
        self.pocket_label = Mock()
        return "pocket-button", self.pocket_label

    def _register_context_menu_row(self, row_id, widget, **kwargs):
        self.registered_row = (row_id, widget, kwargs)


class _MenuHarness(PocketBuddyMixin, _MenuBase):
    pass


class _ShutdownBase:
    def shutdown_presence(self) -> None:
        self.base_shutdown = True


class _ShutdownHarness(PocketBuddyMixin, _ShutdownBase):
    pass


def test_both_production_buddies_include_the_same_pocket_layer() -> None:
    assert PocketBuddyMixin in PresenceBuddy.__mro__
    assert PocketBuddyMixin in PresenceX11Buddy.__mro__


def test_pocket_menu_row_shows_count_and_uses_layout_seam() -> None:
    harness = object.__new__(_MenuHarness)
    harness._pocket_controller = SimpleNamespace(count=3)

    assert harness._build_context_menu() == "menu"

    label, icon, callback = harness.button_args
    assert label == "Pocket · 3"
    assert icon == "folder-download-symbolic"
    assert callback == harness._pocket_from_context_menu
    assert harness.registered_row == (
        "pocket",
        "pocket-button",
        {"before": "sleep"},
    )


def test_pocket_menu_action_defers_the_tray_until_menu_closes() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._close_context_menu_then = Mock()

    harness._pocket_from_context_menu(None)

    harness._close_context_menu_then.assert_called_once_with(
        harness._open_pocket_from_menu
    )


def test_count_change_updates_menu_label_and_open_window() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_tray = None
    harness._pocket_label = Mock()
    harness._pocket_window = Mock()
    harness._pocket_window.get_visible.return_value = True
    items = (object(), object())

    harness._on_pocket_changed(items)

    harness._pocket_label.set_text.assert_called_once_with("Pocket · 2")
    harness._pocket_window.refresh.assert_called_once_with()


def test_shutdown_detaches_drop_adapter_and_destroys_window() -> None:
    harness = object.__new__(_ShutdownHarness)
    harness._pocket_dwell = Mock()
    harness._pocket_tray = None
    harness._pocket_drop = Mock()
    harness._pocket_window = Mock()
    drop = harness._pocket_drop
    window = harness._pocket_window
    harness.base_shutdown = False

    harness.shutdown_presence()

    drop.detach.assert_called_once_with()
    window.destroy.assert_called_once_with()
    assert harness._pocket_drop is None
    assert harness._pocket_window is None
    assert harness.base_shutdown is True


class _DrawBase:
    def _draw(self, area, context, width, height):
        self.base_draws.append((area, context, width, height))


class _DrawHarness(PocketBuddyMixin, _DrawBase):
    pass


def test_pocket_hover_draws_breathing_glow_before_normal_render() -> None:
    harness = object.__new__(_DrawHarness)
    frame = object()
    harness._pocket_controller = SimpleNamespace(hover_active=True)
    harness.player = SimpleNamespace(frame=frame)
    harness.atlas = Mock()
    harness.base_draws = []

    with patch(
        "mochi.pocket_integration.time.monotonic",
        side_effect=(10.0, 10.575),
    ):
        harness._draw("area", "context", 112, 112)
        harness._draw("area", "context", 112, 112)

    first_call, second_call = harness.atlas.draw_glow.call_args_list
    assert first_call.args == ("context", frame, 112, 112)
    assert first_call.kwargs["pulse"] == pytest.approx(0.0)
    assert second_call.args == ("context", frame, 112, 112)
    assert second_call.kwargs["pulse"] == pytest.approx(1.0)
    assert harness.base_draws == [
        ("area", "context", 112, 112),
        ("area", "context", 112, 112),
    ]


def test_pocket_glow_phase_resets_after_hover_ends() -> None:
    harness = object.__new__(_DrawHarness)
    frame = object()
    harness._pocket_controller = SimpleNamespace(hover_active=True)
    harness.player = SimpleNamespace(frame=frame)
    harness.atlas = Mock()
    harness.base_draws = []

    with patch(
        "mochi.pocket_integration.time.monotonic",
        side_effect=(20.0, 20.2, 30.0),
    ):
        harness._draw("area", "context", 112, 112)
        harness._draw("area", "context", 112, 112)
        harness._pocket_controller.hover_active = False
        harness._draw("area", "context", 112, 112)
        harness._pocket_controller.hover_active = True
        harness._draw("area", "context", 112, 112)

    assert harness.atlas.draw_glow.call_args_list[-1].kwargs["pulse"] == pytest.approx(0.0)


def test_normal_render_skips_pocket_glow_when_not_hovering() -> None:
    harness = object.__new__(_DrawHarness)
    harness._pocket_controller = SimpleNamespace(hover_active=False)
    harness.player = SimpleNamespace(frame=object())
    harness.atlas = Mock()
    harness.base_draws = []

    harness._draw("area", "context", 112, 112)

    harness.atlas.draw_glow.assert_not_called()
    assert harness.base_draws == [("area", "context", 112, 112)]



def test_hidden_pocket_window_skips_row_rebuild_until_next_open() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_tray = None
    harness._pocket_label = Mock()
    harness._pocket_window = Mock()
    harness._pocket_window.get_visible.return_value = False

    harness._on_pocket_changed((object(),))

    harness._pocket_label.set_text.assert_called_once_with("Pocket · 1")
    harness._pocket_window.refresh.assert_not_called()


class _PointerBase:
    def _on_enter(self, controller, x, y):
        self.order.append("base-enter")

    def _on_leave(self, controller):
        self.order.append("base-leave")

    def _on_motion(self, controller, x, y):
        self.order.append("base-motion")

    def _on_pressed(self, gesture, presses, x, y):
        self.order.append("base-press")

    def _on_context_pressed(self, gesture, presses, x, y):
        self.order.append("base-context")


class _PointerHarness(PocketBuddyMixin, _PointerBase):
    pass


def _pointer_harness() -> _PointerHarness:
    harness = object.__new__(_PointerHarness)
    harness.order = []
    harness._pocket_dwell = Mock()
    for name in (
        "pointer_entered",
        "pointer_moved",
        "pointer_left",
        "interrupt",
    ):
        getattr(harness._pocket_dwell, name).side_effect = (
            lambda name=name: harness.order.append(name)
        )
    return harness


def test_pointer_events_reach_the_base_and_then_the_dwell() -> None:
    harness = _pointer_harness()

    harness._on_enter(None, 1.0, 2.0)
    harness._on_motion(None, 2.0, 3.0)
    harness._on_leave(None)

    assert harness.order == [
        "base-enter",
        "pointer_entered",
        "base-motion",
        "pointer_moved",
        "base-leave",
        "pointer_left",
    ]


def test_press_and_right_click_interrupt_before_the_base_runs() -> None:
    harness = _pointer_harness()

    harness._on_pressed(None, 1, 4.0, 5.0)
    harness._on_context_pressed(None, 1, 4.0, 5.0)

    assert harness.order == [
        "interrupt",
        "base-press",
        "interrupt",
        "base-context",
    ]


def _arm_harness() -> PocketBuddyMixin:
    harness = object.__new__(PocketBuddyMixin)
    harness._preview_mode = False
    harness._placement = SimpleNamespace(layer_shell_enabled=False)
    harness._pocket_controller = SimpleNamespace(count=2, busy=False, hover_active=False)
    harness._context_menu_open = False
    harness._press = None
    harness._drag_started = False
    harness.state = SimpleNamespace(
        current=MochiState.IDLE, presentation=PresentationState.NORMAL
    )
    harness._pocket_window = None
    harness.presence_speech_visible = lambda: False
    return harness


def test_hover_can_arm_in_the_ordinary_case() -> None:
    assert _arm_harness()._pocket_hover_can_arm() is True


@pytest.mark.parametrize(
    "block",
    (
        lambda h: setattr(h, "_preview_mode", True),
        lambda h: setattr(h._placement, "layer_shell_enabled", True),
        lambda h: setattr(h._pocket_controller, "count", 0),
        lambda h: setattr(h._pocket_controller, "busy", True),
        lambda h: setattr(h._pocket_controller, "hover_active", True),
        lambda h: setattr(h, "_context_menu_open", True),
        lambda h: setattr(h, "_press", (3.0, 4.0)),
        lambda h: setattr(h, "_drag_started", True),
        lambda h: setattr(h.state, "presentation", PresentationState.LEVEL_UP),
        lambda h: setattr(
            h, "_pocket_window", SimpleNamespace(get_visible=lambda: True)
        ),
        lambda h: setattr(h.state, "current", MochiState.WALKING),
        lambda h: setattr(h.state, "current", MochiState.FEDORA),
        lambda h: setattr(h.state, "current", MochiState.DRAGGED),
        lambda h: setattr(h, "presence_speech_visible", lambda: True),
    ),
    ids=(
        "preview",
        "layer-shell",
        "empty",
        "receiving",
        "drag-in",
        "menu",
        "press",
        "drag",
        "level-up",
        "window-open",
        "walking",
        "fedora",
        "dragged",
        "talking",
    ),
)
def test_hover_never_arms_when_something_else_owns_mochi(block) -> None:
    harness = _arm_harness()
    block(harness)

    assert harness._pocket_hover_can_arm() is False


def test_menu_opens_a_focused_tray_on_the_x11_path() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._preview_mode = False
    harness._placement = SimpleNamespace(layer_shell_enabled=False)
    harness._pocket_dwell = Mock()
    harness._show_pocket_window = Mock()

    harness._open_pocket_from_menu()

    harness._pocket_dwell.open_pinned.assert_called_once_with()
    harness._show_pocket_window.assert_not_called()


@pytest.mark.parametrize(("preview", "layer_shell"), ((True, False), (False, True)))
def test_menu_keeps_the_window_path_without_x11_placement(
    preview: bool, layer_shell: bool
) -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._preview_mode = preview
    harness._placement = SimpleNamespace(layer_shell_enabled=layer_shell)
    harness._pocket_dwell = Mock()
    harness._show_pocket_window = Mock()

    harness._open_pocket_from_menu()

    harness._show_pocket_window.assert_called_once_with()
    harness._pocket_dwell.open_pinned.assert_not_called()


def test_opening_the_tray_offers_first_and_opens_even_if_refused() -> None:
    harness = object.__new__(PocketBuddyMixin)
    order: list[str] = []
    harness._pocket_controller = Mock()
    harness._pocket_controller.begin_offer.side_effect = (
        lambda: order.append("offer") or False
    )
    harness._pocket_tray = Mock()
    harness._pocket_tray.open.side_effect = (
        lambda *, focus: order.append(f"open:{focus}")
    )

    assert harness._open_pocket_tray(False) is True
    assert order == ["offer", "open:False"]


def test_peek_shows_the_live_count() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_tray = Mock()
    harness._pocket_controller = SimpleNamespace(count=4)

    harness._show_pocket_peek(1400)

    harness._pocket_tray.show_peek.assert_called_once_with(4, 1400)


def test_hide_and_close_are_safe_before_the_tray_exists() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_tray = None

    harness._hide_pocket_peek()
    harness._close_pocket_tray()


def test_manage_closes_the_tray_then_opens_the_window() -> None:
    harness = object.__new__(PocketBuddyMixin)
    order: list[str] = []
    harness._pocket_dwell = Mock()
    harness._pocket_dwell.close.side_effect = lambda: order.append("close")
    harness._show_pocket_window = Mock(side_effect=lambda: order.append("window"))

    harness._manage_pocket_from_tray()

    assert order == ["close", "window"]


def test_count_change_refreshes_an_open_tray() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_label = Mock()
    harness._pocket_window = None
    harness._pocket_tray = Mock()

    harness._on_pocket_changed((object(),))

    harness._pocket_tray.refresh.assert_called_once_with()


def test_shutdown_stops_the_dwell_before_destroying_the_tray() -> None:
    harness = object.__new__(_ShutdownHarness)
    order: list[str] = []
    harness._pocket_dwell = Mock()
    harness._pocket_dwell.shutdown.side_effect = lambda: order.append("dwell")
    tray = Mock()
    tray.destroy.side_effect = lambda: order.append("tray")
    harness._pocket_tray = tray
    harness._pocket_drop = Mock()
    harness._pocket_window = Mock()
    harness.base_shutdown = False

    harness.shutdown_presence()

    assert order == ["dwell", "tray"]
    assert harness._pocket_tray is None
    assert harness.base_shutdown is True


def test_hover_delay_change_is_normalized_and_saved() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._config = Mock()
    harness._pocket_hover_delay_ms = 2000

    harness._set_pocket_hover_delay(3000)
    harness._set_pocket_hover_delay(2500)

    assert harness._pocket_hover_delay_ms == 2000
    assert harness._config.save_pocket_hover_delay_ms.call_args_list == [
        call(3000),
        call(2000),
    ]


def test_pocket_window_receives_the_current_hover_delay() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_window = None
    harness._pocket_controller = Mock()
    harness._pocket_hover_delay_ms = 1500
    harness._window = Mock()

    with patch("mochi.pocket_integration.PocketWindow") as window_class:
        harness._show_pocket_window()

    window_class.assert_called_once_with(
        harness._pocket_controller,
        hover_delay_ms=1500,
        on_hover_delay_changed=harness._set_pocket_hover_delay,
    )


# Speech and the tray never share the space above Mochi ----------------------


class _SpeechBase:
    def _presence_interaction_active(self) -> bool:
        return self.base_active


class _SpeechHarness(PocketBuddyMixin, _SpeechBase):
    pass


@pytest.mark.parametrize(
    ("base_active", "phase", "tray", "expected"),
    (
        (False, DwellPhase.IDLE, None, False),
        (False, DwellPhase.IDLE, SimpleNamespace(view=None), False),
        (False, DwellPhase.ARMED, None, True),
        (False, DwellPhase.PEEK, SimpleNamespace(view="peek"), True),
        (False, DwellPhase.OPEN, SimpleNamespace(view="tray"), True),
        (True, DwellPhase.IDLE, None, True),
    ),
    ids=("idle", "tray-hidden", "counting", "peek", "tray", "press"),
)
def test_ambient_speech_waits_while_resting_on_mochi_or_the_tray_shows(
    base_active: bool, phase, tray, expected: bool
) -> None:
    harness = object.__new__(_SpeechHarness)
    harness.base_active = base_active
    harness._pocket_dwell = SimpleNamespace(phase=phase)
    harness._pocket_tray = tray

    assert harness._presence_interaction_active() is expected


def test_presence_interaction_seam_reflects_press_and_drag() -> None:
    harness = object.__new__(PresenceBuddyMixin)
    harness._press = None
    harness._drag_started = False
    assert harness._presence_interaction_active() is False

    harness._press = (1.0, 2.0)
    assert harness._presence_interaction_active() is True

    harness._press = None
    harness._drag_started = True
    assert harness._presence_interaction_active() is True


def test_presence_speech_visible_reflects_the_bubble() -> None:
    harness = object.__new__(PresenceBuddyMixin)
    harness._presence_bubble = None
    assert harness.presence_speech_visible() is False

    harness._presence_bubble = SimpleNamespace(visible=False)
    assert harness.presence_speech_visible() is False

    harness._presence_bubble = SimpleNamespace(visible=True)
    assert harness.presence_speech_visible() is True


def test_ambient_evaluation_asks_the_interaction_seam() -> None:
    harness = object.__new__(PresenceBuddyMixin)
    engine = Mock()
    engine.typing_snapshot.return_value = (0.0, 0.0)
    engine.evaluate.return_value = None
    harness._ambient_presence_engine = engine
    harness._presence_shutting_down = False
    harness._media_monitor = None
    harness._system_signal_monitor = None
    harness._user_idle = False
    harness._session_blocked = lambda: False
    harness._presence_active_session_started_at = 0.0
    harness._presence_app_category = "unknown"
    harness.state = SimpleNamespace(current=MochiState.IDLE)
    harness._context_menu_open = False
    harness._presence_bubble = SimpleNamespace(visible=True)
    harness._presence_interaction_active = lambda: True

    harness._evaluate_ambient_presence()

    context = engine.evaluate.call_args.args[0]
    assert context.interaction_active is True
    assert context.overlay_visible is True
