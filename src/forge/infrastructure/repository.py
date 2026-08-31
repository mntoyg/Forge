"""Asking git what changed.

This module is the only place in Forge that imports GitPython, so a future
worktree, submodule, or non-git backend is an adapter change and nothing more.

The work is deliberately small: produce the set of line numbers a file has
uncommitted changes on. Everything else about a repository - branches, blame,
history - stays out until something needs it.
"""

import re
from pathlib import Path

import git

from forge.domain.errors import NoChangesError, NotARepositoryError

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
"""Matches ``@@ -14,6 +14,8 @@``, capturing the new-file start and length.

Only the ``+`` side matters: findings cite lines in the file as it is now.
"""

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
"""Git's empty tree object, present in every repository.

Comparing against it makes a repository with no commits behave like one where
everything was just added, without special-casing the diff itself.
"""


class GitRepositoryInspector:
    """Reads uncommitted changes from a git repository.

    Implements :class:`forge.domain.source.RepositoryInspector`.
    """

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace.resolve()

    def changed_lines(self, path: Path) -> frozenset[int]:
        """Implement :meth:`forge.domain.source.RepositoryInspector.changed_lines`."""
        repo = self._open()

        try:
            relative = path.resolve().relative_to(Path(repo.working_tree_dir or ""))
        except ValueError as error:
            raise NoChangesError(
                f"{path} is not inside this repository, so it has no tracked "
                "changes to analyse."
            ) from error

        if _is_untracked(repo, relative):
            # git diff says nothing about a file it has never seen, but a file
            # the user just wrote is the most likely thing they want reviewed.
            # Every line of it is new.
            return _all_lines(path)

        diff = self._diff(repo, relative)
        if not diff.strip():
            raise NoChangesError(
                f"{path} has no uncommitted changes. Drop --diff to analyse the "
                "whole file."
            )

        lines = _added_lines(diff)
        if not lines:
            raise NoChangesError(
                f"{path} has only deletions uncommitted. There are no new lines "
                "to analyse."
            )
        return lines

    def _open(self) -> git.Repo:
        try:
            return git.Repo(self._workspace, search_parent_directories=True)
        except git.InvalidGitRepositoryError as error:
            raise NotARepositoryError(
                f"{self._workspace} is not inside a git repository, so there is "
                "no change to compare against. Drop --diff to analyse the whole "
                "file."
            ) from error
        except git.NoSuchPathError as error:
            raise NotARepositoryError(f"{self._workspace} does not exist.") from error

    @staticmethod
    def _diff(repo: git.Repo, relative: Path) -> str:
        """Diff the working tree against HEAD for one file.

        Staged and unstaged together: to someone mid-change, "what I am about
        to commit" includes both, and making them choose is a distinction the
        tool should not impose.

        A repository with no commits yet has no HEAD, so it is compared against
        git's empty tree instead - every line is then new, which is exactly
        right. The empty tree has a fixed, well-known hash and works on every
        platform, unlike diffing against a null device.
        """
        target = relative.as_posix()
        against = "HEAD" if repo.head.is_valid() else EMPTY_TREE
        return str(repo.git.diff(against, "--unified=0", "--", target))


def _is_untracked(repo: git.Repo, relative: Path) -> bool:
    """Has git never seen this file?

    ``git diff`` reports nothing for an untracked file, so without this check a
    newly written file looks unchanged - which is the opposite of the truth and
    the worst possible answer for the command that exists to review new work.
    """
    target = relative.as_posix()
    return any(entry == target for entry in repo.untracked_files)


def _all_lines(path: Path) -> frozenset[int]:
    """Every line of the file, for a file that is entirely new."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return frozenset(range(1, len(text.splitlines()) + 1))


def _added_lines(diff: str) -> frozenset[int]:
    """Read the new-file line numbers out of a unified diff.

    Walks the hunk headers rather than counting lines from the top, because a
    single file's diff can contain many hunks and each one restates where it
    begins. Deletions are skipped: they have no line in the current file for a
    finding to point at.
    """
    lines: set[int] = set()
    current = 0
    in_hunk = False

    for line in diff.splitlines():
        header = _HUNK_HEADER.match(line)
        if header:
            current = int(header.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.add(current)
            current += 1
        elif line.startswith("-"):
            continue
        elif line.startswith(" "):
            current += 1

    return frozenset(lines)
