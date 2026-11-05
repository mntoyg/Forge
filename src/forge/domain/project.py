"""Bounded project evidence and the port that collects it.

Repository inspection reports only facts supported by this snapshot. The
snapshot contains a shallow tree and selected metadata; it is never an
instruction source and it is never sent to a provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProjectFile:
    """A selected, readable metadata file and its repository-relative path."""

    path: str
    content: str


@dataclass(frozen=True, slots=True)
class ProjectEvidence:
    """Bounded evidence collected from one selected project root."""

    root: Path
    files: tuple[ProjectFile, ...]
    file_paths: tuple[str, ...]
    directories: tuple[str, ...]
    entries_seen: int
    complete: bool
    omissions: tuple[str, ...] = ()
    structured_omissions: tuple[ProjectOmission, ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectFact:
    """A concise claim and the paths that support it."""

    name: str
    paths: tuple[str, ...]


class ProjectOmissionCode(StrEnum):
    """Stable categories for known gaps in bounded inspect evidence."""

    DIRECTORY_UNREADABLE = "directory_unreadable"
    ENTRY_LIMIT = "entry_limit"
    DEPTH_LIMIT = "depth_limit"
    PATH_UNINSPECTABLE = "path_uninspectable"
    METADATA_FILE_LIMIT = "metadata_file_limit"
    METADATA_BYTE_LIMIT = "metadata_byte_limit"
    METADATA_UNREADABLE = "metadata_unreadable"
    IGNORE_RULES_UNAVAILABLE = "ignore_rules_unavailable"
    IGNORE_RULES_BYTE_LIMIT = "ignore_rules_byte_limit"
    NO_SUPPORTED_METADATA = "no_supported_metadata"
    GIT_GLOBAL_EXCLUDES_NOT_CONSULTED = "git_global_excludes_not_consulted"


@dataclass(frozen=True, slots=True)
class ProjectOmission:
    """A structured omission with an optional workspace-relative path."""

    code: ProjectOmissionCode
    path: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectOverview:
    """The evidence-backed result rendered by ``forge inspect``."""

    root: Path
    guidance: tuple[str, ...]
    languages: tuple[ProjectFact, ...]
    tooling: tuple[ProjectFact, ...]
    checks: tuple[ProjectFact, ...]
    directories: tuple[str, ...]
    omissions: tuple[str, ...]
    scan_complete: bool
    """True when the bounded evidence scan completed within its declared scope."""
    structured_omissions: tuple[ProjectOmission, ...] = ()


class ProjectEvidenceReader(Protocol):
    """Port for collecting a safe, bounded snapshot of a project."""

    def collect(self, root: Path) -> ProjectEvidence:
        """Collect selected metadata and a shallow directory listing."""
        ...
