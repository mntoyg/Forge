"""Reading source files from disk, safely.

Forge sends what it reads to a third party. That single fact turns ordinary
file handling into a security boundary: a path that escapes the workspace is
not a bug that crashes, it is a way to exfiltrate a file the user never meant
to share. Every refusal below exists for that reason, and each has a test.
"""

from pathlib import Path

from forge.domain.errors import (
    PathOutsideWorkspaceError,
    SourceNotFoundError,
    SourceTooLargeError,
    SourceUnreadableError,
)
from forge.domain.source import SourceFile

DEFAULT_MAX_BYTES = 200_000
"""Roughly 5,000 lines of code - far more than a model reasons about well."""


class FilesystemSourceReader:
    """Reads a file from within a workspace directory.

    Implements :class:`forge.domain.source.SourceReader`.
    """

    def __init__(self, workspace: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        """Build the reader.

        Args:
            workspace: The directory nothing may be read from outside of.
                Resolved once here, so a later ``chdir`` cannot move the
                boundary out from under a running command.
            max_bytes: Largest file to accept.
        """
        self._workspace = workspace.resolve()
        self._max_bytes = max_bytes

    def read(self, path: Path) -> SourceFile:
        """Implement :meth:`forge.domain.source.SourceReader.read`."""
        resolved = self._resolve_inside_workspace(path)

        if not resolved.exists():
            raise SourceNotFoundError(f"No such file: {path}")
        if resolved.is_dir():
            raise SourceUnreadableError(
                f"{path} is a directory. Give the path to a single file."
            )
        if not resolved.is_file():
            raise SourceUnreadableError(f"{path} is not a regular file.")

        size = resolved.stat().st_size
        if size > self._max_bytes:
            raise SourceTooLargeError(
                f"{path} is {size:,} bytes, over the {self._max_bytes:,} byte "
                "limit. Raise FORGE_MAX_FILE_BYTES, or analyse a smaller file."
            )

        content = self._decode(resolved, path)

        try:
            return SourceFile(path=resolved, content=content)
        except ValueError as error:
            # The domain rejects an empty file. To the user that is the same
            # class of problem as an unreadable one: nothing to analyse.
            raise SourceUnreadableError(str(error)) from error

    def _resolve_inside_workspace(self, path: Path) -> Path:
        """Resolve ``path`` and refuse anything outside the workspace.

        ``resolve()`` follows symlinks, so this catches both ``../../etc/passwd``
        and a link inside the workspace pointing out of it. The check is made
        on the resolved path for exactly that reason - validating the string
        the user typed would miss the link entirely.
        """
        candidate = (
            (self._workspace / path).resolve()
            if not path.is_absolute()
            else path.resolve()
        )

        if not candidate.is_relative_to(self._workspace):
            raise PathOutsideWorkspaceError(
                f"{path} resolves outside the workspace ({self._workspace}). "
                "Forge only reads files inside the directory you are working in."
            )
        return candidate

    @staticmethod
    def _decode(resolved: Path, original: Path) -> str:
        """Read the file as UTF-8 text, or explain that it is not text.

        Read as bytes first so that a binary file fails here, with a message
        about what it is, rather than partway through analysis or - worse -
        as mojibake the model cheerfully reviews.

        Line endings are normalised to ``\\n``. The same file checked out on
        Windows and on Linux must produce the same prompt, or the tool gives
        different answers on different machines for reasons no user could ever
        guess. Nothing is written back, so this changes only what is analysed.
        """
        try:
            raw = resolved.read_bytes()
        except OSError as error:
            raise SourceUnreadableError(f"Cannot read {original}: {error}") from error

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SourceUnreadableError(
                f"{original} is not UTF-8 text. Forge analyses source files, "
                "not binaries."
            ) from error

        return text.replace("\r\n", "\n").replace("\r", "\n")
