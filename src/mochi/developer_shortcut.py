"""Privacy-safe bridge for Mochi's private developer-menu shortcut.

The GNOME Shell companion extension owns the global keybinding and reduces it to
the zero-payload ``DeveloperMenuRequested`` D-Bus signal. Mochi never receives
key identity, keycodes, modifier state, typed text, or window contents.
"""

from __future__ import annotations

from collections.abc import Callable
import logging


class GnomeShellDeveloperShortcutBackend:
    """Receive the semantic developer-menu request from GNOME Shell."""

    name = "GNOME Shell developer shortcut"
    BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    INTERFACE_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    SIGNAL_NAME = "DeveloperMenuRequested"

    def __init__(self) -> None:
        self._connection = None
        self._subscription_id: int | None = None
        self._on_requested: Callable[[], None] | None = None
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._connection is not None and self._subscription_id is not None

    @staticmethod
    def _load_gio():
        import gi

        from gi.repository import Gio

        return Gio

    def start(self, on_requested: Callable[[], None]) -> bool:
        if self.active:
            return True

        self.last_error = None
        try:
            Gio = self._load_gio()
            connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            if connection is None:
                self.last_error = "session D-Bus connection is unavailable"
                return False


            self._connection = connection
            self._on_requested = on_requested
            subscription_id = connection.signal_subscribe(
                self.BUS_NAME,
                self.INTERFACE_NAME,
                self.SIGNAL_NAME,
                self.OBJECT_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_signal,
            )
            if not subscription_id:
                self.last_error = "developer-menu signal subscription failed"
                self.stop()
                return False

            self._subscription_id = int(subscription_id)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

        return True

    def stop(self) -> None:
        if self._connection is not None and self._subscription_id is not None:
            try:
                self._connection.signal_unsubscribe(self._subscription_id)
            except Exception:
                pass

        self._subscription_id = None
        self._connection = None
        self._on_requested = None

    def _on_signal(self, *_ignored) -> None:
        # PRIVACY BOUNDARY: this is deliberately a zero-payload semantic event.
        callback = self._on_requested
        if callback is not None:
            callback()


class DeveloperShortcutMonitor:
    """Lifecycle wrapper for the private developer-menu shortcut bridge."""

    def __init__(
        self,
        *,
        on_requested: Callable[[], None],
        logger: logging.Logger | None = None,
        backend: GnomeShellDeveloperShortcutBackend | None = None,
    ) -> None:
        self._on_requested = on_requested
        self._logger = logger or logging.getLogger(__name__)
        self._backend = backend or GnomeShellDeveloperShortcutBackend()
        self.available = False

    @property
    def backend_name(self) -> str | None:
        return self._backend.name if self.available else None

    def start(self) -> bool:
        if self.available:
            return True

        self.available = self._backend.start(self._on_requested)
        if self.available:
            self._logger.info(
                "Developer shortcut enabled via %s",
                self._backend.name,
            )
        else:
            self._logger.debug(
                "Developer shortcut unavailable via %s: %s",
                self._backend.name,
                self._backend.last_error or "unknown error",
            )
        return self.available

    def stop(self) -> None:
        if not self.available:
            return
        self._backend.stop()
        self.available = False
