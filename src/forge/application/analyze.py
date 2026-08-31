"""The use case behind `forge debug`.

This is the whole operation, expressed in terms of two ports and some domain
types. It does not know that a CLI invoked it, which provider answered, or
where the file came from - which is why its tests need none of those things.
"""

from pathlib import Path

from forge.application.parsing import parse_findings
from forge.application.prompt import build_request
from forge.domain.ai import AIProvider
from forge.domain.source import AnalysisResult, RepositoryInspector, SourceReader


class AnalyzeSourceFile:
    """Read a source file, ask a provider about it, return findings.

    Every collaborator arrives through the constructor. The use case never
    builds one, which is what lets a test hand it a fake filesystem and a fake
    provider and get a real answer in microseconds.

    ``inspector`` is optional because reviewing a change is optional. A command
    that never passes ``changes_only`` never needs a repository, so a user
    outside version control keeps the whole of `forge debug`.
    """

    def __init__(
        self,
        reader: SourceReader,
        provider: AIProvider,
        inspector: RepositoryInspector | None = None,
    ) -> None:
        self._reader = reader
        self._provider = provider
        self._inspector = inspector

    def __call__(self, path: Path, *, changes_only: bool = False) -> AnalysisResult:
        """Analyse the file at ``path``.

        With ``changes_only``, the analysis is narrowed to the lines the file
        has uncommitted changes on. The whole file is still sent - the model
        cannot judge a change it cannot see the surroundings of - but the
        changed lines are marked and the instructions scope the answer to them.
        See ADR-0008.

        Errors are deliberately not caught here. A missing file and a rate
        limit are both things the *caller* must tell the user about and turn
        into an exit code, and swallowing them to return an empty result would
        report "no problems found" for a run that never happened.

        Raises:
            SourceError: the file cannot be used as input.
            RepositoryError: ``changes_only`` was asked for and cannot be
                answered - no repository, or no changes.
            ProviderError: the provider failed, or replied unusably.
        """
        # Read first. Both checks are cheap, but a missing path is the more
        # fundamental problem: "no such file" beats "no changes" for a
        # filename the user mistyped.
        source = self._reader.read(path)
        changed = self._changed_lines(path) if changes_only else None
        response = self._provider.complete(build_request(source, changed))
        findings = parse_findings(response.text, source)

        return AnalysisResult(
            source_path=source.path,
            findings=findings,
            model=response.model,
            usage=response.usage,
        )

    def _changed_lines(self, path: Path) -> frozenset[int]:
        if self._inspector is None:
            raise RuntimeError(
                "changes_only was requested but no RepositoryInspector was "
                "wired in. This is a composition error, not a user error."
            )
        return self._inspector.changed_lines(path)
