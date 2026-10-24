"""Read a bounded command's current change set through GitPython."""

from os.path import normpath
from pathlib import Path

import git

from forge.domain.errors import NoChangesError, NotARepositoryError
from forge.domain.review import (
    ChangeKind,
    ChangeOmission,
    ChangeSet,
    OmissionReason,
    ReviewFile,
)
from forge.infrastructure.repository import EMPTY_TREE, _added_lines


class GitChangeSetReader:
    """Collect staged, unstaged, and non-ignored untracked files read-only."""

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace.resolve()

    def read(self, paths: tuple[Path, ...] = ()) -> ChangeSet:
        """Build one immutable current snapshot, or explain unusable scope."""
        repo = self._open()
        root = Path(repo.working_tree_dir or "").resolve()
        candidates = self._changes(repo)
        requested = self._requested_paths(paths, root)
        try:
            candidates.update(
                {
                    ("A", path.as_posix(), None)
                    for path in (Path(item) for item in repo.untracked_files)
                }
            )
        except git.GitCommandError as error:
            raise NoChangesError("Git could not list untracked files.") from error
        candidates.update(
            {("I", path, None) for path in _ignored_untracked(repo, requested)}
        )

        selected = sorted(
            (
                change
                for change in candidates
                if not requested
                or any(
                    _matches_scope(change[1], change[2], scope) for scope in requested
                )
            ),
            key=lambda change: (change[1].casefold(), change[1], change[2] or ""),
        )
        if not selected:
            raise NoChangesError("No changed files match the requested review scope.")

        files: list[ReviewFile] = []
        omissions: list[ChangeOmission] = []
        for status, current_name, previous_name in selected:
            current = Path(current_name)
            previous = Path(previous_name) if previous_name else None
            if status == "D":
                omissions.append(
                    ChangeOmission(current, OmissionReason.DELETED, previous)
                )
                continue
            if status == "T":
                omissions.append(
                    ChangeOmission(current, OmissionReason.UNSUPPORTED, previous)
                )
                continue
            if status == "I":
                omissions.append(ChangeOmission(current, OmissionReason.IGNORED))
                continue

            source_path = root / current
            if _has_symlink_component(root, current):
                omissions.append(
                    ChangeOmission(current, OmissionReason.SYMLINK, previous)
                )
                continue

            try:
                raw = source_path.read_bytes()
            except OSError as error:
                raise NoChangesError(
                    f"Cannot read changed file {current.as_posix()}: {error}"
                ) from error

            if b"\0" in raw:
                omissions.append(
                    ChangeOmission(current, OmissionReason.BINARY, previous)
                )
                continue
            try:
                content = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeDecodeError:
                omissions.append(
                    ChangeOmission(current, OmissionReason.INVALID_TEXT, previous)
                )
                continue

            line_set = (
                frozenset(range(1, len(content.splitlines()) + 1))
                if status == "A"
                else _added_lines(_diff_for_path(repo, current, previous))
            )
            files.append(
                ReviewFile(
                    path=current,
                    content=content,
                    changed_lines=line_set,
                    kind=_kind(status),
                    previous_path=previous,
                )
            )

        if not files and not omissions:
            raise NoChangesError("No changed files match the requested review scope.")
        return ChangeSet(root=root, files=tuple(files), omissions=tuple(omissions))

    def _open(self) -> git.Repo:
        try:
            return git.Repo(self._workspace, search_parent_directories=True)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError) as error:
            raise NotARepositoryError(
                f"{self._workspace} is not inside a git worktree."
            ) from error

    def _requested_paths(self, paths: tuple[Path, ...], root: Path) -> tuple[Path, ...]:
        scopes: list[Path] = []
        for path in paths:
            candidate = path if path.is_absolute() else self._workspace / path
            normalized = Path(normpath(candidate))
            try:
                normalized.relative_to(root)
            except ValueError as error:
                raise NoChangesError(
                    f"Requested path {path} is outside the Git worktree."
                ) from error
            scopes.append(normalized.relative_to(root))
        return tuple(scopes)

    @staticmethod
    def _changes(repo: git.Repo) -> set[tuple[str, str, str | None]]:
        against = "HEAD" if repo.head.is_valid() else EMPTY_TREE
        try:
            output = str(
                repo.git.diff(against, "--name-status", "--find-renames", "-z")
            )
        except git.GitCommandError as error:
            raise NoChangesError("Git could not collect changed paths.") from error
        fields = output.split("\0")
        changes: set[tuple[str, str, str | None]] = set()
        index = 0
        while index < len(fields) and fields[index]:
            status = fields[index]
            index += 1
            if status.startswith(("R", "C")):
                previous, current = fields[index], fields[index + 1]
                index += 2
                changes.add(("R", current, previous))
            else:
                current = fields[index]
                index += 1
                if status[:1] in {"A", "M", "D", "T"}:
                    changes.add((status[:1], current, None))
        return changes


def _diff_for_path(repo: git.Repo, path: Path, previous: Path | None) -> str:
    """Get current-side line changes, including staged and unstaged edits."""
    against = "HEAD" if repo.head.is_valid() else EMPTY_TREE
    paths = [path.as_posix()]
    if previous is not None:
        paths.append(previous.as_posix())
    try:
        return str(
            repo.git.diff(against, "--unified=0", "--find-renames", "--", *paths)
        )
    except git.GitCommandError as error:
        raise NoChangesError(f"Git could not compare changed file {path}.") from error


def _ignored_untracked(repo: git.Repo, scopes: tuple[Path, ...]) -> tuple[str, ...]:
    """List ignored paths without reading their contents."""
    options = ["--others", "--ignored", "--exclude-standard"]
    if not scopes:
        options.append("--directory")
    options.append("-z")
    if scopes:
        options.extend(("--", *(scope.as_posix() for scope in scopes)))
    try:
        output = str(repo.git.ls_files(*options))
    except git.GitCommandError as error:
        raise NoChangesError("Git could not list ignored untracked paths.") from error
    return tuple(path for path in output.split("\0") if path)


def _kind(status: str) -> ChangeKind:
    return {
        "A": ChangeKind.ADDED,
        "M": ChangeKind.MODIFIED,
        "R": ChangeKind.RENAMED,
    }[status]


def _matches_scope(current: str, previous: str | None, scope: Path) -> bool:
    """Match an explicit file or directory against a current or old name."""
    return any(
        path == scope or scope in path.parents
        for path in (Path(current), Path(previous) if previous else Path(current))
    )


def _has_symlink_component(root: Path, relative: Path) -> bool:
    """Refuse links anywhere along a changed path without following them."""
    current = root
    for part in relative.parts:
        current /= part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False
