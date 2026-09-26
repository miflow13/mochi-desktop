"""External GUI updater orchestration tests."""

from __future__ import annotations

import inspect
from unittest.mock import Mock

from mochi.update.external import (
    ExternalUpdateApplication,
    apply_progress_to_window,
)
from mochi.update.worker import UpdateProgress, UpdateStage


def test_progress_mapper_uses_single_update_window_surface() -> None:
    window = Mock()

    apply_progress_to_window(
        window,
        UpdateProgress(UpdateStage.DOWNLOADING, "downloading", 5, 10),
    )
    window.show_progress.assert_called_once()

    window.reset_mock()
    apply_progress_to_window(
        window,
        UpdateProgress(UpdateStage.FAILED, "install failed"),
    )
    window.show_failure.assert_called_once()
    assert "install failed" in window.show_failure.call_args.args[1]

    window.reset_mock()
    apply_progress_to_window(
        window,
        UpdateProgress(UpdateStage.SUCCESS, "done"),
    )
    window.show_success.assert_called_once()


def test_external_app_marshals_worker_updates_onto_gtk_main_loop() -> None:
    source = inspect.getsource(ExternalUpdateApplication)
    assert "GLib.idle_add" in source
    assert "threading.Thread" in source
    assert "UpdateChecker" not in source


def test_external_app_passes_pre_resolved_target_directly_to_worker() -> None:
    source = inspect.getsource(ExternalUpdateApplication)
    assert "self.target" in source
    assert "worker.run(" in source
    assert "resolve_main_sha" not in source
