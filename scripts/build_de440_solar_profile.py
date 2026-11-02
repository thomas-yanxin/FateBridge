"""Losslessly extract fixed DE440 type2 records; no event/reference inputs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_de440_default_v1"
DESTINATION = ROOT / "src/fatebridge/data/astronomy"
MODEL_ID = "fatebridge_de440_solar_v1"
NUMBER = r"[-+]?(?:\d+\.?(?:\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def build(kernel_path: Path) -> tuple[bytes, dict[str, Any], bytes]:
    from jplephem.spk import SPK  # type: ignore[import-untyped]

    protocol = json.loads((FIXTURE / "protocol.json").read_text())
    kernel_sha = hashlib.sha256(kernel_path.read_bytes()).hexdigest()
    if kernel_sha != protocol["source_kernel"]["sha256"]:
        raise ValueError("Only the pinned original DE440 kernel can be extracted")
    low = (date(1798, 1, 1).toordinal() + 1721424.5 - 2451545.0) * 86400
    high = (date(2203, 1, 1).toordinal() + 1721424.5 - 2451545.0) * 86400
    chunks, segments, offset = [], [], 0
    with SPK.open(str(kernel_path)) as kernel, kernel_path.open("rb") as stream:
        if kernel.daf.locfmt != b"LTL-IEEE":
            raise ValueError("Pinned extraction requires original little-endian bytes")
        for center, target in [(0, 3), (3, 399), (0, 10)]:
            candidates = [
                s for s in kernel.segments if (s.center, s.target) == (center, target)
            ]
            if len(candidates) != 1:
                raise ValueError("Unexpected original segment priority")
            segment = candidates[0]
            if segment.frame != 1 or segment.data_type != 2:
                raise ValueError("Only J2000 type2 position records are supported")
            init, span, size, count = map(
                float, segment.daf.read_array(segment.end_i - 3, segment.end_i)
            )
            size, count = int(size), int(count)
            first = max(0, math.ceil((low - init) / span) - 1)
            last = min(count - 1, math.floor((high - init) / span))
            n = last - first + 1
            start_byte = (segment.start_i - 1 + first * size) * 8
            stream.seek(start_byte)
            raw = stream.read(n * size * 8)
            if len(raw) != n * size * 8:
                raise ValueError("Incomplete original coefficient records")
            segments.append(
                {
                    "center": center,
                    "target": target,
                    "frame": 1,
                    "data_type": 2,
                    "initial_seconds_from_j2000_tdb": init + first * span,
                    "interval_seconds": span,
                    "record_size_doubles": size,
                    "record_count": n,
                    "offset_bytes": offset,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "original_first_record_index": first,
                    "original_record_count": count,
                    "original_segment_start_word": segment.start_i,
                    "original_start_byte": start_byte,
                }
            )
            chunks.append(raw)
            offset += len(raw)
        comments = kernel.comments()
    raw = b"".join(chunks)
    manifest = {
        "model_id": MODEL_ID,
        "version": "1.0.0",
        "source": {
            "kernel_filename": "de440.bsp",
            "kernel_sha256": kernel_sha,
            "url": protocol["source_kernel"]["url"],
            "publication_url": "https://ssd.jpl.nasa.gov/doc/de440_de441.html",
            "format_url": "https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/spk.html",
            "original_comments": comments,
        },
        "storage": "gzip of concatenated original little-endian float64 type2 records",
        "file": "de440-solar-v1.bin.gz",
        "uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
        "uncompressed_bytes": len(raw),
        "selected_tdb_years_with_padding": [1798, 2203],
        "software_solar_term_years": [1800, 2200],
        "segments": segments,
        "coefficients_resampled_rounded_fitted_or_degree_reduced": False,
        "reference_event_table_used": False,
        "source_endorsement_or_full_accuracy_certified": False,
        "derived_product_producer": {
            "name": "FateBridge project contributors",
            "institution": "FateBridge project",
            "product": "Third-party extracted solar orbit coefficients; not an unmodified NASA kernel",
            "modifications": "Body/time selection and storage format; all selected original coefficient bytes retained",
            "original_kernel_comments_are_source_archive_only": True,
            "redistribution_rules_url": "https://naif.jpl.nasa.gov/naif/rules.html",
        },
    }
    source = (FIXTURE / "dtdb.c").read_bytes()
    if (
        hashlib.sha256(source).hexdigest()
        != protocol["geocentric_tdb_source"]["sha256"]
    ):
        raise ValueError("Pinned ERFA dtdb source changed")
    clean = re.sub(r"/\*.*?\*/", "", source.decode(), flags=re.S)
    table = re.search(r"fairhd\[787\]\[3\]\s*=\s*\{(.*?)\};", clean, re.S)
    if table is None:
        raise ValueError("Missing Fairhead table")
    rows = [
        [float(n) for n in re.findall(NUMBER, row)]
        for row in re.findall(r"\{([^{}]+)\}", table[1])
    ]
    if len(rows) != 787 or any(len(row) != 3 for row in rows):
        raise ValueError("Incomplete Fairhead terms")
    tdb = encoded(
        {
            "model_id": "fatebridge_geocentric_erfa_dtdb_v1",
            "source": protocol["geocentric_tdb_source"],
            "license": "erfa-license.txt",
            "observer_u_v_km": [0, 0],
            "fairhead_terms": rows,
            "author_comparison_years": [1950, 2050],
            "source_endorsement_or_full_accuracy_certified": False,
        }
    )
    return raw, manifest, tdb


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--update-metadata", action="store_true")
    args = parser.parse_args()
    raw, manifest, tdb = build(args.kernel)
    binary = DESTINATION / manifest["file"]
    metadata = DESTINATION / "de440-solar-v1.json"
    tdb_path = DESTINATION / "geocentric-tdb-v1.json"
    if args.check or args.update_metadata:
        packed = binary.read_bytes()
        manifest["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        if gzip.decompress(packed) != raw:
            raise SystemExit("Distributed DE440 records differ from pinned source")
        if tdb_path.read_bytes() != tdb:
            raise SystemExit("Distributed geocentric TDB terms differ from ERFA")
        if args.update_metadata:
            metadata.write_bytes(encoded(manifest))
        elif metadata.read_bytes() != encoded(manifest):
            raise SystemExit("Distributed DE440 metadata differ from the extractor")
    else:
        if any(p.exists() for p in [binary, metadata, tdb_path]):
            raise SystemExit("Refusing to replace an existing data profile")
        packed = gzip.compress(raw, compresslevel=9, mtime=0)
        manifest["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        binary.write_bytes(packed)
        metadata.write_bytes(encoded(manifest))
        tdb_path.write_bytes(tdb)
    print(
        {
            "all_original_record_bytes_equal": True,
            "uncompressed_bytes": len(raw),
            "compressed_bytes": len(packed),
            "manifest_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(),
            "record_counts": [s["record_count"] for s in manifest["segments"]],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
