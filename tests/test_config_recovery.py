"""A damaged or unavailable settings file must not break desktop behavior."""
import json
from unittest.mock import patch

import pytest

from mochi.config import ConfigStore, Position


def assert_defaults(store):
    assert store.load_position() is None
    assert store.load_size() == 128
    assert store.load_volume() == 0.6
    assert not store.load_muted()
    assert not store.load_stay_put()
    assert not store.load_edge_roam()


@pytest.mark.parametrize('raw', [b'', b'{', b'null', b'[]', b'"text"', b'\xff'])
def test_bad_file_recovers_all_settings(tmp_path, raw):
    path = tmp_path / 'config.json'
    path.write_bytes(raw)
    assert_defaults(ConfigStore(path))


@pytest.mark.parametrize('value', [None, [], {}, True, 'bad', float('inf'), float('-inf'), float('nan')])
def test_bad_numeric_fields_preserve_valid_preferences(tmp_path, value):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(dict(x=value, y=12, size=value, volume=value,
                                   muted=True, stay_put=True, edge_roam=True)))
    store = ConfigStore(path)
    assert store.load_position() is None
    assert store.load_size() == 128
    assert store.load_volume() == 0.6
    assert store.load_muted() and store.load_stay_put() and store.load_edge_roam()


@pytest.mark.parametrize('value', [-10**400, 10**400])
def test_extreme_position_falls_back(tmp_path, value):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(dict(x=value, y=value)))
    assert ConfigStore(path).load_position() is None


def test_unreadable_config_logs_once_and_uses_defaults(tmp_path, caplog):
    store = ConfigStore(tmp_path / 'config.json')
    with patch('pathlib.Path.read_text', side_effect=PermissionError('denied')):
        assert_defaults(store)
        assert_defaults(store)
    assert len(caplog.records) == 1


def test_failed_replace_preserves_previous_config_and_allows_retry(tmp_path, caplog):
    store = ConfigStore(tmp_path / 'config.json')
    store.save_size(192)
    before = store.path.read_bytes()
    with patch('pathlib.Path.replace', side_effect=OSError('disk full')):
        store.save_position(Position(42, 73))
        store.save_position(Position(43, 74))
    assert store.path.read_bytes() == before
    assert len(caplog.records) == 1
    store.save_position(Position(44, 75))
    assert store.load_position() == Position(44, 75)
    assert store.load_size() == 192


def test_unwritable_directory_does_not_abort_settings_callbacks(tmp_path):
    store = ConfigStore(tmp_path / 'config.json')
    with patch('pathlib.Path.mkdir', side_effect=PermissionError('denied')):
        store.save_size(192)
        store.save_position(Position(42, 73))
        store.save_volume(0.4)
        store.save_muted(True)
        store.save_stay_put(True)
        store.save_edge_roam(True)


def test_reset_unavailable_path_does_not_prevent_launch(tmp_path):
    store = ConfigStore(tmp_path)  # A directory where the file should be.
    store.reset_position()
    assert_defaults(store)


def test_partial_settings_round_trip_and_reset(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('{"size": 999, "muted": "false", "x": 1}')
    store = ConfigStore(path)
    assert store.load_size() == 256
    assert not store.load_muted()
    assert store.load_position() is None
    store.save_position(Position(42, 73))
    store.save_volume(0.4)
    store.save_muted(True)
    store.save_stay_put(True)
    store.save_edge_roam(True)
    store = ConfigStore(path)
    store.reset_position()
    assert store.load_position() is None
    assert store.load_size() == 256
    assert store.load_volume() == 0.4
    assert store.load_muted() and store.load_stay_put() and store.load_edge_roam()
