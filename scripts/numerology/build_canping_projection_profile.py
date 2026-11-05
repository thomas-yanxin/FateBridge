"""Extract original DE440 position records for the frozen120-year projection.

No runtime calculator or event reference is imported. The existing solar
profiles and civil clock coefficients must remain byte-identical.
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
FIXTURE = ROOT / "tests/fixtures/canping_projection_v1"
DESTINATION = ROOT / "src/fatebridge/data/astronomy"


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def build(kernel_path: Path) -> tuple[bytes, dict[str, Any]]:
    from jplephem.spk import SPK

    protocol_raw = (FIXTURE / "protocol.json").read_bytes()
    p = json.loads(protocol_raw)
    if (
        p["id"] != "canping_complete120_projection_v1"
        or p["future_event_years"] != [2201, 2320]
        or p["record_padding_years"] != [2200, 2323]
        or p["maximum_horizon_years"] != 120
        or hashlib.sha256(kernel_path.read_bytes()).hexdigest()
        != p["source_kernel"]["sha256"]
    ):
        raise ValueError(
            "Preserve the full predeclared horizon and pinned original kernel"
        )
    for name, digest in p["preserve_existing_profiles"].items():
        if hashlib.sha256((DESTINATION / name).read_bytes()).hexdigest() != digest:
            raise ValueError("An existing solar profile changed: " + name)
    low, high = [
        (date(y, 1, 1).toordinal() + 1721424.5 - 2451545.0) * 86400
        for y in p["record_padding_years"]
    ]
    chunks = []
    segments = []
    offset = 0
    with SPK.open(str(kernel_path)) as kernel, kernel_path.open("rb") as stream:
        if kernel.daf.locfmt != b"LTL-IEEE":
            raise ValueError("Expected original little-endian DE440 records")
        for center, target in p["state_sampling"]["body_pairs"]:
            choices = [
                s for s in kernel.segments if (s.center, s.target) == (center, target)
            ]
            if len(choices) != 1:
                raise ValueError("Unexpected source segment priority")
            s = choices[0]
            if s.frame != 1 or s.data_type != 2:
                raise ValueError("Expected J2000 type2 position records")
            initial, span, size, count = map(
                float, s.daf.read_array(s.end_i - 3, s.end_i)
            )
            size, count = int(size), int(count)
            first = max(0, math.ceil((low - initial) / span) - 1)
            last = min(count - 1, math.floor((high - initial) / span))
            n = last - first + 1
            start = (s.start_i - 1 + first * size) * 8
            stream.seek(start)
            raw = stream.read(n * size * 8)
            if len(raw) != n * size * 8:
                raise ValueError("Incomplete original records")
            segments.append(
                dict(
                    center=center,
                    target=target,
                    frame=1,
                    data_type=2,
                    initial_seconds_from_j2000_tdb=initial + first * span,
                    interval_seconds=span,
                    record_size_doubles=size,
                    record_count=n,
                    offset_bytes=offset,
                    bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    original_first_record_index=first,
                    original_record_count=count,
                    original_segment_start_word=s.start_i,
                    original_start_byte=start,
                )
            )
            chunks.append(raw)
            offset += len(raw)
        comments = kernel.comments()
    raw = b"".join(chunks)
    manifest = dict(
        model_id=p["model_id"],
        version="1.0.0",
        source=dict(
            kernel_filename="de440.bsp",
            kernel_sha256=p["source_kernel"]["sha256"],
            url=p["source_kernel"]["url"],
            publication_url="https://ssd.jpl.nasa.gov/doc/de440_de441.html",
            format_url="https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/spk.html",
            original_comments=comments,
        ),
        storage="gzip of concatenated original little-endian float64 type2 records",
        file=p["data_basename"] + ".bin.gz",
        uncompressed_sha256=hashlib.sha256(raw).hexdigest(),
        uncompressed_bytes=len(raw),
        selected_tdb_years_with_padding=p["record_padding_years"],
        software_solar_term_years=p["future_event_years"],
        projection_origin_civil_years=p["origin_civil_years"],
        maximum_projection_horizon_years=120,
        admitted_projection_events=["立春"],
        segments=segments,
        tdb_coefficient_sha256=p["preserve_existing_profiles"][
            "geocentric-tdb-v1.json"
        ],
        selection_protocol_sha256=hashlib.sha256(protocol_raw).hexdigest(),
        coefficients_resampled_rounded_fitted_or_degree_reduced=False,
        reference_event_table_used=False,
        source_endorsement_or_full_accuracy_certified=False,
        derived_product_producer=dict(
            name="FateBridge project contributors",
            institution="FateBridge project",
            product="Third-party extracted solar position coefficients for bounded Canping projections; not an unmodified NASA kernel",
            modifications="Body/time selection and storage; selected original coefficient bytes retained",
            original_kernel_comments_are_source_archive_only=True,
            redistribution_rules_url="https://naif.jpl.nasa.gov/naif/rules.html",
        ),
    )
    return raw, manifest


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw, m = build(args.kernel)
    binary = DESTINATION / m["file"]
    metadata = DESTINATION / (m["file"].replace(".bin.gz", ".json"))
    if args.check:
        packed = binary.read_bytes()
        m["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        assert gzip.decompress(packed) == raw and json.loads(metadata.read_bytes()) == m
    else:
        if binary.exists() or metadata.exists():
            raise SystemExit("Refusing to overwrite existing profile files")
        packed = gzip.compress(raw, compresslevel=9, mtime=0)
        m["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        binary.write_bytes(packed)
        metadata.write_bytes(encoded(m))
    content = hashlib.sha256(
        json.dumps(
            m,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    print(
        dict(
            original_records_equal=True,
            raw_bytes=len(raw),
            compressed_bytes=len(packed),
            manifest_content_sha256=content,
            protocol_sha256=m["selection_protocol_sha256"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
