"""Bounded project evidence and the port that collects it.

Repository inspection reports only facts supported by this snapshot. The
snapshot contains a shallow tree and selected metadata; it is never an
instruction source and it is never sent to a provider.
"""

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class ProjectFact:
    """A concise claim and the paths that support it."""

    name: str
    paths: tuple[str, ...]


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


class ProjectEvidenceReader(Protocol):
    """Port for collecting a safe, bounded snapshot of a project."""

    def collect(self, root: Path) -> ProjectEvidence:
        """Collect selected metadata and a shallow directory listing."""
        ...
