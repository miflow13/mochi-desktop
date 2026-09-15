"""Privacy-preserving user presence events for Mochi.

The optional GNOME Shell companion extension emits zero-payload ``UserIdle``
and ``UserActive`` signals derived from Mutter's server-global idle monitor.
Mochi receives only those semantic state transitions; no key, pointer, window,
or application details cross the D-Bus boundary.
"""

from __future__ import annotations

from collections.abc import Callable
import logging

from mochi.helper_connection import HelperConnection


class GnomeShellPresenceBackend:
    """Receive semantic idle/active transitions from the Mochi Shell extension."""

    name = "GNOME Shell user presence"
    BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    INTERFACE_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    IDLE_SIGNAL_NAME = "UserIdle"
    ACTIVE_SIGNAL_NAME = "UserActive"

    def __init__(self) -> None:
        self._helper = None
        self.last_error = None
        self._on_user_idle = None
        self._on_user_active = None

    @property
    def active(self) -> bool:
        return self._helper is not None and self._helper.active

    @staticmethod
    def _load_gio():
        import gi

        from gi.repository import Gio, GLib

        return Gio, GLib

    def start(
        self, on_user_idle: Callable[[], None], on_user_active: Callable[[], None]
    ) -> bool:
        if self._helper is not None:
            return True
        self._on_user_idle = on_user_idle
        self._on_user_active = on_user_active
        self._helper = HelperConnection(
            self._load_gio,
            {
                self.IDLE_SIGNAL_NAME: self._on_idle_signal,
                self.ACTIVE_SIGNAL_NAME: self._on_active_signal,
            },
            on_state=lambda state: (
                self._on_idle_signal() if state[0] else self._on_active_signal()
            ),
            on_lost=self._on_active_signal,
        )
        if self._helper.start():
            self.last_error = None
            return True
        self.last_error = self._helper.last_error
        self.stop()
        return False

    def stop(self) -> None:
        if self._helper is not None:
            self._helper.stop()
            self._helper = None
        self._on_user_idle = None
        self._on_user_active = None

    def _on_idle_signal(self, *_ignored) -> None:
        # PRIVACY BOUNDARY: the signal is zero-payload. Ignore all Gio callback
        # bookkeeping arguments and expose only the semantic presence event.
        callback = self._on_user_idle
        if callback is not None:
            callback()

    def _on_active_signal(self, *_ignored) -> None:
        callback = self._on_user_active
        if callback is not None:
            callback()


class PresenceActivityMonitor:
    """Small lifecycle wrapper around the GNOME Shell presence backend."""

    def __init__(
        self,
        *,
        on_user_idle: Callable[[], None],
        on_user_active: Callable[[], None],
        logger: logging.Logger | None = None,
        backend: GnomeShellPresenceBackend | None = None,
    ) -> None:
        self._on_user_idle = on_user_idle
        self._on_user_active = on_user_active
        self._logger = logger or logging.getLogger(__name__)
        self._backend = backend or GnomeShellPresenceBackend()
        self.available = False

    @property
    def backend_name(self) -> str | None:
        return self._backend.name if self.available else None

    def start(self) -> bool:
        if self.available:
            return True

        self.available = self._backend.start(
            self._on_user_idle,
            self._on_user_active,
        )
        if self.available:
            self._logger.info(
                "Presence awareness enabled via %s",
                self._backend.name,
            )
        else:
            self._logger.debug(
                "Presence awareness unavailable via %s: %s",
                self._backend.name,
                self._backend.last_error or "unknown error",
            )
        return self.available

    def stop(self) -> None:
        if not self.available:
            return
        self._backend.stop()
        self.available = False
