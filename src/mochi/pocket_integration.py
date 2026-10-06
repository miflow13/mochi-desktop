"""Thin Buddy composition layer for the Pocket subsystem."""

from __future__ import annotations

from collections.abc import Sequence
import math
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from mochi.behavior import can_arm_pocket_hover
from mochi.pocket import PocketItem
from mochi.pocket_controller import PocketController
from mochi.pocket_drop import PocketDropAdapter
from mochi.pocket_hover import (
    DEFAULT_POCKET_HOVER_DELAY_MS,
    PocketHoverDwell,
    normalize_hover_delay_ms,
)
from mochi.pocket_store import PocketStore
from mochi.pocket_tray import PocketTray
from mochi.pocket_window import PocketWindow
from mochi.sprites import ANIMATIONS
from mochi.state import PresentationState


POCKET_GLOW_PERIOD_SECONDS = 1.15


def _pocket_glow_pulse(elapsed_seconds: float) -> float:
    """Return a smooth 0..1 breathing pulse for Pocket hover feedback."""
    elapsed = max(0.0, float(elapsed_seconds))
    phase = (elapsed % POCKET_GLOW_PERIOD_SECONDS) / POCKET_GLOW_PERIOD_SECONDS
    return 0.5 - 0.5 * math.cos(phase * math.tau)


class PocketBuddyMixin:
    """Compose Pocket services without moving their logic into Buddy."""

    def __init__(self, *args, **kwargs) -> None:
        self._pocket_label: Gtk.Label | None = None
        self._pocket_window: PocketWindow | None = None
        self._pocket_drop: PocketDropAdapter | None = None
        self._pocket_tray: PocketTray | None = None
        self._pocket_hover_delay_ms = DEFAULT_POCKET_HOVER_DELAY_MS
        store = getattr(self, "_pocket_store_override", None) or PocketStore()
        self._pocket_controller = PocketController(
            store,
            current_state=lambda: self.state.current,
            cancel_walk=self._cancel_walk,
            cancel_ambient=self._cancel_active_emote,
            transition=self._transition_to,
            play_animation=lambda name, after: self._play_animation(
                name, after=after
            ),
            mark_interaction=self._mark_interaction,
            resume_ambient=self._maybe_resume_ambient_activity,
            show_feedback=self._show_pocket_feedback,
            on_changed=self._on_pocket_changed,
        )
        self._pocket_dwell = PocketHoverDwell(
            delay_ms=lambda: self._pocket_hover_delay_ms,
            can_arm=self._pocket_hover_can_arm,
            show_peek=self._show_pocket_peek,
            hide_peek=self._hide_pocket_peek,
            open_tray=self._open_pocket_tray,
            close_tray=self._close_pocket_tray,
        )
        super().__init__(*args, **kwargs)
        self._pocket_hover_delay_ms = self._config.load_pocket_hover_delay_ms()
        if not self._preview_mode:
            self._pocket_drop = PocketDropAdapter(self, self._pocket_controller)

    def _draw(self, area, context, width: int, height: int) -> None:
        """Add a breathing Pocket acceptance glow behind the Buddy render."""
        if self._pocket_controller.hover_active:
            now = time.monotonic()
            started_at = getattr(self, "_pocket_glow_started_at", None)
            if started_at is None or now < started_at:
                started_at = now
                self._pocket_glow_started_at = now

            frame = self.player.frame
            if frame is None:
                frame = ANIMATIONS["default"].frames[0]
            self.atlas.draw_glow(
                context,
                frame,
                width,
                height,
                pulse=_pocket_glow_pulse(now - started_at),
            )
        else:
            self._pocket_glow_started_at = None
        super()._draw(area, context, width, height)

    # Pointer: always run the existing handler, then feed the dwell. Presses
    # interrupt first so a click or right-click wins before anything else runs.

    def _on_enter(self, controller, x: float, y: float) -> None:
        super()._on_enter(controller, x, y)
        self._pocket_dwell.pointer_entered()

    def _on_leave(self, controller) -> None:
        super()._on_leave(controller)
        self._pocket_dwell.pointer_left()

    def _on_motion(self, controller, x: float, y: float) -> None:
        super()._on_motion(controller, x, y)
        self._pocket_dwell.pointer_moved()

    def _on_pressed(self, gesture, presses: int, x: float, y: float) -> None:
        self._pocket_dwell.interrupt()
        super()._on_pressed(gesture, presses, x, y)

    def _on_context_pressed(self, gesture, presses: int, x: float, y: float) -> None:
        self._pocket_dwell.interrupt()
        super()._on_context_pressed(gesture, presses, x, y)

    def _pocket_hover_can_arm(self) -> bool:
        controller = self._pocket_controller
        window = self._pocket_window
        return (
            not self._preview_mode
            and not self._placement.layer_shell_enabled
            and controller.count > 0
            and not controller.busy
            and not controller.hover_active
            and not self._context_menu_open
            and self._press is None
            and not self._drag_started
            and self.state.presentation is PresentationState.NORMAL
            and not (window is not None and window.get_visible())
            # Resting on a talking Mochi is how you read him; the tray waits.
            and not self.presence_speech_visible()
            and can_arm_pocket_hover(self.state.current)
        )

    def _presence_interaction_active(self) -> bool:
        # Ambient speech waits while the peek or tray is on screen, the same
        # way it waits for a press or a drag.
        tray = self._pocket_tray
        return super()._presence_interaction_active() or (
            tray is not None and tray.view is not None
        )

    # Tray -------------------------------------------------------------------

    def _ensure_pocket_tray(self) -> PocketTray:
        if self._pocket_tray is None:
            self._pocket_tray = PocketTray(
                owner=self._window,
                controller=self._pocket_controller,
                dwell=self._pocket_dwell,
                on_manage=self._manage_pocket_from_tray,
                show_feedback=self._show_pocket_feedback,
            )
        return self._pocket_tray

    def _show_pocket_peek(self, fill_ms: int) -> None:
        self._ensure_pocket_tray().show_peek(self._pocket_controller.count, fill_ms)

    def _hide_pocket_peek(self) -> None:
        if self._pocket_tray is not None:
            self._pocket_tray.hide_peek()

    def _open_pocket_tray(self, focus: bool) -> bool:
        tray = self._ensure_pocket_tray()
        # Presentation only: the tray opens even when Mochi is waking or busy.
        self._pocket_controller.begin_offer()
        tray.open(focus=focus)
        return True

    def _close_pocket_tray(self) -> None:
        if self._pocket_tray is not None:
            self._pocket_tray.close()

    def _manage_pocket_from_tray(self) -> None:
        self._pocket_dwell.close()
        self._show_pocket_window()

    # Context menu -------------------------------------------------------------

    def _build_context_menu(self):
        menu = super()._build_context_menu()
        button, self._pocket_label = self._make_menu_button(
            f"Pocket · {self._pocket_controller.count}",
            "folder-download-symbolic",
            self._pocket_from_context_menu,
        )
        self._register_context_menu_row(
            "pocket",
            button,
            before="sleep",
        )
        return menu

    def _pocket_from_context_menu(self, _button: Gtk.Button) -> None:
        self._close_context_menu_then(self._open_pocket_from_menu)

    def _open_pocket_from_menu(self) -> None:
        if self._preview_mode or self._placement.layer_shell_enabled:
            # No X11 root coordinates to anchor a tray: keep the window path.
            self._show_pocket_window()
            return
        self._pocket_dwell.open_pinned()

    # Window and setting -------------------------------------------------------

    def _show_pocket_window(self) -> None:
        if self._pocket_window is None:
            self._pocket_window = PocketWindow(
                self._pocket_controller,
                hover_delay_ms=self._pocket_hover_delay_ms,
                on_hover_delay_changed=self._set_pocket_hover_delay,
            )
            self._pocket_window.set_transient_for(self._window)
        else:
            self._pocket_window.refresh()
        self._pocket_window.present()

    def _set_pocket_hover_delay(self, delay_ms: int) -> None:
        self._pocket_hover_delay_ms = normalize_hover_delay_ms(delay_ms)
        self._config.save_pocket_hover_delay_ms(self._pocket_hover_delay_ms)

    def _on_pocket_changed(self, items: Sequence[PocketItem]) -> None:
        if self._pocket_label is not None:
            self._pocket_label.set_text(f"Pocket · {len(items)}")
        if (
            self._pocket_window is not None
            and self._pocket_window.get_visible()
        ):
            self._pocket_window.refresh()
        if self._pocket_tray is not None:
            self._pocket_tray.refresh()

    def _show_pocket_feedback(self, message: str) -> None:
        show_feedback = getattr(self, "show_nameplate_feedback", None)
        if callable(show_feedback):
            show_feedback(message)
        else:
            self._logger.info("Pocket: %s", message)

    def shutdown_presence(self) -> None:
        # Stop the dwell first so no timer can call into a destroyed tray.
        self._pocket_dwell.shutdown()
        if self._pocket_tray is not None:
            self._pocket_tray.destroy()
            self._pocket_tray = None
        if self._pocket_drop is not None:
            self._pocket_drop.detach()
            self._pocket_drop = None
        if self._pocket_window is not None:
            self._pocket_window.destroy()
            self._pocket_window = None
        super().shutdown_presence()
