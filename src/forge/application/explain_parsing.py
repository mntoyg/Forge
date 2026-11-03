"""Validate evidence ranges and limitations in an explanation response."""

import json
from collections.abc import Mapping
from typing import Any

from forge.domain.ai import TokenUsage
from forge.domain.errors import ProviderResponseError
from forge.domain.explanation import (
    EvidenceRange,
    ExplanationClaim,
    ExplanationResult,
)
from forge.domain.source import Confidence, SourceFile


def parse_explanation(
    text: str, source: SourceFile, *, model: str, usage: TokenUsage
) -> ExplanationResult:
    """Keep only claims with valid locations in the submitted source snapshot."""
    payload = _decode(text)
    incomplete = False
    sections: dict[str, tuple[ExplanationClaim, ...]] = {}
    for name in ("purpose", "flow", "symbols"):
        raw_claims = payload.get(name)
        if not isinstance(raw_claims, list):
            sections[name] = ()
            incomplete = True
            continue
        claims: list[ExplanationClaim] = []
        for item in raw_claims:
            claim, invalid = _claim(item, source)
            incomplete = incomplete or invalid
            if claim is not None:
                claims.append(claim)
        sections[name] = tuple(claims)

    limitations, invalid_limitations = _limitations(payload.get("limitations"))
    incomplete = incomplete or invalid_limitations or bool(limitations)

    context_insufficient = payload.get("context_insufficient")
    if not isinstance(context_insufficient, bool):
        context_insufficient = True
        incomplete = True
    if context_insufficient and not limitations:
        limitations = (
            "This file alone does not provide enough context to explain all behavior.",
        )
    incomplete = incomplete or context_insufficient

    if not any(sections.values()) and not limitations and not incomplete:
        raise ProviderResponseError(
            "The model's explanation contained no evidence-grounded claims or "
            "useful context limits."
        )

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
    )


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


def _claim(item: object, source: SourceFile) -> tuple[ExplanationClaim | None, bool]:
    if not isinstance(item, dict):
        return None, True
    text = item.get("claim")
    if not isinstance(text, str) or not text.strip():
        return None, True
    raw_evidence = item.get("evidence")
    if not isinstance(raw_evidence, list) or not raw_evidence:
        return None, True

    evidence: list[EvidenceRange] = []
    for raw_range in raw_evidence:
        if not isinstance(raw_range, dict):
            return None, True
        start_line = raw_range.get("start_line")
        end_line = raw_range.get("end_line")
        if (
            isinstance(start_line, bool)
            or not isinstance(start_line, int)
            or isinstance(end_line, bool)
            or not isinstance(end_line, int)
            or not 1 <= start_line <= end_line <= source.line_count
        ):
            return None, True
        evidence.append(EvidenceRange(start_line, end_line))

    confidence = item.get("confidence")
    try:
        level = Confidence(confidence) if isinstance(confidence, str) else None
    except ValueError:
        level = None
    invalid_confidence = level is None
    return (
        ExplanationClaim(
            text=text.strip(),
            confidence=level or Confidence.POSSIBLE,
            evidence=tuple(evidence),
        ),
        invalid_confidence,
    )


def _limitations(value: object) -> tuple[tuple[str, ...], bool]:
    if not isinstance(value, list):
        return (), True
    valid: list[str] = []
    invalid = False
    for item in value:
        if isinstance(item, str) and item.strip():
            valid.append(item.strip())
        else:
            invalid = True
    return tuple(valid), invalid
