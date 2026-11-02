"""Shared exact file-metadata validation; supplied hashes are not signatures."""

import re
from typing import Any

from fatebridge.core.astro.ephemeris_integrity import load_ephemeris_manifest
from fatebridge.validation.claims import _same_value


def verify_source_files(
    files: list[dict[str, Any]], *, allowed_slots: tuple[int, ...] = (0, 1, 2)
) -> dict[str, dict[str, Any]]:
    manifest = load_ephemeris_manifest()["files"]
    by_id = {r["id"]: r for r in files}
    if len(by_id) != len(files) or [r["id"] for r in files] != sorted(by_id):
        raise ValueError("Duplicate or unsorted cycle source files")
    for row in files:
        name, slot, digest = row["filename"], row["slot"], row["sha256"]
        if (
            not isinstance(name, str)
            or not name
            or any(c in name for c in "/\\\0")
            or type(slot) is not int
            or slot not in allowed_slots
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or type(row["bytes"]) is not int
            or row["bytes"] <= 0
            or type(row["de_number"]) is not int
            or row["de_number"] <= 0
        ):
            raise ValueError("Malformed cycle source file identity")
        start, end = row["start_julian_day_tt"], row["end_julian_day_tt"]
        if (
            type(start) not in (float, int)
            or type(end) not in (float, int)
            or not -1e9 < start < end < 1e9
        ):
            raise ValueError("Malformed cycle file range")
        prefix = row["id"].split(":")[0]
        if prefix not in {"se1", "jpl"} or (prefix == "jpl" and slot != 0):
            raise ValueError("Invalid cycle file slot/prefix")
        if row["id"] != f"{prefix}:{slot}:{digest}":
            raise ValueError("Cycle file id does not bind its digest")
        record = manifest.get(name)
        expected = {
            "id": row["id"],
            "slot": slot,
            "filename": name,
            "sha256": digest,
            "bytes": row["bytes"],
            "start_julian_day_tt": start,
            "end_julian_day_tt": end,
            "de_number": row["de_number"],
            "matches_packaged_manifest": bool(
                record
                and record["sha256"] == digest
                and record["bytes"] == row["bytes"]
            ),
        }
        if not _same_value(row, expected):
            raise ValueError("Cycle manifest or file metadata mismatch")
    return by_id
