"""Build shared runtime archives from pinned original source polynomials.

The DE440 inputs are staging products of the five source extractors. The
DE441 input is the continuous direct-access source span and its preserved
download manifest. DE440 views preserve source words; DE441 retains every
selected polynomial degree/domain with bounded binary coefficient quanta.
Neither operation consumes reference states or event times.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import struct
import sys
from array import array
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import TypedDict

from fatebridge.core.astro.coefficient_storage import RecordBlock, pack_records
from fatebridge.core.astro.de441_source import (
    FRAME_URL,
    MODEL_ID,
    PAPER_URL,
    SOURCE_URL,
)
from fatebridge.core.astro.tdb import COEFFICIENT_SHA256 as TDB_SHA256
from fatebridge.core.de440_solar import RecordSegment, SolarManifest

DE441_SOURCE_SHA256 = "88289997e437cf115a95fc60d787129f7213952ecae323035ce341325674eee1"
DE441_DOWNLOAD_MANIFEST_SHA256 = (
    "942787c91479fcb6d4a49cba31e7805e637c423304f1e122003fcdf22a31d3b4"
)
SOLAR_SOURCE_SHA256 = {
    "fatebridge_de440_solar_v1": "19e443ed65e73871ef342effa7bc931bbfb51753270377b9511c75b29b7e4850",
    "fatebridge_de440_solar_historical_v1": "c98f944353434ac9f8c65989837d3196f09a8cb41ecbaecae0f853e0861e5d31",
    "fatebridge_de440_solar_extended_v1": "48df495bc2513d58d369e7e02c53a30209771972e0d40b1b3c58c9385eda6b6b",
    "fatebridge_de440_solar_canping_v1": "cd898a8e5df620581e86049bcb3e4eb856a7fbfc6c52731ce91c3649b37f3f89",
    "fatebridge_de440_solar_canping_extended_v1": "de6e16d62b8bdf293261d88bf47dec2bf4bb548ee1bd5424d8adc8f5c8dffac5",
}


class SourceGroup(TypedDict):
    source_group: int
    source_pointer: list[int]
    offset_words: int
    coefficient_count: int
    subintervals: int
    quantum_binary_exponent_km: int
    coefficient_error_bound_km_exact: str
    position_error_bound_km_exact: str
    velocity_error_bound_km_per_TDB_day_exact: str


def encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()


def solar_atlas(staging: Path) -> dict[str, bytes]:
    profiles: dict[str, SolarManifest] = {}
    records: dict[tuple[int, int], dict[float, bytes]] = {}
    formats: dict[tuple[int, int], tuple[int, float]] = {}
    for metadata in sorted(staging.glob("de440-solar*.json")):
        manifest: SolarManifest = json.loads(metadata.read_bytes())
        packed = (staging / manifest["file"]).read_bytes()
        data = gzip.decompress(packed)
        if (
            manifest["model_id"] not in SOLAR_SOURCE_SHA256
            or manifest["uncompressed_sha256"]
            != SOLAR_SOURCE_SHA256[manifest["model_id"]]
            or hashlib.sha256(packed).hexdigest() != manifest["compressed_sha256"]
            or hashlib.sha256(data).hexdigest() != manifest["uncompressed_sha256"]
            or len(data) != manifest["uncompressed_bytes"]
        ):
            raise ValueError("Staged DE440 records differ from their source commitment")
        profiles[metadata.name] = manifest
        for segment in manifest["segments"]:
            pair = segment["center"], segment["target"]
            size = segment["record_size_doubles"] * 8
            span = segment["interval_seconds"]
            if pair in formats and formats[pair] != (size, span):
                raise ValueError("Inconsistent original DE440 source record layout")
            formats[pair] = size, span
            bucket = records.setdefault(pair, {})
            for index in range(segment["record_count"]):
                at = segment["offset_bytes"] + index * size
                raw = data[at : at + size]
                midpoint, radius = struct.unpack_from("<2d", raw)
                if (midpoint, radius) != (
                    segment["initial_seconds_from_j2000_tdb"] + (index + 0.5) * span,
                    span / 2,
                ) or (midpoint in bucket and bucket[midpoint] != raw):
                    raise ValueError("DE440 source grid or overlapping words differ")
                bucket[midpoint] = raw
    if (
        {m["model_id"] for m in profiles.values()} != set(SOLAR_SOURCE_SHA256)
        or len(profiles) != 5
        or set(records) != {(0, 3), (3, 399), (0, 10)}
    ):
        raise ValueError("All five original solar source selections are required")
    logical = bytearray()
    segments: list[RecordSegment] = []
    offsets: dict[tuple[int, int], tuple[int, float, int, float]] = {}
    for pair, bucket in sorted(records.items()):
        size, span = formats[pair]
        times = sorted(bucket)
        if any(b - a != span for a, b in zip(times, times[1:])):
            raise ValueError("DE440 original record union is not continuous")
        raw = b"".join(bucket[t] for t in times)
        offset = len(logical)
        logical.extend(raw)
        offsets[pair] = offset, times[0], size, span
        segments.append(
            {
                "center": pair[0],
                "target": pair[1],
                "initial_seconds_from_j2000_tdb": times[0] - span / 2,
                "interval_seconds": span,
                "record_size_doubles": size // 8,
                "record_count": len(times),
                "offset_bytes": offset,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    packed = pack_records(
        bytes(logical),
        [
            RecordBlock(s["record_count"], s["record_size_doubles"] * 8)
            for s in segments
        ],
    )
    name = "de440-solar-record-atlas-v1"
    packed_sha = hashlib.sha256(packed).hexdigest()
    atlas = {
        "model_id": "lossless_de440_solar_record_atlas_v1",
        "storage": "record_byte_channels_gzip_v1",
        "file": name + ".bin.gz",
        "uncompressed_bytes": len(logical),
        "uncompressed_sha256": hashlib.sha256(logical).hexdigest(),
        "compressed_sha256": packed_sha,
        "segments": segments,
        "coefficient_values_or_record_domains_changed": False,
        "profile_views": "Five established logical model selections retain their original selected coefficient bytes and individual time domains; only physical storage overlaps are shared.",
    }
    outputs = {name + ".bin.gz": packed, name + ".json": encoded(atlas)}
    for filename, original in profiles.items():
        view = deepcopy(original)
        view["file"] = name + ".bin.gz"
        view["storage"] = "shared_original_type2_record_atlas_v1"
        view["compressed_sha256"] = packed_sha
        view["tdb_coefficient_sha256"] = TDB_SHA256
        selected = bytearray()
        for segment in view["segments"]:
            base, first, size, span = offsets[segment["center"], segment["target"]]
            midpoint = segment["initial_seconds_from_j2000_tdb"] + span / 2
            index = int((midpoint - first) / span)
            if first + index * span != midpoint:
                raise ValueError("DE440 view does not follow its original source grid")
            segment["offset_bytes"] = base + index * size
            at = segment["offset_bytes"]
            raw = logical[at : at + segment["bytes"]]
            if hashlib.sha256(raw).hexdigest() != segment["sha256"]:
                raise ValueError("DE440 selected source-record words changed")
            selected.extend(raw)
        if (
            len(selected) != original["uncompressed_bytes"]
            or hashlib.sha256(selected).hexdigest() != original["uncompressed_sha256"]
        ):
            raise ValueError("DE440 logical profile changed during deduplication")
        outputs[filename] = encoded(view)
    return outputs


def planetary_archive(source: Path, download_manifest: Path) -> dict[str, bytes]:
    if (
        hashlib.sha256(download_manifest.read_bytes()).hexdigest()
        != DE441_DOWNLOAD_MANIFEST_SHA256
    ):
        raise ValueError("DE441 source download commitment changed")
    groups: dict[str, SourceGroup] = {}
    words = array("q")
    source_sha = hashlib.sha256()
    selected_source_sha = hashlib.sha256()
    logical_sha = hashlib.sha256()
    outputs: dict[str, bytes] = {}
    chunks: list[dict[str, str | int]] = []
    chunk_records = 8192
    chunk_count = 0
    name = "de441-planetary-0001-9999-v3"
    with source.open("rb") as stream:
        header = stream.read(8144)
        constants = stream.read(8144)
        source_sha.update(header)
        source_sha.update(constants)
        start, end, span = struct.unpack_from("<3d", header, 2652)
        au, emrat = struct.unpack_from("<2d", header, 2680)
        if struct.unpack_from("<i", header, 2840)[0] != 441 or (
            start,
            end,
            span,
            au,
        ) != (1721392.5, 5373520.5, 32.0, 149597870.7):
            raise ValueError("Unexpected original DE441 source header")
        offset = 0
        for body, number, exponent in [
            ("Mercury", 0, -24),
            ("Venus", 1, -22),
            ("EarthMoonBarycenter", 2, -23),
            ("Mars", 3, -22),
            ("Jupiter", 4, -20),
            ("Saturn", 5, -20),
            ("Uranus", 6, -20),
            ("Neptune", 7, -20),
            ("Pluto", 8, -20),
            ("MoonGeocentric", 9, -25),
            ("Sun", 10, -22),
        ]:
            pointer, count, parts = struct.unpack_from(
                "<3i", header, 2696 + 12 * number
            )
            quantum = Fraction(1, 1 << -exponent)
            width = Fraction(32, parts)
            groups[body] = {
                "source_group": number,
                "source_pointer": [pointer, count, parts],
                "offset_words": offset,
                "coefficient_count": count,
                "subintervals": parts,
                "quantum_binary_exponent_km": exponent,
                "coefficient_error_bound_km_exact": str(quantum / 2),
                "position_error_bound_km_exact": str(count * quantum / 2),
                "velocity_error_bound_km_per_TDB_day_exact": str(
                    quantum * sum(k * k for k in range(count)) / width
                ),
            }
            offset += 3 * count * parts
        records = int((end - start) / span)
        for index in range(records):
            raw = stream.read(8144)
            source_sha.update(raw)
            if len(raw) != 8144 or struct.unpack_from("<2d", raw) != (
                start + index * span,
                start + (index + 1) * span,
            ):
                raise ValueError("Incomplete or discontinuous original DE441 record")
            for group in groups.values():
                at = (group["source_pointer"][0] - 1) * 8
                count = 3 * group["coefficient_count"] * group["subintervals"]
                selected = raw[at : at + count * 8]
                selected_source_sha.update(selected)
                values = struct.unpack("<" + str(count) + "d", selected)
                exponent = group["quantum_binary_exponent_km"]
                quantized = [round(math.ldexp(value, -exponent)) for value in values]
                if any(abs(value) > 2**53 for value in quantized):
                    raise ValueError("Quantized coefficients cannot restore exactly")
                words.extend(quantized)
            chunk_count += 1
            if chunk_count == chunk_records or index == records - 1:
                if sys.byteorder != "little":
                    words.byteswap()
                logical = words.tobytes()
                logical_sha.update(logical)
                packed = pack_records(logical, [RecordBlock(chunk_count, offset * 8)])
                filename = f"{name}-part-{len(chunks):02d}.bin.gz"
                outputs[filename] = packed
                chunks.append(
                    {
                        "file": filename,
                        "first_record": index + 1 - chunk_count,
                        "record_count": chunk_count,
                        "uncompressed_bytes": len(logical),
                        "uncompressed_sha256": hashlib.sha256(logical).hexdigest(),
                        "compressed_bytes": len(packed),
                        "compressed_sha256": hashlib.sha256(packed).hexdigest(),
                    }
                )
                words = array("q")
                chunk_count = 0
        if stream.read() or source_sha.hexdigest() != DE441_SOURCE_SHA256:
            raise ValueError("The continuous DE441 source words changed")
    metadata = {
        "model_id": MODEL_ID,
        "source_version": "JPL DE441, Park-Folkner-Williams-Boggs 2021",
        "source_url": SOURCE_URL,
        "paper_url": PAPER_URL,
        "source_object": "Original planetary-system barycenters, EMB, geocentric Moon and barycentric Sun",
        "source_frame": "ICRF",
        "source_time_scale": "TDB",
        "source_position_unit": "km",
        "source_AU_km": au,
        "source_EMRAT": emrat,
        "binary_order": "little_endian_int64",
        "source_TDB_JD_bounds": [start, end],
        "record_days": span,
        "record_count": records,
        "record_size_words": offset,
        "records_per_chunk": chunk_records,
        "groups": groups,
        "storage": "source_time_chunks_fixed_point_int64_record_byte_channels_gzip_v1",
        "chunks": chunks,
        "uncompressed_bytes": records * offset * 8,
        "uncompressed_sha256": logical_sha.hexdigest(),
        "compressed_bytes": sum(len(value) for value in outputs.values()),
        "coefficient_counts_subcells_axes_and_coverage_preserved": True,
        "original_float_coefficients_bitwise_preserved": False,
        "source_selected_float64_sha256": selected_source_sha.hexdigest(),
        "source_file_sha256": DE441_SOURCE_SHA256,
        "source_header_sha256": hashlib.sha256(header).hexdigest(),
        "source_manifest_sha256": DE441_DOWNLOAD_MANIFEST_SHA256,
        "coefficient_representation": {
            "method": "nearest_even_integer_of_original_binary64_scaled_by_exact_binary_quantum",
            "maximum_integer_magnitude": 2**53,
            "coefficient_bound": "abs(delta_c_k) <= q/2",
            "uniform_position_bound": "N*q/2 per original source axis over x in[-1,1]",
            "uniform_velocity_bound": "q/width * sum(k*k for k in range(N)) per source axis and TDB day",
            "references": [
                "https://dlmf.nist.gov/18.5.E1",
                "https://dlmf.nist.gov/18.9.E21",
            ],
            "scope": "Coefficient representation only; excludes evaluator rounding, physical source error, time conversion and output frame. Small nonzero coefficients may round to zero; basis slots and original time cells remain. Linear derived-state bounds propagate through EMRAT; bounds add for differences.",
        },
        "derived_states": {
            "Earth": "EMB - geocentricMoon/(1+EMRAT)",
            "Moon": "Earth + geocentricMoon",
        },
        "frame_bias": {
            "ICRF_to_mean_J2000": [
                [0.9999999999999941, -7.078368960971559e-08, 8.056213977613186e-08],
                [7.078368694637678e-08, 0.9999999999999969, 3.305943738009795e-08],
                [-8.056214211620057e-08, -3.305943169468331e-08, 0.9999999999999962],
            ],
            "source": FRAME_URL,
            "calculation_epoch_TT_JD": [2451545.0, 0.0],
            "ERFA_version": "2.0.1",
            "pyerfa_version": "2.0.1.5",
        },
        "runtime_usage": "One shared barycentric receiver/target source; TT-tagged lookup uses declared geocentricTDB(TT). Source TDB velocity supplies observer aberration; displayed longitude is differentiated in TT through the complete mapping.",
        "derived_product_producer": "FateBridge project contributors; source selection, bounded fixed-point coefficients and reversible byte-channel/gzip time chunks. Not an unmodified NASA kernel or provider endorsement.",
        "source_qualification": "Prepared continuous source span with guard records, not the whole remote2.79GB file. Source-file SHA and original download manifest are separate commitments. All original coefficient slots, source/time coverage and fixed quantization policy retained; no reference-state fit. No observational or broad civil-clock certification.",
    }
    outputs[name + ".json"] = encoded(metadata)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--solar-profiles", type=Path, required=True)
    parser.add_argument("--de441-source", type=Path, required=True)
    parser.add_argument("--de441-source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = solar_atlas(args.solar_profiles)
    outputs.update(planetary_archive(args.de441_source, args.de441_source_manifest))
    for name, content in outputs.items():
        path = args.output / name
        if args.check:
            if path.read_bytes() != content:
                raise SystemExit(f"Distributed coefficient product differs: {name}")
        else:
            args.output.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    print(
        json.dumps(
            {
                name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                for name, raw in outputs.items()
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
