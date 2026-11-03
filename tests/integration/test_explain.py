import io
import json
from pathlib import Path
from typing import Any

import pytest

from forge.application.explain import ExplainSource
from forge.domain.ai import CompletionResponse, TokenUsage
from forge.domain.errors import SourceTooLargeError
from forge.infrastructure.source import FilesystemSourceReader
from forge.presentation.explanation import render_explanation
from tests.support.fakes import FakeProvider


class _RecordingBytesIO(io.BytesIO):
    def __init__(self, value: bytes, sizes: list[int | None]) -> None:
        super().__init__(value)
        self._sizes = sizes

    def read(self, size: int | None = -1) -> bytes:
        self._sizes.append(size)
        return super().read(size)


def _provider(response_text: str) -> FakeProvider:
    return FakeProvider(
        response=CompletionResponse(
            text=response_text,
            model="fake-model",
            usage=TokenUsage(input_tokens=12, output_tokens=8),
        )
    )


@pytest.mark.integration
def test_explanation_cites_excerpts_from_the_submitted_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = "def total(values):\n    return sum(values)\n"
    (workspace / "app.py").write_bytes(source_text.encode())
    payload = {
        "purpose": [
            {
                "claim": "Returns the sum of values.",
                "confidence": "certain",
                "evidence": [{"start_line": 1, "end_line": 2}],
            }
        ],
        "flow": [],
        "symbols": [],
        "limitations": [],
        "context_insufficient": False,
    }
    provider = _provider(json.dumps(payload))
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("app.py"))
    rendered = render_explanation(result)

    assert provider.call_count == 1
    assert "1 | def total(values):" in provider.requests[0].messages[1].content
    assert "Evidence: lines 1-2" in rendered
    assert "1 | def total(values):" in rendered
    assert "2 |     return sum(values)" in rendered


@pytest.mark.integration
def test_growth_after_preflight_is_bounded_and_makes_no_provider_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path
    source_path = workspace / "app.py"
    source_path.write_bytes(b"x = 1\n")
    max_bytes = 16
    original_open = Path.open
    read_sizes: list[int | None] = []
    provider = _provider("{}")

    def grow_before_read(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if path == source_path and mode == "rb":
            grown_content = b"x" * (max_bytes * 20)
            with original_open(path, "wb") as stream:
                stream.write(grown_content)
            return _RecordingBytesIO(grown_content, read_sizes)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", grow_before_read)

    with pytest.raises(SourceTooLargeError, match="grew beyond"):
        ExplainSource(FilesystemSourceReader(workspace, max_bytes=max_bytes), provider)(
            Path("app.py")
        )

    assert read_sizes == [max_bytes + 1]
    assert provider.call_count == 0
    assert source_path.stat().st_size == max_bytes * 20
