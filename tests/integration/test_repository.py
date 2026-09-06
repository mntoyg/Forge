"""The git adapter, against real repositories built in a temporary directory.

Integration because it crosses a real boundary. Each test constructs the
repository state it needs rather than depending on the state of the repository
the tests happen to be running in - that would make the suite pass or fail
depending on whether the developer had uncommitted work.
"""

from datetime import date
from pathlib import Path

import git
import pytest

from forge.domain.errors import (
    NoChangesError,
    NoHistoryError,
    NotARepositoryError,
    RepositoryError,
)
from forge.infrastructure.repository import (
    HISTORY_WINDOW_DAYS,
    GitRepositoryInspector,
)


@pytest.fixture
def repo(tmp_path: Path) -> git.Repo:
    """A repository with one committed file, `app.py`, of four lines."""
    repository = git.Repo.init(tmp_path)
    with repository.config_writer() as config:
        config.set_value("user", "name", "Test")
        config.set_value("user", "email", "test@example.invalid")

    (tmp_path / "app.py").write_bytes(b"one = 1\ntwo = 2\nthree = 3\nfour = 4\n")
    repository.index.add(["app.py"])
    repository.index.commit("initial")
    return repository


def _inspect(repo: git.Repo) -> GitRepositoryInspector:
    return GitRepositoryInspector(Path(str(repo.working_tree_dir)))


# --- what counts as changed -------------------------------------------------


@pytest.mark.integration
def test_an_edited_line_is_reported(repo: git.Repo) -> None:
    root = Path(str(repo.working_tree_dir))
    (root / "app.py").write_bytes(b"one = 1\ntwo = CHANGED\nthree = 3\nfour = 4\n")

    assert _inspect(repo).changed_lines(Path("app.py")) == frozenset({2})


@pytest.mark.integration
def test_appended_lines_are_reported(repo: git.Repo) -> None:
    root = Path(str(repo.working_tree_dir))
    (root / "app.py").write_bytes(
        b"one = 1\ntwo = 2\nthree = 3\nfour = 4\nfive = 5\nsix = 6\n"
    )

    assert _inspect(repo).changed_lines(Path("app.py")) == frozenset({5, 6})


@pytest.mark.integration
def test_an_untracked_file_counts_entirely_as_new(repo: git.Repo) -> None:
    """git diff says nothing about a file it has never seen.

    Without special handling a file the user just wrote looks unchanged, which
    is the worst possible answer from the command that exists to review new
    work.
    """
    root = Path(str(repo.working_tree_dir))
    (root / "brand_new.py").write_bytes(b"a = 1\nb = 2\nc = 3\n")

    assert _inspect(repo).changed_lines(Path("brand_new.py")) == frozenset({1, 2, 3})


@pytest.mark.integration
def test_staged_and_unstaged_changes_are_both_included(repo: git.Repo) -> None:
    """ "What I am about to commit" means both, to someone mid-change."""
    root = Path(str(repo.working_tree_dir))
    (root / "app.py").write_bytes(b"one = STAGED\ntwo = 2\nthree = 3\nfour = 4\n")
    repo.index.add(["app.py"])
    (root / "app.py").write_bytes(
        b"one = STAGED\ntwo = 2\nthree = 3\nfour = UNSTAGED\n"
    )

    assert _inspect(repo).changed_lines(Path("app.py")) == frozenset({1, 4})


@pytest.mark.integration
def test_deletions_alone_are_reported_as_nothing_to_review(repo: git.Repo) -> None:
    """A deleted line has no number in the current file to cite."""
    root = Path(str(repo.working_tree_dir))
    (root / "app.py").write_bytes(b"one = 1\ntwo = 2\n")

    with pytest.raises(NoChangesError, match="only deletions"):
        _inspect(repo).changed_lines(Path("app.py"))


@pytest.mark.integration
def test_a_change_in_two_places_reports_both(repo: git.Repo) -> None:
    """Hunk headers restate the position, so each must be read separately."""
    root = Path(str(repo.working_tree_dir))
    (root / "app.py").write_bytes(
        b"one = EDITED\ntwo = 2\nthree = 3\nfour = ALSO_EDITED\n"
    )

    assert _inspect(repo).changed_lines(Path("app.py")) == frozenset({1, 4})


# --- when there is nothing to answer ----------------------------------------


@pytest.mark.integration
def test_an_unchanged_file_says_so_and_suggests_the_alternative(
    repo: git.Repo,
) -> None:
    with pytest.raises(NoChangesError) as caught:
        _inspect(repo).changed_lines(Path("app.py"))

    assert "--diff" in str(caught.value)


@pytest.mark.integration
def test_outside_a_repository_says_so_plainly(tmp_path: Path) -> None:
    """Not being in a repository is a normal state, not a fault."""
    outside = tmp_path / "plain_directory"
    outside.mkdir()
    (outside / "app.py").write_bytes(b"a = 1\n")

    with pytest.raises(NotARepositoryError) as caught:
        GitRepositoryInspector(outside).changed_lines(Path("app.py"))

    message = str(caught.value)
    assert "not inside a git repository" in message
    assert "--diff" in message


@pytest.mark.integration
def test_a_file_outside_the_repository_is_reported(
    repo: git.Repo, tmp_path: Path
) -> None:
    elsewhere = tmp_path.parent / "stray.py"
    elsewhere.write_bytes(b"a = 1\n")

    with pytest.raises(RepositoryError):
        _inspect(repo).changed_lines(elsewhere)


@pytest.mark.integration
def test_a_repository_with_no_commits_treats_everything_as_new(
    tmp_path: Path,
) -> None:
    """There is no HEAD to compare against, so the empty tree stands in."""
    repository = git.Repo.init(tmp_path)
    (tmp_path / "app.py").write_bytes(b"a = 1\nb = 2\n")
    repository.index.add(["app.py"])

    inspector = GitRepositoryInspector(tmp_path)

    assert inspector.changed_lines(Path("app.py")) == frozenset({1, 2})


# --- the contract -----------------------------------------------------------


@pytest.mark.integration
def test_every_refusal_is_a_repository_error(repo: git.Repo, tmp_path: Path) -> None:
    """One base class, so the CLI maps them all to exit code 2 at once."""
    outside = tmp_path.parent / "not_a_repo_dir"
    outside.mkdir(exist_ok=True)

    with pytest.raises(RepositoryError):
        _inspect(repo).changed_lines(Path("app.py"))
    with pytest.raises(RepositoryError):
        GitRepositoryInspector(outside).changed_lines(Path("anything.py"))


@pytest.mark.integration
def test_nothing_is_written_while_inspecting(repo: git.Repo) -> None:
    """FR-3.7: Forge must not modify any file."""
    root = Path(str(repo.working_tree_dir))
    (root / "app.py").write_bytes(b"one = CHANGED\ntwo = 2\nthree = 3\nfour = 4\n")
    before = (root / "app.py").read_bytes()

    _inspect(repo).changed_lines(Path("app.py"))

    assert (root / "app.py").read_bytes() == before


# --- what history says ------------------------------------------------------


@pytest.mark.integration
def test_a_committed_line_names_who_last_changed_it(repo: git.Repo) -> None:
    history = _inspect(repo).history(Path("app.py"), frozenset({2}))

    record = history.at(2)

    assert record is not None
    assert record.author == "Test"
    assert record.commit == repo.head.commit.hexsha[:7]


@pytest.mark.integration
def test_only_the_lines_that_were_asked_about_come_back(repo: git.Repo) -> None:
    """The cost of the annotation stays proportional to the findings."""
    history = _inspect(repo).history(Path("app.py"), frozenset({1, 3}))

    assert [record.line for record in history.records] == [1, 3]


@pytest.mark.integration
def test_an_uncommitted_line_has_no_record(repo: git.Repo) -> None:
    """Git can name no commit for it, and naming one anyway would be a lie."""
    root = Path(str(repo.working_tree_dir))
    (root / "app.py").write_bytes(b"one = 1\ntwo = MINE\nthree = 3\nfour = 4\n")

    history = _inspect(repo).history(Path("app.py"), frozenset({1, 2}))

    assert history.at(2) is None
    assert history.at(1) is not None


@pytest.mark.integration
def test_line_numbers_follow_the_working_tree_not_head(repo: git.Repo) -> None:
    """An uncommitted insertion shifts every line below it.

    Blaming HEAD would annotate the wrong lines for exactly the file this is
    most often run on: one that has just been edited.
    """
    root = Path(str(repo.working_tree_dir))
    (root / "app.py").write_bytes(
        b"inserted = 0\none = 1\ntwo = 2\nthree = 3\nfour = 4\n"
    )

    history = _inspect(repo).history(Path("app.py"), frozenset({1, 2}))

    assert history.at(1) is None
    assert history.at(2) is not None


@pytest.mark.integration
def test_the_date_is_the_one_the_author_saw(tmp_path: Path) -> None:
    """Git stores the instant in UTC and the offset beside it.

    01:00 on the 15th in +0700 is still the 14th in UTC. Reporting the 14th
    would be wrong in the one field a reader uses to judge how long ago
    something happened.
    """
    repository = git.Repo.init(tmp_path)
    (tmp_path / "app.py").write_bytes(b"one = 1\n")
    repository.index.add(["app.py"])
    repository.index.commit(
        "initial",
        author=git.Actor("A U Thor", "author@example.invalid"),
        # The committer is named too. Left out, GitPython invents one from
        # whatever git config the machine happens to have - the kind of
        # dependency that makes a suite pass here and fail on a fresh runner.
        committer=git.Actor("Test", "test@example.invalid"),
        author_date="2026-01-15 01:00:00 +0700",
    )

    history = GitRepositoryInspector(tmp_path).history(Path("app.py"), frozenset({1}))

    record = history.at(1)
    assert record is not None
    assert record.changed_on == date(2026, 1, 15)


@pytest.mark.integration
def test_a_control_character_in_an_author_name_never_reaches_the_output(
    tmp_path: Path,
) -> None:
    """A name is whatever somebody put in their git config, and it is printed."""
    repository = git.Repo.init(tmp_path)
    (tmp_path / "app.py").write_bytes(b"one = 1\n")
    repository.index.add(["app.py"])
    repository.index.commit(
        "initial",
        author=git.Actor("Bad\x07Name", "bad@example.invalid"),
        committer=git.Actor("Test", "test@example.invalid"),
    )

    history = GitRepositoryInspector(tmp_path).history(Path("app.py"), frozenset({1}))

    record = history.at(1)
    assert record is not None
    assert record.author == "BadName"


# --- how much the file has been moving --------------------------------------


@pytest.mark.integration
def test_recent_commits_counts_what_touched_this_file(repo: git.Repo) -> None:
    root = Path(str(repo.working_tree_dir))
    for text_line in (b"one = 2\n", b"one = 3\n"):
        (root / "app.py").write_bytes(text_line)
        repo.index.add(["app.py"])
        repo.index.commit("edit")

    history = _inspect(repo).history(Path("app.py"), frozenset({1}))

    assert history.recent_commits == 3


@pytest.mark.integration
def test_a_commit_to_another_file_is_not_counted(repo: git.Repo) -> None:
    """Churn is a property of the file being analysed, not of the repository."""
    root = Path(str(repo.working_tree_dir))
    (root / "other.py").write_bytes(b"x = 1\n")
    repo.index.add(["other.py"])
    repo.index.commit("unrelated")

    history = _inspect(repo).history(Path("app.py"), frozenset({1}))

    assert history.recent_commits == 1


@pytest.mark.integration
def test_the_window_is_reported_alongside_the_count(repo: git.Repo) -> None:
    """A count with no period attached is a number nobody can read."""
    history = _inspect(repo).history(Path("app.py"), frozenset({1}))

    assert history.window_days == HISTORY_WINDOW_DAYS


# --- when there is no history to give ---------------------------------------


@pytest.mark.integration
def test_an_untracked_file_has_no_history(repo: git.Repo) -> None:
    """It is not a failure. The caller degrades to showing none."""
    root = Path(str(repo.working_tree_dir))
    (root / "brand_new.py").write_bytes(b"a = 1\n")

    with pytest.raises(NoHistoryError, match="never been committed"):
        _inspect(repo).history(Path("brand_new.py"), frozenset({1}))


@pytest.mark.integration
def test_a_repository_with_no_commits_has_no_history(tmp_path: Path) -> None:
    repository = git.Repo.init(tmp_path)
    (tmp_path / "app.py").write_bytes(b"a = 1\n")
    repository.index.add(["app.py"])

    with pytest.raises(NoHistoryError):
        GitRepositoryInspector(tmp_path).history(Path("app.py"), frozenset({1}))


@pytest.mark.integration
def test_a_file_outside_the_repository_has_no_history(
    repo: git.Repo, tmp_path: Path
) -> None:
    elsewhere = tmp_path.parent / "stray_history.py"
    elsewhere.write_bytes(b"a = 1\n")

    with pytest.raises(NoHistoryError):
        _inspect(repo).history(elsewhere, frozenset({1}))


@pytest.mark.integration
def test_history_outside_a_repository_says_so(tmp_path: Path) -> None:
    outside = tmp_path / "plain_directory_for_history"
    outside.mkdir()
    (outside / "app.py").write_bytes(b"a = 1\n")

    with pytest.raises(NotARepositoryError):
        GitRepositoryInspector(outside).history(Path("app.py"), frozenset({1}))


@pytest.mark.integration
def test_nothing_is_written_while_reading_history(repo: git.Repo) -> None:
    """FR-3.7: Forge must not modify any file."""
    root = Path(str(repo.working_tree_dir))
    before = (root / "app.py").read_bytes()

    _inspect(repo).history(Path("app.py"), frozenset({1, 2, 3, 4}))

    assert (root / "app.py").read_bytes() == before


# --- a file git was told to ignore ------------------------------------------


@pytest.fixture
def ignoring_repo(tmp_path: Path) -> git.Repo:
    """A repository that ignores `vendor/`, holding a file inside it."""
    repository = git.Repo.init(tmp_path)
    with repository.config_writer() as config:
        config.set_value("user", "name", "Test")
        config.set_value("user", "email", "test@example.invalid")

    (tmp_path / ".gitignore").write_bytes(b"vendor/\n")
    repository.index.add([".gitignore"])
    repository.index.commit("ignore vendor")

    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "lib.py").write_bytes(b"a = 1\nb = 2\n")
    return repository


@pytest.mark.integration
def test_an_ignored_file_has_no_history_rather_than_a_traceback(
    ignoring_repo: git.Repo,
) -> None:
    """An ignored file is absent from untracked_files, so nothing else notices.

    git blame then fails on a path it has never heard of, and before this was
    handled the GitPython exception escaped the adapter and reached the user as
    a traceback - on a run whose provider call had already been paid for.
    """
    with pytest.raises(NoHistoryError, match="ignores"):
        _inspect(ignoring_repo).history(Path("vendor/lib.py"), frozenset({1}))


@pytest.mark.integration
def test_an_ignored_file_is_not_reported_as_merely_unchanged(
    ignoring_repo: git.Repo,
) -> None:
    """It produces an empty diff and no error, which says nothing useful.

    "No uncommitted changes" is true in the narrowest sense and useless to
    somebody looking at a file full of edits they just made.
    """
    with pytest.raises(NoChangesError) as caught:
        _inspect(ignoring_repo).changed_lines(Path("vendor/lib.py"))

    message = str(caught.value)
    assert "ignores" in message
    assert "--diff" in message


@pytest.mark.integration
def test_no_gitpython_exception_reaches_a_caller(ignoring_repo: git.Repo) -> None:
    """The boundary rule, pinned: only this module may know GitPython exists."""
    inspector = _inspect(ignoring_repo)

    for call in (
        lambda: inspector.history(Path("vendor/lib.py"), frozenset({1})),
        lambda: inspector.changed_lines(Path("vendor/lib.py")),
    ):
        with pytest.raises(RepositoryError):
            call()
