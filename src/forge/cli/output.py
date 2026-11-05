"""Small stdout helpers shared by CLI output modes."""

import sys

from forge.cli.exit_codes import ExitCode
from forge.presentation.json_output import (
    JsonCommand,
    JsonErrorCode,
    serialize_error_json,
)

_ERROR_CODES = {
    ExitCode.FAILED: JsonErrorCode.RESULT_UNAVAILABLE,
    ExitCode.BAD_INPUT: JsonErrorCode.INPUT_UNUSABLE,
    ExitCode.NOT_CONFIGURED: JsonErrorCode.NOT_CONFIGURED,
    ExitCode.PROVIDER_FAILED: JsonErrorCode.PROVIDER_FAILED,
}


def write_json_line(serialized: str) -> None:
    """Write one JSON document to stdout as UTF-8 followed by one newline."""
    encoded = f"{serialized}\n".encode()
    binary_stdout = getattr(sys.stdout, "buffer", None)
    if binary_stdout is not None:
        binary_stdout.write(encoded)
        binary_stdout.flush()
        return
    sys.stdout.write(encoded.decode("utf-8"))
    sys.stdout.flush()


def write_json_error_line(command: JsonCommand, exit_code: ExitCode) -> None:
    """Write one safe JSON error line to stderr using the existing exit class."""
    try:
        code = _ERROR_CODES[exit_code]
    except KeyError as error:
        raise ValueError(
            "A successful exit code cannot represent a JSON error."
        ) from error

    sys.stderr.write(f"{serialize_error_json(command, code)}\n")
    sys.stderr.flush()
