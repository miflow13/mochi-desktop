"""Wire the "Talk to Mochi" placeholder control into Buddy's lifecycle.

No new timers: pointer proximity, drag and menu suppression, and following a
walking Mochi piggyback on `_tick()`; cleanup happens in `shutdown_presence()`.
The control appears when the pointer comes close to the area under Mochi. Mochi
runs on XWayland and cannot see the pointer outside its own windows, so the
optional GNOME helper watches a zone for it (see ``pointer_proximity``). Without
a helper that supports this, hovering Mochi himself shows the control instead.
The control owns its own short-lived frame timer, which runs only while it is
fading, animating, or in its grace period. X11/XWayland only: on the
layer-shell path the control is not created.
"""

from __future__ import annotations

from mochi.pointer_proximity import PointerProximityMonitor
from mochi.state import MochiState

from .voice_control import VoiceControl


_SUPPRESSING_STATES = (MochiState.PICKUP, MochiState.DRAGGED, MochiState.DROPPING)
# Refresh the watched zone every few ticks (~100 ms at Buddy's ~60 Hz tick);
# it is only sent to the helper when it actually changed.
PROXIMITY_EVERY_TICKS = 6
# With no helper answering, look for one again every ~5 s instead.
PROXIMITY_RETRY_TICKS = 300


class VoiceControlMixin:
    def __init__(self, *args, **kwargs) -> None:
        self._voice_control: VoiceControl | None = None
        self._voice_proximity: PointerProximityMonitor | None = None
        self._voice_control_suppressed = False
        self._voice_proximity_countdown = 0
        super().__init__(*args, **kwargs)
        # Positioning uses X11 root coordinates; a layer-shell (native Wayland)
        # buddy has none, so the control would map detached from Mochi.
        if self._preview_mode or getattr(self._placement, "layer_shell_enabled", False):
            return
        self._voice_control = VoiceControl(
            owner=self._window,
            anchor_widget=self,
            on_activate=self._on_voice_control_activated,
            logger=self._logger,
        )
        self._voice_proximity = PointerProximityMonitor(
            on_near_changed=self._voice_control.set_pointer_near,
            logger=self._logger,
        )
        self._voice_proximity.start()

    def _voice_proximity_supported(self) -> bool:
        return self._voice_proximity is not None and self._voice_proximity.supported is True

    def _on_enter(self, controller, x: float, y: float) -> None:
        super()._on_enter(controller, x, y)
        if self._voice_control is not None and not self._voice_proximity_supported():
            self._voice_control.set_pet_hovered(True)

    def _on_leave(self, controller) -> None:
        super()._on_leave(controller)
        if self._voice_control is not None:
            self._voice_control.set_pet_hovered(False)

    def _tick(self) -> bool:
        result = super()._tick()
        control = self._voice_control
        if control is not None:
            suppressed = self.state.current in _SUPPRESSING_STATES or bool(
                getattr(self, "_context_menu_open", False)
            )
            if suppressed != self._voice_control_suppressed:
                self._voice_control_suppressed = suppressed
                control.set_suppressed(suppressed)
                if suppressed and self._voice_proximity is not None:
                    self._voice_proximity.set_zone(None, owner_width=1)
                    control.set_pointer_near(False)
            elif not suppressed:
                control.follow()
                unsupported = (
                    self._voice_proximity is not None
                    and self._voice_proximity.supported is False
                )
                self._voice_proximity_countdown -= 1
                if not unsupported:
                    # A helper that (re)appeared gets the fast cadence at once.
                    self._voice_proximity_countdown = min(
                        self._voice_proximity_countdown, PROXIMITY_EVERY_TICKS
                    )
                if self._voice_proximity_countdown <= 0:
                    self._voice_proximity_countdown = (
                        PROXIMITY_RETRY_TICKS if unsupported else PROXIMITY_EVERY_TICKS
                    )
                    self._push_voice_proximity_zone()
        return result

    def _push_voice_proximity_zone(self) -> None:
        """Tell the helper which zone to watch; it is sent only when it changes."""
        monitor = self._voice_proximity
        surface = self._window.get_surface()
        position = getattr(self._placement, "position", None)
        if monitor is None or surface is None or position is None:
            return
        # placement.position is in X11 device pixels; the zone is logical.
        scale = surface.get_scale() or 1.0
        zone = self._voice_control.proximity_zone(position.x / scale, position.y / scale)
        monitor.set_zone(zone, owner_width=self._window.get_width())

    def _on_voice_control_activated(self) -> None:
        self._start_voice_chat()

    def _start_voice_chat(self) -> None:
        """Seam for the planned voice feature; today it opens the placeholder."""
        if self._voice_control is not None:
            self._voice_control.toggle_placeholder()

    def shutdown_presence(self) -> None:
        if self._voice_proximity is not None:
            self._voice_proximity.stop()
            self._voice_proximity = None
        if self._voice_control is not None:
            self._voice_control.destroy()
            self._voice_control = None
        super().shutdown_presence()
