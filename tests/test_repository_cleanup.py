"""Cleanup must preserve source, tracked files, evidence and symlink targets."""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import clean_repository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr(clean_repository, "ROOT", tmp_path)
    return tmp_path


def put(root: Path, name: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("original bytes", encoding="utf-8")
    return path


def test_preview_is_read_only_and_apply_preserves_evidence(repository):
    artifacts = [
        put(repository, name)
        for name in (
            "build/lib/retired.py",
            "dist/fatebridge-0.0.1.whl",
            "dist/fatebridge-0.0.1.tar.gz",
            ".pytest_cache/state",
            "src/fatebridge/__pycache__/retired.pyc",
            "scripts/__pycache__/old.pyc",
            "tests/__pycache__/old.pyc",
            ".DS_Store",
            "src/.DS_Store",
        )
    ]
    preserved = [
        put(repository, name)
        for name in (
            "src/fatebridge/module.py",
            "dist/validation/receipt.log",
            "dist/validation/source/__pycache__/record.pyc",
            "docs/validation/frozen-source/build/receipt.log",
            "tests/fixtures/evidence/__pycache__/record.pyc",
            "tests/fixtures/evidence/manifest.sha256",
            "uv.lock",
            ".venv/pyvenv.cfg",
        )
    ]
    assert clean_repository.main([]) == 0
    assert all(path.exists() for path in artifacts)
    assert clean_repository.main(["--apply"]) == 0
    assert not any(path.exists() for path in artifacts)
    assert all(path.read_text() == "original bytes" for path in preserved)


def test_tracked_candidate_stops_all_deletions(repository):
    protected = put(repository, "build/important.txt")
    other = put(repository, ".mypy_cache/state")
    subprocess.run(
        ["git", "-C", str(repository), "add", "build/important.txt"], check=True
    )
    assert clean_repository.main(["--apply"]) == 1
    assert protected.exists() and other.exists()


def test_git_failure_stops_all_deletions(repository):
    artifact = put(repository, "build/old.py")
    (repository / ".git").rename(repository / "git-backup")
    assert clean_repository.main(["--apply"]) == 1
    assert artifact.exists()


def test_nested_directory_cannot_borrow_its_parent_git_index(repository, monkeypatch):
    child = repository / "child"
    artifact = put(child, "build/keep.py")
    monkeypatch.setattr(clean_repository, "ROOT", child)
    assert clean_repository.main(["--apply"]) == 1
    assert artifact.exists()


def test_symlinked_trees_are_not_cleanup_candidates(repository, tmp_path_factory):
    external = tmp_path_factory.mktemp("external")
    preserved = put(external, "__pycache__/keep.pyc")
    for name in ("src", "build", "dist"):
        try:
            (repository / name).symlink_to(external, target_is_directory=True)
        except OSError:
            pytest.skip("Directory symlinks unavailable")
    assert clean_repository.main(["--apply"]) == 0
    assert preserved.exists()


def test_nested_symlinks_do_not_expose_external_caches(repository, tmp_path_factory):
    external = tmp_path_factory.mktemp("external")
    preserved = put(external, "__pycache__/keep.pyc")
    (repository / "scripts").mkdir()
    try:
        (repository / "scripts/linked").symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks unavailable")
    assert clean_repository.main(["--apply"]) == 0
    assert preserved.exists()


def test_default_collection_does_not_execute_frozen_fixture_programs(tmp_path):
    source = Path(__file__).resolve().parents[1] / "conftest.py"
    (tmp_path / "conftest.py").write_text(source.read_text(), encoding="utf-8")
    current = put(tmp_path, "tests/test_current.py")
    current.write_text("def test_current():\n    assert True\n", encoding="utf-8")
    archived = put(tmp_path, "tests/fixtures/old/tests/test_current.py")
    archived.write_text("raise AssertionError('historical code executed')\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert archived.read_text() == "raise AssertionError('historical code executed')\n"
    replay = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(archived)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert replay.returncode == 2
    assert "historical code executed" in replay.stdout
