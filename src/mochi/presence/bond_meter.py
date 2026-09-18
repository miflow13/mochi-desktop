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
from mochi.bond_orbs import XpOrbField
from mochi.state import MochiState, PresentationState

from .bond_progress_overlay import BondProgressOverlay


BOND_TYPING_TICK_SECONDS = 1
BOND_PERSIST_INTERVAL_XP = 15
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
        self._bond_orbs = XpOrbField()
        self._bond_meter: BondMeter | None = None
        self._bond_level_label: Gtk.Label | None = None
        self._bond_dev_status_label: Gtk.Label | None = None
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
                on_level_up_finished=self._on_bond_level_up_finished,
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
        if self._bond_dev_status_label is not None:
            self._bond_dev_status_label.set_text(self._bond_dev_status_text())
        if (
            self._bond_progress_overlay is not None
            and self._bond_progress_overlay.active
            and self.state.current is not MochiState.TYPING
        ):
            self._bond_progress_overlay.update(self._bond_state)

    def _bond_dev_status_text(self) -> str:
        return (
            f"Lv. {self._bond_state.level}  ·  "
            f"{self._bond_state.xp}/{self._bond_state.xp_required} XP"
        )

    def _build_developer_menu(self):
        """Add focused care/bond QA controls to Mochi Lab."""
        popover = super()._build_developer_menu()
        card = self._developer_menu_content
        animated_rows = list(self._developer_menu_animated_rows)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        label = Gtk.Label(label="Bond testing")
        label.set_xalign(0)
        label.add_css_class("mochi-menu-section")
        card.append(label)

        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        status_row.add_css_class("mochi-setting-row")
        status_title = Gtk.Label(label="Current bond")
        status_title.set_xalign(0)
        status_title.set_hexpand(True)
        status_row.append(status_title)

        self._bond_dev_status_label = Gtk.Label(label=self._bond_dev_status_text())
        self._bond_dev_status_label.add_css_class("mochi-menu-value")
        status_row.append(self._bond_dev_status_label)
        card.append(status_row)
        animated_rows.append(status_row)

        award_button, _ = self._make_menu_button(
            "Award +1 XP",
            "list-add-symbolic",
            self._test_bond_award_one,
        )
        award_button.set_tooltip_text(
            "Awards one real bond XP and persists the updated bond state"
        )
        card.append(award_button)
        animated_rows.append(award_button)

        swarm_button, _ = self._make_menu_button(
            "Preview 60 XP swarm",
            "weather-clear-symbolic",
            self._test_bond_swarm,
        )
        swarm_button.set_tooltip_text(
            "Visual-only dense particle test; does not change saved bond XP"
        )
        card.append(swarm_button)
        animated_rows.append(swarm_button)

        card_button, _ = self._make_menu_button(
            "Preview level-up card",
            "emblem-favorite-symbolic",
            self._test_bond_level_up_card,
        )
        card_button.set_tooltip_text(
            "Visual-only preview of the next bond level celebration"
        )
        card.append(card_button)
        animated_rows.append(card_button)

        real_level_button, _ = self._make_menu_button(
            "Trigger real level-up",
            "go-up-symbolic",
            self._test_bond_real_level_up,
        )
        real_level_button.set_tooltip_text(
            "Moves to one XP before the next level, then awards the final XP"
        )
        card.append(real_level_button)
        animated_rows.append(real_level_button)

        reset_button, _ = self._make_menu_button(
            "Reset test bond",
            "edit-undo-symbolic",
            self._test_bond_reset,
        )
        reset_button.set_tooltip_text(
            "Resets saved bond progress to Level 1 with 0 XP"
        )
        card.append(reset_button)
        animated_rows.append(reset_button)

        self._developer_menu_animated_rows = tuple(animated_rows)
        return popover

    def _test_bond_award_one(self, _button=None) -> None:
        """Award one real XP for progress/persistence QA."""
        self._award_bond(1, persist=True)

    def _test_bond_swarm(self, _button=None) -> None:
        """Preview a feed-sized particle swarm without mutating bond progress."""
        self._bond_orbs.queue_xp_bounded(
            BOND_FEED_XP,
            max_outstanding=BOND_FEED_XP,
        )
        self._bond_orbs.show_gain_marker(BOND_FEED_XP)
        queue_draw = getattr(self, "queue_draw", None)
        if callable(queue_draw):
            queue_draw()

    def _test_bond_level_up_card(self, _button=None) -> None:
        """Preview the next-level celebration without changing saved progress."""
        preview_state = BondState(level=self._bond_state.level + 1, xp=0)
        self._begin_bond_level_up_presentation(
            preview_state,
            previous_level=self._bond_state.level,
        )

    def _test_bond_real_level_up(self, _button=None) -> None:
        """Cross a real level boundary with one XP so every hook is exercised."""
        near_level = BondState(
            level=self._bond_state.level,
            xp=max(0, self._bond_state.xp_required - 1),
        )
        self._set_bond_state_for_ui(near_level)
        self._persist_bond_state()
        self._award_bond(1, persist=True)

    def _test_bond_reset(self, _button=None) -> None:
        """Restore a predictable Level 1 baseline after developer testing."""
        self._set_bond_state_for_ui(BondState())
        self._persist_bond_state()
        if self._bond_progress_overlay is not None:
            self._bond_progress_overlay.dismiss()
        self._logger.info("Developer bond progress reset to Level 1")

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

    def _award_bond(
        self,
        amount: int,
        *,
        persist: bool = True,
        visual_orb_limit: int | None = None,
    ) -> BondAdvance:
        """Award bond XP while optionally capping only its visual orb backlog."""
        advance = self._bond_state.award(amount)
        if advance.xp_awarded <= 0:
            return advance

        previous_level = self._bond_state.level
        self._set_bond_state_for_ui(advance.state)
        self._bond_unsaved_xp += advance.xp_awarded
        if visual_orb_limit is None:
            self._bond_orbs.queue_xp(advance.xp_awarded)
        else:
            self._bond_orbs.queue_xp_bounded(
                advance.xp_awarded,
                max_outstanding=visual_orb_limit,
            )
        self._bond_orbs.show_gain_marker(advance.xp_awarded)
        if (
            self._bond_progress_overlay is not None
            and self.state.current is not MochiState.TYPING
        ):
            self._bond_progress_overlay.notify_xp_gain(
                self._bond_state,
                advance.xp_awarded,
            )
        queue_draw = getattr(self, "queue_draw", None)
        if callable(queue_draw):
            queue_draw()

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

    def _begin_bond_level_up_presentation(
        self,
        state: BondState,
        *,
        previous_level: int,
    ) -> None:
        overlay = self._bond_progress_overlay
        if overlay is None:
            return

        # Level-up is a presentation priority, not a behavior state. Typing,
        # eating, and other animation state can continue while speech yields.
        self.state.transition_presentation(PresentationState.LEVEL_UP)
        dismiss_dialogue = getattr(self, "_dismiss_presence_bubble", None)
        if callable(dismiss_dialogue):
            dismiss_dialogue(user_initiated=False)

        self._bond_orbs.trigger_level_up()
        overlay.show_level_up(state, previous_level=previous_level)

        queue_draw = getattr(self, "queue_draw", None)
        if callable(queue_draw):
            queue_draw()

    def _on_bond_level_up_finished(self) -> None:
        if self.state.presentation is PresentationState.LEVEL_UP:
            self.state.transition_presentation(PresentationState.NORMAL)

    def _on_bond_level_up(self, previous_level: int, new_level: int) -> None:
        """Celebrate clearly without taking over Mochi's behavior state."""
        self._logger.info("Bond level increased: %d -> %d", previous_level, new_level)
        self._begin_bond_level_up_presentation(
            self._bond_state,
            previous_level=previous_level,
        )

    def _on_feed_animation_completed(self) -> None:
        """A completed feed gives a visible one-time relationship boost."""
        # Establish the reason first so the +XP pulse and any level-up message
        # inherit the correct activity instead of flashing generic "bonding".
        self._show_bond_progress("sharing a snack")
        self._award_bond(
            BOND_FEED_XP,
            persist=True,
            visual_orb_limit=BOND_FEED_XP,
        )
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
        # Typing quips own the shared speech/nameplate area. Bond progression
        # stays ambient through orbs and floating XP markers, never the HUD.
        if (
            self._bond_progress_overlay is not None
            and not self._bond_progress_overlay.level_up_active
        ):
            self._bond_progress_overlay.dismiss()
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

    def _bond_orb_target(self, width: int, height: int) -> tuple[float, float]:
        """Aim XP at the visible center of Mochi instead of transparent padding."""
        frame = getattr(getattr(self, "player", None), "frame", None)
        atlas = getattr(self, "atlas", None)
        if frame is not None and atlas is not None and hasattr(atlas, "visible_bounds"):
            try:
                x, y, visible_width, visible_height = atlas.visible_bounds(
                    frame,
                    width,
                    height,
                )
                return (
                    x + visible_width * 0.50,
                    y + visible_height * 0.58,
                )
            except Exception:
                pass
        return (width * 0.50, height * 0.58)

    def _draw(self, area, context, width: int, height: int) -> None:
        """Paint Mochi normally, then render XP orbs in the same input surface."""
        super()._draw(area, context, width, height)
        if not self._bond_orbs.has_activity:
            return
        target_x, target_y = self._bond_orb_target(width, height)
        self._bond_orbs.draw(
            context,
            target_x=target_x,
            target_y=target_y,
            size=min(width, height),
        )

    def _tick(self) -> bool:
        """Advance XP particles on Mochi's existing 60-ish Hz animation tick."""
        result = super()._tick()
        if self._bond_orbs.has_activity:
            width = max(1, getattr(self, "get_width", lambda: 128)())
            height = max(1, getattr(self, "get_height", lambda: 128)())
            target_x, target_y = self._bond_orb_target(width, height)
            changed = self._bond_orbs.advance(
                getattr(self, "TICK_MS", 16) / 1000.0,
                width=width,
                height=height,
                target_x=target_x,
                target_y=target_y,
            )
            if changed:
                queue_draw = getattr(self, "queue_draw", None)
                if callable(queue_draw):
                    queue_draw()
        return result

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
