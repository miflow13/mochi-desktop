"""Shutdown must release core resources, including already queued UI actions."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.buddy import Buddy
from mochi.menu_window import MenuWindow
from mochi.presence.bubble import SpeechBubble
from mochi.presence.integration import PresenceBuddyMixin


def test_core_shutdown_removes_sources_and_stops_monitors_once():
    monitors = {name: Mock() for name in (
        '_typing_monitor', '_presence_monitor', '_media_monitor',
        '_file_activity_monitor', '_developer_shortcut_monitor')}
    sources = dict(zip((
        '_tick_source_id', '_idle_action_source_id', '_blink_source_id',
        '_computer_idle_source_id', '_hover_heart_source_id'), range(1, 6)))
    buddy = SimpleNamespace(
        **monitors, **sources, _shutting_down=False, _menu_animation_serial=1,
        _pending_context_action=Mock(), _pending_developer_action=Mock(),
        player=Mock(), _context_menu=Mock(), _developer_menu=Mock())
    with patch('mochi.buddy.GLib.source_remove') as remove:
        Buddy.shutdown(buddy)
        Buddy.shutdown(buddy)
    assert [call.args[0] for call in remove.call_args_list] == list(range(1, 6))
    for name, monitor in monitors.items():
        monitor.stop.assert_called_once()
        assert getattr(buddy, name) is None
    assert all(getattr(buddy, name) is None for name in sources)
    buddy.player.stop.assert_called_once()
    buddy._context_menu.destroy.assert_called_once()
    buddy._developer_menu.destroy.assert_called_once()
    assert buddy._pending_context_action is None
    assert buddy._pending_developer_action is None
    assert buddy._menu_animation_serial == 2


def test_queued_actions_cannot_run_after_shutdown():
    action = Mock()
    buddy = SimpleNamespace(_shutting_down=True, _presence_shutting_down=True)
    assert not Buddy._dispatch_context_action(buddy, action)
    assert not PresenceBuddyMixin._dispatch_presence_developer_action(buddy, action)
    action.assert_not_called()


def test_menu_destroy_invalidates_delayed_popup_callbacks():
    menu = SimpleNamespace(_position_serial=3, _dismiss_armed=True,
                           _stop_following_owner=Mock(), window=Mock())
    MenuWindow.destroy(menu)
    assert menu._position_serial == 4
    assert not menu._dismiss_armed
    menu._stop_following_owner.assert_called_once()
    menu.window.destroy.assert_called_once()


def test_speech_destroy_cancels_animation_and_releases_both_surfaces():
    bubble = SimpleNamespace(hide=Mock(), _window=Mock(), _popover=Mock())
    SpeechBubble.destroy(bubble)
    bubble.hide.assert_called_once()
    bubble._window.destroy.assert_called_once()
    bubble._popover.unparent.assert_called_once()
