"""Evidence-backed explanation data returned by one source-file analysis."""

from dataclasses import dataclass

from forge.domain.ai import TokenUsage
from forge.domain.source import Confidence, SourceFile


@dataclass(frozen=True, slots=True)
class EvidenceRange:
    """A one-based inclusive line range in the submitted source snapshot."""

    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        if self.start_line < 1:
            raise ValueError("Evidence line numbers start at 1.")
        if self.end_line < self.start_line:
            raise ValueError("An evidence range must end on or after its start.")


@dataclass(frozen=True, slots=True)
class ExplanationClaim:
    """One model interpretation tied to exact source lines."""

    text: str
    confidence: Confidence
    evidence: tuple[EvidenceRange, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("An explanation claim must contain text.")
        if not self.evidence:
            raise ValueError("An explanation claim needs source evidence.")


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    """A validated explanation, its source snapshot, and measured usage."""

    source: SourceFile
    purpose: tuple[ExplanationClaim, ...]
    flow: tuple[ExplanationClaim, ...]
    symbols: tuple[ExplanationClaim, ...]
    limitations: tuple[str, ...]
    context_insufficient: bool
    incomplete: bool
    model: str
    usage: TokenUsage
