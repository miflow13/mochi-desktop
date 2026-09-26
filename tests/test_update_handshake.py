"""Startup-readiness handshake tests for transactional updates."""

from __future__ import annotations

import inspect
from pathlib import Path

from mochi.app import MochiApplication, signal_update_ready
from mochi.config import ConfigStore
from mochi.main import build_parser


def test_main_parser_accepts_internal_update_ready_file(tmp_path: Path) -> None:
    path = tmp_path / "ready"
    args = build_parser().parse_args(["--update-ready-file", str(path)])
    assert args.update_ready_file == path


def test_signal_update_ready_atomically_creates_marker(tmp_path: Path) -> None:
    ready = tmp_path / "nested" / "ready"
    signal_update_ready(ready)

    assert ready.read_text(encoding="utf-8") == "ready\n"
    assert not ready.with_suffix(".tmp").exists()


def test_application_constructor_does_not_signal_before_activation(
    tmp_path: Path,
) -> None:
    ready = tmp_path / "ready"
    app = MochiApplication(
        config=ConfigStore(tmp_path / "config.json"),
        preview_animations=True,
        update_ready_file=ready,
    )

    assert app.update_ready_file == ready
    assert not ready.exists()


def test_activation_signals_only_after_window_is_presented() -> None:
    source = inspect.getsource(MochiApplication.do_activate)

    assert source.index("window.present()") < source.index("signal_update_ready(")
