"""Finite official calendar data where the legacy lunar library stops.

The HKO month starts define this UTC+08 civil-date mapping. This is a data
extension, not a new astronomical solver or an extrapolation beyond 2100.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from importlib.resources import files
from typing import Optional

START = date(2100, 2, 9)
END = date(2100, 12, 31)


@dataclass(frozen=True)
class _Supplement:
    starts: tuple[date, ...]
    months: tuple[int, ...]
    leap: tuple[bool, ...]
    lunar_year: int
    source: dict[str, str]


@lru_cache(maxsize=1)
def _load() -> _Supplement:
    raw = json.loads(
        files("fatebridge.data")
        .joinpath("lunar_calendar_hko_2100.json")
        .read_text(encoding="utf-8")
    )
    if (
        raw["method_id"] != "hko_2100_month_starts_v1"
        or raw["solar_start"] != START.isoformat()
        or raw["solar_end"] != END.isoformat()
        or raw["lunar_year"] != 2100
    ):
        raise ValueError("农历补充年表的版本或范围不一致")
    starts = tuple(date.fromisoformat(m["solar_start"]) for m in raw["months"])
    months = tuple(m["month"] for m in raw["months"])
    leap = tuple(m["is_leap_month"] for m in raw["months"])
    if (
        months != tuple(range(1, 13))
        or starts[0] != START
        or starts[-1] > END
        or any((b - a).days not in (29, 30) for a, b in zip(starts, starts[1:]))
        or any(type(v) is not bool or v for v in leap)
    ):
        raise ValueError("2100年官方农历月首数据不完整或无序")
    source = raw["source"]
    return _Supplement(
        starts,
        months,
        leap,
        raw["lunar_year"],
        {
            "method_id": raw["method_id"],
            "publisher": source["publisher"],
            "title": source["title"],
            "url": source["url"],
            "raw_sha256": source["raw_sha256"],
            "retrieved_on": source["retrieved_on"],
            "calendar_convention": "HKO UTC+08 civil-date mapping applied to the supplied local calendar date; not an independent astronomical validation of every timezone or solar-time correction.",
        },
    )


def convert(solar_date: date) -> Optional[tuple[int, int, int, bool]]:
    if not START <= solar_date <= END:
        return None
    data = _load()
    index = bisect_right(data.starts, solar_date) - 1
    return (
        data.lunar_year,
        data.months[index],
        (solar_date - data.starts[index]).days + 1,
        data.leap[index],
    )


def source_for(solar_date: date) -> Optional[dict[str, str]]:
    return dict(_load().source) if START <= solar_date <= END else None
