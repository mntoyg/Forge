"""The filesystem source reader, against a real temporary directory.

Integration because it crosses a real boundary. The workspace-escape tests
matter most: Forge sends what it reads to a third party, so a path that leaves
the workspace is an exfiltration route, not merely a bug.
"""

import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from forge.domain.errors import (
    PathOutsideWorkspaceError,
    SourceError,
    SourceNotFoundError,
    SourceTooLargeError,
    SourceUnreadableError,
)
from forge.infrastructure.source import DEFAULT_MAX_BYTES, FilesystemSourceReader

LF_CONTENT = "a = 1\nb = 2\n"


class _RecordingBytesIO(BytesIO):
    """Record the largest read requested from a growing file snapshot."""

    def __init__(self, content: bytes, read_sizes: list[int | None]) -> None:
        super().__init__(content)
        self._read_sizes = read_sizes

    def read(self, size: int | None = -1) -> bytes:
        self._read_sizes.append(size)
        return super().read(size)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    # Written as bytes so the fixture means the same thing on every platform.
    # write_text would translate to CRLF on Windows.
    (tmp_path / "app.py").write_bytes(LF_CONTENT.encode("utf-8"))
    return tmp_path


# --- reading ---------------------------------------------------------------


@pytest.mark.integration
def test_a_file_inside_the_workspace_is_read(workspace: Path) -> None:
    source = FilesystemSourceReader(workspace).read(Path("app.py"))

    assert source.content == LF_CONTENT
    assert source.line_count == 2


@pytest.mark.integration
def test_a_path_in_a_subdirectory_is_read(workspace: Path) -> None:
    nested = workspace / "pkg" / "mod.py"
    nested.parent.mkdir()
    nested.write_bytes(b"x = 1\n")

    source = FilesystemSourceReader(workspace).read(Path("pkg/mod.py"))

    assert source.content == "x = 1\n"


@pytest.mark.integration
def test_an_absolute_path_inside_the_workspace_is_read(workspace: Path) -> None:
    source = FilesystemSourceReader(workspace).read(workspace / "app.py")

    assert source.content == LF_CONTENT


@pytest.mark.integration
def test_the_resolved_path_is_reported_not_the_one_typed(workspace: Path) -> None:
    """A finding should name a file the reader can actually open."""
    source = FilesystemSourceReader(workspace).read(Path("./app.py"))

    assert source.path.is_absolute()
    assert source.path.name == "app.py"


@pytest.mark.integration
@pytest.mark.parametrize(
    "written",
    [b"a = 1\r\nb = 2\r\n", b"a = 1\rb = 2\r", b"a = 1\nb = 2\n"],
    ids=["crlf", "cr", "lf"],
)
def test_line_endings_are_normalised(workspace: Path, written: bytes) -> None:
    """The same file must produce the same prompt on Windows and on Linux.

    Without this, the tool gives different answers on different machines for a
    reason no user could guess.
    """
    (workspace / "endings.py").write_bytes(written)

    source = FilesystemSourceReader(workspace).read(Path("endings.py"))

    assert source.content == LF_CONTENT
    assert source.line_count == 2
    assert "\r" not in source.content


# --- the workspace boundary ------------------------------------------------


@pytest.mark.integration
def test_a_path_escaping_upward_is_refused(workspace: Path) -> None:
    (workspace.parent / "outside.py").write_bytes(b"secret = 1\n")

    with pytest.raises(PathOutsideWorkspaceError, match="outside the workspace"):
        FilesystemSourceReader(workspace).read(Path("../outside.py"))


@pytest.mark.integration
def test_an_absolute_path_elsewhere_is_refused(workspace: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path.parent / "elsewhere.py"
    elsewhere.write_bytes(b"secret = 1\n")

    with pytest.raises(PathOutsideWorkspaceError):
        FilesystemSourceReader(workspace).read(elsewhere)


@pytest.mark.integration
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="creating a symlink on Windows needs elevation or developer mode",
)
def test_a_symlink_pointing_out_of_the_workspace_is_refused(workspace: Path) -> None:
    """The check runs on the resolved path precisely so this cannot slip by.

    A link that lives inside the workspace looks harmless until it is followed.
    Validating the string the user typed would miss it entirely.
    """
    secret = workspace.parent / "secret.py"
    secret.write_bytes(b"api_key = 1\n")
    (workspace / "innocent.py").symlink_to(secret)

    with pytest.raises(PathOutsideWorkspaceError):
        FilesystemSourceReader(workspace).read(Path("innocent.py"))


@pytest.mark.integration
def test_the_boundary_survives_a_later_chdir(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The workspace is resolved once, at construction.

    Otherwise a command that changes directory mid-run would move the boundary
    out from under itself.
    """
    reader = FilesystemSourceReader(workspace)
    monkeypatch.chdir(tmp_path.parent)

    assert reader.read(Path("app.py")).content == LF_CONTENT


# --- refusals --------------------------------------------------------------


@pytest.mark.integration
def test_a_missing_file_is_reported_with_its_path(workspace: Path) -> None:
    with pytest.raises(SourceNotFoundError, match=r"missing\.py"):
        FilesystemSourceReader(workspace).read(Path("missing.py"))


@pytest.mark.integration
def test_a_directory_is_refused_with_advice(workspace: Path) -> None:
    (workspace / "pkg").mkdir()

    with pytest.raises(SourceUnreadableError, match="is a directory"):
        FilesystemSourceReader(workspace).read(Path("pkg"))


@pytest.mark.integration
def test_an_empty_file_is_refused(workspace: Path) -> None:
    (workspace / "empty.py").write_bytes(b"")

    with pytest.raises(SourceUnreadableError, match="nothing to analyse"):
        FilesystemSourceReader(workspace).read(Path("empty.py"))


@pytest.mark.integration
def test_a_whitespace_only_file_is_refused(workspace: Path) -> None:
    (workspace / "blank.py").write_bytes(b"\n\n   \n")

    with pytest.raises(SourceUnreadableError, match="nothing to analyse"):
        FilesystemSourceReader(workspace).read(Path("blank.py"))


@pytest.mark.integration
def test_a_binary_file_is_refused_rather_than_mangled(workspace: Path) -> None:
    """Decoding it loosely would hand the model mojibake to review."""
    (workspace / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00\x01")

    with pytest.raises(SourceUnreadableError, match="not UTF-8 text"):
        FilesystemSourceReader(workspace).read(Path("image.png"))


@pytest.mark.integration
def test_a_file_over_the_limit_is_refused_not_truncated(workspace: Path) -> None:
    """Analysing half a file produces confident nonsense about the other half."""
    (workspace / "big.py").write_bytes(b"x = 1\n" * 1000)

    with pytest.raises(SourceTooLargeError) as caught:
        FilesystemSourceReader(workspace, max_bytes=100).read(Path("big.py"))

    message = str(caught.value)
    assert "100" in message
    assert "FORGE_MAX_FILE_BYTES" in message


@pytest.mark.integration
def test_a_file_exactly_at_the_limit_is_accepted(workspace: Path) -> None:
    (workspace / "edge.py").write_bytes(b"x" * 50)

    assert FilesystemSourceReader(workspace, max_bytes=50).read(Path("edge.py"))


@pytest.mark.integration
def test_growth_after_size_check_is_refused_after_a_bounded_read(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = workspace / "growing.py"
    source_path.write_bytes(b"x = 1\n")
    max_bytes = 16
    original_open = Path.open
    read_sizes: list[int | None] = []
    grew = False

    def grow_before_read(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        nonlocal grew
        if path == source_path and mode == "rb":
            grown_content = b"x" * (max_bytes * 10)
            with original_open(path, "wb") as stream:
                stream.write(grown_content)
            grew = True
            return _RecordingBytesIO(grown_content, read_sizes)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", grow_before_read)

    with pytest.raises(SourceTooLargeError, match="grew beyond"):
        FilesystemSourceReader(workspace, max_bytes=max_bytes).read(Path("growing.py"))

    assert grew
    assert read_sizes == [max_bytes + 1]
    assert source_path.stat().st_size == max_bytes * 10


# --- the contract ----------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    "path", ["missing.py", "pkg", "../outside.py", "image.png", "empty.py"]
)
def test_every_refusal_is_a_source_error(workspace: Path, path: str) -> None:
    """One base class, so a caller maps them all to exit code 2 at once."""
    (workspace / "pkg").mkdir(exist_ok=True)
    (workspace / "image.png").write_bytes(b"\xff\xfe\x00")
    (workspace / "empty.py").write_bytes(b"")
    (workspace.parent / "outside.py").write_bytes(b"x = 1\n")

    with pytest.raises(SourceError):
        FilesystemSourceReader(workspace).read(Path(path))


@pytest.mark.integration
def test_the_default_limit_is_generous_enough_for_real_files() -> None:
    """5,000-odd lines: more than a model reasons about well, either way."""
    assert DEFAULT_MAX_BYTES >= 100_000


@pytest.mark.integration
def test_nothing_is_written_while_reading(workspace: Path) -> None:
    """FR-3.7: Forge must not modify the analysed file or any other."""
    before = {p.name: p.read_bytes() for p in workspace.iterdir() if p.is_file()}

    FilesystemSourceReader(workspace).read(Path("app.py"))

    after = {p.name: p.read_bytes() for p in workspace.iterdir() if p.is_file()}
    assert before == after
