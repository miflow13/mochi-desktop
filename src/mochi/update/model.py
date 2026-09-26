"""Small immutable data types shared by Mochi's update flow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UpdateStatus(Enum):
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    CHECK_FAILED = "check_failed"


@dataclass(frozen=True)
class UpdateMetadata:
    version: str
    channel: str
    highlights: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        cleaned: list[str] = []
        for value in self.highlights:
            text = str(value).strip()
            if text:
                cleaned.append(text)
            if len(cleaned) == 3:
                break
        object.__setattr__(self, "highlights", tuple(cleaned))


@dataclass(frozen=True)
class InstalledBuild:
    version: str
    commit: str | None
    channel: str
    installed_at: str


@dataclass(frozen=True)
class UpdateTarget:
    commit: str
    metadata: UpdateMetadata


@dataclass(frozen=True)
class UpdateCheckResult:
    status: UpdateStatus
    target: UpdateTarget | None = None
    error: str | None = None
    announce: bool = False
