"""The git adapter, against real repositories built in a temporary directory.

Integration because it crosses a real boundary. Each test constructs the
repository state it needs rather than depending on the state of the repository
the tests happen to be running in - that would make the suite pass or fail
depending on whether the developer had uncommitted work.
"""

from pathlib import Path

import git
import pytest

from forge.domain.errors import NoChangesError, NotARepositoryError, RepositoryError
from forge.infrastructure.repository import GitRepositoryInspector


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
