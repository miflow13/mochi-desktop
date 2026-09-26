"""User-facing command for checking and installing Mochi updates."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from mochi.config import ConfigStore
from mochi.update.bootstrap import bootstrap_updater
from mochi.update.checker import UpdateChecker
from mochi.update.model import UpdateStatus
from mochi.update.storage import InstallMetadataStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update Mochi safely.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="install an available update without asking for confirmation",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    checker: UpdateChecker | None = None,
    bootstrap: Callable[..., object] = bootstrap_updater,
    input_func: Callable[[str], str] = input,
) -> int:
    args = build_parser().parse_args(argv)
    selected_checker = checker or UpdateChecker(
        config=ConfigStore(),
        install_store=InstallMetadataStore(),
    )
    result = selected_checker.check(manual=True)

    if result.status is UpdateStatus.UP_TO_DATE:
        print("Mochi is already up to date. 🌱")
        return 0

    if result.status is UpdateStatus.CHECK_FAILED or result.target is None:
        detail = f" ({result.error})" if result.error else ""
        print(f"Mochi couldn't check for updates right now{detail}.")
        return 1

    target = result.target
    print(f"Mochi update available: {target.metadata.version}")
    for highlight in target.metadata.highlights:
        print(f"  • {highlight}")

    if not args.yes:
        answer = input_func("Update & restart Mochi? [y/N] ").strip().casefold()
        if answer not in {"y", "yes"}:
            print("Update skipped.")
            return 0

    bootstrap(target, gui=False, wait_pid=None)
    print("Mochi's updater has started. 🌱")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
