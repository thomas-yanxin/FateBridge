"""Unified Annual, Monthly, Daily, and Hourly ZiBai flying stars + annual afflictions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import TypeAdapter
from typing_extensions import NotRequired

from fatebridge.core import almanac
from fatebridge.core.fengshui.calendar import (
    solar_month_context,
    year_context,
    zibai_solar_segment,
)
from fatebridge.core.fengshui.directions import (
    AnnualStarInfo,
    raw_rule_data,
    wrap9,
)
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


class _CenterPalace(TypedDict):
    direction: str
    label: str
    palace_number: int
    trigram: str | None
    element: str


class MonthlyRuleset(TypedDict):
    ruleset_id: str
    version: str
    method: str
    source_ids: list[str]
    scope: str


class MonthlyYearGroup(TypedDict):
    branches: list[str]
    first_month_center: int


class MonthlyBundle(TypedDict):
    bundle_version: str
    ruleset: MonthlyRuleset
    year_groups: list[MonthlyYearGroup]


class AnnualPalaceEntry(TypedDict):
    direction: str
    palace_number: int
    trigram: str | None
    annual_star_number: int
    annual_star: AnnualStarInfo


class DailyPalaceEntry(TypedDict):
    direction: str
    palace_number: int
    trigram: str | None
    daily_star_number: int
    daily_star: AnnualStarInfo


class HourlyPalaceEntry(TypedDict):
    direction: str
    palace_number: int
    trigram: str | None
    hourly_star_number: int
    hourly_star: AnnualStarInfo


class MonthlyPalaceEntry(TypedDict):
    direction: str
    palace_number: int
    trigram: str | None
    monthly_star_number: int
    monthly_star: AnnualStarInfo


class BranchDirection(TypedDict):
    branch: str
    direction: str


class SanshaInfo(TypedDict):
    direction: str
    branches: list[str]


class StarDirection(TypedDict):
    star_number: int
    direction: str


class AnnualAfflictions(TypedDict):
    year_branch: str
    taisui: BranchDirection
    suipo: BranchDirection
    sansha: SanshaInfo
    wuhuang: StarDirection
    erhei: StarDirection


class PeriodWindow(TypedDict):
    number: int
    start_year: int
    end_year: int


class AnnualStarsResult(TypedDict):
    status: Literal["partial", "complete"]
    time_context: Mapping[str, object]
    palaces: dict[str, AnnualPalaceEntry]
    missing_inputs: list[str]
    effective_year: NotRequired[int]
    center_star_number: NotRequired[int]
    annual_afflictions: NotRequired[AnnualAfflictions]
    flight_path: NotRequired[list[str]]
    current_period: NotRequired[PeriodWindow]


class DailySegment(TypedDict):
    anchor_term: str
    dun_half: str
    jiazi_anchor_star: int
    progression_direction: str


class DailyStarsResult(TypedDict):
    status: Literal["complete"]
    local_moment: str
    day_ganzhi: str
    day_branch: str
    jiazi_index: int
    segment: DailySegment
    center_star_number: int
    palaces: dict[str, DailyPalaceEntry]
    within_palace_flight: Literal["forward"]


class HourlyStarsResult(TypedDict):
    status: Literal["complete"]
    local_moment: str
    day_ganzhi: str
    day_branch: str
    hour_branch: str
    hour_index: int
    dun_half: str
    zi_anchor_star: int
    progression_direction: Literal["ascending", "descending"]
    center_star_number: int
    palaces: dict[str, HourlyPalaceEntry]
    within_palace_flight: Literal["forward"]


class MonthlyStarsResult(TypedDict):
    status: Literal["partial", "complete"]
    time_context: Mapping[str, object]
    palaces: dict[str, MonthlyPalaceEntry]
    missing_inputs: list[str]
    year_branch: NotRequired[str]
    year_group: NotRequired[MonthlyYearGroup]
    center_star_number: NotRequired[int]
    flight_path: NotRequired[list[str]]
    daily_stars: NotRequired[DailyStarsResult]
    hourly_stars: NotRequired[HourlyStarsResult]


class PalaceOverlayEntry(TypedDict, total=False):
    natal_period_star: int
    natal_mountain_star: int
    natal_facing_star: int
    annual_star: int
    monthly_star: int
    daily_star: int
    hourly_star: int


_MONTHLY_BUNDLE_ADAPTER = TypeAdapter(MonthlyBundle)

_CENTER_PALACE: _CenterPalace = {
    "direction": "C",
    "label": "中",
    "palace_number": 5,
    "trigram": None,
    "element": "土",
}


@lru_cache(maxsize=1)
def _monthly_bundle() -> MonthlyBundle:
    path = Path(__file__).parents[2] / "data/fengshui/monthly-v1.json"
    return _MONTHLY_BUNDLE_ADAPTER.validate_json(path.read_bytes())


def _fly_palace_steps(
    center: int,
) -> list[tuple[str, int, str | None, int, AnnualStarInfo]]:
    directions = raw_rule_data("directions")
    stars = raw_rule_data("annual_stars")
    flight_path = raw_rule_data("flight_path")
    steps: list[tuple[str, int, str | None, int, AnnualStarInfo]] = []
    for index, direction in enumerate(flight_path):
        number = wrap9(center + index)
        info = directions.get(direction)
        palace_number = (
            info["palace_number"]
            if info is not None
            else _CENTER_PALACE["palace_number"]
        )
        trigram: str | None = (
            info["trigram"] if info is not None else _CENTER_PALACE["trigram"]
        )
        steps.append((direction, palace_number, trigram, number, stars[str(number)]))
    return steps


def annual_afflictions(
    year: int, palaces: Mapping[str, AnnualPalaceEntry]
) -> AnnualAfflictions:
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


def annual_stars(req: AnnualRequest) -> AnnualStarsResult:
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
    palaces: dict[str, AnnualPalaceEntry] = {
        direction: {
            "direction": direction,
            "palace_number": palace_number,
            "trigram": trigram,
            "annual_star_number": number,
            "annual_star": star,
        }
        for direction, palace_number, trigram, number, star in _fly_palace_steps(center)
    }
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


def daily_stars(moment: datetime, timezone_name: str) -> DailyStarsResult:
    """Compute 《紫白诀》 Daily ZiBai center and 9-palace forward flight."""
    local = almanac.localize_datetime(moment, timezone_name)
    day_gz = almanac.get_day_ganzhi(local.year, local.month, local.day)
    jiazi_index = _GANZHI_60.index(day_gz)
    segment = zibai_solar_segment(local, timezone_name)
    center = wrap9(segment["jiazi_anchor_star"] + segment["step"] * jiazi_index)
    palaces: dict[str, DailyPalaceEntry] = {
        direction: {
            "direction": direction,
            "palace_number": palace_number,
            "trigram": trigram,
            "daily_star_number": number,
            "daily_star": star,
        }
        for direction, palace_number, trigram, number, star in _fly_palace_steps(center)
    }
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


def hourly_stars(moment: datetime, timezone_name: str) -> HourlyStarsResult:
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
    palaces: dict[str, HourlyPalaceEntry] = {
        direction: {
            "direction": direction,
            "palace_number": palace_number,
            "trigram": trigram,
            "hourly_star_number": number,
            "hourly_star": star,
        }
        for direction, palace_number, trigram, number, star in _fly_palace_steps(center)
    }
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


def monthly_stars(req: MonthlyRequest) -> MonthlyStarsResult:
    time = solar_month_context(
        req.effective_solar_year,
        req.solar_month_number,
        req.query_at,
        req.timezone_name,
    )
    year = time["effective_solar_year"]
    complete = year is not None and time["solar_month_number"] is not None
    result: MonthlyStarsResult = {
        "status": "complete" if complete else "partial",
        "time_context": time,
        "palaces": {},
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
        result["year_branch"] = branch
        result["year_group"] = {
            "branches": list(group["branches"]),
            "first_month_center": group["first_month_center"],
        }
        result["center_star_number"] = center
        result["palaces"] = {
            direction: {
                "direction": direction,
                "palace_number": palace_number,
                "trigram": trigram,
                "monthly_star_number": number,
                "monthly_star": star,
            }
            for direction, palace_number, trigram, number, star in _fly_palace_steps(
                center
            )
        }
        result["flight_path"] = list(raw_rule_data("flight_path"))
    if req.query_at is not None and req.include_daily_hourly:
        result["daily_stars"] = daily_stars(req.query_at, req.timezone_name)
        result["hourly_stars"] = hourly_stars(req.query_at, req.timezone_name)
    return result


def build_palace_overlay(
    layers: Mapping[str, object],
) -> dict[str, PalaceOverlayEntry] | None:
    """Build 9-palace star stack overlaying xuankong_natal, annual, monthly, daily, hourly."""
    natal_layer = layers.get("xuankong_natal")
    natal_chart = natal_layer.get("chart") if isinstance(natal_layer, Mapping) else None
    natal_palaces = (
        natal_chart.get("palaces") if isinstance(natal_chart, Mapping) else None
    )
    annual_layer = layers.get("annual_stars")
    annual_palaces = (
        annual_layer.get("palaces") if isinstance(annual_layer, Mapping) else None
    )
    monthly_layer = layers.get("monthly_stars")
    monthly_palaces = (
        monthly_layer.get("palaces") if isinstance(monthly_layer, Mapping) else None
    )
    daily_layer = (
        monthly_layer.get("daily_stars") if isinstance(monthly_layer, Mapping) else None
    )
    daily_palaces = (
        daily_layer.get("palaces") if isinstance(daily_layer, Mapping) else None
    )
    hourly_layer = (
        monthly_layer.get("hourly_stars")
        if isinstance(monthly_layer, Mapping)
        else None
    )
    hourly_palaces = (
        hourly_layer.get("palaces") if isinstance(hourly_layer, Mapping) else None
    )

    if not any(
        (
            isinstance(natal_palaces, Mapping) and bool(natal_palaces),
            isinstance(annual_palaces, Mapping) and bool(annual_palaces),
            isinstance(monthly_palaces, Mapping) and bool(monthly_palaces),
            isinstance(daily_palaces, Mapping) and bool(daily_palaces),
        )
    ):
        return None

    overlay: dict[str, PalaceOverlayEntry] = {}
    for direction in raw_rule_data("flight_path"):
        entry: PalaceOverlayEntry = {}
        if isinstance(natal_palaces, Mapping):
            np = natal_palaces.get(direction)
            if isinstance(np, Mapping):
                p_star = np.get("period_star_number")
                m_star = np.get("mountain_star_number")
                f_star = np.get("facing_star_number")
                if isinstance(p_star, int):
                    entry["natal_period_star"] = p_star
                if isinstance(m_star, int):
                    entry["natal_mountain_star"] = m_star
                if isinstance(f_star, int):
                    entry["natal_facing_star"] = f_star
        if isinstance(annual_palaces, Mapping):
            ap = annual_palaces.get(direction)
            if isinstance(ap, Mapping):
                a_star = ap.get("annual_star_number")
                if isinstance(a_star, int):
                    entry["annual_star"] = a_star
        if isinstance(monthly_palaces, Mapping):
            mp = monthly_palaces.get(direction)
            if isinstance(mp, Mapping):
                mo_star = mp.get("monthly_star_number")
                if isinstance(mo_star, int):
                    entry["monthly_star"] = mo_star
        if isinstance(daily_palaces, Mapping):
            dp = daily_palaces.get(direction)
            if isinstance(dp, Mapping):
                d_star = dp.get("daily_star_number")
                if isinstance(d_star, int):
                    entry["daily_star"] = d_star
        if isinstance(hourly_palaces, Mapping):
            hp = hourly_palaces.get(direction)
            if isinstance(hp, Mapping):
                h_star = hp.get("hourly_star_number")
                if isinstance(h_star, int):
                    entry["hourly_star"] = h_star
        overlay[direction] = entry
    return overlay
