"""Wire the "Talk to Mochi" placeholder control into Buddy's lifecycle.

No new timers: hover comes from Buddy's existing motion controller, drag and
menu suppression plus following a walking Mochi piggyback on `_tick()`, and
cleanup on `shutdown_presence()`. The control owns its own short-lived frame
timer, which runs only while it is fading, animating, or in its grace period.
"""

from __future__ import annotations

from mochi.state import MochiState

from .voice_control import VoiceControl


_SUPPRESSING_STATES = (MochiState.PICKUP, MochiState.DRAGGED, MochiState.DROPPING)


class VoiceControlMixin:
    def __init__(self, *args, **kwargs) -> None:
        self._voice_control: VoiceControl | None = None
        self._voice_control_suppressed = False
        super().__init__(*args, **kwargs)
        if self._preview_mode:
            return
        self._voice_control = VoiceControl(
            owner=self._window,
            anchor_widget=self,
            on_activate=self._on_voice_control_activated,
            logger=self._logger,
        )

    def _on_enter(self, controller, x: float, y: float) -> None:
        super()._on_enter(controller, x, y)
        if self._voice_control is not None:
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
            elif not suppressed:
                control.follow()
        return result

    def _on_voice_control_activated(self) -> None:
        self._start_voice_chat()

    def _start_voice_chat(self) -> None:
        """Seam for the planned voice feature; today it opens the placeholder."""
        if self._voice_control is not None:
            self._voice_control.toggle_placeholder()

    def shutdown_presence(self) -> None:
        if self._voice_control is not None:
            self._voice_control.destroy()
            self._voice_control = None
        super().shutdown_presence()
