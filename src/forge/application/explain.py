"""Explain one explicitly selected source file through the existing ports."""

from pathlib import Path

from forge.application.explain_parsing import parse_explanation
from forge.application.explain_prompt import build_explain_request
from forge.domain.ai import AIProvider
from forge.domain.explanation import ExplanationResult
from forge.domain.source import SourceReader


class ExplainSource:
    """Read one safe source snapshot and request one evidence-backed answer."""

    def __init__(self, reader: SourceReader, provider: AIProvider) -> None:
        self._reader = reader
        self._provider = provider

    def __call__(self, path: Path) -> ExplanationResult:
        """Explain the selected file without discovering more context or retrying."""
        source = self._reader.read(path)
        response = self._provider.complete(build_explain_request(source))
        return parse_explanation(
            response.text,
            source,
            model=response.model,
            usage=response.usage,
        )
