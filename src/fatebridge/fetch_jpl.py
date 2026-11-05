"""Explicit acquisition of a full content-pinned DE441 file or continuous span.

The full-file pin comes from FateBridge's independent-reader record, not a
NASA-published checksum. Span mode retains original coefficient words with
HTTP range/ETag identity and does not claim a full remote-file checksum. Acquisition does not change the default backend
or certify astronomical accuracy. Existing invalid files are left unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import ssl
import struct
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable, Final, Optional, Sequence

import certifi

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


SOURCE_URL = (
    "https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de441/linux_m13000p17000.441"
)
RECORD_BYTES = 8144
CHUNK_RECORDS = 4096


def stream_sha256(source: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return stream_sha256(source)


def january_first(year: int) -> float:
    previous = year - 1
    return (
        1721425.5 + previous * 365 + previous // 4 - previous // 100 + previous // 400
    )


def original_header(raw: bytes) -> tuple[float, float]:
    if len(raw) != RECORD_BYTES:
        raise ValueError("Incomplete original DE441 header")
    begin, end, step = struct.unpack_from("<3d", raw, 2652)
    if not (
        struct.unpack_from("<i", raw, 2840)[0] == 441
        and step == 32
        and math.isfinite(begin)
        and math.isfinite(end)
        and begin < end
        and (end - begin) % step == 0
        and struct.unpack_from("<d", raw, 2680)[0] == 149597870.7
        and 81 < struct.unpack_from("<d", raw, 2688)[0] < 82
        and struct.unpack_from("<3i", raw, 2696 + 9 * 12)[0:] == (441, 13, 8)
        and struct.unpack_from("<3i", raw, 2844) == (899, 10, 4)
    ):
        raise ValueError("Unsupported original DE441 direct-access layout")
    return begin, end


def source_range(
    start: int, size: int, etag: str | None = None
) -> tuple[bytes, dict[str, str]]:
    end = start + size - 1
    headers = {
        "Range": f"bytes={start}-{end}",
        "Accept-Encoding": "identity",
        "User-Agent": "FateBridge complete DE441 span preparer",
    }
    if etag is not None:
        headers["If-Match"] = etag
    request = urllib.request.Request(SOURCE_URL, headers=headers)
    with urllib.request.urlopen(
        request,
        context=ssl.create_default_context(cafile=certifi.where()),
        timeout=45,
    ) as response:
        raw = response.read(size + 1)
        received = dict(response.headers)
        content_range = received.get("Content-Range", "")
        if (
            response.status != 206
            or len(raw) != size
            or not content_range.startswith(f"bytes {start}-{end}/")
            or not received.get("ETag")
            or (etag is not None and received["ETag"] != etag)
        ):
            raise ValueError("Original DE441 byte range or source identity changed")
    return raw, received


def prepare(output: Path, start_year: int, end_year: int) -> dict[str, object]:
    if not 1 <= start_year < end_year <= 10000:
        raise ValueError("Require 1 <= start-year < end-year <= 10000")
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    partial = output.with_suffix(output.suffix + ".partial")
    if any(path.exists() for path in (output, manifest_path, partial)):
        raise ValueError("An output, manifest or partial source already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    ranges: list[dict[str, int | str]] = []
    manifest: dict[str, object] = {
        "format": "fatebridge_complete_de441_span_v1",
        "source_url": SOURCE_URL,
        "output": output.name,
        "requested_start_year": start_year,
        "requested_end_year_exclusive": end_year,
        "time_scale": "TDB",
        "guard_days_each_side": 32,
        "all_bodies_and_coefficients_retained": True,
        "runtime_default_changed": False,
        "full_remote_file_sha256_verified": False,
        "status": "planned",
        "ranges": ranges,
    }

    def save() -> None:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    save()
    try:
        raw, headers = source_range(0, 2 * RECORD_BYTES)
        header, constants = raw[:RECORD_BYTES], raw[RECORD_BYTES:]
        begin, end = original_header(header)
        total = int(headers["Content-Range"].split("/")[1])
        if total != (int((end - begin) / 32) + 2) * RECORD_BYTES:
            raise ValueError("Original DE441 object length and header disagree")
        first = math.floor((january_first(start_year) - 32 - begin) / 32)
        stop = math.ceil((january_first(end_year) + 32 - begin) / 32)
        if not 0 <= first < stop <= (end - begin) / 32:
            raise ValueError("Requested complete span exceeds official source coverage")
        actual_begin, actual_end = begin + first * 32, begin + stop * 32
        modified = bytearray(header)
        title = b"FateBridge complete continuous DE441 span; original coefficient words retained"
        modified[:252] = title.ljust(252, b" ")
        struct.pack_into("<2d", modified, 2652, actual_begin, actual_end)
        manifest.update(
            status="downloading",
            original_object_bytes=total,
            original_headers=headers,
            original_header_sha256=hashlib.sha256(header).hexdigest(),
            original_constants_sha256=hashlib.sha256(constants).hexdigest(),
            original_first_record=first,
            record_count=stop - first,
            start_julian_day_tdb=actual_begin,
            end_julian_day_tdb=actual_end,
            header_modified_byte_ranges=[[0, 251], [2652, 2667]],
            downloaded_coefficient_bytes=0,
        )
        save()
        raw_digest = hashlib.sha256()
        downloaded = 0
        with partial.open("xb") as target:
            target.write(modified)
            target.write(constants)
            for index in range(first, stop, CHUNK_RECORDS):
                count = min(CHUNK_RECORDS, stop - index)
                offset, size = (index + 2) * RECORD_BYTES, count * RECORD_BYTES
                manifest["active_range"] = {"start": offset, "bytes": size}
                save()
                block, response_headers = source_range(offset, size, headers["ETag"])
                if response_headers["Content-Range"].split("/")[1] != str(total):
                    raise ValueError("Original DE441 object extent changed")
                for k in range(count):
                    record = block[k * RECORD_BYTES : (k + 1) * RECORD_BYTES]
                    values = struct.unpack("<1018d", record)
                    expected = begin + (index + k) * 32
                    if values[:2] != (expected, expected + 32) or not all(
                        math.isfinite(value) for value in values
                    ):
                        raise ValueError(
                            "Nonconsecutive or nonfinite original DE441 record"
                        )
                target.write(block)
                raw_digest.update(block)
                ranges.append(
                    {
                        "start": offset,
                        "bytes": size,
                        "sha256": hashlib.sha256(block).hexdigest(),
                    }
                )
                downloaded += size
                manifest["downloaded_coefficient_bytes"] = downloaded
                save()
                print(
                    f"DE441 {index + count - first}/{stop - first} complete records",
                    flush=True,
                )
        info = jpl_header(partial)
        if (info["start_julian_day_tdb"], info["end_julian_day_tdb"]) != (
            actual_begin,
            actual_end,
        ):
            raise ValueError("Prepared native source extent changed")
        manifest.update(
            status="ready",
            active_range=None,
            original_coefficient_sha256=raw_digest.hexdigest(),
            output_sha256=file_sha256(partial),
            output_bytes=partial.stat().st_size,
        )
        partial.rename(output)
        save()
    except (OSError, ValueError, struct.error, EphemerisSourceError) as error:
        manifest.update(
            status="failed", error_type=type(error).__name__, error=str(error)
        )
        save()
        raise
    return manifest


def verify(output: Path) -> dict[str, object]:
    loaded: object = json.loads(
        output.with_suffix(output.suffix + ".manifest.json").read_text()
    )
    if not isinstance(loaded, dict):
        raise ValueError("The source manifest must be a JSON object")
    manifest: dict[str, object] = loaded
    if manifest["status"] != "ready" or manifest["output"] != output.name:
        raise ValueError("The source manifest is not ready or bound to this basename")
    with output.open("rb") as source:
        source.seek(RECORD_BYTES)
        constants = source.read(RECORD_BYTES)
        coefficient_sha = stream_sha256(source)
    info = jpl_header(output)
    if (
        output.stat().st_size != manifest["output_bytes"]
        or file_sha256(output) != manifest["output_sha256"]
        or hashlib.sha256(constants).hexdigest()
        != manifest["original_constants_sha256"]
        or coefficient_sha != manifest["original_coefficient_sha256"]
        or info["start_julian_day_tdb"] != manifest["start_julian_day_tdb"]
        or info["end_julian_day_tdb"] != manifest["end_julian_day_tdb"]
    ):
        raise ValueError("The prepared source bytes or extent changed")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument(
        "--output", type=Path, help="prepare or verify a continuous span at this path"
    )
    parser.add_argument("--start-year", type=int)
    parser.add_argument(
        "--end-year", type=int, help="exclusive end of the requested continuous span"
    )
    parser.add_argument(
        "--ca-file",
        type=Path,
        help="optional trusted CA bundle; TLS verification stays enabled",
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    if args.output is not None:
        if args.dest is not None or args.ca_file is not None:
            parser.error(
                "--output span mode cannot be combined with --dest or --ca-file"
            )
        if args.verify_only:
            if args.start_year is not None or args.end_year is not None:
                parser.error(
                    "span --verify-only uses the saved manifest, not year arguments"
                )
        try:
            if args.verify_only:
                result = verify(args.output)
            else:
                start_year: int | None = args.start_year
                end_year: int | None = args.end_year
                if start_year is None or end_year is None:
                    parser.error(
                        "span preparation requires --start-year and --end-year"
                    )
                result = prepare(args.output, start_year, end_year)
        except (OSError, ValueError, EphemerisSourceError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2))
        return 0
    if args.start_year is not None or args.end_year is not None:
        parser.error("year arguments require --output span mode")
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
