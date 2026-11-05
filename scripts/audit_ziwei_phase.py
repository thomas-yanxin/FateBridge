"""Independently parse NASA new moons and verify the 1900 lunar-day gap."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import _lunar_date_from_solar

FIXTURES = Path(__file__).resolve().parents[1] / "tests/data/ziwei_independent"
MONTHS = dict(
    zip(
        (
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ),
        range(1, 13),
    )
)


def new_moons(text: str) -> list[datetime]:
    """Read only the fixed-width new-moon column, never another phase.

    NASA can print a year on a row with no new moon (1901 starts with a full
    moon). Matching the first date anywhere on that line would be incorrect.
    """
    year = None
    moments = []
    for line in text.splitlines():
        prefix = line[:8].strip()
        if prefix.isdecimal() and len(prefix) == 4:
            year = int(prefix)
        elif prefix:
            continue
        cell = re.fullmatch(
            r"([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2})", line[8:21]
        )
        if year is None or not cell:
            continue
        month, day, hour, minute = cell.groups()
        moments.append(
            datetime(
                year,
                MONTHS[month],
                int(day),
                int(hour),
                int(minute),
                tzinfo=timezone.utc,
            )
        )
    return moments


def audit_phase_days(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "phase_manifest.json").read_text(encoding="utf-8")
    )
    moments = []
    for source in manifest["sources"]:
        data = (fixtures / source["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError("NASA phase source checksum mismatch")
        moments.extend(new_moons(data.decode("utf-8")))
    if len(moments) != len(set(moments)):
        raise ValueError("Duplicate NASA new-moon boundary")
    moments = sorted(moments)
    offset = timezone(timedelta(hours=manifest["civil_day_offset_hours"]))
    local = [t.astimezone(offset) for t in moments]
    start, end = (
        date.fromisoformat(manifest[key]) for key in ("coverage_start", "coverage_end")
    )
    boundaries = [
        t
        for t in local
        if start - timedelta(days=31) <= t.date() <= end + timedelta(days=31)
    ]
    if not boundaries or boundaries[0].date() > start or boundaries[-1].date() <= end:
        raise ValueError("NASA boundary coverage is incomplete")
    if any(
        not 29 <= (b.date() - a.date()).days <= 30
        for a, b in zip(boundaries, boundaries[1:])
    ):
        raise ValueError("Missing or non-lunation NASA boundary")
    mismatches = []
    current = start
    checked = 0
    while current <= end:
        previous = max(t.date() for t in boundaries if t.date() <= current)
        expected = (current - previous).days + 1
        actual = _lunar_date_from_solar(current).day
        if actual != expected:
            mismatches.append(
                dict(solar=current.isoformat(), expected=expected, actual=actual)
            )
        checked += 1
        current += timedelta(days=1)
    near = [t for t in boundaries if start <= t.date() <= end]
    margins = [min(t.hour * 60 + t.minute, 1440 - t.hour * 60 - t.minute) for t in near]
    return {
        "status": "pass_in_frozen_corpus" if not mismatches else "failed",
        "lunar_day_cells_checked": checked,
        "new_moon_boundaries_in_range": len(near),
        "minimum_minutes_to_local_midnight": min(margins),
        "checked_field": manifest["checked_field"],
        "civil_day_offset_hours": manifest["civil_day_offset_hours"],
        "mismatches": mismatches,
        "limits": manifest["limits"],
    }
