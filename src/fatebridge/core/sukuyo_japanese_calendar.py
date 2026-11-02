"""Offline HuTime daily-reference facts with a captured immutable month index.

This is a named reference-calendar snapshot, not an ancient time standard or
an independently collated complete Jingu edition. Never fall back to China.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_japanese_daily_v1.json"


@dataclass(frozen=True)
class _Table:
    starts: tuple[int, ...]
    rows: tuple[tuple[int, int, bool, int], ...]
    first: date
    last: date
    sha256: str
    metadata_json: str


@lru_cache(maxsize=4)
def _table(path: Path) -> _Table:
    record = load_source(path)
    bundle = record.data
    rows, starts = [], []
    previous_end = None
    previous_label = None
    for civil_text, year, month, leap, length in bundle["months"]:
        civil = date.fromisoformat(civil_text)
        if (
            type(year) is not int
            or type(month) is not int
            or type(leap) is not bool
            or type(length) is not int
            or not 1 <= month <= 12
            or length not in (29, 30)
        ):
            raise ValueError("Invalid Japanese reference-calendar month")
        if previous_end is not None and civil != previous_end:
            raise ValueError(
                "Japanese reference-calendar month intervals are not contiguous"
            )
        if previous_label is not None:
            py, pm, pl = previous_label
            expected = (py + 1, 1) if pm == 12 else (py, pm + 1)
            if (leap and (pl or (year, month) != (py, pm))) or (
                not leap and (year, month) != expected
            ):
                raise ValueError(
                    "Japanese reference-calendar labels are not sequential"
                )
        starts.append(civil.toordinal())
        rows.append((year, month, leap, length))
        previous_end = civil + timedelta(days=length)
        previous_label = (year, month, leap)
    first, last = map(date.fromisoformat, bundle["supported_range_inclusive"])
    if (
        not starts
        or first.toordinal() != starts[0]
        or previous_end != last + timedelta(days=1)
        or sum(r[3] for r in rows) != bundle["reference_day_count"]
    ):
        raise ValueError("Japanese reference-calendar domain does not match its data")
    metadata = {k: v for k, v in bundle.items() if k != "months"}
    # The immutable index and its metadata use this same captured record. An
    # LRU eviction elsewhere cannot attach a new disk hash to an old index.
    return _Table(
        tuple(starts),
        tuple(rows),
        first,
        last,
        record.sha256,
        json.dumps(metadata, ensure_ascii=False),
    )


def supported_range() -> tuple[date, date]:
    table = _table(SOURCE)
    return table.first, table.last


def reference_metadata() -> dict[str, Any]:
    table = _table(SOURCE)
    return {**json.loads(table.metadata_json), "source_bundle_sha256": table.sha256}


def lunar_fields(civil: date) -> tuple[int, int, int, bool]:
    table = _table(SOURCE)
    if not table.first <= civil <= table.last:
        raise ValueError(
            f"日本旧历参考数据仅支持{table.first}至{table.last}；范围外不回退中国历或外推"
        )
    index = bisect_right(table.starts, civil.toordinal()) - 1
    year, month, leap, _ = table.rows[index]
    return year, month, civil.toordinal() - table.starts[index] + 1, leap


def date_reference(civil: date) -> dict[str, Any]:
    year, _, _, _ = lunar_fields(civil)
    metadata = reference_metadata()
    origin = (
        "published_almanac_entries"
        if civil.year <= 1909
        else (
            "provider_reconstruction_from_published_astronomical_data"
            if civil.year <= 1946
            else (
                "provider_transcription_of_jingu_almanacs_with_disclosed_editorial_choices"
                if civil.year <= 2014
                else "provider_reference_projection_not_whole_jingu_edition_verified"
            )
        )
    )
    jd = 2451544.5 + (civil - date(2000, 1, 1)).days
    return {
        **metadata,
        "date_source_uri": f"http://datetime.hutime.org/calendar/1002.1/date/{jd:.1f}",
        "date_provenance": origin,
        "lunar_year_is_gregorian_era_year": False,
        "printed_lunar_year": year,
        "calendar_reference_timezone": "UTC+09:00",
        "historical_local_time_reconstruction": False,
    }
