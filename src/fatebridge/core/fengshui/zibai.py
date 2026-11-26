"""Unified Annual, Monthly, Daily, and Hourly ZiBai flying stars + annual afflictions."""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from fatebridge.core import almanac
from fatebridge.core.fengshui.calendar import (
    solar_month_context,
    year_context,
    zibai_solar_segment,
)
from fatebridge.core.fengshui.directions import raw_rule_data, wrap9
from fatebridge.core.fengshui.models import AnnualRequest, MonthlyRequest

_BRANCHES = tuple("子丑寅卯辰巳午未申酉戌亥")
_STEMS = tuple("甲乙丙丁戊己庚辛壬癸")
_GANZHI_60 = tuple(f"{_STEMS[i % 10]}{_BRANCHES[i % 12]}" for i in range(60))

_BRANCH_TO_DIRECTION = {
    "子": "N",
    "丑": "NE",
    "寅": "NE",
    "卯": "E",
    "辰": "SE",
    "巳": "SE",
    "午": "S",
    "未": "SW",
    "申": "SW",
    "酉": "W",
    "戌": "NW",
    "亥": "NW",
}

# 三合局冲煞: 申子辰->S, 寅午戌->N, 巳酉丑->E, 亥卯未->W
_SANSHA_BY_BRANCH: dict[str, tuple[str, tuple[str, ...]]] = {
    "申": ("S", ("巳", "午", "未")),
    "子": ("S", ("巳", "午", "未")),
    "辰": ("S", ("巳", "午", "未")),
    "寅": ("N", ("亥", "子", "丑")),
    "午": ("N", ("亥", "子", "丑")),
    "戌": ("N", ("亥", "子", "丑")),
    "巳": ("E", ("寅", "卯", "辰")),
    "酉": ("E", ("寅", "卯", "辰")),
    "丑": ("E", ("寅", "卯", "辰")),
    "亥": ("W", ("申", "酉", "戌")),
    "卯": ("W", ("申", "酉", "戌")),
    "未": ("W", ("申", "酉", "戌")),
}

# Hourly ZiBai: (yang_dun_zi_star, yin_dun_zi_star)
_HOURLY_ANCHOR_BY_BRANCH: dict[str, tuple[int, int]] = {
    "子": (1, 9),
    "午": (1, 9),
    "卯": (1, 9),
    "酉": (1, 9),
    "辰": (4, 6),
    "戌": (4, 6),
    "丑": (4, 6),
    "未": (4, 6),
    "寅": (7, 3),
    "申": (7, 3),
    "巳": (7, 3),
    "亥": (7, 3),
}

_CENTER_PALACE = {
    "direction": "C",
    "label": "中",
    "palace_number": 5,
    "trigram": None,
    "element": "土",
}


@lru_cache(maxsize=1)
def _monthly_bundle() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data/fengshui/monthly-v1.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def monthly_provenance() -> dict[str, Any]:
    data = _monthly_bundle()
    ruleset = data["ruleset"]
    sources = data["sources"]
    return {
        "ruleset_id": ruleset["ruleset_id"],
        "version": ruleset["version"],
        "method": ruleset["method"],
        "source_ids": list(ruleset["source_ids"]),
        "scope": ruleset["scope"],
        "conventions": list(ruleset["conventions"]),
        "bundle_version": data["bundle_version"],
        "sources": [{"source_id": k, **sources[k]} for k in ruleset["source_ids"]],
    }


def _fly_palaces(center: int, star_key: str, number_key: str) -> dict[str, Any]:
    directions = raw_rule_data("directions")
    stars = raw_rule_data("annual_stars")
    flight_path = raw_rule_data("flight_path")
    palaces: dict[str, Any] = {}
    for index, direction in enumerate(flight_path):
        number = wrap9(center + index)
        info = directions.get(direction, _CENTER_PALACE)
        palaces[direction] = {
            "direction": direction,
            "palace_number": info["palace_number"],
            "trigram": info["trigram"],
            number_key: number,
            star_key: stars[str(number)],
        }
    return palaces


def annual_afflictions(year: int, palaces: dict[str, Any]) -> dict[str, Any]:
    """Compute classical annual afflictions: 太岁, 岁破, 三煞, 五黄, 二黑."""
    b_idx = (year - 4) % 12
    branch = _BRANCHES[b_idx]
    opp_branch = _BRANCHES[(b_idx + 6) % 12]
    sansha_dir, sansha_branches = _SANSHA_BY_BRANCH[branch]
    wuhuang_dir = next(d for d, p in palaces.items() if p["annual_star_number"] == 5)
    erhei_dir = next(d for d, p in palaces.items() if p["annual_star_number"] == 2)
    return {
        "year_branch": branch,
        "taisui": {"branch": branch, "direction": _BRANCH_TO_DIRECTION[branch]},
        "suipo": {"branch": opp_branch, "direction": _BRANCH_TO_DIRECTION[opp_branch]},
        "sansha": {"direction": sansha_dir, "branches": list(sansha_branches)},
        "wuhuang": {"star_number": 5, "direction": wuhuang_dir},
        "erhei": {"star_number": 2, "direction": erhei_dir},
    }


def annual_stars(req: AnnualRequest) -> dict[str, Any]:
    time = year_context(req.effective_year, req.query_at, req.timezone_name)
    year = time["effective_year"]
    if time.get("effective_year_status") == "requires_confirmation":
        return {
            "status": "partial",
            "time_context": time,
            "palaces": {},
            "missing_inputs": [
                "annual_stars.confirmed_effective_year_due_to_boundary_precision"
            ],
        }
    if year is None:
        return {
            "status": "partial",
            "time_context": time,
            "palaces": {},
            "missing_inputs": ["annual_stars.query_at_or_effective_year"],
        }
    center = wrap9(1 - (year - 1864))
    palaces = _fly_palaces(center, "annual_star", "annual_star_number")
    period_index = (year - 1864) // 20
    period_start = 1864 + period_index * 20
    return {
        "status": "complete",
        "effective_year": year,
        "time_context": time,
        "center_star_number": center,
        "palaces": palaces,
        "annual_afflictions": annual_afflictions(year, palaces),
        "flight_path": list(raw_rule_data("flight_path")),
        "current_period": {
            "number": period_index % 9 + 1,
            "start_year": period_start,
            "end_year": period_start + 19,
        },
        "missing_inputs": [],
    }


def daily_stars(moment: datetime, timezone_name: str) -> dict[str, Any]:
    """Compute 《紫白诀》 Daily ZiBai center and 9-palace forward flight."""
    local = almanac.localize_datetime(moment, timezone_name)
    day_gz = almanac.get_day_ganzhi(local.year, local.month, local.day)
    jiazi_index = _GANZHI_60.index(day_gz)
    segment = zibai_solar_segment(local, timezone_name)
    center = wrap9(segment["jiazi_anchor_star"] + segment["step"] * jiazi_index)
    palaces = _fly_palaces(center, "daily_star", "daily_star_number")
    return {
        "status": "complete",
        "local_moment": local.isoformat(),
        "day_ganzhi": day_gz,
        "day_branch": day_gz[1],
        "jiazi_index": jiazi_index,
        "segment": {
            "anchor_term": segment["anchor_term"],
            "dun_half": segment["dun_half"],
            "jiazi_anchor_star": segment["jiazi_anchor_star"],
            "progression_direction": segment["progression_direction"],
        },
        "center_star_number": center,
        "palaces": palaces,
        "within_palace_flight": "forward",
    }


def hourly_stars(moment: datetime, timezone_name: str) -> dict[str, Any]:
    """Compute 《紫白诀》 Hourly ZiBai center and 9-palace forward flight."""
    local = almanac.localize_datetime(moment, timezone_name)
    day_gz = almanac.get_day_ganzhi(local.year, local.month, local.day)
    day_branch = day_gz[1]
    hour_index = ((local.hour + 1) // 2) % 12
    hour_branch = _BRANCHES[hour_index]
    segment = zibai_solar_segment(local, timezone_name)
    yang_anchor, yin_anchor = _HOURLY_ANCHOR_BY_BRANCH[day_branch]
    is_yang = segment["dun_half"] == "yang_dun"
    zi_anchor = yang_anchor if is_yang else yin_anchor
    step = 1 if is_yang else -1
    center = wrap9(zi_anchor + step * hour_index)
    palaces = _fly_palaces(center, "hourly_star", "hourly_star_number")
    return {
        "status": "complete",
        "local_moment": local.isoformat(),
        "day_ganzhi": day_gz,
        "day_branch": day_branch,
        "hour_branch": hour_branch,
        "hour_index": hour_index,
        "dun_half": segment["dun_half"],
        "zi_anchor_star": zi_anchor,
        "progression_direction": "ascending" if is_yang else "descending",
        "center_star_number": center,
        "palaces": palaces,
        "within_palace_flight": "forward",
    }


def monthly_stars(req: MonthlyRequest) -> dict[str, Any]:
    time = solar_month_context(
        req.effective_solar_year,
        req.solar_month_number,
        req.query_at,
        req.timezone_name,
    )
    year = time["effective_solar_year"]
    complete = year is not None and time["solar_month_number"] is not None
    result: dict[str, Any] = {
        "status": "complete" if complete else "partial",
        "time_context": time,
        "palaces": {},
        "ruleset": monthly_provenance(),
        "missing_inputs": (
            [
                (
                    "monthly_stars.confirmed_solar_month_due_to_boundary_precision"
                    if time.get("month_status") == "requires_confirmation"
                    else "monthly_stars.query_at_or_confirmed_effective_solar_year_and_solar_month"
                )
            ]
            if not complete
            else []
        ),
    }
    if complete:
        assert year is not None
        branch = _BRANCHES[(year - 4) % 12]
        group = next(
            g for g in _monthly_bundle()["year_groups"] if branch in g["branches"]
        )
        month = time["solar_month_number"]
        center = wrap9(group["first_month_center"] - month + 1)
        result.update(
            year_branch=branch,
            year_group=dict(group),
            center_star_number=center,
            palaces=_fly_palaces(center, "monthly_star", "monthly_star_number"),
            flight_path=list(raw_rule_data("flight_path")),
        )
    if req.query_at is not None and req.include_daily_hourly:
        result["daily_stars"] = daily_stars(req.query_at, req.timezone_name)
        result["hourly_stars"] = hourly_stars(req.query_at, req.timezone_name)
    return result


def build_palace_overlay(layers: dict[str, Any]) -> dict[str, Any] | None:
    """Build 9-palace star stack overlaying xuankong_natal, annual, monthly, daily, hourly."""
    natal_layer = layers.get("xuankong_natal", {})
    natal_chart = natal_layer.get("chart")
    annual_layer = layers.get("annual_stars", {})
    monthly_layer = layers.get("monthly_stars", {})
    daily_layer = monthly_layer.get("daily_stars") or {}
    hourly_layer = monthly_layer.get("hourly_stars") or {}

    if not any(
        [
            natal_chart and natal_chart.get("palaces"),
            annual_layer.get("palaces"),
            monthly_layer.get("palaces"),
            daily_layer.get("palaces"),
        ]
    ):
        return None

    overlay: dict[str, Any] = {}
    for direction in raw_rule_data("flight_path"):
        entry: dict[str, Any] = {}
        if natal_chart and direction in natal_chart.get("palaces", {}):
            np = natal_chart["palaces"][direction]
            entry["natal_period_star"] = np["period_star_number"]
            entry["natal_mountain_star"] = np["mountain_star_number"]
            entry["natal_facing_star"] = np["facing_star_number"]
        if direction in annual_layer.get("palaces", {}):
            entry["annual_star"] = annual_layer["palaces"][direction][
                "annual_star_number"
            ]
        if direction in monthly_layer.get("palaces", {}):
            entry["monthly_star"] = monthly_layer["palaces"][direction][
                "monthly_star_number"
            ]
        if direction in daily_layer.get("palaces", {}):
            entry["daily_star"] = daily_layer["palaces"][direction]["daily_star_number"]
        if direction in hourly_layer.get("palaces", {}):
            entry["hourly_star"] = hourly_layer["palaces"][direction][
                "hourly_star_number"
            ]
        overlay[direction] = entry
    return overlay
