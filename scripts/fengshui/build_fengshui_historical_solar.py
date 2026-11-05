"""Extract original DE440 records for the predeclared Feng Shui protocol span.

Research dependency: jplephem2.24. No FateBridge calculation or event table is
imported. The existing default data profile is never replaced.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/fengshui_historical_solar_v1"
DATA = ROOT / "src/fatebridge/data/astronomy"


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def build(kernel_path: Path) -> tuple[bytes, dict[str, Any], bytes]:
    from jplephem.spk import SPK  # type: ignore[import-untyped]

    protocol_raw = (FIXTURE / "protocol.json").read_bytes()
    protocol = json.loads(protocol_raw)
    if (
        protocol["id"] != "fengshui_de440_historical_extension_v1"
        or protocol["software_years"] != [1784, 2204]
        or protocol["record_padding_years"] != [1782, 2207]
        or protocol["source_kernel"]["sha256"]
        != hashlib.sha256(kernel_path.read_bytes()).hexdigest()
    ):
        raise ValueError("Keep the predeclared full protocol and pinned DE440 kernel")
    for name, digest in protocol["preserve_base_profile"]["files"].items():
        if hashlib.sha256((DATA / name).read_bytes()).hexdigest() != digest:
            raise ValueError("The original data profile must remain byte-identical")
    low, high = [
        (date(year, 1, 1).toordinal() + 1721424.5 - 2451545.0) * 86400
        for year in protocol["record_padding_years"]
    ]
    chunks, segments, offset, states = [], [], 0, []
    with SPK.open(str(kernel_path)) as kernel, kernel_path.open("rb") as stream:
        if kernel.daf.locfmt != b"LTL-IEEE":
            raise ValueError("Expected the pinned little-endian original kernel")
        for center, target in protocol["state_sampling"]["body_pairs"]:
            candidates = [
                s for s in kernel.segments if (s.center, s.target) == (center, target)
            ]
            if len(candidates) != 1:
                raise ValueError("Unexpected original segment priority")
            segment = candidates[0]
            if segment.frame != 1 or segment.data_type != 2:
                raise ValueError(
                    "Only original J2000 type2 position records are admitted"
                )
            initial, span, size, count = map(
                float, segment.daf.read_array(segment.end_i - 3, segment.end_i)
            )
            size, count = int(size), int(count)
            first = max(0, math.ceil((low - initial) / span) - 1)
            last = min(count - 1, math.floor((high - initial) / span))
            n = last - first + 1
            start_byte = (segment.start_i - 1 + first * size) * 8
            stream.seek(start_byte)
            raw = stream.read(n * size * 8)
            if len(raw) != n * size * 8:
                raise ValueError("Incomplete original record extraction")
            segments.append(
                {
                    "center": center,
                    "target": target,
                    "frame": 1,
                    "data_type": 2,
                    "initial_seconds_from_j2000_tdb": initial + first * span,
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
            for year in range(1784, 2205):
                for month in (1, 4, 7, 10):
                    epoch = date(year, month, 1).toordinal() + 1721424.5
                    position, velocity = segment.compute_and_differentiate(epoch)
                    states.append(
                        {
                            "center": center,
                            "target": target,
                            "tdb_jd": epoch,
                            "position_km": list(map(float, position)),
                            "velocity_km_per_day": list(map(float, velocity)),
                        }
                    )
        comments = kernel.comments()
    data = b"".join(chunks)
    manifest = {
        "model_id": protocol["model_id"],
        "version": "1.0.0",
        "source": {
            "kernel_filename": "de440.bsp",
            "kernel_sha256": protocol["source_kernel"]["sha256"],
            "url": protocol["source_kernel"]["url"],
            "publication_url": "https://ssd.jpl.nasa.gov/doc/de440_de441.html",
            "format_url": "https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/spk.html",
            "original_comments": comments,
        },
        "storage": "gzip of concatenated original little-endian float64 type2 records",
        "file": protocol["data_basename"] + ".bin.gz",
        "uncompressed_sha256": hashlib.sha256(data).hexdigest(),
        "uncompressed_bytes": len(data),
        "selected_tdb_years_with_padding": protocol["record_padding_years"],
        "software_solar_term_years": protocol["software_years"],
        "segments": segments,
        "tdb_coefficient_sha256": protocol["tdb_sha256"],
        "selection_protocol_sha256": hashlib.sha256(protocol_raw).hexdigest(),
        "coefficients_resampled_rounded_fitted_or_degree_reduced": False,
        "reference_event_table_used": False,
        "source_endorsement_or_full_accuracy_certified": False,
        "derived_product_producer": {
            "name": "FateBridge project contributors",
            "institution": "FateBridge project",
            "product": "Third-party extracted historical solar orbit coefficients; not an unmodified NASA kernel",
            "modifications": "Body/time selection and storage format; original selected coefficient bytes retained",
            "original_kernel_comments_are_source_archive_only": True,
            "redistribution_rules_url": "https://naif.jpl.nasa.gov/naif/rules.html",
        },
    }
    return (
        data,
        manifest,
        encoded(
            {
                "protocol_sha256": hashlib.sha256(protocol_raw).hexdigest(),
                "source_kernel_sha256": protocol["source_kernel"]["sha256"],
                "independent_evaluator": "jplephem2.24 original full SPK",
                "epochs": 1684,
                "state_rows": 5052,
                "rows": states,
            }
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw, manifest, states = build(args.kernel)
    binary = DATA / manifest["file"]
    metadata = binary.with_name("de440-solar-historical-v1.json")
    expected = FIXTURE / "states.json.gz"
    if args.check:
        packed = binary.read_bytes()
        if (
            gzip.decompress(packed) != raw
            or gzip.decompress(expected.read_bytes()) != states
        ):
            raise SystemExit(
                "Historical coefficients or independent states differ from source"
            )
        manifest["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        if metadata.read_bytes() != encoded(manifest):
            raise SystemExit("Historical source metadata changed")
    else:
        if any(p.exists() for p in (binary, metadata, expected)):
            raise SystemExit("Refusing to replace an existing frozen profile")
        packed = gzip.compress(raw, compresslevel=9, mtime=0)
        manifest["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        binary.write_bytes(packed)
        metadata.write_bytes(encoded(manifest))
        expected.write_bytes(gzip.compress(states, compresslevel=9, mtime=0))
    print(
        json.dumps(
            {
                "all_selected_original_record_bytes_retained": True,
                "compressed_bytes": len(packed),
                "raw_bytes": len(raw),
                "manifest_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(),
                "independent_state_rows": 5052,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
