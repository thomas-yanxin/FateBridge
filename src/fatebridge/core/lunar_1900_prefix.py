"""Finite PMO printed-date prefix before lunardate's 1900-01-31 anchor."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from importlib.resources import files
from typing import Any

START = date(1900, 1, 1)
END = date(1900, 1, 30)


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(
        files("fatebridge.data")
        .joinpath("lunar_calendar_pmo_1900_prefix.json")
        .read_text(encoding="utf-8")
    )
    if (
        raw["method_id"] != "pmo_1900_january_prefix_v1"
        or raw["solar_start"] != START.isoformat()
        or raw["solar_end"] != END.isoformat()
        or raw["lunar_year"] != 1899
        or raw["lunar_month"] != 12
        or raw["lunar_first_day"] != 1
        or raw["is_leap_month"] is not False
    ):
        raise ValueError("紫台1900年一月农历补表的版本、月序或范围不一致")
    return raw


def convert(solar_date: date) -> tuple[int, int, int, bool] | None:
    if not START <= solar_date <= END:
        return None
    raw = _load()
    return raw["lunar_year"], raw["lunar_month"], (solar_date - START).days + 1, False


def source_for(solar_date: date) -> dict[str, str] | None:
    if not START <= solar_date <= END:
        return None
    raw = _load()
    return {"method_id": raw["method_id"], **raw["source"]}
