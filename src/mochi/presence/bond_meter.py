"""Persistent bond progression and its lightweight UI integration."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from mochi.care import (
    BOND_FEED_XP,
    BOND_TYPING_XP_PER_SECOND,
    BondAdvance,
    BondState,
)
from mochi.state import MochiState

from .bond_progress_overlay import BondProgressOverlay


BOND_TYPING_TICK_SECONDS = 1
BOND_PERSIST_INTERVAL_XP = 15
BOND_PROGRESS_HOLD_SECONDS = 1.6
BOND_FEED_HOLD_SECONDS = 2.4


class BondMeter(Gtk.ProgressBar):
    """Passive thin bar used inside Mochi's existing right-click menu."""

    def __init__(self, state: BondState | None = None) -> None:
        super().__init__()
        self.set_show_text(False)
        self.set_can_target(False)
        self.set_focusable(False)
        self.set_size_request(110, 6)
        self.add_css_class("mochi-bond-progress")
        self.set_state(state or BondState())

    def set_state(self, state: BondState) -> None:
        self.set_fraction(state.progress_fraction)
        self.set_tooltip_text(
            f"{state.xp}/{state.xp_required} bond XP "
            f"({state.progress_percent}%)"
        )


class BondMeterMixin:
    """Connect shared activities to persistent, non-decaying bond XP."""

    def __init__(self, *args, **kwargs) -> None:
        self._bond_state = BondState()
        self._bond_meter: BondMeter | None = None
        self._bond_level_label: Gtk.Label | None = None
        self._bond_progress_overlay: BondProgressOverlay | None = None
        self._bond_typing_source_id: int | None = None
        self._bond_unsaved_xp = 0
        super().__init__(*args, **kwargs)
        self._restore_bond_state()

        window = getattr(self, "_window", None)
        if not getattr(self, "_preview_mode", False) and window is not None:
            self._bond_progress_overlay = BondProgressOverlay(
                owner=window,
                anchor_widget=self,
                logger=self._logger,
            )

    def _build_context_menu(self):
        menu = super()._build_context_menu()
        self._register_context_menu_row(
            "bond",
            self._build_bond_meter_row(),
            before="feed",
            animated=False,
        )
        return menu

    def _build_bond_meter_row(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("mochi-setting-row")
        row.set_can_target(False)

        self._bond_level_label = Gtk.Label(label=self._bond_label_text())
        self._bond_level_label.set_xalign(0)
        self._bond_level_label.set_hexpand(True)
        self._bond_level_label.set_can_target(False)
        row.append(self._bond_level_label)

        self._bond_meter = BondMeter(self._bond_state)
        row.append(self._bond_meter)
        return row

    def _bond_label_text(self) -> str:
        return f"Bond Lv. {self._bond_state.level}"

    def _set_bond_state_for_ui(self, state: BondState) -> None:
        self._bond_state = BondState(level=state.level, xp=state.xp)
        if self._bond_level_label is not None:
            self._bond_level_label.set_label(self._bond_label_text())
        if self._bond_meter is not None:
            self._bond_meter.set_state(self._bond_state)
        if (
            self._bond_progress_overlay is not None
            and self._bond_progress_overlay.active
        ):
            self._bond_progress_overlay.update(self._bond_state)

    def _restore_bond_state(self) -> None:
        config = getattr(self, "_config", None)
        if config is None:
            return
        self._set_bond_state_for_ui(config.load_bond_state())

    def _persist_bond_state(self) -> None:
        config = getattr(self, "_config", None)
        if config is None:
            return
        config.save_bond_state(self._bond_state)
        self._bond_unsaved_xp = 0

    def _award_bond(self, amount: int, *, persist: bool = True) -> BondAdvance:
        """Award positive bond XP and update every live presentation."""
        advance = self._bond_state.award(amount)
        if advance.xp_awarded <= 0:
            return advance

        previous_level = self._bond_state.level
        self._set_bond_state_for_ui(advance.state)
        self._bond_unsaved_xp += advance.xp_awarded

        if persist or self._bond_unsaved_xp >= BOND_PERSIST_INTERVAL_XP:
            self._persist_bond_state()

        self._logger.debug(
            "Bond advanced: level=%d progress=%d/%d XP (+%d)",
            self._bond_state.level,
            self._bond_state.xp,
            self._bond_state.xp_required,
            advance.xp_awarded,
        )

        if advance.levelled_up:
            self._on_bond_level_up(previous_level, self._bond_state.level)
        return advance

    def _show_bond_progress(self, activity: str) -> None:
        overlay = self._bond_progress_overlay
        if overlay is not None:
            overlay.show_activity(self._bond_state, activity)

    def _on_bond_level_up(self, previous_level: int, new_level: int) -> None:
        """Surface a quiet celebration without taking over animation state."""
        self._logger.info("Bond level increased: %d -> %d", previous_level, new_level)
        feedback = getattr(self, "show_nameplate_feedback", None)
        if callable(feedback):
            feedback(f"Bond Lv. {new_level}!")

    def _on_feed_animation_completed(self) -> None:
        """A completed feed gives a visible one-time relationship boost."""
        self._award_bond(BOND_FEED_XP, persist=True)
        self._show_bond_progress("sharing a snack")
        if self._bond_progress_overlay is not None:
            self._bond_progress_overlay.finish_activity(BOND_FEED_HOLD_SECONDS)

        next_hook = getattr(super(), "_on_feed_animation_completed", None)
        if callable(next_hook):
            next_hook()

    def _on_typing_activity(self) -> None:
        """Start/refresh shared-work bonding only when Mochi is typing too."""
        super()._on_typing_activity()
        if self.state.current is MochiState.TYPING:
            self._start_bond_typing_session()

    def _start_bond_typing_session(self) -> None:
        self._show_bond_progress("typing together")
        if self._bond_typing_source_id is None:
            self._bond_typing_source_id = GLib.timeout_add_seconds(
                BOND_TYPING_TICK_SECONDS,
                self._bond_typing_tick,
            )

    def _bond_typing_tick(self) -> bool:
        if self.state.current is not MochiState.TYPING:
            self._bond_typing_source_id = None
            self._finish_bond_typing_session(remove_timer=False)
            return GLib.SOURCE_REMOVE

        self._award_bond(BOND_TYPING_XP_PER_SECOND, persist=False)
        return GLib.SOURCE_CONTINUE

    def _on_typing_stopped(self) -> None:
        self._finish_bond_typing_session()
        super()._on_typing_stopped()

    def _finish_bond_typing_session(self, *, remove_timer: bool = True) -> None:
        source_id = self._bond_typing_source_id
        self._bond_typing_source_id = None
        if remove_timer and source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

        if self._bond_unsaved_xp > 0:
            self._persist_bond_state()

        if self._bond_progress_overlay is not None:
            self._bond_progress_overlay.finish_activity(BOND_PROGRESS_HOLD_SECONDS)

    def shutdown_presence(self) -> None:
        """Flush earned XP and tear down the visual-only progress surface."""
        source_id = self._bond_typing_source_id
        self._bond_typing_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass
        if self._bond_unsaved_xp > 0:
            self._persist_bond_state()
        if self._bond_progress_overlay is not None:
            self._bond_progress_overlay.destroy()
            self._bond_progress_overlay = None
        super().shutdown_presence()
