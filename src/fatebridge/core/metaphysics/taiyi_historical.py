"""Explicit old-style date normalization and selected Key source references.

The four printed calendar observations are curated factual source data, not a
substitute for a historical Chinese-calendar engine. Calendar arithmetic uses
proleptic Gregorian/Julian definitions, without inferring national adoptions.
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from fatebridge.core.ephemeris_runtime import swe


def julian_to_proleptic_gregorian(year: int, month: int, day: int) -> date:
    if (
        any(type(n) is not int for n in (year, month, day))
        or not 1 <= year <= 9999
        or not 1 <= month <= 12
        or not 1 <= day <= 31
    ):
        raise ValueError("须明确给出有效的正整数儒略历年月日")
    if swe is None:
        raise ValueError("儒略历转换需要 Swiss Ephemeris 的日历算术接口")
    jd = swe.julday(year, month, day, 12.0, swe.JUL_CAL)
    # julday accepts overflowing dates. A normalized date is not permission to
    # silently turn, for example, an invalid February 30 into a different input.
    if swe.revjul(jd, swe.JUL_CAL)[:3] != (year, month, day):
        raise ValueError("无效儒略历日期，不能自动进位")
    y, m, d, _ = swe.revjul(jd, swe.GREG_CAL)
    try:
        return date(y, m, d)
    except ValueError as exc:
        raise ValueError("转换后的推算公历日期超出可表达范围") from exc


@lru_cache(maxsize=1)
def historical_date_records() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[2]
        / "data/classical/taiyi-key-historical-dates-v1.json"
    )
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def source_date_reference(
    selected_date: date,
    mode: str,
    counter: int,
    day_ganzhi: str,
    hour_branch: str | None = None,
) -> dict[str, Any] | None:
    data = historical_date_records()
    row = next(
        (
            r
            for r in data["records"]
            if r.get("mode") == mode
            and r["gregorian_date"] == selected_date.isoformat()
        ),
        None,
    )
    if row is None:
        return None
    return {
        "case_id": row["id"],
        "source_date": row["chinese_date"],
        "western_source_date": row["julian_date"],
        "western_source_calendar": "julian",
        "normalized_gregorian_date": row["gregorian_date"],
        "calendar_table_title": data["source"]["title"],
        "calendar_table_authors": data["source"]["authors"],
        "calendar_table_edition": data["source"]["edition"],
        "calendar_table_source": data["source"]["url"],
        "calendar_table_printed_page": data["source"]["printed_page"],
        "source_day_ganzhi": row["day_ganzhi"],
        "actual_day_ganzhi": day_ganzhi,
        "day_ganzhi_matches": day_ganzhi == row["day_ganzhi"],
        "source_accumulation": row["expected_accumulation"],
        "actual_accumulation": counter,
        "counter_matches": counter == row["expected_accumulation"],
        "source_hour_branch": row.get("source_hour_branch"),
        "actual_hour_branch": hour_branch,
        "hour_branch_matches": (
            hour_branch == row["source_hour_branch"]
            if "source_hour_branch" in row
            else None
        ),
        "scope": row["source_time_scope"]
        + "这里只核对选定日期与现代适配计数，不认证完整古历或全盘原典符合。",
    }
