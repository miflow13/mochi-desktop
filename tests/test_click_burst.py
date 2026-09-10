from __future__ import annotations

from mochi.presence.clicks import ClickBurstDetector


def test_three_clicks_inside_window_trigger_once():
    detector = ClickBurstDetector(required_clicks=3, window_seconds=1.4)

    assert detector.record(now=0.0) is False
    assert detector.record(now=0.4) is False
    assert detector.record(now=0.8) is True
    assert detector.record(now=0.9) is False


def test_slow_clicks_do_not_form_a_burst():
    detector = ClickBurstDetector(required_clicks=3, window_seconds=1.4)

    assert detector.record(now=0.0) is False
    assert detector.record(now=1.0) is False
    assert detector.record(now=2.0) is False


def test_detector_resets_after_trigger():
    detector = ClickBurstDetector(required_clicks=3, window_seconds=1.4)

    for timestamp in (0.0, 0.2):
        assert detector.record(now=timestamp) is False
    assert detector.record(now=0.4) is True

    for timestamp in (1.0, 1.2):
        assert detector.record(now=timestamp) is False
    assert detector.record(now=1.4) is True
