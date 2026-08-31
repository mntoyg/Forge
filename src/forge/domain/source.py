"""Source files, findings, and the port for reading them.

These are the types `forge debug` is built out of. Like everything else in the
domain they perform no I/O: a :class:`SourceFile` is content that has already
been read, and :class:`SourceReader` is the promise that somebody else will do
the reading.

The vocabulary here is deliberately small. A finding is a claim about a piece
of code, made by something that can be wrong - so it carries how serious it
would be if true (:class:`Severity`) *and* how sure the claim is
(:class:`Confidence`). Collapsing those two into one number would hide exactly
the distinction a reader needs.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from forge.domain.ai import TokenUsage


class Severity(StrEnum):
    """How much it matters if the finding is correct.

    Three levels, not five. A model applies a small scale consistently and a
    large one arbitrarily, and a scale nobody trusts is worse than none.
    """

    HIGH = "high"
    """Fails at runtime, loses data, or exposes something it should not."""

    MEDIUM = "medium"
    """Wrong under conditions that will occur, or a latent bug."""

    LOW = "low"
    """Clarity, maintainability, or a risk needing unusual conditions."""


class Confidence(StrEnum):
    """How sure the claim is.

    Separate vocabulary from :class:`Severity` on purpose: two scales sharing
    the words high/medium/low would be misread constantly, in the output and
    in the prompt.
    """

    CERTAIN = "certain"
    """Provable from the code alone."""

    LIKELY = "likely"
    """Very probably true, but depends on how the code is called."""

    POSSIBLE = "possible"
    """Worth a look; may be intentional."""


@dataclass(frozen=True, slots=True)
class Location:
    """Where in the file a finding points.

    Raises:
        ValueError: the line number is not a real line.
    """

    line: int

    def __post_init__(self) -> None:
        if self.line < 1:
            raise ValueError(f"Line numbers start at 1, got {self.line}.")


@dataclass(frozen=True, slots=True)
class Finding:
    """One claim about the analysed file.

    ``location`` is optional because some real findings genuinely have no
    single line - "this module has no error handling anywhere" is useful and
    unlocatable. Inventing a line for it would be worse than admitting there
    is none.

    Raises:
        ValueError: the finding says nothing usable.
    """

    summary: str
    detail: str
    severity: Severity
    confidence: Confidence
    location: Location | None = None

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("A finding must have a summary.")
        if not self.detail.strip():
            raise ValueError("A finding must explain itself.")


@dataclass(frozen=True, slots=True)
class SourceFile:
    """A file that has been read, and is worth analysing.

    Raises:
        ValueError: there is nothing here to analyse.
    """

    path: Path
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError(f"{self.path} is empty; there is nothing to analyse.")

    @property
    def line_count(self) -> int:
        return len(self.content.splitlines())

    def numbered(self) -> str:
        """Render the content with line numbers, for the prompt.

        The model cannot cite a line it was never shown. Numbering here rather
        than in the prompt builder keeps the numbering and ``line_count`` - the
        two things a location is validated against - in one place.
        """
        return "\n".join(
            f"{number:>4} | {line}"
            for number, line in enumerate(self.content.splitlines(), start=1)
        )


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Everything one `forge debug` run produced.

    Carries the model and the token usage because the user paid for both, and
    because "which model said this" is the first question asked about a
    surprising finding.
    """

    source_path: Path
    findings: tuple[Finding, ...]
    model: str
    usage: TokenUsage

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    def by_severity(self) -> tuple[Finding, ...]:
        """Findings ordered most serious first, then most confident first.

        Reading order is a product decision, not a rendering detail: whatever
        appears first is what a hurried reader acts on.
        """
        severity_rank = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        confidence_rank = {
            Confidence.CERTAIN: 0,
            Confidence.LIKELY: 1,
            Confidence.POSSIBLE: 2,
        }
        return tuple(
            sorted(
                self.findings,
                key=lambda f: (
                    severity_rank[f.severity],
                    confidence_rank[f.confidence],
                    f.location.line if f.location else 0,
                ),
            )
        )


class SourceReader(Protocol):
    """The port for getting a :class:`SourceFile` from somewhere.

    Every implementation is responsible for refusing what it must not read -
    a path outside the workspace, a file too large, something that is not
    text - and for saying so with a
    :class:`forge.domain.errors.SourceError` subclass.
    """

    def read(self, path: Path) -> SourceFile:
        """Read ``path``, or explain why it cannot be analysed.

        Raises:
            SourceNotFoundError: nothing exists at that path.
            SourceUnreadableError: it exists but cannot be used as source.
            SourceTooLargeError: it exceeds the configured limit.
            PathOutsideWorkspaceError: it resolves outside the workspace.
        """
        ...
