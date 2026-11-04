"""Evidence-backed explanation data returned by one source-file analysis."""

from dataclasses import dataclass
from enum import StrEnum

from forge.domain.ai import TokenUsage
from forge.domain.source import Confidence, SourceFile


class EvidenceKind(StrEnum):
    """A source shape that gives a citation a checkable structural role."""

    CALL = "call"
    ACCESS = "access"
    RETURN_TYPE = "return_type"
    RETURN_VALUE = "return_value"
    OPERATION = "operation"


@dataclass(frozen=True, slots=True)
class EvidenceAnchor:
    """A typed target and one-based range in the submitted source snapshot."""

    kind: EvidenceKind
    target: str
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise ValueError("An evidence anchor needs a target.")
        if self.start_line < 1:
            raise ValueError("Evidence line numbers start at 1.")
        if self.end_line < self.start_line:
            raise ValueError("An evidence range must end on or after its start.")


@dataclass(frozen=True, slots=True)
class ExplanationClaim:
    """One model interpretation tied to exact source lines."""

    text: str
    confidence: Confidence
    evidence: tuple[EvidenceAnchor, ...]

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
