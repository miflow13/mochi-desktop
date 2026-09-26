"""Standalone GTK application that presents the external Mochi updater."""

from __future__ import annotations

import threading
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from .model import UpdateTarget
from .window import UpdateWindow
from .worker import UpdateProgress, UpdateStage, UpdateWorker


_PRE_SWAP_STAGES = frozenset(
    (
        UpdateStage.DOWNLOADING,
        UpdateStage.VERIFYING,
    )
)
_CRITICAL_STAGES = frozenset(
    (
        UpdateStage.SWAPPING,
        UpdateStage.INSTALLING,
        UpdateStage.REFRESHING,
        UpdateStage.RESTARTING,
    )
)


def apply_progress_to_window(window: UpdateWindow, progress: UpdateProgress) -> None:
    """Render one worker progress event onto the shared updater window."""
    if progress.stage is UpdateStage.FAILED:
        window.show_failure(
            "The update couldn’t be installed.",
            progress.message,
        )
    elif progress.stage is UpdateStage.SUCCESS:
        window.show_success()
    else:
        window.show_progress(progress)


class ExternalUpdateApplication(Gtk.Application):
    """Run UpdateWorker off-thread while GTK stays on its main loop."""

    def __init__(
        self,
        target: UpdateTarget,
        *,
        wait_pid: int | None,
        worker_factory: Callable[[], UpdateWorker] = UpdateWorker,
        window_factory: Callable[..., UpdateWindow] = UpdateWindow,
    ) -> None:
        super().__init__(
            application_id="io.github.mochi_desktop.Mochi.Updater",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.target = target
        self.wait_pid = wait_pid
        self._worker_factory = worker_factory
        self._window_factory = window_factory
        self._window: UpdateWindow | None = None
        self._cancel_event = threading.Event()
        self._current_stage = UpdateStage.DOWNLOADING
        self._worker_active = False
        self._closing_after_cancel = False

    def do_activate(self) -> None:
        if self._window is None:
            self._window = self._window_factory(
                on_later=lambda: None,
                on_update_restart=lambda: None,
                on_retry=self._retry,
                on_close=self._request_close,
                on_cancel=self._request_cancel,
            )
            self._window.set_application(self)
            self._window.connect("close-request", self._on_close_request)

        self._window.show_progress(
            UpdateProgress(
                UpdateStage.DOWNLOADING,
                "Preparing Mochi’s update…",
            )
        )
        self._window.present()
        if not self._worker_active:
            self._start_worker()

    def _start_worker(self) -> None:
        self._cancel_event.clear()
        self._closing_after_cancel = False
        self._worker_active = True
        threading.Thread(
            target=self._run_worker,
            name="mochi-external-updater",
            daemon=True,
        ).start()

    def _run_worker(self) -> None:
        worker = self._worker_factory()
        result = worker.run(
            self.target,
            wait_pid=self.wait_pid,
            on_progress=self._queue_progress,
            cancel_event=self._cancel_event,
        )
        GLib.idle_add(self._finish_worker, result)

    def _queue_progress(self, progress: UpdateProgress) -> None:
        GLib.idle_add(self._apply_progress, progress)

    def _apply_progress(self, progress: UpdateProgress) -> bool:
        self._current_stage = progress.stage
        if self._window is not None:
            apply_progress_to_window(self._window, progress)
        return False

    def _finish_worker(self, result: int) -> bool:
        self._worker_active = False

        if result == 0:
            if self._window is not None:
                self._window.show_success()
            GLib.timeout_add(700, self._quit_after_success)
            return False

        if result == 130 and self._cancel_event.is_set():
            self.quit()
            return False

        if self._window is not None and self._window.state_name != "failure":
            self._window.show_failure(
                "The update couldn’t be installed.",
                f"Updater exited with status {result}.",
            )
        return False

    def _quit_after_success(self) -> bool:
        self.quit()
        return False

    def _request_cancel(self) -> None:
        if self._worker_active and self._current_stage in _PRE_SWAP_STAGES:
            self._cancel_event.set()

    def _request_close(self) -> None:
        if self._worker_active:
            if self._current_stage in _CRITICAL_STAGES:
                return
            self._closing_after_cancel = True
            self._cancel_event.set()
            if self._window is not None:
                self._window.hide()
            return
        self.quit()

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        self._request_close()
        return True

    def _retry(self) -> None:
        if self._worker_active:
            return
        if self._window is not None:
            self._window.show_progress(
                UpdateProgress(
                    UpdateStage.DOWNLOADING,
                    "Getting the newest Mochi…",
                )
            )
        self._start_worker()


def run_external_update(target: UpdateTarget, *, wait_pid: int | None) -> int:
    """Run the polished updater UI for one already-resolved update target."""
    application = ExternalUpdateApplication(target, wait_pid=wait_pid)
    return int(application.run([]))
