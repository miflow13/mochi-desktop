"""First-run guidance when GNOME has not loaded Mochi's helper yet."""

from __future__ import annotations

from gi.repository import GLib


class GnomeHelperSetupReminderMixin:
    """Make the one-time GNOME session reload hard to miss.

    The helper lifecycle itself remains owned by PresenceBuddyMixin. This mixin
    only presents first-run guidance when that lifecycle has never observed the
    helper in the current Mochi process.
    """

    HELPER_SETUP_REMINDER_DELAY_MS = 1_250
    HELPER_SETUP_REMINDER_RETRY_MS = 1_500
    HELPER_SETUP_REMINDER_SECONDS = 12.0
    HELPER_SETUP_MESSAGE = (
        "One-time setup needed 🌱\n"
        "Log out and back in once to enable typing, app, file, and YouTube awareness."
    )

    def __init__(self, *args, **kwargs) -> None:
        self._gnome_helper_seen_available = False
        self._gnome_helper_reminder_source_id: int | None = None
        self._gnome_helper_reminder_shown = False
        self._gnome_helper_suppressed_startup_greeting = False
        super().__init__(*args, **kwargs)

        if self._preview_mode:
            return

        helper = getattr(self, "_gnome_helper_lifecycle", None)
        if helper is not None and not helper.available:
            self._schedule_gnome_helper_setup_reminder()

    def _on_gnome_helper_available(self) -> None:
        super()._on_gnome_helper_available()
        self._gnome_helper_seen_available = True
        self._cancel_gnome_helper_setup_reminder()

        # If the helper appeared before the setup notice was ever shown, restore
        # the normal startup greeting that the notice temporarily displaced.
        if (
            self._gnome_helper_suppressed_startup_greeting
            and not self._gnome_helper_reminder_shown
            and not self._presence_shutting_down
            and self._presence_startup_source_id is None
        ):
            self._gnome_helper_suppressed_startup_greeting = False
            self._presence_startup_source_id = GLib.timeout_add(
                500,
                self._show_startup_greeting,
            )

    def _on_gnome_helper_unavailable(self) -> None:
        super()._on_gnome_helper_unavailable()

        # A helper that disappears after working is a runtime disconnect, not a
        # first-install condition. Do not tell an established user to log out.
        if not self._gnome_helper_seen_available:
            self._schedule_gnome_helper_setup_reminder()

    def _schedule_gnome_helper_setup_reminder(self) -> None:
        if (
            self._preview_mode
            or self._presence_shutting_down
            or self._gnome_helper_seen_available
            or self._gnome_helper_reminder_shown
            or self._gnome_helper_reminder_source_id is not None
        ):
            return

        # Setup guidance outranks the friendly startup greeting. Otherwise the
        # greeting can occupy the single speech bubble and hide the important
        # first-run instruction.
        startup_source = self._presence_startup_source_id
        if startup_source is not None:
            try:
                GLib.source_remove(startup_source)
            except Exception:
                pass
            self._presence_startup_source_id = None
            self._gnome_helper_suppressed_startup_greeting = True

        self._gnome_helper_reminder_source_id = GLib.timeout_add(
            self.HELPER_SETUP_REMINDER_DELAY_MS,
            self._show_gnome_helper_setup_reminder,
        )

    def _show_gnome_helper_setup_reminder(self) -> bool:
        self._gnome_helper_reminder_source_id = None

        helper = getattr(self, "_gnome_helper_lifecycle", None)
        if (
            self._preview_mode
            or self._presence_shutting_down
            or self._gnome_helper_seen_available
            or (helper is not None and helper.available)
        ):
            return GLib.SOURCE_REMOVE

        bubble = self._presence_bubble
        if bubble is None:
            return GLib.SOURCE_REMOVE

        if bubble.show(
            self.HELPER_SETUP_MESSAGE,
            duration_seconds=self.HELPER_SETUP_REMINDER_SECONDS,
        ):
            self._gnome_helper_reminder_shown = True
            self._logger.info(
                "GNOME helper setup pending; showing one-time logout/login reminder"
            )
            return GLib.SOURCE_REMOVE

        # Another direct interaction may temporarily own the speech bubble.
        # Retry until the setup notice has had one clear chance to be seen.
        self._gnome_helper_reminder_source_id = GLib.timeout_add(
            self.HELPER_SETUP_REMINDER_RETRY_MS,
            self._show_gnome_helper_setup_reminder,
        )
        return GLib.SOURCE_REMOVE

    def _cancel_gnome_helper_setup_reminder(self) -> None:
        source_id = self._gnome_helper_reminder_source_id
        self._gnome_helper_reminder_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

    def _shutdown_presence(self) -> None:
        self._cancel_gnome_helper_setup_reminder()
        super()._shutdown_presence()
