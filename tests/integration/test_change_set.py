"""The review change-set adapter against isolated temporary Git repositories."""

from pathlib import Path

import git
import pytest

from forge.domain.errors import NoChangesError
from forge.domain.review import ChangeKind, OmissionReason
from forge.infrastructure.change_set import GitChangeSetReader


@pytest.fixture
def repository(tmp_path: Path) -> git.Repo:
    """A small committed worktree with a tracked source file."""
    repo = git.Repo.init(tmp_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test")
        config.set_value("user", "email", "test@example.invalid")
    (tmp_path / "app.py").write_bytes(b"one = 1\ntwo = 2\nthree = 3\n")
    repo.index.add(["app.py"])
    repo.index.commit("initial")
    return repo


def _reader(repo: git.Repo) -> GitChangeSetReader:
    return GitChangeSetReader(Path(str(repo.working_tree_dir)))


@pytest.mark.integration
def test_review_snapshot_combines_staged_and_unstaged_lines(
    repository: git.Repo,
) -> None:
    root = Path(str(repository.working_tree_dir))
    (root / "app.py").write_bytes(b"one = staged\ntwo = 2\nthree = 3\n")
    repository.index.add(["app.py"])
    (root / "app.py").write_bytes(b"one = staged\ntwo = 2\nthree = unstaged\n")

    change_set = _reader(repository).read()

    assert len(change_set.files) == 1
    source = change_set.files[0]
    assert source.content == "one = staged\ntwo = 2\nthree = unstaged\n"
    assert source.changed_lines == frozenset({1, 3})
    assert source.kind is ChangeKind.MODIFIED


@pytest.mark.integration
def test_review_snapshot_includes_non_ignored_untracked_files(
    repository: git.Repo,
) -> None:
    root = Path(str(repository.working_tree_dir))
    (root / "brand_new.py").write_bytes(b"first = 1\nsecond = 2\n")

    change_set = _reader(repository).read()

    source = next(
        item for item in change_set.files if item.path == Path("brand_new.py")
    )
    assert source.kind is ChangeKind.ADDED
    assert source.changed_lines == frozenset({1, 2})


@pytest.mark.integration
def test_review_snapshot_recognizes_a_rename_and_keeps_the_current_path(
    repository: git.Repo,
) -> None:
    root = Path(str(repository.working_tree_dir))
    repository.git.mv("app.py", "renamed.py")
    (root / "renamed.py").write_bytes(b"one = 1\ntwo = changed\nthree = 3\n")

    change_set = _reader(repository).read()

    assert len(change_set.files) == 1
    source = change_set.files[0]
    assert source.path == Path("renamed.py")
    assert source.previous_path == Path("app.py")
    assert source.kind is ChangeKind.RENAMED
    assert source.changed_lines == frozenset({2})


@pytest.mark.integration
def test_review_snapshot_reports_deleted_files_without_reading_old_contents(
    repository: git.Repo,
) -> None:
    (Path(str(repository.working_tree_dir)) / "app.py").unlink()

    change_set = _reader(repository).read()

    assert change_set.files == ()
    assert len(change_set.omissions) == 1
    assert change_set.omissions[0].path == Path("app.py")
    assert change_set.omissions[0].reason is OmissionReason.DELETED


@pytest.mark.integration
def test_review_snapshot_omits_binary_files(repository: git.Repo) -> None:
    binary_path = Path(str(repository.working_tree_dir)) / "image.bin"
    binary_path.write_bytes(b"header\x00payload")

    change_set = _reader(repository).read()

    omission = next(
        item for item in change_set.omissions if item.path == Path("image.bin")
    )
    assert omission.reason is OmissionReason.BINARY
    assert all(item.path != Path("image.bin") for item in change_set.files)


@pytest.mark.integration
def test_review_snapshot_omits_invalid_utf8(repository: git.Repo) -> None:
    source_path = Path(str(repository.working_tree_dir)) / "invalid.txt"
    source_path.write_bytes(b"\xff\xfe")

    change_set = _reader(repository).read()

    omission = next(
        item for item in change_set.omissions if item.path == Path("invalid.txt")
    )
    assert omission.reason is OmissionReason.INVALID_TEXT


@pytest.mark.integration
def test_review_snapshot_reports_ignored_paths_without_reading_them(
    repository: git.Repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(str(repository.working_tree_dir))
    (root / ".gitignore").write_bytes(b"vendor/\n")
    repository.index.add([".gitignore"])
    repository.index.commit("ignore vendor")
    ignored_directory = root / "vendor"
    ignored_directory.mkdir()
    ignored_file = ignored_directory / "secret.py"
    ignored_file.write_bytes(b"must not be read\n")
    original_read_bytes = Path.read_bytes

    def reject_ignored_path(path: Path) -> bytes:
        if path == ignored_file:
            raise AssertionError("ignored file contents must not be read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_ignored_path)

    change_set = _reader(repository).read()

    omission = next(
        item for item in change_set.omissions if item.path == Path("vendor")
    )
    assert omission.reason is OmissionReason.IGNORED


@pytest.mark.integration
def test_explicit_ignored_file_scope_reports_the_exact_path(
    repository: git.Repo,
) -> None:
    root = Path(str(repository.working_tree_dir))
    (root / ".gitignore").write_bytes(b"*.secret\n")
    repository.index.add([".gitignore"])
    repository.index.commit("ignore secret files")
    (root / "credential.secret").write_bytes(b"not read\n")

    change_set = _reader(repository).read((Path("credential.secret"),))

    assert change_set.files == ()
    assert len(change_set.omissions) == 1
    assert change_set.omissions[0].path == Path("credential.secret")
    assert change_set.omissions[0].reason is OmissionReason.IGNORED


@pytest.mark.integration
def test_review_snapshot_omits_symlinks(repository: git.Repo, tmp_path: Path) -> None:
    root = Path(str(repository.working_tree_dir))
    target = tmp_path / "outside.py"
    target.write_bytes(b"secret = 'not read'\n")
    link = root / "linked.py"
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    change_set = _reader(repository).read()

    omission = next(
        item for item in change_set.omissions if item.path == Path("linked.py")
    )
    assert omission.reason is OmissionReason.SYMLINK
    assert all(item.path != Path("linked.py") for item in change_set.files)


@pytest.mark.integration
def test_explicit_directory_narrows_review_scope(repository: git.Repo) -> None:
    root = Path(str(repository.working_tree_dir))
    (root / "app.py").write_bytes(b"one = changed\ntwo = 2\nthree = 3\n")
    (root / "other").mkdir()
    (root / "other" / "new.py").write_bytes(b"new = True\n")

    change_set = _reader(repository).read((Path("other"),))

    assert [item.path for item in change_set.files] == [Path("other/new.py")]


@pytest.mark.integration
def test_review_scope_cannot_escape_the_worktree(repository: git.Repo) -> None:
    with pytest.raises(NoChangesError, match="outside the Git worktree"):
        _reader(repository).read((Path("..") / "outside.py",))
