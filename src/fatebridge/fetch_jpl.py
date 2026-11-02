"""Explicit, streaming acquisition of one content-pinned original DE441 file.

The pin comes from FateBridge's historical full-file/independent-reader record,
not a NASA-published checksum. Acquisition does not change the default backend
or certify astronomical accuracy. Existing invalid files are left unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import ssl
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final, Optional, Sequence

from fatebridge.core.ephemeris_installation import (
    ephemeris_path_fits,
    user_ephemeris_dir,
)
from fatebridge.core.jpl_ephemeris import jpl_header
from fatebridge.utils.errors import EphemerisSourceError


@dataclass(frozen=True)
class _KernelSpec:
    filename: str
    url: str
    bytes: int
    sha256: str
    start_jd_tdb: float
    end_jd_tdb: float


DE441: Final = _KernelSpec(
    "linux_m13000p17000.441",
    "https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de441/linux_m13000p17000.441",
    2788676624,
    "476096486def4e41bfceb29aa27f50784da0bce318902bcf7b88caad058cd4da",
    -3027215.5,
    7930192.5,
)
_CHUNK = 1024 * 1024


def _signature(path: Path) -> tuple[int, int, int, int]:
    state = path.stat()
    return state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns


def _verify(path: Path, spec: _KernelSpec) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Kernel must be a regular file, not a symlink")
    before = _signature(path)
    if before[2] != spec.bytes:
        raise ValueError("Kernel size does not match the fixed content pin")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(_CHUNK), b""):
            digest.update(block)
    if digest.hexdigest() != spec.sha256:
        raise ValueError("Kernel SHA-256 does not match the fixed content pin")
    header = jpl_header(path)
    if (
        header["start_julian_day_tdb"] != spec.start_jd_tdb
        or header["end_julian_day_tdb"] != spec.end_jd_tdb
        or _signature(path) != before
    ):
        raise ValueError("Kernel header or file changed during verification")
    return {
        "filename": spec.filename,
        "bytes": spec.bytes,
        "sha256": spec.sha256,
        "time_scale": "TDB",
        "start_julian_day_tdb": spec.start_jd_tdb,
        "end_julian_day_tdb": spec.end_jd_tdb,
        "de_number": header["de_number"],
        "file_content_verified": True,
        "astronomical_accuracy_certified": False,
    }


def verify_de441(path: Path) -> dict[str, Any]:
    return _verify(path, DE441)


def default_dest() -> Path:
    return user_ephemeris_dir() / "jpl-de441"


def _acquire(
    destination: Path,
    spec: _KernelSpec,
    *,
    ca_file: Optional[Path] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    receipt: Optional[dict[str, Any]] = None,
) -> Path:
    if not ephemeris_path_fits(destination):
        raise ValueError(
            "Choose a shorter destination within native search-path limits"
        )
    target = destination / spec.filename
    if target.exists() or target.is_symlink():
        _verify(target, spec)
        if receipt is not None:
            receipt.update(
                existing_verified_file_reused=True, network_request_performed=False
            )
        return target
    destination.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".de441-download-", dir=destination)
    pending = Path(name)
    operational = receipt if receipt is not None else {}
    operational.update(
        url=spec.url,
        expected_bytes=spec.bytes,
        expected_sha256=spec.sha256,
        verification_disabled=False,
        network_request_performed=False,
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            context = ssl.create_default_context(
                cafile=str(ca_file) if ca_file else None
            )
            request = urllib.request.Request(
                spec.url,
                headers={
                    "User-Agent": "FateBridge-data/1.0 (+https://github.com/thomas-yanxin/FateBridge/issues)",
                    "Accept-Encoding": "identity",
                },
            )
            operational["network_request_performed"] = True
            with urllib.request.urlopen(
                request, timeout=60, context=context
            ) as response:
                operational.update(
                    network_request_performed=True,
                    http_status=response.status,
                    headers=dict(response.headers.items()),
                )
                if response.status != 200 or response.headers.get("Content-Range"):
                    raise ValueError(
                        "Full acquisition requires an unambiguous HTTP 200 response"
                    )
                length = response.headers.get("Content-Length")
                if length is not None and int(length) != spec.bytes:
                    raise ValueError(
                        "Server Content-Length differs from the fixed kernel size"
                    )
                received = 0
                for block in iter(lambda: response.read(_CHUNK), b""):
                    received += len(block)
                    operational["received_bytes"] = received
                    if received > spec.bytes:
                        raise ValueError(
                            "Server returned more bytes than the fixed kernel size"
                        )
                    output.write(block)
                    if progress is not None:
                        progress(received, spec.bytes)
                output.flush()
                os.fsync(output.fileno())
        metadata = _verify(pending, spec)
        # Same-directory hard-link creation is atomic and never overwrites an
        # existing target, including one created by another process meanwhile.
        try:
            os.link(pending, target)
        except FileExistsError:
            _verify(target, spec)
        operational.update(file_content_verified=True, final_metadata=metadata)
        return target
    finally:
        pending.unlink(missing_ok=True)


def fetch_de441(
    destination: Optional[Path] = None,
    *,
    ca_file: Optional[Path] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    receipt: Optional[dict[str, Any]] = None,
) -> Path:
    return _acquire(
        destination if destination is not None else default_dest(),
        DE441,
        ca_file=ca_file,
        progress=progress,
        receipt=receipt,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument(
        "--ca-file",
        type=Path,
        help="optional trusted CA bundle; TLS verification stays enabled",
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    destination = args.dest if args.dest is not None else default_dest()
    try:
        path = destination / DE441.filename
        if args.verify_only:
            verify_de441(path)
        else:
            last = [-1]

            def progress(done: int, total: int) -> None:
                milestone = done // (256 * 1024 * 1024)
                if milestone != last[0] or done == total:
                    print(f"DE441 {done}/{total} bytes", flush=True)
                    last[0] = milestone

            path = fetch_de441(destination, ca_file=args.ca_file, progress=progress)
    except (OSError, ValueError, EphemerisSourceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Full content pin verified: {path}")
    print(
        f"Select explicitly with SE_EPHE_PATH={destination} and FATEBRIDGE_JPL_FILE={DE441.filename}; restart the client before use."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
