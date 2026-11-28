"""Acquire and verify pinned Swiss Ephemeris files for a local installation.

The data files are separately licensed by Astrodienst under AGPL-3.0 or commercial terms. See LICENSE and NOTICE.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import urllib.request
from collections.abc import Sequence
from pathlib import Path

from fatebridge.core.astro.ephemeris_files import ephemeris_files_for_years
from fatebridge.core.astro.ephemeris_integrity import (
    EphemerisManifest,
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
    has_project_ephemeris_files,
    user_ephemeris_dir,
    verified_user_ephemeris_dir,
)
from fatebridge.core.ephemeris_paths import (
    ephemeris_search_directories,
    ephemeris_search_path_fits,
)
from fatebridge.core.ephemeris_runtime import bump_ephemeris_generation

# note (mirror): This URL serves raw files where the astro.com front serves HTML.
BASE_URL = load_ephemeris_manifest()["base_url"]

# note (coverage): These planet, Moon and asteroid segments cover CE 1800–2399.
DEFAULT_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")

TIMEOUT_SECONDS = 60
logger = logging.getLogger(__name__)


def default_dest() -> Path:
    """Return the checkout-local data directory discovered by the runtime."""
    return Path(__file__).resolve().parents[2] / "ephe"


def _download(url: str, timeout: int = TIMEOUT_SECONDS) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        response_bytes: bytes = response.read()
    return response_bytes


def fetch_one(
    name: str,
    dest: Path,
    *,
    base_url: str | None = None,
    force: bool = False,
    manifest: EphemerisManifest | None = None,
) -> Path:
    """Install one verified ephemeris file."""
    catalog = manifest if manifest is not None else load_ephemeris_manifest()
    validate_file_name(name)
    if name not in catalog["files"]:
        raise ValueError(f"{name}: not listed in the selected manifest")
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
    downloaded_bytes = _download(f"{base_url or catalog['base_url']}/{name}")
    verify_ephemeris_bytes(name, downloaded_bytes, catalog)
    dest.mkdir(parents=True, exist_ok=True)
    descriptor, staging_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=dest)
    pending = Path(staging_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(downloaded_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        current = target.read_bytes() if target.exists() else None
        if current != previous:
            if current == downloaded_bytes:
                return target
            raise ValueError(
                f"{name}: destination changed during download; left unchanged"
            )
        pending.replace(target)
        bump_ephemeris_generation()
    finally:
        pending.unlink(missing_ok=True)
    return target


def fetch_ephemeris(
    dest: Path | None = None,
    files: Sequence[str] = DEFAULT_FILES,
    *,
    base_url: str | None = None,
    force: bool = False,
    manifest: EphemerisManifest | None = None,
) -> list[Path]:
    """Install the selected files using one edition manifest."""
    destination = dest if dest is not None else default_dest()
    catalog = manifest if manifest is not None else load_ephemeris_manifest()
    return [
        fetch_one(name, destination, base_url=base_url, force=force, manifest=catalog)
        for name in files
    ]


def main(argv: Sequence[str] | None = None) -> int:
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
        help="explicit manifest for a different or custom data edition",
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
        if has_project_ephemeris_files(project_directory)
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
                "Profile directory is not a literal Swiss Ephemeris search directory; "
                "choose a shorter --dest without search-path delimiters"
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
    override = os.environ.get("SE_EPHE_PATH")
    resolved_destination = destination.resolve()
    usable_override = override is None or ephemeris_search_path_fits(override)
    chosen = (
        [item.resolve() for item in ephemeris_search_directories(override)]
        if usable_override
        else []
    )
    if resolved_destination in chosen:
        print(
            "Done. SE_EPHE_PATH already includes this directory; restart FateBridge to reload data."
        )
    elif not ephemeris_path_fits(destination):
        print(
            "Done. To use these files, make them available through a shorter directory path without Swiss Ephemeris search-path delimiters."
        )
    elif not usable_override:
        print(
            "Done. The current SE_EPHE_PATH exceeds the Swiss Ephemeris path limit. Set SE_EPHE_PATH to this directory before starting FateBridge to use these files."
        )
    elif override:
        print(
            "Done. SE_EPHE_PATH selects another directory. Set SE_EPHE_PATH to include this directory before starting FateBridge to use these files."
        )
    elif resolved_destination == project_directory.resolve() or (
        (cached := verified_user_ephemeris_dir()) is not None
        and resolved_destination == Path(cached).resolve()
        and not has_project_ephemeris_files(project_directory)
    ):
        print("Done. FateBridge auto-discovers this directory on the next run.")
    else:
        print("Done. Set SE_EPHE_PATH to this directory before starting FateBridge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
