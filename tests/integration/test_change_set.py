"""The review change-set adapter against isolated temporary Git repositories."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import git
import pytest

from forge.application.review import ReviewChanges
from forge.domain.errors import (
    NoChangesError,
    ReviewSnapshotChangedError,
    ReviewTooLargeError,
)
from forge.domain.review import MAX_REVIEW_REQUEST_BYTES, ChangeKind, OmissionReason
from forge.infrastructure import change_set as change_set_module
from forge.infrastructure.change_set import GitChangeSetReader
from tests.support.fakes import FakeProvider


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
@pytest.mark.parametrize("sizes", [(MAX_REVIEW_REQUEST_BYTES + 1,), (8_001, 8_000)])
def test_over_budget_scope_is_refused_before_source_reads_or_diff(
    repository: git.Repo,
    monkeypatch: pytest.MonkeyPatch,
    sizes: tuple[int, ...],
) -> None:
    root = Path(str(repository.working_tree_dir))
    tracked = root / "app.py"
    tracked.write_bytes(b"x" * sizes[0])
    paths = [tracked]
    for index, size in enumerate(sizes[1:]):
        path = root / f"extra-{index}.py"
        path.write_bytes(b"x" * size)
        paths.append(path)

    read_attempts: list[Path] = []
    diff_attempts: list[Path] = []

    def reject_read(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path in paths:
            read_attempts.append(path)
            raise AssertionError("over-budget source must not be read")
        return original_open(path, *args, **kwargs)

    def reject_diff(repo: git.Repo, path: Path, previous: Path | None) -> str:
        diff_attempts.append(path)
        raise AssertionError("over-budget scope must not create a diff")

    original_open = Path.open
    monkeypatch.setattr(Path, "open", reject_read)
    monkeypatch.setattr(change_set_module, "_diff_for_path", reject_diff)
    provider = FakeProvider()
    review = ReviewChanges(_reader(repository), provider, model="fake-model")

    with pytest.raises(ReviewTooLargeError, match="preflight budget"):
        review.prepare()

    assert read_attempts == []
    assert diff_attempts == []
    assert provider.call_count == 0


@pytest.mark.integration
def test_file_growth_after_preflight_is_refused_without_truncation(
    repository: git.Repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(str(repository.working_tree_dir))
    tracked = root / "app.py"
    tracked.write_bytes(b"x" * (MAX_REVIEW_REQUEST_BYTES + 1))
    original_stat = Path.stat
    diff_attempts: list[Path] = []

    def report_small_size(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == tracked:
            return SimpleNamespace(
                st_size=1,
                st_mode=original_stat(path, *args, **kwargs).st_mode,
            )
        return original_stat(path, *args, **kwargs)

    def reject_diff(repo: git.Repo, path: Path, previous: Path | None) -> str:
        diff_attempts.append(path)
        raise AssertionError("oversized source must not create a diff")

    monkeypatch.setattr(Path, "stat", report_small_size)
    monkeypatch.setattr(change_set_module, "_diff_for_path", reject_diff)
    provider = FakeProvider()
    review = ReviewChanges(_reader(repository), provider, model="fake-model")

    with pytest.raises(ReviewTooLargeError, match="preflight budget"):
        review.prepare()

    assert diff_attempts == []
    assert provider.call_count == 0


@pytest.mark.integration
def test_oversized_git_base_is_refused_before_source_read_or_diff(
    repository: git.Repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(str(repository.working_tree_dir))
    tracked = root / "app.py"
    tracked.write_bytes(b"x" * (MAX_REVIEW_REQUEST_BYTES + 1))
    repository.index.add(["app.py"])
    repository.index.commit("large base")
    tracked.write_bytes(b"small current source\n")

    read_attempts: list[Path] = []
    diff_attempts: list[Path] = []
    original_open = Path.open

    def reject_read(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == tracked:
            read_attempts.append(path)
            raise AssertionError("over-budget source must not be read")
        return original_open(path, *args, **kwargs)

    def reject_diff(repo: git.Repo, path: Path, previous: Path | None) -> str:
        diff_attempts.append(path)
        raise AssertionError("over-budget base must not create a diff")

    monkeypatch.setattr(Path, "open", reject_read)
    monkeypatch.setattr(change_set_module, "_diff_for_path", reject_diff)
    provider = FakeProvider()
    review = ReviewChanges(_reader(repository), provider, model="fake-model")

    with pytest.raises(ReviewTooLargeError, match="preflight budget"):
        review.prepare()

    assert read_attempts == []
    assert diff_attempts == []
    assert provider.call_count == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    "replacement",
    [b"one = changed\ntwo = 2\n", b"x" * (MAX_REVIEW_REQUEST_BYTES + 1)],
)
def test_changed_snapshot_is_refused_before_diff_or_provider_call(
    repository: git.Repo,
    monkeypatch: pytest.MonkeyPatch,
    replacement: bytes,
) -> None:
    root = Path(str(repository.working_tree_dir))
    tracked = root / "app.py"
    tracked.write_bytes(b"one = updated\ntwo = 2\nthree = 3\n")
    original_read = change_set_module._read_bounded_source
    read_count = 0
    diff_attempts: list[Path] = []

    def change_file_after_snapshot(path: Path, max_bytes: int) -> bytes:
        nonlocal read_count
        snapshot = original_read(path, max_bytes)
        if path == tracked and read_count == 0:
            read_count += 1
            tracked.write_bytes(replacement)
        return snapshot

    def reject_diff(repo: git.Repo, path: Path, previous: Path | None) -> str:
        diff_attempts.append(path)
        raise AssertionError("a changed snapshot must not be diffed")

    monkeypatch.setattr(
        change_set_module, "_read_bounded_source", change_file_after_snapshot
    )
    monkeypatch.setattr(change_set_module, "_diff_for_path", reject_diff)
    provider = FakeProvider()
    review = ReviewChanges(_reader(repository), provider, model="fake-model")

    with pytest.raises(ReviewSnapshotChangedError, match="moved while preparing"):
        review.prepare()

    assert read_count == 1
    assert diff_attempts == []
    assert provider.call_count == 0


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
def test_review_snapshot_omits_a_tracked_file_with_only_deleted_lines(
    repository: git.Repo,
) -> None:
    (Path(str(repository.working_tree_dir)) / "app.py").write_bytes(b"one = 1\n")

    change_set = _reader(repository).read()

    assert change_set.files == ()
    assert len(change_set.omissions) == 1
    assert change_set.omissions[0].path == Path("app.py")
    assert change_set.omissions[0].reason is OmissionReason.NO_REVIEWABLE_LINES


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
