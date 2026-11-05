"""Validate evidence ranges and limitations in an explanation response."""

import ast
import io
import json
import re
import tokenize
from collections.abc import Iterator, Mapping
from typing import Any

from forge.domain.ai import TokenUsage
from forge.domain.errors import ProviderResponseError
from forge.domain.explanation import (
    EvidenceAnchor,
    EvidenceKind,
    ExplanationClaim,
    ExplanationDiagnostic,
    ExplanationDiagnosticKind,
    ExplanationResult,
    ExplanationSection,
)
from forge.domain.source import Confidence, SourceFile

_IGNORED_TOKEN_TYPES = frozenset(
    {
        tokenize.ENCODING,
        tokenize.ENDMARKER,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.NL,
    }
)
_IGNORED_TARGET_TOKEN_TYPES = _IGNORED_TOKEN_TYPES | {tokenize.NEWLINE}
_DIAGNOSTIC_SECTION_ORDER = {
    ExplanationSection.PURPOSE: 0,
    ExplanationSection.FLOW: 1,
    ExplanationSection.SYMBOLS: 2,
    None: 3,
}
_OMISSION_DIAGNOSTICS = frozenset(
    {
        ExplanationDiagnosticKind.SECTION_MISSING,
        ExplanationDiagnosticKind.SECTION_MALFORMED,
        ExplanationDiagnosticKind.CLAIM_MALFORMED,
        ExplanationDiagnosticKind.SUBJECT_UNAVAILABLE,
        ExplanationDiagnosticKind.EVIDENCE_MALFORMED,
        ExplanationDiagnosticKind.EVIDENCE_KIND_UNSUPPORTED,
        ExplanationDiagnosticKind.EVIDENCE_TARGET_SHAPE_UNSUPPORTED,
        ExplanationDiagnosticKind.EVIDENCE_TARGET_NOT_FOUND,
        ExplanationDiagnosticKind.EVIDENCE_SOURCE_SHAPE_MISMATCH,
        ExplanationDiagnosticKind.EVIDENCE_VALIDATION_UNAVAILABLE,
        ExplanationDiagnosticKind.CALL_TARGET_IS_DECLARATION,
        ExplanationDiagnosticKind.CALL_EXPRESSION_NOT_FOUND,
        ExplanationDiagnosticKind.SYMBOL_OPERATION_DISALLOWED,
        ExplanationDiagnosticKind.EVIDENCE_OUT_OF_SCOPE,
        ExplanationDiagnosticKind.PURPOSE_CALL_NOT_IN_FLOW,
        ExplanationDiagnosticKind.NAME_ONLY,
        ExplanationDiagnosticKind.LIMITATIONS_MISSING,
        ExplanationDiagnosticKind.LIMITATIONS_FIELD_MALFORMED,
        ExplanationDiagnosticKind.LIMITATIONS_MALFORMED,
        ExplanationDiagnosticKind.CONTEXT_STATUS_MISSING,
        ExplanationDiagnosticKind.CONTEXT_STATUS_MALFORMED,
    }
)
_VALIDATION_UNAVAILABLE_DIAGNOSTICS = frozenset(
    {
        ExplanationDiagnosticKind.SOURCE_VALIDATION_UNAVAILABLE,
        ExplanationDiagnosticKind.SYMBOL_VALIDATION_UNAVAILABLE,
    }
)
_WARNING_DIAGNOSTICS = frozenset(
    {
        ExplanationDiagnosticKind.CONFIDENCE_UNRECOGNIZED,
        ExplanationDiagnosticKind.CONTEXT_INSUFFICIENT,
    }
)
_INFORMATIONAL_DIAGNOSTICS = frozenset({ExplanationDiagnosticKind.SECTION_EMPTY})


def parse_explanation(
    text: str, source: SourceFile, *, model: str, usage: TokenUsage
) -> ExplanationResult:
    """Keep only claims with valid locations in the submitted source snapshot."""
    payload = _decode(text)
    source_tokens = _python_tokens(source)
    source_tree = _python_tree(source) if source_tokens is not None else None
    incomplete = source_tokens is None
    sections: dict[str, tuple[ExplanationClaim, ...]] = {}
    diagnostic_counts: dict[
        tuple[ExplanationSection | None, ExplanationDiagnosticKind], int
    ] = {}

    def record(
        section: ExplanationSection | None,
        kind: ExplanationDiagnosticKind,
        count: int = 1,
    ) -> None:
        key = (section, kind)
        diagnostic_counts[key] = diagnostic_counts.get(key, 0) + count

    if source_tokens is None:
        record(None, ExplanationDiagnosticKind.SOURCE_VALIDATION_UNAVAILABLE)
    elif source_tree is None:
        record(None, ExplanationDiagnosticKind.SYMBOL_VALIDATION_UNAVAILABLE)

    validated_flow_calls: frozenset[EvidenceAnchor] = frozenset()
    for name in ("flow", "purpose", "symbols"):
        section = ExplanationSection(name)
        if name not in payload:
            sections[name] = ()
            record(section, ExplanationDiagnosticKind.SECTION_MISSING)
            incomplete = True
            continue
        raw_claims = payload[name]
        if not isinstance(raw_claims, list):
            sections[name] = ()
            record(section, ExplanationDiagnosticKind.SECTION_MALFORMED)
            incomplete = True
            continue
        if not raw_claims:
            record(section, ExplanationDiagnosticKind.SECTION_EMPTY)
        claims: list[ExplanationClaim] = []
        for item in raw_claims:
            claim, diagnostic = _claim(
                item,
                source,
                section=name,
                source_tokens=source_tokens,
                source_tree=source_tree,
            )
            if diagnostic is not None:
                record(section, diagnostic)
                incomplete = True
            if claim is not None:
                if name == "purpose":
                    purpose_calls = tuple(
                        anchor
                        for anchor in claim.evidence
                        if anchor.kind is EvidenceKind.CALL
                    )
                    if not purpose_calls or not any(
                        anchor in validated_flow_calls for anchor in purpose_calls
                    ):
                        record(
                            section,
                            ExplanationDiagnosticKind.PURPOSE_CALL_NOT_IN_FLOW,
                        )
                        incomplete = True
                        continue
                claims.append(claim)
        sections[name] = tuple(claims)
        if name == "flow":
            validated_flow_calls = frozenset(
                anchor
                for claim in claims
                for anchor in claim.evidence
                if anchor.kind is EvidenceKind.CALL
            )

    limitations: tuple[str, ...]
    limitations_missing = "limitations" not in payload
    if limitations_missing:
        limitations, invalid_limitations, malformed_limitations = (), 0, False
        record(None, ExplanationDiagnosticKind.LIMITATIONS_MISSING)
    else:
        limitations, invalid_limitations, malformed_limitations = _limitations(
            payload["limitations"]
        )
    if malformed_limitations:
        record(None, ExplanationDiagnosticKind.LIMITATIONS_FIELD_MALFORMED)
    if invalid_limitations:
        record(
            None,
            ExplanationDiagnosticKind.LIMITATIONS_MALFORMED,
            invalid_limitations,
        )
    incomplete = (
        incomplete
        or limitations_missing
        or bool(invalid_limitations)
        or malformed_limitations
        or bool(limitations)
    )
    if source_tokens is not None and source_tree is None:
        limitation = (
            "Python syntax could not be parsed; symbol scope validation was "
            "unavailable and symbol claims were omitted."
        )
        if limitation not in limitations:
            limitations = (*limitations, limitation)
        incomplete = True

    context_status_missing = "context_insufficient" not in payload
    context_insufficient = payload.get("context_insufficient")
    if not isinstance(context_insufficient, bool):
        context_insufficient = True
        record(
            None,
            (
                ExplanationDiagnosticKind.CONTEXT_STATUS_MISSING
                if context_status_missing
                else ExplanationDiagnosticKind.CONTEXT_STATUS_MALFORMED
            ),
        )
        incomplete = True
    elif context_insufficient:
        record(None, ExplanationDiagnosticKind.CONTEXT_INSUFFICIENT)
    if source_tokens is None:
        context_insufficient = True
        validation_limit = _validation_limitation(source)
        if validation_limit not in limitations:
            limitations = (*limitations, validation_limit)
    if (
        context_insufficient
        and not limitations
        and isinstance(payload.get("context_insufficient"), bool)
    ):
        limitations = (
            "This file alone does not provide enough context to explain all behavior.",
        )
    incomplete = incomplete or context_insufficient

    if not any(sections.values()) and not limitations and not incomplete:
        raise ProviderResponseError(
            "The model's explanation contained no evidence-grounded claims or "
            "useful context limits."
        )

    diagnostics = tuple(
        ExplanationDiagnostic(section, kind, count)
        for (section, kind), count in sorted(
            diagnostic_counts.items(),
            key=lambda item: _DIAGNOSTIC_SECTION_ORDER[item[0][0]],
        )
    )
    processing_incomplete = _processing_incomplete(diagnostics)
    return ExplanationResult(
        source=source,
        purpose=sections["purpose"],
        flow=sections["flow"],
        symbols=sections["symbols"],
        limitations=limitations,
        context_insufficient=context_insufficient,
        incomplete=incomplete,
        model=model,
        usage=usage,
        diagnostics=diagnostics,
        processing_incomplete=processing_incomplete,
    )


def _processing_incomplete(
    diagnostics: tuple[ExplanationDiagnostic, ...],
) -> bool | None:
    """Report known omissions separately from unavailable validation."""
    kinds = {diagnostic.kind for diagnostic in diagnostics}
    if kinds & _OMISSION_DIAGNOSTICS:
        return True
    classified = (
        _OMISSION_DIAGNOSTICS
        | _VALIDATION_UNAVAILABLE_DIAGNOSTICS
        | _WARNING_DIAGNOSTICS
        | _INFORMATIONAL_DIAGNOSTICS
    )
    if kinds & _VALIDATION_UNAVAILABLE_DIAGNOSTICS or kinds - classified:
        return None
    return False


def _validation_limitation(source: SourceFile) -> str:
    """State why evidence anchors could not be validated for this snapshot."""
    if source.path.suffix.casefold() not in {".py", ".pyi"}:
        return (
            "Evidence validation supports Python .py and .pyi files only; "
            "claims from this file were omitted."
        )
    return "Python tokenization failed; evidence claims from this file were omitted."


def _decode(text: str) -> Mapping[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) > 1:
            candidate = "\n".join(
                lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
            ).strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        raise ProviderResponseError(
            "The model's explanation reply was not valid JSON."
        ) from None
    if not isinstance(payload, dict):
        raise ProviderResponseError(
            "The model's explanation reply was not a JSON object."
        )
    return payload


def _claim(
    item: object,
    source: SourceFile,
    *,
    section: str,
    source_tokens: tuple[tokenize.TokenInfo, ...] | None,
    source_tree: ast.Module | None,
) -> tuple[ExplanationClaim | None, ExplanationDiagnosticKind | None]:
    if not isinstance(item, dict):
        return None, ExplanationDiagnosticKind.CLAIM_MALFORMED
    text = item.get("claim")
    if not isinstance(text, str) or not text.strip():
        return None, ExplanationDiagnosticKind.CLAIM_MALFORMED
    raw_evidence = item.get("evidence")
    if not isinstance(raw_evidence, list) or not raw_evidence:
        return None, ExplanationDiagnosticKind.EVIDENCE_MALFORMED

    symbol: str | None = None
    symbol_scope: tuple[int, int] | None = None
    if section == "symbols":
        resolved = _symbol_scope(item.get("symbol"), source_tree)
        if resolved is None:
            return None, ExplanationDiagnosticKind.SUBJECT_UNAVAILABLE
        symbol, symbol_scope = resolved

    evidence: list[EvidenceAnchor] = []
    for raw_anchor in raw_evidence:
        anchor, diagnostic = _anchor(
            raw_anchor,
            source,
            source_tokens=source_tokens,
            source_tree=source_tree,
        )
        if anchor is None:
            return None, diagnostic or ExplanationDiagnosticKind.EVIDENCE_MALFORMED
        if section == "symbols" and anchor.kind is EvidenceKind.OPERATION:
            return None, ExplanationDiagnosticKind.SYMBOL_OPERATION_DISALLOWED
        if symbol_scope is not None and not _range_within_scope(anchor, symbol_scope):
            return None, ExplanationDiagnosticKind.EVIDENCE_OUT_OF_SCOPE
        evidence.append(anchor)

    if symbol is not None and _is_name_only(
        text, tuple(evidence), source, symbol=symbol
    ):
        return None, ExplanationDiagnosticKind.NAME_ONLY

    confidence = item.get("confidence")
    try:
        level = Confidence(confidence) if isinstance(confidence, str) else None
    except ValueError:
        level = None
    invalid_confidence = level is None
    # The model cannot reliably establish that a broad interpretation is
    # certain. Cap its strongest label because entailment is not mechanically
    # verifiable; source citations identify evidence but do not prove a claim.
    if level is Confidence.CERTAIN:
        level = Confidence.LIKELY
    return (
        ExplanationClaim(
            text=text.strip(),
            confidence=level or Confidence.POSSIBLE,
            evidence=tuple(evidence),
            symbol=symbol,
        ),
        (
            ExplanationDiagnosticKind.CONFIDENCE_UNRECOGNIZED
            if invalid_confidence
            else None
        ),
    )


def _symbol_scope(
    value: object, source_tree: ast.Module | None
) -> tuple[str, tuple[int, int]] | None:
    """Resolve one explicit symbol name to a unique Python declaration scope."""
    if (
        source_tree is None
        or not isinstance(value, str)
        or value != value.strip()
        or not value.isidentifier()
    ):
        return None
    definitions = tuple(
        node
        for node in ast.walk(source_tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == value
    )
    if len(definitions) != 1:
        return None
    definition = definitions[0]
    if not isinstance(definition.end_lineno, int):
        return None
    return value, (definition.lineno, definition.end_lineno)


def _range_within_scope(anchor: EvidenceAnchor, scope: tuple[int, int]) -> bool:
    start, end = scope
    return start <= anchor.start_line <= anchor.end_line <= end


def _anchor(
    value: object,
    source: SourceFile,
    *,
    source_tokens: tuple[tokenize.TokenInfo, ...] | None,
    source_tree: ast.Module | None,
) -> tuple[EvidenceAnchor | None, ExplanationDiagnosticKind | None]:
    """Validate an anchor's target and declared source shape against the snapshot."""
    if not isinstance(value, dict):
        return None, ExplanationDiagnosticKind.EVIDENCE_MALFORMED
    raw_kind = value.get("kind")
    target = value.get("target")
    start_line = value.get("start_line")
    end_line = value.get("end_line")
    if (
        not isinstance(raw_kind, str)
        or not isinstance(target, str)
        or isinstance(start_line, bool)
        or not isinstance(start_line, int)
        or isinstance(end_line, bool)
        or not isinstance(end_line, int)
        or not 1 <= start_line <= end_line <= source.line_count
    ):
        return None, ExplanationDiagnosticKind.EVIDENCE_MALFORMED
    if target != target.strip() or not target:
        return None, ExplanationDiagnosticKind.EVIDENCE_TARGET_SHAPE_UNSUPPORTED
    try:
        kind = EvidenceKind(raw_kind)
    except ValueError:
        return None, ExplanationDiagnosticKind.EVIDENCE_KIND_UNSUPPORTED

    target_tokens = _target_tokens(target)
    if target_tokens is None:
        return None, ExplanationDiagnosticKind.EVIDENCE_TARGET_SHAPE_UNSUPPORTED
    if source_tokens is None:
        return None, ExplanationDiagnosticKind.EVIDENCE_VALIDATION_UNAVAILABLE
    anchor_tokens = tuple(
        token
        for token in source_tokens
        if start_line <= token.start[0] <= end_line
        and token.type not in _IGNORED_TOKEN_TYPES
    )
    if not tuple(_target_occurrences(target_tokens, anchor_tokens)):
        return None, ExplanationDiagnosticKind.EVIDENCE_TARGET_NOT_FOUND
    if not _matches_anchor(kind, target_tokens, anchor_tokens):
        return None, ExplanationDiagnosticKind.EVIDENCE_SOURCE_SHAPE_MISMATCH
    if kind is EvidenceKind.CALL:
        if source_tree is None:
            return None, ExplanationDiagnosticKind.EVIDENCE_VALIDATION_UNAVAILABLE
        if not _has_call_expression(
            source, source_tree, target_tokens, start_line, end_line
        ):
            if _is_function_declaration_target(
                source_tree, target_tokens, start_line, end_line
            ):
                return None, ExplanationDiagnosticKind.CALL_TARGET_IS_DECLARATION
            return None, ExplanationDiagnosticKind.CALL_EXPRESSION_NOT_FOUND
    return EvidenceAnchor(kind, target, start_line, end_line), None


def _python_tokens(source: SourceFile) -> tuple[tokenize.TokenInfo, ...] | None:
    """Tokenize Python snapshots; other languages remain unverified and incomplete."""
    if source.path.suffix.casefold() not in {".py", ".pyi"}:
        return None
    try:
        return tuple(
            token
            for token in tokenize.generate_tokens(io.StringIO(source.content).readline)
            if token.type not in _IGNORED_TOKEN_TYPES
        )
    except (IndentationError, tokenize.TokenError):
        return None


def _python_tree(source: SourceFile) -> ast.Module | None:
    """Parse the submitted Python snapshot without reading any other file."""
    if source.path.suffix.casefold() not in {".py", ".pyi"}:
        return None
    try:
        return ast.parse(source.content)
    except SyntaxError:
        return None


def _has_call_expression(
    source: SourceFile,
    source_tree: ast.Module | None,
    target: tuple[tuple[int, str], ...],
    start_line: int,
    end_line: int,
) -> bool:
    """Reject call-shaped function declarations that are not call expressions."""
    if source_tree is None:
        return False
    for node in ast.walk(source_tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        function_end = function.end_lineno
        if (
            not isinstance(function_end, int)
            or not start_line <= function.lineno <= function_end <= end_line
        ):
            continue
        segment = ast.get_source_segment(source.content, function)
        if segment is not None and _target_tokens(segment) == target:
            return True
    return False


def _is_function_declaration_target(
    source_tree: ast.Module,
    target: tuple[tuple[int, str], ...],
    start_line: int,
    end_line: int,
) -> bool:
    """Tell a declared function name from a call to that function."""
    if len(target) != 1 or target[0][0] != tokenize.NAME:
        return False
    name = target[0][1]
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
        and start_line <= node.lineno <= end_line
        for node in ast.walk(source_tree)
    )


def _target_tokens(target: str) -> tuple[tuple[int, str], ...] | None:
    """Tokenize an exact target without permitting comments or string literals."""
    try:
        tokens = tuple(
            token
            for token in tokenize.generate_tokens(io.StringIO(target).readline)
            if token.type not in _IGNORED_TARGET_TOKEN_TYPES
        )
    except (IndentationError, tokenize.TokenError):
        return None
    if not tokens or any(
        token.type in {tokenize.COMMENT, tokenize.STRING, tokenize.ERRORTOKEN}
        for token in tokens
    ):
        return None
    return tuple((token.type, token.string) for token in tokens)


def _matches_anchor(
    kind: EvidenceKind,
    target: tuple[tuple[int, str], ...],
    tokens: tuple[tokenize.TokenInfo, ...],
) -> bool:
    matches = tuple(_target_occurrences(target, tokens))
    if not matches:
        return False
    if kind is EvidenceKind.CALL:
        return any(
            _next_token(tokens, start + len(target)) == (tokenize.OP, "(")
            for start in matches
        )
    if kind is EvidenceKind.RETURN_TYPE:
        return any(
            start > 0 and _token_key(tokens[start - 1]) == (tokenize.OP, "->")
            for start in matches
        )
    if kind is EvidenceKind.RETURN_VALUE:
        return any(_in_return_statement(tokens, start) for start in matches)
    if kind is EvidenceKind.ACCESS:
        return any(_is_access_read(tokens, start, len(target)) for start in matches)
    return True


def _target_occurrences(
    target: tuple[tuple[int, str], ...], tokens: tuple[tokenize.TokenInfo, ...]
) -> Iterator[int]:
    """Yield exact token-sequence matches; identifiers are never substring matched."""
    for start in range(len(tokens) - len(target) + 1):
        if (
            tuple(_token_key(token) for token in tokens[start : start + len(target)])
            == target
        ):
            yield start


def _token_key(token: tokenize.TokenInfo) -> tuple[int, str]:
    return token.type, token.string


def _next_token(
    tokens: tuple[tokenize.TokenInfo, ...], start: int
) -> tuple[int, str] | None:
    if start >= len(tokens):
        return None
    return _token_key(tokens[start])


def _in_return_statement(tokens: tuple[tokenize.TokenInfo, ...], index: int) -> bool:
    for token in reversed(tokens[:index]):
        if token.type == tokenize.NEWLINE:
            return False
        if token.type == tokenize.NAME and token.string == "return":
            return True
    return False


def _is_access_read(
    tokens: tuple[tokenize.TokenInfo, ...], start: int, target_size: int
) -> bool:
    target = tokens[start : start + target_size]
    if not any(
        token.type == tokenize.OP and token.string in {".", "["} for token in target
    ):
        return False
    statement_start = start
    while statement_start > 0 and tokens[statement_start - 1].type != tokenize.NEWLINE:
        statement_start -= 1
    statement_end = start + target_size
    while (
        statement_end < len(tokens) and tokens[statement_end].type != tokenize.NEWLINE
    ):
        statement_end += 1
    statement = tokens[statement_start:statement_end]
    if (
        statement
        and statement[0].type == tokenize.NAME
        and statement[0].string
        in {
            "async",
            "class",
            "def",
            "from",
            "import",
        }
    ):
        return False
    assignment_positions = [
        position
        for position, token in enumerate(statement)
        if token.type == tokenize.OP and token.string in {"=", ":="}
    ]
    target_position = start - statement_start
    return not assignment_positions or target_position > assignment_positions[0]


_SYMBOL_FILLER = frozenset(
    {
        "a",
        "an",
        "the",
        "class",
        "method",
        "function",
        "symbol",
        "named",
        "called",
        "is",
        "of",
    }
)


def _is_name_only(
    text: str,
    evidence: tuple[EvidenceAnchor, ...],
    source: SourceFile,
    *,
    symbol: str,
) -> bool:
    """Reject symbol entries that only repeat identifiers or declaration kinds."""
    source_lines = source.content.splitlines()
    cited_text = " ".join(
        source_lines[line - 1]
        for span in evidence
        for line in range(span.start_line, span.end_line + 1)
    )
    source_identifiers = {word.casefold() for word in re.findall(r"[\w$]+", cited_text)}
    source_identifiers.update(word.casefold() for word in re.findall(r"[\w$]+", symbol))
    claim_words = [word.casefold() for word in re.findall(r"[\w$]+", text)]
    useful_words = [
        word
        for word in claim_words
        if word not in source_identifiers and word not in _SYMBOL_FILLER
    ]
    return not useful_words


def _limitations(value: object) -> tuple[tuple[str, ...], int, bool]:
    if not isinstance(value, list):
        return (), 0, True
    valid: list[str] = []
    invalid = 0
    for item in value:
        if isinstance(item, str) and item.strip():
            valid.append(item.strip())
        else:
            invalid += 1
    return tuple(valid), invalid, False
