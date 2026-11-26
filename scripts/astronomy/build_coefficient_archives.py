"""Build shared runtime archives from pinned original source polynomials.

The DE440 inputs are staging products of the five source extractors. The
DE441 input is the continuous direct-access source span and its preserved
download manifest. DE440 views preserve source words; DE441 preserves every
selected original coefficient byte on its existing polynomial grid/domain.
Neither operation consumes reference states or event times.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import struct
from collections.abc import Iterator
from copy import deepcopy
from itertools import chain
from pathlib import Path
from typing import TypedDict

from fatebridge.core.astro.coefficient_storage import RecordBlock, pack_records
from fatebridge.core.astro.de441_source import (
    FRAME_URL,
    PAPER_URL,
    SOURCE_URL,
)
from fatebridge.core.astro.de441_storage import BASENAME as DE441_BASENAME
from fatebridge.core.astro.de441_storage import BINARY_ORDER as DE441_BINARY_ORDER
from fatebridge.core.astro.de441_storage import MODEL_ID
from fatebridge.core.astro.de441_storage import STORAGE as DE441_STORAGE
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
    """Header layout for one planetary body group in the DE441 source."""

    source_group: int
    source_pointer: list[int]
    offset_words: int
    coefficient_count: int
    subintervals: int


def encoded(value: object) -> bytes:
    """Serialize a manifest dictionary to deterministic UTF-8 JSON bytes."""
    return (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()


def solar_atlas(staging: Path) -> dict[str, bytes]:
    """Merge the five staged DE440 solar profiles into one shared record atlas."""
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
        else:
            pass
        profiles[metadata.name] = manifest
        for segment in manifest["segments"]:
            pair = segment["center"], segment["target"]
            size = segment["record_size_doubles"] * 8
            span = segment["interval_seconds"]
            if pair in formats and formats[pair] != (size, span):
                raise ValueError("Inconsistent original DE440 source record layout")
            else:
                pass
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
                else:
                    pass
                bucket[midpoint] = raw
    if (
        {m["model_id"] for m in profiles.values()} != set(SOLAR_SOURCE_SHA256)
        or len(profiles) != 5
        or set(records) != {(0, 3), (3, 399), (0, 10)}
    ):
        raise ValueError("All five original solar source selections are required")
    else:
        pass
    logical = bytearray()
    segments: list[RecordSegment] = []
    offsets: dict[tuple[int, int], tuple[int, float, int, float]] = {}
    for pair, bucket in sorted(records.items()):
        size, span = formats[pair]
        times = sorted(bucket)
        if any(b - a != span for a, b in zip(times, times[1:])):
            raise ValueError("DE440 original record union is not continuous")
        else:
            pass
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
            }
        )
    logical_bytes = bytes(logical)
    packed = pack_records(
        logical_bytes,
        [
            RecordBlock(s["record_count"], s["record_size_doubles"] * 8)
            for s in segments
        ],
    )
    name = "de440-solar-record-atlas-v1"
    atlas = {
        "model_id": "lossless_de440_solar_record_atlas_v1",
        "storage": "record_byte_channels_gzip_v1",
        "file": name + ".bin.gz",
        "uncompressed_bytes": len(logical_bytes),
        "segments": segments,
        "coefficient_values_or_record_domains_changed": False,
        "profile_views": "Five established logical model selections retain their original selected coefficient bytes and individual time domains; only physical storage overlaps are shared.",
    }
    outputs = {name + ".bin.gz": packed, name + ".json": encoded(atlas)}
    for filename, original in profiles.items():
        view = deepcopy(original)
        view["file"] = name + ".bin.gz"
        view["storage"] = "shared_original_type2_record_atlas_v1"
        view_obj: dict[str, object] = dict(view)
        for key in (
            "compressed_sha256",
            "uncompressed_sha256",
            "tdb_coefficient_sha256",
            "selection_protocol_sha256",
        ):
            view_obj.pop(key, None)
        if filename != "de440-solar-v1.json" and isinstance(
            source_value := view_obj.get("source"), dict
        ):
            view_obj["source"] = {
                k: v for k, v in source_value.items() if k != "kernel_sha256"
            }
        selected = bytearray()
        cleaned_segments: list[dict[str, object]] = []
        for segment in view["segments"]:
            base, first, size, span = offsets[segment["center"], segment["target"]]
            midpoint = segment["initial_seconds_from_j2000_tdb"] + span / 2
            index = int((midpoint - first) / span)
            if first + index * span != midpoint:
                raise ValueError("DE440 view does not follow its original source grid")
            else:
                pass
            segment["offset_bytes"] = base + index * size
            at = segment["offset_bytes"]
            segment_raw = logical_bytes[at : at + segment["bytes"]]
            segment_obj: dict[str, object] = dict(segment)
            expected_segment_sha = segment_obj.pop("sha256", None)
            if (
                isinstance(expected_segment_sha, str)
                and hashlib.sha256(segment_raw).hexdigest() != expected_segment_sha
            ):
                raise ValueError("DE440 selected source-record words changed")
            else:
                pass
            cleaned_segments.append(segment_obj)
            selected.extend(segment_raw)
        view_obj["segments"] = cleaned_segments
        original_obj: dict[str, object] = dict(original)
        expected_uncompressed_sha = original_obj.get("uncompressed_sha256")
        if len(selected) != original["uncompressed_bytes"] or (
            isinstance(expected_uncompressed_sha, str)
            and hashlib.sha256(selected).hexdigest() != expected_uncompressed_sha
        ):
            raise ValueError("DE440 logical profile changed during deduplication")
        else:
            pass
        outputs[filename] = encoded(view_obj)
    return outputs


def planetary_archive(
    source: Path, download_manifest: Path
) -> Iterator[tuple[str, bytes]]:
    """Chunk continuous DE441 polynomial records and yield archive files and metadata."""
    if (
        hashlib.sha256(download_manifest.read_bytes()).hexdigest()
        != DE441_DOWNLOAD_MANIFEST_SHA256
    ):
        raise ValueError("DE441 source download commitment changed")
    else:
        pass
    groups: dict[str, SourceGroup] = {}
    words = bytearray()
    source_sha = hashlib.sha256()
    compressed_bytes = 0
    chunks: list[dict[str, str | int]] = []
    chunk_records = 8192
    chunk_count = 0
    name = DE441_BASENAME
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
        else:
            pass
        offset = 0
        for body, number in [
            ("Mercury", 0),
            ("Venus", 1),
            ("EarthMoonBarycenter", 2),
            ("Mars", 3),
            ("Jupiter", 4),
            ("Saturn", 5),
            ("Uranus", 6),
            ("Neptune", 7),
            ("Pluto", 8),
            ("MoonGeocentric", 9),
            ("Sun", 10),
        ]:
            pointer, count, parts = struct.unpack_from(
                "<3i", header, 2696 + 12 * number
            )
            groups[body] = {
                "source_group": number,
                "source_pointer": [pointer, count, parts],
                "offset_words": offset,
                "coefficient_count": count,
                "subintervals": parts,
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
            else:
                pass
            for group in groups.values():
                at = (group["source_pointer"][0] - 1) * 8
                count = 3 * group["coefficient_count"] * group["subintervals"]
                selected = raw[at : at + count * 8]
                # Preserve the actual 8-byte words, including signed zero and
                # every coefficient bit; no float decode/encode is performed.
                words.extend(selected)
            chunk_count += 1
            if chunk_count == chunk_records or index == records - 1:
                logical = bytes(words)
                packed = pack_records(logical, [RecordBlock(chunk_count, offset * 8)])
                filename = f"{name}-part-{len(chunks):02d}.bin.gz"
                compressed_bytes += len(packed)
                chunks.append(
                    {
                        "file": filename,
                        "first_record": index + 1 - chunk_count,
                        "record_count": chunk_count,
                        "uncompressed_bytes": len(logical),
                        "compressed_bytes": len(packed),
                    }
                )
                yield filename, packed
                words = bytearray()
                chunk_count = 0
            else:
                pass
        if stream.read() or source_sha.hexdigest() != DE441_SOURCE_SHA256:
            raise ValueError("The continuous DE441 source words changed")
        else:
            pass
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
        "binary_order": DE441_BINARY_ORDER,
        "source_TDB_JD_bounds": [start, end],
        "record_days": span,
        "record_count": records,
        "record_size_words": offset,
        "records_per_chunk": chunk_records,
        "groups": groups,
        "storage": DE441_STORAGE,
        "chunks": chunks,
        "uncompressed_bytes": records * offset * 8,
        "compressed_bytes": compressed_bytes,
        "coefficient_counts_subcells_axes_and_coverage_preserved": True,
        "original_float_coefficients_bitwise_preserved": True,
        "coefficient_representation": {
            "method": "original_selected_binary64_bytes_copied_without_numeric_conversion",
            "coefficient_rounding_or_quantization_applied": False,
            "scope": "Selected original coefficient bytes only; excludes evaluator rounding, source physics, time conversion, optical mapping and output frame.",
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
        "derived_product_producer": "FateBridge project contributors; selected original binary64 coefficient bytes and reversible byte-channel/gzip time chunks. Not a complete unmodified NASA kernel or provider endorsement.",
        "source_qualification": "Prepared continuous source span with guard records, not the whole remote2.79GB file. Source-file SHA and original download manifest are separate commitments. Selected original8-byte coefficient fields are copied without numeric conversion; source/time coverage retained. Independent acceptance is separate from generation. No observational, optical or broad civil-clock certification.",
    }
    yield name + ".json", encoded(metadata)


def main() -> int:
    """Build or verify shared DE440 and DE441 runtime coefficient archives."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solar-profiles", type=Path)
    parser.add_argument("--de441-source", type=Path, required=True)
    parser.add_argument("--de441-source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    identities = {}
    outputs = chain(
        (
            solar_atlas(args.solar_profiles).items()
            if args.solar_profiles is not None
            else ()
        ),
        planetary_archive(args.de441_source, args.de441_source_manifest),
    )
    for name, content in outputs:
        path = args.output / name
        if args.check:
            if path.read_bytes() != content:
                raise SystemExit(f"Distributed coefficient product differs: {name}")
            else:
                pass
        else:
            args.output.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        identities[name] = {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    print(json.dumps(identities, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
