"""Preview or remove regenerable local artifacts, preserving current references."""

from __future__ import annotations

import argparse
import hashlib
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
    ".coverage",
    "htmlcov",
    "__pycache__",
    ".DS_Store",
    "ci-selection.json",
    "cache-status.txt",
    "pytest-results.xml",
    "nonuniform-reference-results.xml",
    "resolved-dependencies.txt",
    "ci-evidence",
)
SOURCE_SCAN_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


def find_duplicate_scans(root: Path) -> dict[str, list[Path]]:
    """Group byte-identical original scans, excluding links and mutable records."""
    sizes: dict[int, list[Path]] = {}
    for base in (root / "tests/fixtures", root / "tests/data"):
        if base.is_symlink():
            continue
        for current, directories, files in os.walk(base, followlinks=False):
            parent = Path(current)
            directories[:] = [
                name
                for name in directories
                if name != "__pycache__" and not (parent / name).is_symlink()
            ]
            for name in files:
                path = parent / name
                if (
                    path.suffix.lower() in SOURCE_SCAN_SUFFIXES
                    and not path.is_symlink()
                ):
                    sizes.setdefault(path.stat().st_size, []).append(path)
    groups: dict[str, list[Path]] = {}
    for paths in sizes.values():
        if len(paths) < 2:
            continue
        for path in sorted(paths):
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            groups.setdefault(digest.hexdigest(), []).append(path)
    return {digest: paths for digest, paths in groups.items() if len(paths) > 1}


def share_source_scans(root: Path, groups: dict[str, list[Path]]) -> None:
    """Store each original once; frozen corpus paths remain relative references."""
    storage = root / "tests/data/shared_sources"
    for paths in groups.values():
        stored = [path for path in paths if path.is_relative_to(storage)]
        canonical = (
            stored[0] if stored else storage / paths[0].relative_to(root / "tests")
        )
        if not stored:
            canonical.parent.mkdir(parents=True, exist_ok=True)
            os.link(paths[0], canonical)
        for path in paths:
            if path == canonical:
                continue
            # Replace only after the relative link exists. A failed link creation
            # leaves the original scan in place, including on Windows hosts.
            temporary = path.with_name("." + path.name + ".shared-source")
            temporary.symlink_to(os.path.relpath(canonical, path.parent))
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)


def find_artifacts(root: Path) -> list[Path]:
    """Return a narrow allowlist without touching external reference bundles."""
    candidates = [root / name for name in CACHES]
    candidates.extend(root.glob(".coverage.*"))
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
                item for item in directories if not (parent / item).is_symlink()
            ]
            if "__pycache__" in directories:
                candidates.append(parent / "__pycache__")
                directories.remove("__pycache__")
            if ".DS_Store" in files:
                candidates.append(parent / ".DS_Store")
            candidates.extend(
                parent / item for item in files if item.endswith((".pyc", ".pyo"))
            )
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
    relative = {item.relative_to(root) for item in candidates}
    return [
        str(path)
        for path in tracked
        if path in relative or any(parent in relative for parent in path.parents)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="remove listed artifacts")
    parser.add_argument(
        "--deduplicate-scans",
        action="store_true",
        help="share identical local source scans using relative symbolic links",
    )
    options = parser.parse_args(argv)
    candidates = find_artifacts(ROOT)
    scans = find_duplicate_scans(ROOT) if options.deduplicate_scans else {}
    try:
        protected = tracked_artifacts(
            ROOT, candidates + [path for paths in scans.values() for path in paths]
        )
    except (subprocess.CalledProcessError, OSError, ValueError):
        print("Cannot read the Git index; no artifacts removed.")
        return 1
    if protected:
        print("Tracked files found in cleanup candidates; no artifacts removed:")
        print("\n".join(protected))
        return 1
    if options.deduplicate_scans:
        aliases = sum(len(paths) - 1 for paths in scans.values())
        size = sum(
            paths[0].stat().st_size * (len(paths) - 1) for paths in scans.values()
        )
        print(
            f"Source scans: {len(scans)} duplicate groups, {aliases} extra copies, {size} bytes."
        )
        if options.apply:
            share_source_scans(ROOT, scans)
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
