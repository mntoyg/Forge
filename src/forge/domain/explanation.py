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


class ExplanationSection(StrEnum):
    """A fixed explanation section used in safe validation diagnostics."""

    PURPOSE = "purpose"
    FLOW = "flow"
    SYMBOLS = "symbols"


class ExplanationDiagnosticKind(StrEnum):
    """A fixed, non-content-bearing reason for an omitted or incomplete result."""

    SECTION_EMPTY = "section_empty"
    SECTION_MISSING = "section_missing"
    SECTION_MALFORMED = "section_malformed"
    CLAIM_MALFORMED = "claim_malformed"
    SUBJECT_UNAVAILABLE = "subject_unavailable"
    EVIDENCE_MALFORMED = "evidence_malformed"
    EVIDENCE_KIND_UNSUPPORTED = "evidence_kind_unsupported"
    EVIDENCE_TARGET_SHAPE_UNSUPPORTED = "evidence_target_shape_unsupported"
    EVIDENCE_TARGET_NOT_FOUND = "evidence_target_not_found"
    EVIDENCE_SOURCE_SHAPE_MISMATCH = "evidence_source_shape_mismatch"
    EVIDENCE_VALIDATION_UNAVAILABLE = "evidence_validation_unavailable"
    CALL_TARGET_IS_DECLARATION = "call_target_is_declaration"
    CALL_EXPRESSION_NOT_FOUND = "call_expression_not_found"
    SYMBOL_OPERATION_DISALLOWED = "symbol_operation_disallowed"
    EVIDENCE_OUT_OF_SCOPE = "evidence_out_of_scope"
    PURPOSE_CALL_NOT_IN_FLOW = "purpose_call_not_in_flow"
    NAME_ONLY = "name_only"
    CONFIDENCE_UNRECOGNIZED = "confidence_unrecognized"
    LIMITATIONS_MISSING = "limitations_missing"
    LIMITATIONS_FIELD_MALFORMED = "limitations_field_malformed"
    LIMITATIONS_MALFORMED = "limitations_malformed"
    CONTEXT_STATUS_MISSING = "context_status_missing"
    CONTEXT_STATUS_MALFORMED = "context_status_malformed"
    CONTEXT_INSUFFICIENT = "context_insufficient"
    SOURCE_VALIDATION_UNAVAILABLE = "source_validation_unavailable"
    SYMBOL_VALIDATION_UNAVAILABLE = "symbol_validation_unavailable"


@dataclass(frozen=True, slots=True)
class ExplanationDiagnostic:
    """A safe category and count, with no provider-controlled text."""

    section: ExplanationSection | None
    kind: ExplanationDiagnosticKind
    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("An explanation diagnostic count must be positive.")


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
    symbol: str | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("An explanation claim must contain text.")
        if not self.evidence:
            raise ValueError("An explanation claim needs source evidence.")
        if self.symbol is not None and not self.symbol.strip():
            raise ValueError("An explanation symbol needs a name.")


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    """A validated explanation, its source snapshot, and measured usage.

    ``processing_incomplete`` marks known parser omissions: true means an
    omission diagnostic exists, false means validation found no omission, and
    None means validation availability leaves completeness unknown. The legacy
    ``incomplete`` field remains the broader text-output signal.
    """

    source: SourceFile
    purpose: tuple[ExplanationClaim, ...]
    flow: tuple[ExplanationClaim, ...]
    symbols: tuple[ExplanationClaim, ...]
    limitations: tuple[str, ...]
    context_insufficient: bool
    incomplete: bool
    model: str
    usage: TokenUsage
    diagnostics: tuple[ExplanationDiagnostic, ...] = ()
    processing_incomplete: bool | None = None
