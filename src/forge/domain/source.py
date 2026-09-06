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

A :class:`ChangeRecord` sits on the other side of that line. It is a fact from
version control rather than a claim from a model, and it is a separate type for
that reason: the output has to be able to say which of the two a reader is
looking at.
"""

from dataclasses import dataclass
from datetime import date
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

    def numbered(self, changed: frozenset[int] | None = None) -> str:
        """Render the content with line numbers, for the prompt.

        The model cannot cite a line it was never shown. Numbering here rather
        than in the prompt builder keeps the numbering and ``line_count`` - the
        two things a location is validated against - in one place.

        When ``changed`` is given, those lines are marked with ``>`` instead of
        ``|``. Per ADR-0008 this is how a change is presented: the whole file,
        so the model can see the code surrounding the edit, with the edit
        itself picked out. Line numbers stay file line numbers either way, so
        nothing has to be translated back and nothing can be translated wrongly.
        """
        marked = changed or frozenset()
        return "\n".join(
            f"{number:>4} {'>' if number in marked else '|'} {line}"
            for number, line in enumerate(self.content.splitlines(), start=1)
        )


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    """When one line was last changed, and by whom.

    Everything here comes from version control, so nothing here is a guess.
    That is the whole point of the type: a reader deciding how much to trust a
    finding needs to know which parts of what they are reading were asserted by
    a model and which were asserted by git.

    A line the working tree has changed but has not committed gets no record at
    all. Git can name no commit for it, and naming one anyway - the previous
    author, say - would attribute the developer's own unsaved work to somebody
    else.

    Raises:
        ValueError: the record does not identify a real line or a real commit.
    """

    line: int
    commit: str
    author: str
    changed_on: date

    def __post_init__(self) -> None:
        if self.line < 1:
            raise ValueError(f"Line numbers start at 1, got {self.line}.")
        if not self.commit.strip():
            raise ValueError("A change record must name the commit it came from.")


@dataclass(frozen=True, slots=True)
class FileHistory:
    """What version control knows about the file that was analysed.

    Two different things, because they answer two different questions. The
    records say when each cited line was last touched; ``recent_commits`` says
    how much the file as a whole has been moving lately. A line last changed a
    year ago in a file nobody edits is a different risk from the same line in a
    file that changed nine times this quarter.

    The window is carried alongside the count rather than assumed by the
    reader, because "4 commits" means nothing without the period it covers.

    Raises:
        ValueError: the counts describe a period or a total that cannot exist.
    """

    recent_commits: int
    window_days: int
    records: tuple[ChangeRecord, ...] = ()

    def __post_init__(self) -> None:
        if self.recent_commits < 0:
            raise ValueError(
                f"A commit count cannot be negative, got {self.recent_commits}."
            )
        if self.window_days < 1:
            raise ValueError(
                f"A history window must cover at least a day, got {self.window_days}."
            )

    def at(self, line: int) -> ChangeRecord | None:
        """The record for ``line``, or ``None`` if git can name no commit.

        ``None`` is a real answer, not a lookup failure: it is what an
        uncommitted line looks like.
        """
        return next((record for record in self.records if record.line == line), None)


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
    history: FileHistory | None = None
    """What version control knows about the cited lines, when it knows anything.

    Optional because it is context around the answer rather than part of it.
    Outside a repository, or for a file git has never seen, there is nothing to
    say - and a result with no history is still a complete result.
    """

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


class RepositoryInspector(Protocol):
    """The port for asking version control what changed.

    Deliberately narrow, for the same reason as
    :class:`forge.domain.ai.AIProvider`: it expresses what Forge needs, not
    what a version control system offers. Branch state, tags, and remotes are
    not here because nothing needs them yet.
    """

    def changed_lines(self, path: Path) -> frozenset[int]:
        """Return the 1-based line numbers ``path`` has uncommitted changes on.

        The comparison is the working tree against ``HEAD`` - staged and
        unstaged together, which is what "what I am about to commit" means to
        someone mid-change.

        Only added and modified lines are returned. A deleted line has no
        number in the current file to point at, and a finding must be able to
        cite a line that exists.

        Raises:
            NotARepositoryError: there is no repository here.
            NoChangesError: the file has no uncommitted changes.
        """
        ...

    def history(self, path: Path, lines: frozenset[int]) -> FileHistory:
        """Return what version control knows about ``lines`` of ``path``.

        ``lines`` are the lines somebody actually cares about - the ones
        findings cite. Asking for those rather than for the whole file keeps
        the cost proportional to the answer being annotated.

        The line numbers are the ones in the file on disk, uncommitted edits
        included, so they mean the same thing as a finding's location. A line
        with no commit behind it is simply absent from the result.

        Raises:
            NotARepositoryError: there is no repository here.
            NoHistoryError: the file has no history to report - git has never
                seen it, or it lies outside the repository.
        """
        ...
