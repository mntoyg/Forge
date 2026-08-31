"""The use case behind `forge debug`.

This is the whole operation, expressed in terms of two ports and some domain
types. It does not know that a CLI invoked it, which provider answered, or
where the file came from - which is why its tests need none of those things.
"""

from pathlib import Path

from forge.application.parsing import parse_findings
from forge.application.prompt import build_request
from forge.domain.ai import AIProvider
from forge.domain.source import AnalysisResult, SourceReader


class AnalyzeSourceFile:
    """Read a source file, ask a provider about it, return findings.

    Both collaborators arrive through the constructor. The use case never
    builds one, which is what lets a test hand it a fake filesystem and a fake
    provider and get a real answer in microseconds.
    """

    def __init__(self, reader: SourceReader, provider: AIProvider) -> None:
        self._reader = reader
        self._provider = provider

    def __call__(self, path: Path) -> AnalysisResult:
        """Analyse the file at ``path``.

        Errors are deliberately not caught here. A missing file and a rate
        limit are both things the *caller* must tell the user about and turn
        into an exit code, and swallowing them to return an empty result would
        report "no problems found" for a run that never happened.

        Raises:
            SourceError: the file cannot be used as input.
            ProviderError: the provider failed, or replied unusably.
        """
        source = self._reader.read(path)
        response = self._provider.complete(build_request(source))
        findings = parse_findings(response.text, source)

        return AnalysisResult(
            source_path=source.path,
            findings=findings,
            model=response.model,
            usage=response.usage,
        )
