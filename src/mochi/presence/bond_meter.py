"""Persistent bond progression and its lightweight UI integration."""

from __future__ import annotations

from dataclasses import replace

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from mochi.animation import Animation, AnimationPlayer
from mochi.care import (
    BOND_FEED_XP,
    BOND_TYPING_XP_PER_SECOND,
    BondAdvance,
    BondState,
)
from mochi.bond_orbs import MAX_ACTIVE_ORBS, XpOrbField
from mochi.emotes import (
    EmoteDefinition,
    newly_unlocked_emotes,
    unlocked_idle_animation_names,
)
from mochi.focus import FocusPhase
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState, PresentationState

from .bond_progress_overlay import BondProgressOverlay


BOND_TYPING_TICK_SECONDS = 1
BOND_PERSIST_INTERVAL_XP = 15
BOND_FEED_HOLD_SECONDS = 2.4
BOND_FEED_VISUAL_ORB_LIMIT = MAX_ACTIVE_ORBS * 2
LEVEL_UP_DEFAULT_ANIMATION = "level_up_default"
EMOTE_UNLOCK_DEMO_DELAY_MS = 150
FOCUS_BOND_BAR_MIN_WIDTH_FRACTION = 0.34
FOCUS_BOND_BAR_MAX_WIDTH_FRACTION = 0.64
FOCUS_BOND_BAR_VISIBLE_WIDTH_FRACTION = 0.78
FOCUS_BOND_BAR_HEIGHT_FRACTION = 0.040
FOCUS_BOND_BAR_GAP_FRACTION = 0.028
FOCUS_BOND_LABEL_GAP_FRACTION = 0.012
FOCUS_BOND_LABEL_SIZE_FRACTION = 0.070
FOCUS_BOND_LABEL = "Bond XP"


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
        self._dev_unlock_all_emotes = False
        self._dev_unlock_all_label: Gtk.Label | None = None
        self._pending_emote_unlocks: list[EmoteDefinition] = []
        self._pending_emote_demo: EmoteDefinition | None = None
        self._bond_emote_demo_source_id: int | None = None
        self._pending_level_up_card: tuple[BondState, int] | None = None
        self._bond_presentation_player: AnimationPlayer | None = None
        self._bond_presentation_animation: str | None = None
        self._bond_presentation_stage: str | None = None
        super().__init__(*args, **kwargs)
        self._bond_presentation_player = AnimationPlayer(
            on_finished=self._on_bond_presentation_animation_finished,
        )
        self._restore_bond_state()

        window = getattr(self, "_window", None)
        if not getattr(self, "_preview_mode", False) and window is not None:
            self._bond_progress_overlay = BondProgressOverlay(
                owner=window,
                anchor_widget=self,
                logger=self._logger,
                on_level_up_finished=self._on_bond_level_up_finished,
                atlas=self.atlas,
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
            and not self._focus_bond_hint_active()
        ):
            self._bond_progress_overlay.update(self._bond_state)

    def _bond_dev_status_text(self) -> str:
        suffix = "  ·  EMOTES UNLOCKED (DEV)" if self._dev_unlock_all_emotes else ""
        return (
            f"Lv. {self._bond_state.level}  ·  "
            f"{self._bond_state.xp}/{self._bond_state.xp_required} XP"
            f"{suffix}"
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

        unlock_button, self._dev_unlock_all_label = self._make_menu_button(
            "Unlock all emotes",
            "changes-allow-symbolic",
            self._test_unlock_all_emotes,
        )
        unlock_button.set_tooltip_text(
            "Session-only QA override; does not change saved bond level or XP"
        )
        card.append(unlock_button)
        animated_rows.append(unlock_button)

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

    def _test_unlock_all_emotes(self, _button=None) -> None:
        """Toggle all available emotes for this developer session only."""
        self._dev_unlock_all_emotes = not self._dev_unlock_all_emotes
        if self._dev_unlock_all_label is not None:
            self._dev_unlock_all_label.set_text(
                "Restore bond locks"
                if self._dev_unlock_all_emotes
                else "Unlock all emotes"
            )
        if self._bond_dev_status_label is not None:
            self._bond_dev_status_label.set_text(self._bond_dev_status_text())
        refresh = getattr(self, "_refresh_emote_catalogue", None)
        if callable(refresh):
            refresh(force=True)
        self._logger.info(
            "Developer emote unlock override: %s",
            self._dev_unlock_all_emotes,
        )

    def _available_idle_emote_animations(self) -> tuple[str, ...]:
        return unlocked_idle_animation_names(
            self._bond_state,
            unlock_all=self._dev_unlock_all_emotes,
        )

    def _test_bond_reset(self, _button=None) -> None:
        """Restore a predictable Level 1 baseline after developer testing."""
        self._dev_unlock_all_emotes = False
        self._pending_emote_unlocks.clear()
        self._pending_emote_demo = None
        self._pending_level_up_card = None
        self._cancel_bond_emote_demo_timer()
        self._cancel_bond_presentation_animation()
        if self.state.presentation is not PresentationState.NORMAL:
            self.state.transition_presentation(PresentationState.NORMAL)
        if self._dev_unlock_all_label is not None:
            self._dev_unlock_all_label.set_text("Unlock all emotes")
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
        focus_hint_active = self._focus_bond_hint_active()
        if not focus_hint_active:
            self._bond_orbs.show_gain_marker(advance.xp_awarded)
        if (
            self._bond_progress_overlay is not None
            and self.state.current is not MochiState.TYPING
            and not focus_hint_active
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
        if self._focus_bond_hint_active():
            return
        overlay = self._bond_progress_overlay
        if overlay is not None:
            overlay.show_activity(self._bond_state, activity)

    def _level_up_animation_name(self, state: BondState) -> str:
        """Select the authored level-up animation for the reached bond level.

        FR-10 ships with one default celebration. Keeping selection behind this
        seam lets a future legendary level-up supersede it without changing the
        presentation pipeline.
        """
        _ = state
        return LEVEL_UP_DEFAULT_ANIMATION

    def _play_bond_presentation_animation(
        self,
        name: str,
        *,
        stage: str,
    ) -> bool:
        """Play one visual-only presentation pass without disturbing behavior."""
        player = self._bond_presentation_player
        animation = ANIMATIONS.get(name)
        if player is None or animation is None:
            self._logger.warning("Bond presentation animation unavailable: %s", name)
            return False
        if player.animation is not None:
            self._logger.warning(
                "Bond presentation animation already active: %s",
                self._bond_presentation_animation,
            )
            return False

        # Presentation demos are always one pass, even if a future unlocked
        # emote is normally authored as a loop.
        player.play(replace(animation, looping=False, next_state=None))
        self._bond_presentation_animation = name
        self._bond_presentation_stage = stage
        queue_draw = getattr(self, "queue_draw", None)
        if callable(queue_draw):
            queue_draw()
        return True

    def _cancel_bond_presentation_animation(self) -> None:
        player = self._bond_presentation_player
        if player is not None:
            player.stop()
        self._bond_presentation_animation = None
        self._bond_presentation_stage = None

    def _on_bond_presentation_animation_finished(
        self,
        finished_animation: Animation,
    ) -> None:
        """Advance FR-10 after a visual-only presentation animation finishes."""
        if finished_animation.name != self._bond_presentation_animation:
            self._logger.debug(
                "Ignoring stale bond presentation completion: %s",
                finished_animation.name,
            )
            return

        stage = self._bond_presentation_stage
        self._bond_presentation_animation = None
        self._bond_presentation_stage = None

        if stage == "level_up":
            self._show_pending_level_up_card()
        elif stage == "emote_demo":
            self._logger.debug(
                "Unlocked emote demonstration finished while card remains visible"
            )

    def _show_pending_level_up_card(self) -> None:
        pending = self._pending_level_up_card
        self._pending_level_up_card = None
        if pending is None:
            return

        state, previous_level = pending
        overlay = self._bond_progress_overlay
        if overlay is None:
            self._show_next_emote_unlock_or_finish()
            return
        overlay.show_level_up(state, previous_level=previous_level)

    def _cancel_bond_emote_demo_timer(self) -> None:
        source_id = self._bond_emote_demo_source_id
        self._bond_emote_demo_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

    def _start_pending_emote_demo(self) -> bool:
        self._bond_emote_demo_source_id = None
        emote = self._pending_emote_demo
        if (
            self.state.presentation is not PresentationState.EMOTE_UNLOCK
            or emote is None
            or emote.animation is None
        ):
            return GLib.SOURCE_REMOVE

        if self._play_bond_presentation_animation(
            emote.animation,
            stage="emote_demo",
        ):
            self._logger.info(
                "Demonstrating newly unlocked emote: %s",
                emote.label,
            )
        return GLib.SOURCE_REMOVE

    def _show_next_emote_unlock_or_finish(self) -> None:
        overlay = self._bond_progress_overlay
        if self._pending_emote_unlocks and overlay is not None:
            emote = self._pending_emote_unlocks.pop(0)
            self._pending_emote_demo = emote
            self.state.transition_presentation(PresentationState.EMOTE_UNLOCK)
            overlay.show_emote_unlock(emote)

            # Give the reward card a tiny anticipation beat before Mochi shows
            # what she learned. A dedicated "notice" transition can later reuse
            # this seam without changing the reward flow.
            self._cancel_bond_emote_demo_timer()
            self._bond_emote_demo_source_id = GLib.timeout_add(
                EMOTE_UNLOCK_DEMO_DELAY_MS,
                self._start_pending_emote_demo,
            )
            self._logger.info(
                "Emote unlocked: %s at bond level %d",
                emote.label,
                emote.required_bond_level,
            )
            return

        self._pending_emote_demo = None
        if self.state.presentation in (
            PresentationState.LEVEL_UP,
            PresentationState.EMOTE_UNLOCK,
        ):
            self.state.transition_presentation(PresentationState.NORMAL)

    def _begin_bond_level_up_presentation(
        self,
        state: BondState,
        *,
        previous_level: int,
    ) -> None:
        overlay = self._bond_progress_overlay
        if overlay is None:
            return

        # The presentation player draws over Mochi while the normal behavior
        # player continues underneath. Typing, eating, dragging, and ambient
        # state therefore resume naturally after the celebration.
        self.state.transition_presentation(PresentationState.LEVEL_UP)
        dismiss_dialogue = getattr(self, "_dismiss_presence_bubble", None)
        if callable(dismiss_dialogue):
            dismiss_dialogue(user_initiated=False)

        self._bond_orbs.trigger_level_up()
        self._pending_level_up_card = (
            BondState(level=state.level, xp=state.xp),
            previous_level,
        )
        animation_name = self._level_up_animation_name(state)
        if not self._play_bond_presentation_animation(
            animation_name,
            stage="level_up",
        ):
            self._show_pending_level_up_card()

        queue_draw = getattr(self, "queue_draw", None)
        if callable(queue_draw):
            queue_draw()

    def _on_bond_level_up_finished(self) -> None:
        if self.state.presentation is PresentationState.EMOTE_UNLOCK:
            # The unlock card and demonstration own the same presentation beat.
            # If a future emote ever outlives the card, stop it before moving on
            # so demonstrations never overlap consecutive rewards.
            self._cancel_bond_emote_demo_timer()
            if self._bond_presentation_stage == "emote_demo":
                self._cancel_bond_presentation_animation()
            self._pending_emote_demo = None

        self._show_next_emote_unlock_or_finish()

    def _on_bond_level_up(self, previous_level: int, new_level: int) -> None:
        """Celebrate the bond milestone, then reveal newly learned idle emotes."""
        self._logger.info("Bond level increased: %d -> %d", previous_level, new_level)
        play_level_up = getattr(getattr(self, "_sound", None), "play_level_up", None)
        if callable(play_level_up):
            play_level_up()
        self._pending_emote_unlocks.extend(
            newly_unlocked_emotes(
                previous_level,
                new_level,
                reveal_only=True,
            )
        )
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
            visual_orb_limit=BOND_FEED_VISUAL_ORB_LIMIT,
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
            and not self._bond_progress_overlay.presentation_active
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

    def _focus_bond_hint_active(self) -> bool:
        """Show the quiet XP hint only while focus time is actively earning XP."""
        session = getattr(self, "_focus_session", None)
        return bool(
            session is not None
            and session.active
            and session.phase is FocusPhase.FOCUS
            and not session.paused
            and self.state.presentation is PresentationState.NORMAL
        )

    def _focus_bond_bar_geometry(
        self,
        width: int,
        height: int,
    ) -> tuple[float, float, float, float]:
        """Place a thin bond bar immediately below Mochi's visible sprite."""
        size = float(max(1, min(width, height)))
        visible_x = 0.0
        visible_y = 0.0
        visible_width = float(width)
        visible_height = float(height)

        frame = getattr(getattr(self, "player", None), "frame", None)
        atlas = getattr(self, "atlas", None)
        if frame is not None and atlas is not None and hasattr(atlas, "visible_bounds"):
            try:
                (
                    visible_x,
                    visible_y,
                    visible_width,
                    visible_height,
                ) = atlas.visible_bounds(frame, width, height)
            except Exception:
                pass

        minimum_width = size * FOCUS_BOND_BAR_MIN_WIDTH_FRACTION
        maximum_width = size * FOCUS_BOND_BAR_MAX_WIDTH_FRACTION
        preferred_width = visible_width * FOCUS_BOND_BAR_VISIBLE_WIDTH_FRACTION
        bar_width = max(minimum_width, min(preferred_width, maximum_width))
        bar_height = max(5.0, size * FOCUS_BOND_BAR_HEIGHT_FRACTION)
        gap = max(4.0, size * FOCUS_BOND_BAR_GAP_FRACTION)
        label_size = max(7.0, min(11.0, size * FOCUS_BOND_LABEL_SIZE_FRACTION))
        label_gap = max(1.0, size * FOCUS_BOND_LABEL_GAP_FRACTION)

        center_x = visible_x + visible_width / 2.0
        x = max(2.0, min(center_x - bar_width / 2.0, width - bar_width - 2.0))

        preferred_y = (
            visible_y
            + visible_height
            + gap
            + label_size
            + label_gap
        )
        maximum_y = max(2.0, height - bar_height - 2.0)
        y = min(preferred_y, maximum_y)
        return (x, y, bar_width, bar_height)

    def _draw_focus_bond_hint(self, context, width: int, height: int) -> None:
        if not self._focus_bond_hint_active():
            return

        x, y, bar_width, bar_height = self._focus_bond_bar_geometry(width, height)
        fraction = max(0.0, min(1.0, self._bond_state.progress_fraction))
        size = float(max(1, min(width, height)))

        # Label the persistent relationship progress explicitly so this bar
        # cannot be mistaken for the focus-session countdown/progress.
        label_size = max(7.0, min(11.0, size * FOCUS_BOND_LABEL_SIZE_FRACTION))
        label_gap = max(1.0, size * FOCUS_BOND_LABEL_GAP_FRACTION)
        context.save()
        context.select_font_face("Sans")
        context.set_font_size(label_size)
        extents = context.text_extents(FOCUS_BOND_LABEL)
        if hasattr(extents, "width"):
            text_width = float(extents.width)
            x_bearing = float(getattr(extents, "x_bearing", 0.0))
        else:
            x_bearing = float(extents[0])
            text_width = float(extents[2])
        label_x = x + (bar_width - text_width) / 2.0 - x_bearing
        label_y = max(label_size, y - label_gap)
        context.set_source_rgba(0.78, 0.92, 0.80, 0.94)
        context.move_to(label_x, label_y)
        context.show_text(FOCUS_BOND_LABEL)
        context.restore()

        # Track: subtle enough to read as context, not a second HUD.
        context.set_source_rgba(0.05, 0.08, 0.06, 0.58)
        context.rectangle(x, y, bar_width, bar_height)
        context.fill()

        if fraction <= 0.0:
            return

        context.set_source_rgba(0.47, 0.79, 0.55, 0.96)
        context.rectangle(x, y, bar_width * fraction, bar_height)
        context.fill()

    def _bond_orb_target(self, width: int, height: int) -> tuple[float, float]:
        """Aim XP at the visible center of whichever Mochi frame is shown."""
        presentation_player = self._bond_presentation_player
        frame = (
            presentation_player.frame
            if presentation_player is not None and presentation_player.frame is not None
            else getattr(getattr(self, "player", None), "frame", None)
        )
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
        """Paint the presentation pass when active, then render XP orbs."""
        presentation_player = self._bond_presentation_player
        presentation_frame = (
            presentation_player.frame
            if presentation_player is not None
            else None
        )
        if presentation_frame is None:
            super()._draw(area, context, width, height)
        else:
            self.atlas.draw(context, presentation_frame, width, height)

        self._draw_focus_bond_hint(context, width, height)

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
        """Advance behavior, presentation animation, and XP feedback together."""
        result = super()._tick()
        elapsed_ms = max(
            1,
            int(getattr(self, "_frame_elapsed_ms", getattr(self, "TICK_MS", 16))),
        )
        needs_redraw = False
        presentation_player = self._bond_presentation_player
        if (
            presentation_player is not None
            and presentation_player.animation is not None
            and presentation_player.tick(elapsed_ms)
        ):
            needs_redraw = True

        focus_hint_active = self._focus_bond_hint_active()
        overlay = self._bond_progress_overlay
        if (
            focus_hint_active
            and overlay is not None
            and overlay.active
            and not overlay.presentation_active
        ):
            overlay.dismiss()

        if self._bond_orbs.has_activity:
            width = max(1, getattr(self, "get_width", lambda: 128)())
            height = max(1, getattr(self, "get_height", lambda: 128)())
            target_x, target_y = self._bond_orb_target(width, height)
            changed = self._bond_orbs.advance(
                elapsed_ms / 1000.0,
                width=width,
                height=height,
                target_x=target_x,
                target_y=target_y,
            )
            if changed:
                needs_redraw = True
        if needs_redraw:
            queue_draw = getattr(self, "queue_draw", None)
            if callable(queue_draw):
                queue_draw()
        return result

    def shutdown_presence(self) -> None:
        """Flush earned XP and tear down the visual-only progress surface."""
        self._cancel_bond_emote_demo_timer()
        self._cancel_bond_presentation_animation()
        self._pending_level_up_card = None
        self._pending_emote_unlocks.clear()
        self._pending_emote_demo = None
        source_id = self._bond_typing_source_id
        self._bond_typing_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass
        if self._bond_unsaved_xp > 0:
            self._persist_bond_state()
        overlay = self._bond_progress_overlay
        self._bond_progress_overlay = None
        if overlay is not None:
            # Clear our reference before destroy: destroy may synchronously
            # report a finished card, and that callback must not enqueue the
            # next reward against a surface that is being torn down.
            overlay.destroy()
        if self.state.presentation in (
            PresentationState.LEVEL_UP,
            PresentationState.EMOTE_UNLOCK,
        ):
            self.state.transition_presentation(PresentationState.NORMAL)
        super().shutdown_presence()
