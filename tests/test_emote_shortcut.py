"""Regression coverage for the emote-catalogue global shortcut bridge."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.emote_shortcut import GnomeShellEmoteCatalogueShortcutBackend


def test_emote_shortcut_subscribes_to_zero_payload_semantic_signal() -> None:
    connection = SimpleNamespace(
        signal_subscribe=Mock(return_value=12),
        signal_unsubscribe=Mock(),
    )
    fake_gio = SimpleNamespace(
        BusType=SimpleNamespace(SESSION=1),
        DBusSignalFlags=SimpleNamespace(NONE=0),
        bus_get_sync=Mock(return_value=connection),
    )

    backend = GnomeShellEmoteCatalogueShortcutBackend()
    callback = Mock()

    with patch.object(backend, "_load_gio", return_value=fake_gio):
        assert backend.start(callback) is True

    args = connection.signal_subscribe.call_args.args
    assert args[0] == backend.BUS_NAME
    assert args[1] == backend.INTERFACE_NAME
    assert args[2] == "EmoteCatalogueRequested"
    assert args[3] == backend.OBJECT_PATH


def test_signal_invokes_only_requested_callback() -> None:
    backend = GnomeShellEmoteCatalogueShortcutBackend()
    callback = Mock()
    backend._on_requested = callback

    backend._on_signal(None, None, None, None, None, None)

    callback.assert_called_once_with()
