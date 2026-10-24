"""The immutable, local snapshot of a Git change set for review."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class ChangeKind(StrEnum):
    """Git's relevant change categories, independent of GitPython."""

    ADDED = "added"
    MODIFIED = "modified"
    RENAMED = "renamed"


class OmissionReason(StrEnum):
    """Why a changed path cannot be included in a current-source review."""

    DELETED = "deleted"
    SYMLINK = "symlink"
    BINARY = "binary"
    INVALID_TEXT = "invalid-text"
    IGNORED = "ignored-untracked"
    UNSUPPORTED = "unsupported-change"


@dataclass(frozen=True, slots=True)
class ReviewFile:
    """A changed current file and its validated working-tree snapshot."""

    path: Path
    content: str
    changed_lines: frozenset[int]
    kind: ChangeKind
    previous_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ChangeOmission:
    """A path in scope that this review cannot inspect as current source."""

    path: Path
    reason: OmissionReason
    previous_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ChangeSet:
    """A deterministic snapshot of eligible files and known omissions."""

    root: Path
    files: tuple[ReviewFile, ...]
    omissions: tuple[ChangeOmission, ...]


class ChangeSetReader(Protocol):
    """The port for collecting current changes without exposing Git details."""

    def read(self, paths: tuple[Path, ...] = ()) -> ChangeSet:
        """Return changed files narrowed to ``paths`` when supplied."""
        ...
