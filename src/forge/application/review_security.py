"""Heuristic secret checks performed before review requests are built."""

import re
from pathlib import Path

_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".crt", ".cer", ".der")
_SECRET_NAMES = frozenset(
    {
        "id_rsa",
        "id_ed25519",
        "credentials",
        "secrets",
        ".npmrc",
        ".pypirc",
        ".netrc",
    }
)
_INLINE_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    re.compile(
        r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
    ),
    re.compile(
        r"(?im)\b(?:api[_-]?key|secret|password|passwd|token|client[_-]?secret|access[_-]?token)\b"
        r"\s*[:=]\s*(['\"])[^'\"\r\n]{12,}\1"
    ),
)


def sensitive_path(path: Path) -> bool:
    """Recognize the same sensitive path classes used by project inspection."""
    for part in path.parts:
        lowered = part.casefold()
        if lowered.startswith(".env") or lowered in _SECRET_NAMES:
            return True
        words = set(re.split(r"[^a-z0-9]+", Path(lowered).stem))
        if words & {"secret", "credential", "password", "token"}:
            return True
        if {"api", "key"} <= words or {"private", "key"} <= words:
            return True
        if lowered.endswith(_SECRET_SUFFIXES):
            return True
    return False


def contains_inline_secret(content: str) -> bool:
    """Return a boolean only; callers must never expose the matched value."""
    return any(pattern.search(content) for pattern in _INLINE_PATTERNS)
