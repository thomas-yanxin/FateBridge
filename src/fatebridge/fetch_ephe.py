"""Download Swiss Ephemeris ``.se1`` data files for full-precision charts.

FateBridge ships this fetcher under Apache-2.0, but never the data files: the
``.se1`` ephemeris files are Astrodienst's, dual-licensed AGPL-3.0 / commercial.
Running this script acquires data separately; its licence is independent of
FateBridge's source licence. See LICENSE and NOTICE.

Usage::

    python -m fatebridge.fetch_ephe                 # into <repo>/ephe
    python -m fatebridge.fetch_ephe --dest /tmp/se  # custom directory
    python -m fatebridge.fetch_ephe --force         # re-download existing files

Once the files are present, FateBridge auto-discovers the ``ephe/`` directory
(see :func:`fatebridge.core.ephemeris_runtime.default_ephe_dir`) and upgrades
planetary positions from the built-in Moshier model to full Swiss Ephemeris
precision — no environment variable required.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import List, Optional, Sequence

# Alois Treindl's official mirror serves the raw .se1 files reliably; the
# astro.com HTTP front returns an HTML page for these same paths.
BASE_URL = "https://github.com/aloistr/swisseph/raw/master/ephe"

# 1800-2400 AD planet, moon, and main-asteroid segments — ~1.9 MB total, enough
# for any modern birth chart. Other eras need their own additional segments.
DEFAULT_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")

# Swiss Ephemeris data files begin with this magic; an HTML error page does not,
# so it cheaply distinguishes real data from a redirect/error response.
_MAGIC = b"SW"
_TIMEOUT_SECONDS = 60


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
    base_url: str = BASE_URL,
    force: bool = False,
) -> Path:
    """Download a single ``.se1`` file into ``dest``, validating its content.

    Existing files are kept unless ``force`` is set. Raises ``ValueError`` if the
    downloaded bytes are not a Swiss Ephemeris file (e.g. an HTML error page),
    leaving no partial file behind.
    """
    target = dest / name
    if target.exists() and not force:
        return target
    data = _download(f"{base_url}/{name}")
    if not data.startswith(_MAGIC):
        raise ValueError(
            f"{name}: downloaded content is not a Swiss Ephemeris file "
            f"(got {data[:16]!r}); check the source URL."
        )
    dest.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=dest)
    pending = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    return target


def fetch_ephemeris(
    dest: Optional[Path] = None,
    files: Sequence[str] = DEFAULT_FILES,
    *,
    base_url: str = BASE_URL,
    force: bool = False,
) -> List[Path]:
    """Download ``files`` into ``dest`` (default: the project ``ephe/`` dir)."""
    destination = dest if dest is not None else default_dest()
    return [
        fetch_one(name, destination, base_url=base_url, force=force) for name in files
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
    parser.add_argument(
        "--files",
        nargs="+",
        default=list(DEFAULT_FILES),
        help=f"file names to download (default: {' '.join(DEFAULT_FILES)})",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="base URL to download from",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-download even if the file already exists",
    )
    args = parser.parse_args(argv)

    destination: Path = args.dest if args.dest is not None else default_dest()
    print(f"Downloading {len(args.files)} ephemeris file(s) into {destination}")
    try:
        paths = fetch_ephemeris(
            destination,
            args.files,
            base_url=args.base_url,
            force=args.force,
        )
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for path in paths:
        size_kb = path.stat().st_size / 1024
        print(f"  ok  {path.name}  ({size_kb:.0f} KB)")
    print("Done. FateBridge auto-discovers this directory on the next run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
