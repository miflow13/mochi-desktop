"""User-facing update discovery and notification controls for Mochi."""

from __future__ import annotations

import os
import threading

from gi.repository import GLib, Gtk

from mochi.update.bootstrap import bootstrap_updater
from mochi.update.checker import GitHubUpdateSource, UpdateChecker
from mochi.update.model import UpdateCheckResult, UpdateStatus, UpdateTarget
from mochi.update.storage import InstallMetadataStore
from mochi.update.window import UpdateWindow


UPDATE_STARTUP_DELAY_MS = 5_000
UPDATE_BUBBLE_TEXT = "psst... i learned some new things! 🌱"
UPDATE_BUBBLE_SECONDS = 4.0


class UpdateControlsMixin:
    """Add quiet update discovery without owning Mochi behavior state."""

    def __init__(self, *args, **kwargs) -> None:
        self._update_checker = None
        self._update_install_store = None
        self._update_target: UpdateTarget | None = None
        self._update_window: UpdateWindow | None = None
        self._update_menu_button = None
        self._update_menu_label = None
        self._update_startup_source_id: int | None = None
        self._update_callback_generation = 0
        self._update_shutting_down = False
        self._update_announced_commits: set[str] = set()
        super().__init__(*args, **kwargs)

        if self._preview_mode:
            return

        self._update_install_store = InstallMetadataStore()
        self._update_checker = UpdateChecker(
            config=self._config,
            install_store=self._update_install_store,
            source=GitHubUpdateSource(),
        )
        self._schedule_update_startup_check()

    def _build_context_menu(self):
        menu = super()._build_context_menu()
        button, self._update_menu_label = self._make_menu_button(
            "Check for updates",
            "software-update-available-symbolic",
            self._on_update_menu_clicked,
        )
        self._update_menu_button = button
        self._register_context_menu_row(
            "update",
            button,
            after="quick-start",
        )
        return menu

    def _schedule_update_startup_check(self) -> None:
        if self._preview_mode or self._update_shutting_down:
            return
        self._update_startup_source_id = GLib.timeout_add(
            UPDATE_STARTUP_DELAY_MS,
            self._run_scheduled_update_check,
        )

    def _run_scheduled_update_check(self) -> bool:
        self._update_startup_source_id = None
        self._start_update_check(manual=False)
        return False

    def _start_update_check(self, *, manual: bool) -> None:
        if self._update_shutting_down or self._update_checker is None:
            return

        generation = self._update_callback_generation
        checker = self._update_checker

        def check() -> None:
            result = checker.check(manual=manual)
            GLib.idle_add(
                self._apply_update_result_if_current,
                result,
                manual,
                generation,
            )

        threading.Thread(
            target=check,
            name="mochi-update-check",
            daemon=True,
        ).start()

    def _apply_update_result_if_current(
        self,
        result: UpdateCheckResult,
        manual: bool,
        generation: int,
    ) -> bool:
        if generation != self._update_callback_generation:
            return False
        return self._apply_update_check_result(result, manual=manual)

    def _apply_update_check_result(
        self,
        result: UpdateCheckResult,
        *,
        manual: bool,
    ) -> bool:
        if self._update_shutting_down:
            return False

        if result.status is UpdateStatus.UPDATE_AVAILABLE and result.target is not None:
            self._update_target = result.target
            if self._update_menu_label is not None:
                self._update_menu_label.set_text("Update available")

            if (
                result.announce
                and result.target.commit not in self._update_announced_commits
            ):
                self._update_announced_commits.add(result.target.commit)
                bubble = getattr(self, "_presence_bubble", None)
                if (
                    bubble is not None
                    and getattr(self.state, "dialogue_allowed", False)
                ):
                    bubble.show(
                        UPDATE_BUBBLE_TEXT,
                        duration_seconds=UPDATE_BUBBLE_SECONDS,
                    )

            if manual:
                self._show_update_window(result.target)
            return False

        if result.status is UpdateStatus.UP_TO_DATE:
            self._update_target = None
            if self._update_menu_label is not None:
                self._update_menu_label.set_text("Check for updates")
            if manual:
                window = self._get_update_window()
                window.show_success()
                window.present()
            return False

        if manual:
            window = self._get_update_window()
            window.show_failure(
                "Couldn’t check for updates.",
                result.error or "Update check failed without additional details.",
            )
            window.present()
        return False

    def _on_update_menu_clicked(self, _button=None) -> None:
        close_then = getattr(self, "_close_context_menu_then", None)
        if callable(close_then):
            close_then(self._handle_update_menu_action)
        else:
            self._handle_update_menu_action()

    def _handle_update_menu_action(self) -> None:
        if self._update_target is None:
            self._start_update_check(manual=True)
            return
        self._show_update_window(self._update_target)

    def _get_update_window(self) -> UpdateWindow:
        if self._update_window is None:
            self._update_window = UpdateWindow(
                on_later=self._dismiss_update_target,
                on_update_restart=self._begin_update_restart,
                on_retry=lambda: self._start_update_check(manual=True),
                on_close=self._destroy_update_window,
            )
            self._update_window.connect(
                "close-request",
                self._on_update_window_close_request,
            )
            if getattr(self, "_window", None) is not None:
                self._update_window.set_transient_for(self._window)
        return self._update_window

    def _on_update_window_close_request(self, _window: Gtk.Window) -> bool:
        self._destroy_update_window()
        return True

    def _show_update_window(self, target: UpdateTarget) -> None:
        window = self._get_update_window()
        installed = (
            self._update_install_store.load()
            if self._update_install_store is not None
            else None
        )
        window.show_available(installed, target)
        window.present()

    def _dismiss_update_target(self) -> None:
        target = self._update_target
        if target is not None:
            self._config.save_dismissed_update_commit(target.commit)
            self._update_announced_commits.add(target.commit)
        self._destroy_update_window()

    def _destroy_update_window(self) -> None:
        if self._update_window is not None:
            self._update_window.destroy()
            self._update_window = None

    def _begin_update_restart(self) -> None:
        target = self._update_target
        if target is None:
            return

        bootstrap_updater(
            target,
            gui=True,
            wait_pid=os.getpid(),
        )
        application = Gtk.Application.get_default()
        if application is not None:
            application.quit()

    def shutdown_presence(self) -> None:
        self._update_shutting_down = True
        self._update_callback_generation += 1

        source_id = self._update_startup_source_id
        self._update_startup_source_id = None
        if source_id is not None:
            GLib.source_remove(source_id)

        self._destroy_update_window()
        super().shutdown_presence()
