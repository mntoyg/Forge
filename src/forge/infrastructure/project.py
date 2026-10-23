"""Collect selected project evidence without following or executing it."""

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path

from forge.domain.project import ProjectEvidence, ProjectEvidenceReader, ProjectFile

MAX_ENTRIES = 500
MAX_FILES = 200
MAX_BYTES = 128_000
MAX_DEPTH = 3
MAX_GITIGNORE_BYTES = 32_000

_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "virtualenv",
        "venvs",
        "node_modules",
        "dist",
        "build",
        "out",
        ".next",
        ".nuxt",
        ".gradle",
        ".terraform",
        ".tox",
        "target",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "coverage",
        "htmlcov",
        "vendor",
        ".ssh",
        ".aws",
        ".azure",
        ".kube",
    }
)
_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".crt", ".cer", ".der")
_BINARY_SUFFIXES = frozenset(
    {
        ".7z",
        ".a",
        ".bin",
        ".bmp",
        ".class",
        ".dll",
        ".dylib",
        ".exe",
        ".gif",
        ".gz",
        ".ico",
        ".jar",
        ".jpeg",
        ".jpg",
        ".pdf",
        ".png",
        ".pyc",
        ".so",
        ".tar",
        ".wasm",
        ".webp",
        ".zip",
    }
)
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
_METADATA_NAMES = frozenset(
    {
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "requirements.txt",
        "tox.ini",
        "pytest.ini",
        "ruff.toml",
        ".ruff.toml",
        "Makefile",
        "justfile",
    }
)
_METADATA_PATHS = frozenset(
    {
        "uv.lock",
        "scripts/check.py",
        ".github/workflows",
    }
)


@dataclass(frozen=True, slots=True)
class _IgnoreRule:
    base: Path
    pattern: str
    negated: bool
    directory_only: bool
    anchored: bool


class FilesystemProjectEvidenceReader(ProjectEvidenceReader):
    """Read an allowlist of metadata and a bounded, shallow project tree."""

    def collect(self, root: Path) -> ProjectEvidence:
        resolved_root = root.resolve()
        files: list[ProjectFile] = []
        file_paths: list[str] = []
        directories: set[str] = set()
        omissions: list[str] = []
        byte_count = 0
        entries_seen = 0
        complete = True

        def walk(
            directory: Path, inherited: tuple[_IgnoreRule, ...], depth: int
        ) -> None:
            nonlocal byte_count, entries_seen, complete
            local_rules = self._read_ignore_rules(
                directory, resolved_root, omissions, byte_count
            )
            if local_rules is None:
                complete = False
                return
            new_rules, ignore_bytes = local_rules
            byte_count += ignore_bytes
            rules = inherited + new_rules
            try:
                with os.scandir(directory) as scan:
                    entries = sorted(
                        scan, key=lambda item: (item.name.casefold(), item.name)
                    )
            except OSError:
                omissions.append(
                    f"Could not read directory: {_relative(directory, resolved_root)}"
                )
                complete = False
                return

            for entry in entries:
                if entries_seen >= MAX_ENTRIES:
                    complete = False
                    omissions.append(f"Stopped at the {MAX_ENTRIES}-entry scan limit.")
                    return
                entries_seen += 1
                path = Path(entry.path)
                relative = _relative(path, resolved_root)
                if _is_sensitive_path(relative) or _is_ignored(path, rules):
                    continue
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name in _SKIP_DIRS:
                            continue
                        if depth < MAX_DEPTH and len(Path(relative).parts) <= 2:
                            directories.add(relative)
                        if depth < MAX_DEPTH:
                            walk(path, rules, depth + 1)
                        else:
                            omissions.append(
                                f"Deeper directory content not inspected (depth limit {MAX_DEPTH}): {relative}"
                            )
                            complete = False
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                except OSError:
                    omissions.append(f"Could not inspect path: {relative}")
                    complete = False
                    continue

                if path.suffix.casefold() in _BINARY_SUFFIXES:
                    continue
                file_paths.append(relative)
                if not _is_metadata(relative):
                    continue
                if len(files) >= MAX_FILES:
                    omissions.append(f"Stopped after {MAX_FILES} metadata files.")
                    complete = False
                    return
                try:
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    omissions.append(f"Could not inspect metadata file: {relative}")
                    complete = False
                    continue
                if size > MAX_BYTES or byte_count + size > MAX_BYTES:
                    omissions.append(
                        f"Skipped metadata beyond the {MAX_BYTES:,}-byte read limit: {relative}"
                    )
                    complete = False
                    continue
                try:
                    with path.open("rb") as stream:
                        raw = stream.read(MAX_BYTES - byte_count + 1)
                    if len(raw) > MAX_BYTES - byte_count:
                        omissions.append(
                            f"Skipped metadata beyond the {MAX_BYTES:,}-byte read limit: {relative}"
                        )
                        complete = False
                        continue
                    content = raw.decode("utf-8")
                except (OSError, UnicodeDecodeError):
                    omissions.append(f"Could not read UTF-8 metadata: {relative}")
                    complete = False
                    continue
                files.append(ProjectFile(relative, content))
                byte_count += len(raw)

        walk(resolved_root, (), 0)
        return ProjectEvidence(
            root=resolved_root,
            files=tuple(files),
            file_paths=tuple(file_paths),
            directories=tuple(sorted(directories)),
            entries_seen=entries_seen,
            complete=complete,
            omissions=tuple(dict.fromkeys(omissions)),
        )

    @staticmethod
    def _read_ignore_rules(
        directory: Path,
        root: Path,
        omissions: list[str],
        bytes_read: int,
    ) -> tuple[tuple[_IgnoreRule, ...], int] | None:
        ignore_file = directory / ".gitignore"
        if not ignore_file.exists():
            return (), 0
        if ignore_file.is_symlink():
            omissions.append(
                f"Skipped directory because ignore rules are a symlink: {_relative(directory, root)}"
            )
            return None
        try:
            size = ignore_file.stat().st_size
            if size > MAX_GITIGNORE_BYTES or bytes_read + size > MAX_BYTES:
                omissions.append(
                    f"Ignored-file rules too large to read: {_relative(ignore_file, root)}"
                )
                return None
            with ignore_file.open("rb") as stream:
                raw_content = stream.read(
                    min(MAX_GITIGNORE_BYTES, MAX_BYTES - bytes_read) + 1
                )
            if (
                len(raw_content) > MAX_GITIGNORE_BYTES
                or len(raw_content) > MAX_BYTES - bytes_read
            ):
                omissions.append(
                    f"Ignored-file rules too large to read: {_relative(ignore_file, root)}"
                )
                return None
            lines = raw_content.decode("utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            omissions.append(
                f"Could not read ignored-file rules: {_relative(ignore_file, root)}"
            )
            return None

        rules: list[_IgnoreRule] = []
        for line in lines:
            pattern = line.strip()
            if not pattern or pattern.startswith("#"):
                continue
            negated = pattern.startswith("!")
            if negated:
                pattern = pattern[1:]
            pattern = pattern.replace("\\#", "#").replace("\\!", "!")
            if not pattern:
                continue
            anchored = pattern.startswith("/")
            if anchored:
                pattern = pattern[1:]
            directory_only = pattern.endswith("/")
            pattern = pattern.rstrip("/")
            if pattern:
                rules.append(
                    _IgnoreRule(directory, pattern, negated, directory_only, anchored)
                )
        return tuple(rules), len(raw_content)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() or "."


def _is_sensitive_path(relative: str) -> bool:
    parts = Path(relative).parts
    for part in parts:
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


def _is_metadata(relative: str) -> bool:
    path = Path(relative)
    return (
        path.name in _METADATA_NAMES
        or relative in _METADATA_PATHS
        or (
            path.parts[:2] == (".github", "workflows")
            and path.suffix in {".yml", ".yaml"}
        )
    )


def _is_ignored(path: Path, rules: tuple[_IgnoreRule, ...]) -> bool:
    ignored = False
    is_dir = path.is_dir()
    for rule in rules:
        try:
            relative = path.relative_to(rule.base).as_posix()
        except ValueError:
            continue
        pattern = rule.pattern
        if "/" in pattern or rule.anchored:
            matches = fnmatch.fnmatchcase(relative, pattern)
        else:
            matches = any(
                fnmatch.fnmatchcase(part, pattern) for part in Path(relative).parts
            )
        if rule.directory_only and not is_dir:
            matches = any(
                fnmatch.fnmatchcase("/".join(Path(relative).parts[:index]), pattern)
                for index in range(1, len(Path(relative).parts))
            )
        if matches:
            ignored = not rule.negated
    return ignored
