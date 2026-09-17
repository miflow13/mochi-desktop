"""Passive bond progress presentation for Mochi's context menu."""

from __future__ import annotations

import math

from gi.repository import Gtk

from mochi.care import BOND_POINTS_PER_LEVEL, BondAdvance, BondState


def bond_pip_states(filled: int) -> tuple[bool, ...]:
    """Return active/inactive states for Mochi's four-step bond cycle."""
    try:
        normalized = int(filled)
    except (TypeError, ValueError):
        normalized = 0
    normalized = max(0, min(BOND_POINTS_PER_LEVEL, normalized))
    return tuple(index < normalized for index in range(BOND_POINTS_PER_LEVEL))


class BondMeter(Gtk.Box):
    """Tiny non-interactive pips representing progress toward the next level."""

    PIP_SIZE = 14
    OUTLINE_RGBA = (0.58, 0.58, 0.66, 0.62)
    ACTIVE_RING_RGBA = (0.70, 0.70, 0.76, 0.76)
    ACTIVE_ORANGE_RGBA = (1.0, 0.57, 0.13, 1.0)

    def __init__(self, filled: int = 0) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.set_can_target(False)
        self.set_valign(Gtk.Align.CENTER)
        self._filled = sum(bond_pip_states(filled))
        self._pips: list[Gtk.DrawingArea] = []

        for index in range(BOND_POINTS_PER_LEVEL):
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

    def set_filled(self, filled: int) -> None:
        normalized = sum(bond_pip_states(filled))
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

        inner_radius = max(1.0, radius - 3.0)
        cr.set_source_rgba(*self.ACTIVE_ORANGE_RGBA)
        cr.arc(center_x, center_y, inner_radius, 0, 2 * math.pi)
        cr.fill()


class BondMeterMixin:
    """Connect persistent care progress to a passive context-menu display."""

    def __init__(self, *args, **kwargs) -> None:
        self._bond_state = BondState()
        self._bond_meter: BondMeter | None = None
        self._bond_level_label: Gtk.Label | None = None
        super().__init__(*args, **kwargs)
        self._restore_bond_state()

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

        self._bond_meter = BondMeter(self._bond_state.points)
        row.append(self._bond_meter)
        return row

    def _bond_label_text(self) -> str:
        return f"Bond Lv. {self._bond_state.level}"

    def _set_bond_state_for_ui(self, state: BondState) -> None:
        self._bond_state = BondState(level=state.level, points=state.points)
        if self._bond_level_label is not None:
            self._bond_level_label.set_label(self._bond_label_text())
        if self._bond_meter is not None:
            self._bond_meter.set_filled(self._bond_state.points)

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

    def _award_bond(self, amount: int = 1) -> BondAdvance:
        """Reusable seam for future care actions such as play or co-working."""
        advance = self._bond_state.award(amount)
        if advance.points_awarded <= 0:
            return advance

        previous_level = self._bond_state.level
        self._set_bond_state_for_ui(advance.state)
        self._persist_bond_state()
        self._logger.debug(
            "Bond advanced: level=%d progress=%d/%d (+%d)",
            self._bond_state.level,
            self._bond_state.points,
            self._bond_state.points_per_level,
            advance.points_awarded,
        )

        if advance.levelled_up:
            self._on_bond_level_up(previous_level, self._bond_state.level)
        return advance

    def _on_bond_level_up(self, previous_level: int, new_level: int) -> None:
        """Presentation hook for a future level-up reaction or unlock."""

    def _on_feed_animation_completed(self) -> None:
        """A completed feed earns one bond point; interrupted feeds earn none."""
        self._award_bond(1)
        next_hook = getattr(super(), "_on_feed_animation_completed", None)
        if callable(next_hook):
            next_hook()
