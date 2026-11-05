"""Small stdout helpers shared by CLI output modes."""

import sys


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
