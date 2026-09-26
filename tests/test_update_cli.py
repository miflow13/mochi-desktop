"""Command-line updater behavior tests."""

from __future__ import annotations

from pathlib import Path

from mochi.update.model import (
    UpdateCheckResult,
    UpdateMetadata,
    UpdateStatus,
    UpdateTarget,
)
from mochi import update_cli


class _Checker:
    def __init__(self, result: UpdateCheckResult) -> None:
        self.result = result
        self.calls = []

    def check(self, *, manual: bool, now=None):
        self.calls.append(manual)
        return self.result


def _target() -> UpdateTarget:
    return UpdateTarget(
        commit="abc123",
        metadata=UpdateMetadata(
            version="0.4.0a1",
            channel="main",
            highlights=("Better roaming", "More personality"),
        ),
    )


def test_cli_up_to_date_returns_zero_without_bootstrap(capsys) -> None:
    checker = _Checker(UpdateCheckResult(status=UpdateStatus.UP_TO_DATE))
    calls = []

    result = update_cli.main(
        [],
        checker=checker,
        bootstrap=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert result == 0
    assert calls == []
    assert checker.calls == [True]
    assert "already up to date" in capsys.readouterr().out.lower()


def test_cli_decline_returns_zero_without_bootstrap(capsys) -> None:
    target = _target()
    checker = _Checker(
        UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            target=target,
            announce=True,
        )
    )
    calls = []

    result = update_cli.main(
        [],
        checker=checker,
        bootstrap=lambda *args, **kwargs: calls.append((args, kwargs)),
        input_func=lambda _prompt: "n",
    )

    assert result == 0
    assert calls == []
    output = capsys.readouterr().out
    assert "Better roaming" in output
    assert "More personality" in output


def test_cli_yes_bootstraps_exact_target_without_prompt() -> None:
    target = _target()
    checker = _Checker(
        UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            target=target,
            announce=True,
        )
    )
    calls = []

    result = update_cli.main(
        ["--yes"],
        checker=checker,
        bootstrap=lambda *args, **kwargs: calls.append((args, kwargs)),
        input_func=lambda _prompt: (_ for _ in ()).throw(AssertionError("prompted")),
    )

    assert result == 0
    assert calls == [((target,), {"gui": False, "wait_pid": None})]


def test_cli_check_failure_is_friendly_and_nonzero(capsys) -> None:
    checker = _Checker(
        UpdateCheckResult(
            status=UpdateStatus.CHECK_FAILED,
            error="offline",
        )
    )

    result = update_cli.main([], checker=checker)

    assert result == 1
    output = capsys.readouterr().out.lower()
    assert "couldn't check" in output
    assert "offline" in output
