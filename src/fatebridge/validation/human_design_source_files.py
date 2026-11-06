"""Shared exact file-metadata validation; supplied hashes are not signatures."""

from typing import Any

from fatebridge.core.astro.ephemeris_integrity import load_ephemeris_manifest
from fatebridge.core.public_output import same_public_value as _same_value


def verify_source_files(
    files: list[dict[str, Any]], *, allowed_slots: tuple[int, ...] = (0, 1, 2)
) -> dict[str, dict[str, Any]]:
    manifest = load_ephemeris_manifest()["files"]
    by_id = {r["id"]: r for r in files}
    if len(by_id) != len(files) or [r["id"] for r in files] != sorted(by_id):
        raise ValueError("Duplicate or unsorted cycle source files")
    for row in files:
        name, slot = row["filename"], row["slot"]
        if (
            not isinstance(name, str)
            or not name
            or any(c in name for c in "/\\\0")
            or type(slot) is not int
            or slot not in allowed_slots
            or type(row["bytes"]) is not int
            or row["bytes"] <= 0
            or type(row["de_number"]) is not int
            or row["de_number"] <= 0
        ):
            raise ValueError("Malformed cycle source file identity")
        prefix = row["id"].split(":")[0]
        if prefix not in {"se1", "jpl"} or (prefix == "jpl" and slot != 0):
            raise ValueError("Invalid cycle file slot/prefix")
        scale = "tdb" if prefix == "jpl" else "tt"
        start, end = row[f"start_julian_day_{scale}"], row[f"end_julian_day_{scale}"]
        if (
            type(start) not in (float, int)
            or type(end) not in (float, int)
            or not -1e9 < start < end < 1e9
        ):
            raise ValueError("Malformed cycle file range")
        if row["id"] != f"{prefix}:{slot}:{name}":
            raise ValueError("Cycle file id does not match its filename and slot")
        record = manifest.get(name)
        matched = row["matches_packaged_manifest"]
        if type(matched) is not bool or (
            matched and (not record or record["bytes"] != row["bytes"])
        ):
            raise ValueError("File manifest metadata is inconsistent")
        expected = {
            "id": row["id"],
            "slot": slot,
            "filename": name,
            "bytes": row["bytes"],
            "range_time_scale": scale.upper(),
            f"start_julian_day_{scale}": start,
            f"end_julian_day_{scale}": end,
            "de_number": row["de_number"],
            "matches_packaged_manifest": matched,
        }
        if not _same_value(row, expected):
            raise ValueError("Cycle manifest or file metadata mismatch")
    return by_id
