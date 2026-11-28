"""Preview or remove regenerable local build and cache artifacts."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIRECTORIES = (
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "__pycache__",
    "ci-evidence",
)
ARTIFACT_FILES = (
    ".coverage",
    ".DS_Store",
    "ci-selection.json",
    "cache-status.txt",
    "pytest-results.xml",
    "nonuniform-reference-results.xml",
    "resolved-dependencies.txt",
)


def find_artifacts(root: Path) -> list[Path]:
    """Return a narrow allowlist without touching external reference bundles."""
    directories = [root / name for name in ARTIFACT_DIRECTORIES]
    files = [root / name for name in ARTIFACT_FILES]
    files.extend(root.glob(".coverage.*"))
    dist = root / "dist"
    if not dist.is_symlink():
        files.extend(dist.glob("*.whl"))
        files.extend(dist.glob("*.tar.gz"))
    for name in ("src", "scripts", "tests"):
        base = root / name
        if base.is_symlink() or not base.exists():
            continue
        if name == "src":
            directories.extend(base.glob("*.egg-info"))
        for current, subdirectories, filenames in os.walk(base, followlinks=False):
            parent = Path(current)
            subdirectories[:] = [
                item for item in subdirectories if not (parent / item).is_symlink()
            ]
            if "__pycache__" in subdirectories:
                directories.append(parent / "__pycache__")
                subdirectories.remove("__pycache__")
            files.extend(
                parent / item
                for item in filenames
                if item == ".DS_Store" or item.endswith((".pyc", ".pyo"))
            )
    return sorted(
        {path for path in directories if not path.is_symlink() and path.is_dir()}
        | {path for path in files if not path.is_symlink() and path.is_file()}
    )


def tracked_artifacts(root: Path, candidates: list[Path]) -> list[str]:
    """Read the index before deleting anything; Git failures stop the cleanup."""
    if not (root / ".git").exists():
        raise ValueError("The cleanup root has no Git checkout metadata")
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "-z"],
        check=True,
        capture_output=True,
    )
    tracked = [Path(os.fsdecode(item)) for item in result.stdout.split(b"\0") if item]
    relative = {item.relative_to(root) for item in candidates}
    return [
        str(path)
        for path in tracked
        if path in relative or any(parent in relative for parent in path.parents)
    ]


def main(argv: list[str] | None = None) -> int:
    """List or delete untracked local build and cache artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="remove listed artifacts")
    options = parser.parse_args(argv)
    candidates = find_artifacts(ROOT)
    try:
        protected = tracked_artifacts(ROOT, candidates)
    except (subprocess.CalledProcessError, OSError, ValueError):
        print("Cannot read the Git index; no artifacts removed.")
        return 1
    if protected:
        print("Tracked files found in cleanup candidates; no artifacts removed:")
        print("\n".join(protected))
        return 1
    for path in candidates:
        print(path.relative_to(ROOT))
        if options.apply:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    print(
        f"{'Removed' if options.apply else 'Would remove'} {len(candidates)} artifacts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
