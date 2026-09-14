"""Compact bond progress UI for Mochi's context menu."""

from __future__ import annotations

import math

from gi.repository import Gtk


BOND_PHASE_COUNT = 4
DEFAULT_BOND_PHASES_FILLED = 0


def normalize_bond_pips(filled: int) -> int:
    """Clamp a bond phase count to Mochi's four-pip meter."""
    try:
        value = int(filled)
    except (TypeError, ValueError):
        value = 0
    return max(0, min(BOND_PHASE_COUNT, value))


def bond_pip_states(filled: int) -> tuple[bool, ...]:
    """Return the four active/inactive states used by the visual meter."""
    normalized = normalize_bond_pips(filled)
    return tuple(index < normalized for index in range(BOND_PHASE_COUNT))


class BondMeter(Gtk.Box):
    """Four tiny, non-interactive circles representing one bond level cycle."""

    PIP_SIZE = 14
    OUTLINE_RGBA = (0.58, 0.58, 0.66, 0.62)
    ACTIVE_RING_RGBA = (0.70, 0.70, 0.76, 0.76)
    ACTIVE_ORANGE_RGBA = (1.0, 0.57, 0.13, 1.0)

    def __init__(self, filled: int = DEFAULT_BOND_PHASES_FILLED) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.set_can_target(False)
        self.set_valign(Gtk.Align.CENTER)
        self._filled = normalize_bond_pips(filled)
        self._pips: list[Gtk.DrawingArea] = []

        for index in range(BOND_PHASE_COUNT):
            pip = Gtk.DrawingArea()
            pip.set_content_width(self.PIP_SIZE)
            pip.set_content_height(self.PIP_SIZE)
            pip.set_size_request(self.PIP_SIZE, self.PIP_SIZE)
            pip.set_can_target(False)
            pip.set_draw_func(self._draw_pip, index)
            self.append(pip)
            self._pips.append(pip)

    @property
    def filled(self) -> int:
        return self._filled

    @property
    def total(self) -> int:
        return BOND_PHASE_COUNT

    def set_filled(self, filled: int) -> None:
        """Update only the presentation state; care/progression owns the value."""
        normalized = normalize_bond_pips(filled)
        if normalized == self._filled:
            return
        self._filled = normalized
        for pip in self._pips:
            pip.queue_draw()

    def _draw_pip(
        self,
        _area: Gtk.DrawingArea,
        cr,
        width: int,
        height: int,
        index: int,
    ) -> None:
        active = index < self._filled
        center_x = width / 2.0
        center_y = height / 2.0
        radius = max(1.0, min(width, height) / 2.0 - 1.2)

        cr.set_line_width(1.25)
        cr.set_source_rgba(*(self.ACTIVE_RING_RGBA if active else self.OUTLINE_RGBA))
        cr.arc(center_x, center_y, radius, 0, 2 * math.pi)
        cr.stroke()

        if not active:
            return

        # The warm orange stays inside a quiet neutral ring, matching the
        # reference design without turning bond progress into a loud game HUD.
        inner_radius = max(1.0, radius - 3.0)
        cr.set_source_rgba(*self.ACTIVE_ORANGE_RGBA)
        cr.arc(center_x, center_y, inner_radius, 0, 2 * math.pi)
        cr.fill()


class BondMeterMixin:
    """Add Mochi's passive, persistent bond meter to the existing context menu.

    Bond progress is intentionally non-punishing in this v0.3 slice: completed
    care can move the meter forward, but time away from Mochi never moves it
    backward. The current four-pip cycle is persisted through ConfigStore so
    restarting the application does not erase relationship progress.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._bond_ui_filled = DEFAULT_BOND_PHASES_FILLED
        self._bond_meter: BondMeter | None = None
        super().__init__(*args, **kwargs)
        self._restore_bond_progress()

    def _build_context_menu(self):
        popover = super()._build_context_menu()
        self._register_context_menu_row(
            "bond",
            self._build_bond_meter_row(),
            before="sleep",
            animated=False,
        )
        return popover

    def _build_bond_meter_row(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("mochi-setting-row")
        row.set_can_target(False)

        label = Gtk.Label(label="Bond level")
        label.set_xalign(0)
        label.set_hexpand(True)
        label.set_can_target(False)
        row.append(label)

        self._bond_meter = BondMeter(self._bond_ui_filled)
        row.append(self._bond_meter)
        return row

    def set_bond_progress_for_ui(self, filled: int) -> None:
        """Update the four-pip display without owning level-up policy."""
        self._bond_ui_filled = normalize_bond_pips(filled)
        if self._bond_meter is not None:
            self._bond_meter.set_filled(self._bond_ui_filled)

    def advance_bond_progress_for_ui(self, amount: int = 1) -> None:
        """Advance the current bond cycle, clamped until level-up logic exists."""
        try:
            delta = int(amount)
        except (TypeError, ValueError):
            delta = 0
        self.set_bond_progress_for_ui(self._bond_ui_filled + max(0, delta))

    def _restore_bond_progress(self) -> None:
        """Restore persisted progress after the Buddy core has initialized."""
        config = getattr(self, "_config", None)
        if config is None:
            return
        self.set_bond_progress_for_ui(config.load_bond_phases())

    def _persist_bond_progress(self) -> None:
        """Persist the current cycle without coupling storage to the widget."""
        config = getattr(self, "_config", None)
        if config is None:
            return
        config.save_bond_phases(self._bond_ui_filled)

    def _on_feed_animation_completed(self) -> None:
        """Award and persist one bond phase only after a feed fully completes."""
        self.advance_bond_progress_for_ui()
        self._persist_bond_progress()
        next_hook = getattr(super(), "_on_feed_animation_completed", None)
        if callable(next_hook):
            next_hook()
