"""Preview or remove regenerable local artifacts, preserving validation evidence."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHES = (
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    ".DS_Store",
)


def find_artifacts(root: Path) -> list[Path]:
    """Return a narrow allowlist; never descend into fixtures or frozen copies."""
    candidates = [root / name for name in CACHES]
    dist = root / "dist"
    if not dist.is_symlink():
        candidates.extend(dist.glob("*.whl"))
        candidates.extend(dist.glob("*.tar.gz"))
    for name in ("src", "scripts", "tests"):
        base = root / name
        if base.is_symlink():
            continue
        if name == "src":
            candidates.extend(base.glob("*.egg-info"))
        for current, directories, files in os.walk(base, followlinks=False):
            parent = Path(current)
            directories[:] = [
                item
                for item in directories
                if not (parent / item).is_symlink()
                and not (name == "tests" and parent == base and item == "fixtures")
            ]
            if "__pycache__" in directories:
                candidates.append(parent / "__pycache__")
                directories.remove("__pycache__")
            if ".DS_Store" in files:
                candidates.append(parent / ".DS_Store")
    return sorted(
        path for path in set(candidates) if path.exists() and not path.is_symlink()
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
    return [
        str(path)
        for path in tracked
        if any(path.is_relative_to(item.relative_to(root)) for item in candidates)
    ]


def main(argv: list[str] | None = None) -> int:
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
            if path.is_symlink():
                raise RuntimeError(f"Cleanup candidate became a symlink: {path}")
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
