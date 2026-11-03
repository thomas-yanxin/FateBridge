"""Acquire and verify pinned Swiss Ephemeris ``.se1`` data files.

FateBridge ships this fetcher under Apache-2.0, but never the data files: the
``.se1`` ephemeris files are Astrodienst's, dual-licensed AGPL-3.0 / commercial.
Running this script acquires data separately; its licence is independent of
FateBridge's source licence. See LICENSE and NOTICE.

Usage::

    python -m fatebridge.fetch_ephe                 # into <repo>/ephe
    python -m fatebridge.fetch_ephe --dest /tmp/se  # custom directory
    python -m fatebridge.fetch_ephe --force         # re-download existing files
    python -m fatebridge.fetch_ephe --years 1500 9999  # planet/Moon segments
    python -m fatebridge.fetch_ephe --profile fengshui_calendar
    python -m fatebridge.fetch_ephe --profile human_design

Verified repository-local files are discovered in ``ephe/`` on a fresh run.
Custom directories require ``SE_EPHE_PATH``. Computations still report their
actual model; file identity alone is not an astronomical accuracy guarantee.
Both domain profiles support a verified per-user cache for wheel installs.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from fatebridge.core.astro.ephemeris_files import ephemeris_files_for_years
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    validate_file_name,
    verify_ephemeris_bytes,
)
from fatebridge.core.ephemeris_installation import (
    FENGSHUI_FILES,
    FENGSHUI_PROFILE,
    HUMAN_DESIGN_FILES,
    HUMAN_DESIGN_PROFILE,
    ephemeris_path_fits,
    user_ephemeris_dir,
    verified_user_ephemeris_dir,
)
from fatebridge.core.ephemeris_paths import ephemeris_search_directories

# Alois Treindl's official mirror serves the raw .se1 files reliably; the
# astro.com HTTP front returns an HTML page for these same paths.
BASE_URL = load_ephemeris_manifest()["base_url"]

# 1800-2400 AD planet, moon, and main-asteroid segments — ~1.9 MB total, enough
# for any modern birth chart. Other eras need their own additional segments.
DEFAULT_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")

_TIMEOUT_SECONDS = 60
logger = logging.getLogger(__name__)


def _preserve_previous(target: Path, data: bytes) -> Path:
    digest = hashlib.sha256(data).hexdigest()
    backup = target.parent / ".fatebridge-ephemeris-backups" / digest / target.name
    if backup.exists():
        if backup.read_bytes() != data:
            raise ValueError(
                f"{target.name}: existing backup differs; leaving target unchanged"
            )
        return backup
    backup.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{backup.name}.", dir=backup.parent)
    pending = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        pending.replace(backup)
    finally:
        pending.unlink(missing_ok=True)
    return backup


def default_dest() -> Path:
    """Project-root ``ephe/`` directory (created on demand by the caller).

    src layout: this module is ``<repo>/src/fatebridge/fetch_ephe.py``, so the
    repo root is two parents up. Must match ``ephemeris_runtime`` so a fetched
    ``ephe/`` is found by the reader.
    """
    return Path(__file__).resolve().parents[2] / "ephe"


def _download(url: str, timeout: int = _TIMEOUT_SECONDS) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        data: bytes = response.read()
    return data


def fetch_one(
    name: str,
    dest: Path,
    *,
    base_url: Optional[str] = None,
    force: bool = False,
    manifest: Optional[Dict[str, Any]] = None,
) -> Path:
    """Download a single ``.se1`` file into ``dest``, validating its content.

    Existing files must match the selected edition. Unverified files are
    replaced only after a verified download and a recoverable local backup.
    Bad downloads leave the destination unchanged. Concurrent differing edits
    are detected before replacement.
    """
    catalog = manifest if manifest is not None else load_ephemeris_manifest()
    validate_file_name(name)
    if name not in catalog["files"]:
        raise ValueError(f"{name}: no fingerprint in the selected manifest")
    target = dest / name
    previous = target.read_bytes() if target.exists() else None
    if previous is not None and not force:
        try:
            verify_ephemeris_bytes(name, previous, catalog)
            return target
        except ValueError:
            pass
    if target.is_symlink():
        raise ValueError(
            f"{name}: refusing to replace a symlink; choose a regular data directory"
        )
    data = _download(f"{base_url or catalog['base_url']}/{name}")
    verify_ephemeris_bytes(name, data, catalog)
    dest.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=dest)
    pending = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        current = target.read_bytes() if target.exists() else None
        if current != previous:
            if current == data:
                return target
            raise ValueError(
                f"{name}: destination changed during download; left unchanged"
            )
        if previous is not None and previous != data:
            backup = _preserve_previous(target, previous)
            logger.warning("Preserved previous %s at %s", target, backup)
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    return target


def fetch_ephemeris(
    dest: Optional[Path] = None,
    files: Sequence[str] = DEFAULT_FILES,
    *,
    base_url: Optional[str] = None,
    force: bool = False,
    manifest: Optional[Dict[str, Any]] = None,
) -> List[Path]:
    """Download ``files`` into ``dest`` (default: the project ``ephe/`` dir)."""
    destination = dest if dest is not None else default_dest()
    catalog = manifest if manifest is not None else load_ephemeris_manifest()
    return [
        fetch_one(name, destination, base_url=base_url, force=force, manifest=catalog)
        for name in files
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download Swiss Ephemeris .se1 data files for FateBridge."
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="target directory (default: <repo>/ephe)",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--files",
        nargs="+",
        default=None,
        help=f"file names to download (default: {' '.join(DEFAULT_FILES)})",
    )
    selection.add_argument(
        "--profile",
        choices=[FENGSHUI_PROFILE, HUMAN_DESIGN_PROFILE],
        help="verified data for Feng Shui boundaries1784..2204, or Human Design natal/Design/optional65-year cycles1799..2465 (including Chiron)",
    )
    selection.add_argument(
        "--years",
        nargs="+",
        type=int,
        help="CE years 1..9999; select planet/Moon files with adjacent-year boundary coverage",
    )
    selection.add_argument(
        "--year-range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="inclusive CE year range 1..9999; planet/Moon files only",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="mirror URL; content must still match the selected manifest",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="explicit fingerprint manifest for a different or custom data edition",
    )
    policy = parser.add_mutually_exclusive_group()
    policy.add_argument(
        "--force",
        action="store_true",
        help="re-download even if the file already exists",
    )
    policy.add_argument(
        "--verify-only",
        action="store_true",
        help="verify existing files offline; do not download or repair",
    )
    args = parser.parse_args(argv)
    files = args.files if args.files is not None else DEFAULT_FILES
    try:
        if args.profile == FENGSHUI_PROFILE:
            files = FENGSHUI_FILES
        elif args.profile == HUMAN_DESIGN_PROFILE:
            files = HUMAN_DESIGN_FILES
        elif args.years is not None:
            files = ephemeris_files_for_years(args.years)
        elif args.year_range is not None:
            start, end = args.year_range
            if not 1 <= start <= end <= 9999:
                raise ValueError("Year range must satisfy 1 <= START <= END <= 9999")
            files = ephemeris_files_for_years(range(start, end + 1))
    except ValueError as error:
        parser.error(str(error))

    project_directory = default_dest()
    profile_destination = (
        project_directory
        if project_directory.is_dir() and any(project_directory.glob("*.se1"))
        else user_ephemeris_dir()
    )
    destination: Path = (
        args.dest
        if args.dest is not None
        else profile_destination if args.profile else project_directory
    )
    action = "Verifying" if args.verify_only else "Acquiring"
    print(f"{action} {len(files)} ephemeris file(s) in {destination}")
    try:
        if args.profile and not ephemeris_path_fits(destination):
            raise ValueError(
                "Profile directory exceeds Swiss Ephemeris path limits; choose a shorter --dest"
            )
        catalog = load_ephemeris_manifest(args.manifest)
        if args.verify_only:
            for name in files:
                validate_file_name(name)
            paths = [destination / name for name in files]
            for path in paths:
                verify_ephemeris_bytes(path.name, path.read_bytes(), catalog)
        else:
            paths = fetch_ephemeris(
                destination,
                files,
                base_url=args.base_url,
                force=args.force,
                manifest=catalog,
            )
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for path in paths:
        size_kb = path.stat().st_size / 1024
        print(f"  checksum verified  {path.name}  ({size_kb:.0f} KB)")
    cached = verified_user_ephemeris_dir()
    override = os.environ.get("SE_EPHE_PATH")
    if override:
        chosen = [item.resolve() for item in ephemeris_search_directories(override)]
        if destination.resolve() in chosen:
            print(
                "Done. SE_EPHE_PATH already includes this directory; restart FateBridge to reload data."
            )
        else:
            print(
                "Done. SE_EPHE_PATH selects another directory. Set SE_EPHE_PATH to include this directory before starting FateBridge to use these files."
            )
    elif destination.resolve() == default_dest().resolve() or (
        cached is not None
        and destination.resolve() == Path(cached).resolve()
        and not (project_directory.is_dir() and any(project_directory.glob("*.se1")))
    ):
        print("Done. FateBridge auto-discovers this directory on the next run.")
    else:
        print("Done. Set SE_EPHE_PATH to this directory before starting FateBridge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
