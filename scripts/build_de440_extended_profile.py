"""Extract additional original DE440 coefficients without event-time references."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

MODEL_ID = "fatebridge_de440_solar_extended_v1"
KERNEL_SHA256 = "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
SOFTWARE_YEARS = (1684, 2304)
PUBLIC_YEARS = (1700, 2300)
PADDING_YEARS = (1682, 2307)


def extract(kernel_path: Path, tdb_path: Path) -> tuple[bytes, dict[str, Any]]:
    from jplephem.spk import SPK  # type: ignore[import-untyped]

    digest = hashlib.sha256(kernel_path.read_bytes()).hexdigest()
    if digest != KERNEL_SHA256:
        raise ValueError("The extended profile requires the pinned DE440 kernel")
    low, high = [
        (date(y, 1, 1).toordinal() + 1721424.5 - 2451545.0) * 86400
        for y in PADDING_YEARS
    ]
    chunks, segments, offset = [], [], 0
    with SPK.open(str(kernel_path)) as kernel, kernel_path.open("rb") as stream:
        if kernel.daf.locfmt != b"LTL-IEEE":
            raise ValueError("Original little-endian records are required")
        for pair in [(0, 3), (3, 399), (0, 10)]:
            matches = [s for s in kernel.segments if (s.center, s.target) == pair]
            if len(matches) != 1:
                raise ValueError("Unexpected DE440 segment priority")
            segment = matches[0]
            if segment.frame != 1 or segment.data_type != 2:
                raise ValueError("Only original ICRS type2 records are admitted")
            initial, span, size, count = map(
                float, segment.daf.read_array(segment.end_i - 3, segment.end_i)
            )
            size, count = int(size), int(count)
            first = max(0, math.ceil((low - initial) / span) - 1)
            last = min(count - 1, math.floor((high - initial) / span))
            records = last - first + 1
            start = (segment.start_i - 1 + first * size) * 8
            stream.seek(start)
            raw = stream.read(records * size * 8)
            if len(raw) != records * size * 8:
                raise ValueError("Incomplete DE440 coefficient records")
            segments.append(
                dict(
                    center=pair[0],
                    target=pair[1],
                    frame=1,
                    data_type=2,
                    initial_seconds_from_j2000_tdb=initial + first * span,
                    interval_seconds=span,
                    record_size_doubles=size,
                    record_count=records,
                    offset_bytes=offset,
                    bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    original_first_record_index=first,
                    original_record_count=count,
                    original_segment_start_word=segment.start_i,
                    original_start_byte=start,
                )
            )
            chunks.append(raw)
            offset += len(raw)
        comments = kernel.comments()
    raw = b"".join(chunks)
    manifest = dict(
        model_id=MODEL_ID,
        version="1.0.0",
        source=dict(
            kernel_filename="de440.bsp",
            kernel_sha256=digest,
            url="https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp",
            publication_url="https://ssd.jpl.nasa.gov/doc/de440_de441.html",
            format_url="https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/spk.html",
            original_comments=comments,
        ),
        storage="gzip of concatenated original little-endian float64 type2 records",
        file="de440-solar-extended-v1.bin.gz",
        uncompressed_sha256=hashlib.sha256(raw).hexdigest(),
        uncompressed_bytes=len(raw),
        selected_tdb_years_with_padding=list(PADDING_YEARS),
        software_solar_term_years=list(SOFTWARE_YEARS),
        public_auto_and_de440_input_years=list(PUBLIC_YEARS),
        tdb_coefficient_sha256=hashlib.sha256(tdb_path.read_bytes()).hexdigest(),
        segments=segments,
        coefficients_resampled_rounded_fitted_or_degree_reduced=False,
        reference_event_table_used=False,
        source_endorsement_or_full_accuracy_certified=False,
        derived_product_producer=dict(
            name="FateBridge project contributors",
            institution="FateBridge project",
            product="Third-party extracted solar orbit coefficients; not an unmodified NASA kernel",
            modifications="Body/time selection and storage format; all selected original coefficient bytes retained",
            original_kernel_comments_are_source_archive_only=True,
            redistribution_rules_url="https://naif.jpl.nasa.gov/naif/rules.html",
        ),
    )
    if hashlib.sha256(kernel_path.read_bytes()).hexdigest() != digest:
        raise ValueError("DE440 source changed while extracting")
    return raw, manifest


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--tdb", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw, manifest = extract(args.kernel, args.tdb)
    binary = args.output / manifest["file"]
    metadata = args.output / "de440-solar-extended-v1.json"
    if args.check:
        packed = binary.read_bytes()
        if gzip.decompress(packed) != raw:
            raise SystemExit("Extended coefficient bytes differ from original records")
        manifest["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        if json.loads(metadata.read_bytes()) != manifest:
            raise SystemExit("Extended metadata differ from the frozen extraction")
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        if binary.exists() or metadata.exists():
            raise SystemExit("Refusing to overwrite an existing extended profile")
        packed = gzip.compress(raw, compresslevel=9, mtime=0)
        manifest["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        binary.write_bytes(packed)
        metadata.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    content_sha = hashlib.sha256(
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    print(
        dict(
            model_id=MODEL_ID,
            records=sum(s["record_count"] for s in manifest["segments"]),
            compressed_bytes=len(packed),
            uncompressed_bytes=len(raw),
            manifest_content_sha256=content_sha,
            original_record_bytes_equal=True,
        )
    )


if __name__ == "__main__":
    main()
