"""Asking git what changed.

This module is the only place in Forge that imports GitPython, so a future
worktree, submodule, or non-git backend is an adapter change and nothing more.

The work is deliberately small: which lines of a file have uncommitted changes,
and what history stands behind a line somebody is asking about. Branches, tags,
and remotes stay out until something needs them.
"""

import re
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import git

from forge.domain.errors import NoChangesError, NoHistoryError, NotARepositoryError
from forge.domain.source import ChangeRecord, FileHistory

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
"""Matches ``@@ -14,6 +14,8 @@``, capturing the new-file start and length.

Only the ``+`` side matters: findings cite lines in the file as it is now.
"""

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
"""Git's empty tree object, present in every repository.

Comparing against it makes a repository with no commits behave like one where
everything was just added, without special-casing the diff itself.
"""

HISTORY_WINDOW_DAYS = 90
"""How far back "recently" reaches.

A quarter. Long enough that a file nobody touches reads as zero, short enough
that a count above two or three means the file is genuinely moving now. The
number is arbitrary in the way any window is; what matters is that it is
reported next to the count rather than left for a reader to assume.
"""

_BLAME_HEADER = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)")
"""Matches the header of a --line-porcelain block: sha, old line, new line."""

_AUTHOR_TZ = re.compile(r"^([+-])(\d{2})(\d{2})$")
"""Matches a git timezone offset, ``+0700``."""

_UNCOMMITTED = "0" * 40
"""The sha git blame gives a line that is not committed yet."""

_MAX_AUTHOR_LENGTH = 60
"""Enough for a real name; short enough that no name can push a finding off."""


class GitRepositoryInspector:
    """Reads uncommitted changes from a git repository.

    Implements :class:`forge.domain.source.RepositoryInspector`.
    """

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace.resolve()

    def changed_lines(self, path: Path) -> frozenset[int]:
        """Implement :meth:`forge.domain.source.RepositoryInspector.changed_lines`."""
        repo = self._open()

        relative = _relative_to(repo, path)
        if relative is None:
            raise NoChangesError(
                f"{path} is not inside this repository, so it has no tracked "
                "changes to analyse."
            )

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

    def history(self, path: Path, lines: frozenset[int]) -> FileHistory:
        """Implement :meth:`forge.domain.source.RepositoryInspector.history`."""
        repo = self._open()

        relative = _relative_to(repo, path)
        if relative is None:
            raise NoHistoryError(
                f"{path} is not inside this repository, so it has no history here."
            )
        if not repo.head.is_valid() or _is_untracked(repo, relative):
            raise NoHistoryError(
                f"{path} has never been committed, so there is no history for it."
            )

        blamed = _blame(repo, relative)
        return FileHistory(
            recent_commits=_commits_since(repo, relative, HISTORY_WINDOW_DAYS),
            window_days=HISTORY_WINDOW_DAYS,
            records=tuple(blamed[line] for line in sorted(lines) if line in blamed),
        )

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


def _relative_to(repo: git.Repo, path: Path) -> Path | None:
    """The path as git names it, or ``None`` if it lies outside the repository.

    ``None`` rather than an exception because the two callers report the same
    situation differently: one is answering "what changed here", the other
    "what stands behind this line", and the sentence a user should read is not
    the same.
    """
    try:
        return path.resolve().relative_to(Path(repo.working_tree_dir or ""))
    except ValueError:
        return None


def _blame(repo: git.Repo, relative: Path) -> dict[int, ChangeRecord]:
    """Ask git who last touched each line of the file as it stands on disk.

    Blamed with no revision, which blames the working tree. Line numbers then
    mean what they mean to a finding. Blaming ``HEAD`` instead would be subtly
    wrong for exactly the file this is most often run on - one that has just
    been edited - because a single uncommitted insertion shifts every line
    below it, and every annotation with them.
    """
    porcelain = str(repo.git.blame("--line-porcelain", "--", relative.as_posix()))
    return _parse_blame(porcelain)


def _parse_blame(porcelain: str) -> dict[int, ChangeRecord]:
    """Read `git blame --line-porcelain` into one record per committed line.

    The format repeats a whole header block per line: a ``<sha> <old> <new>``
    line, then ``key value`` headers, then the content prefixed with a tab.
    That repetition is the reason for `--line-porcelain` over the shorter
    `--porcelain`, which omits the headers of a commit it has already
    described - and would turn this function into a cache, with the bug a cache
    eventually has.

    A line whose sha is all zeros is not committed yet and gets no record; see
    :class:`forge.domain.source.ChangeRecord`.
    """
    records: dict[int, ChangeRecord] = {}
    sha = ""
    number = 0
    author = ""
    timestamp = 0
    offset = "+0000"

    for row in porcelain.splitlines():
        header = _BLAME_HEADER.match(row)
        if header:
            sha, number = header.group(1), int(header.group(2))
            author, timestamp, offset = "", 0, "+0000"
        elif row.startswith("author "):
            author = _clean(row.removeprefix("author "))
        elif row.startswith("author-time "):
            timestamp = int(row.removeprefix("author-time ").strip())
        elif row.startswith("author-tz "):
            offset = row.removeprefix("author-tz ").strip()
        elif row.startswith("\t") and sha and sha != _UNCOMMITTED:
            records[number] = ChangeRecord(
                line=number,
                commit=sha[:7],
                author=author or "unknown",
                changed_on=_authored_on(timestamp, offset),
            )

    return records


def _authored_on(timestamp: int, offset: str) -> date:
    """The date the author saw on their own clock when they made the commit.

    Git records the instant in UTC and the author's offset beside it. Reading
    the UTC date alone reports the wrong day for anyone who commits in the
    evening east of Greenwich - a small lie, in the one field a reader uses to
    judge how long ago something happened.
    """
    match = _AUTHOR_TZ.match(offset)
    if match is None:
        return datetime.fromtimestamp(timestamp, tz=UTC).date()

    shift = timedelta(hours=int(match.group(2)), minutes=int(match.group(3)))
    if shift >= timedelta(hours=24):
        # Not a real offset. Trust the instant over the annotation.
        return datetime.fromtimestamp(timestamp, tz=UTC).date()

    signed = -shift if match.group(1) == "-" else shift
    return datetime.fromtimestamp(timestamp, tz=timezone(signed)).date()


def _commits_since(repo: git.Repo, relative: Path, days: int) -> int:
    """How many commits touched this file inside the window.

    A count rather than a list. The signal a reader acts on is "this file has
    been moving lately"; printing nine commit subjects to say so would bury the
    findings the run exists to show.
    """
    output = str(
        repo.git.log(f"--since={days}.days", "--format=%H", "--", relative.as_posix())
    )
    return len(output.split())


def _clean(value: str) -> str:
    """Strip what a name must not carry into a terminal.

    An author name is whatever somebody put in their git config, which makes it
    the same class of untrusted input as a source file - and unlike a source
    file it is printed rather than analysed. Control characters go, and the
    length is bounded, because the finding is what the output is for.
    """
    printable = "".join(character for character in value if character.isprintable())
    return printable.strip()[:_MAX_AUTHOR_LENGTH]


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
