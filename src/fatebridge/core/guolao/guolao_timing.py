"""Guolao timing module: 小限 (Small Limit), 月限 (Month Limit), and 洞微大限 (Dongwei Daxian)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Literal

from fatebridge.core.astro.birth import AstroBirthInfo, require_resolved_birth_timezone
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.core.guolao import classical, ephemeris, guolao, moira
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar, utc_ordering_key
from fatebridge.utils.timezones import is_unspecified_local_time

MonthBasis = Literal["jie_month", "chinese_lunar_utc8"]


def _calendar_clock(instant: datetime, recorded: datetime) -> datetime:
    zone = recorded.tzinfo
    assert zone is not None
    clock = ZonedCalendar(utc_calendar(instant), zone).as_datetime()
    if clock is None:
        raise ValueError("目标时刻在出生时区的日历标签超出datetime范围")
    return clock


def _jie_month_number(sun_longitude: float) -> tuple[int, str]:
    idx = int(((sun_longitude - 315.0) % 360.0) // 30.0)
    return idx + 1, "寅卯辰巳午未申酉戌亥子丑"[idx]


def enrich_guolao_timing(
    payload: dict[str, Any],
    birth: AstroBirthInfo,
    analysis_datetime: datetime | None,
    *,
    zodiacal: int | str | None = None,
    month_basis: str | None = None,
) -> None:
    """Compute target transit sky, 小限, 洞微大限 active period, and optional 月限."""
    if analysis_datetime is None:
        if month_basis is not None:
            raise ValueError("月限须显式提供目标时刻")
        return
    require_resolved_birth_timezone(birth.timezone_source)
    if month_basis not in (None, "jie_month", "chinese_lunar_utc8"):
        raise ValueError("须显式选择jie_month或chinese_lunar_utc8月序政策")
    if analysis_datetime.tzinfo is None or analysis_datetime.utcoffset() is None:
        raise ValueError("果老目标时刻 analysis_datetime 须带明确时区偏移")

    target_calendar = utc_calendar(analysis_datetime)
    target_utc = target_calendar.as_datetime()
    if target_utc is None:
        offset = analysis_datetime.utcoffset()
        assert offset is not None
        instant = analysis_datetime.replace(tzinfo=timezone(offset))
    else:
        instant = target_utc
    recorded = birth.recorded_datetime or birth.local_datetime
    if utc_ordering_key(instant) < utc_ordering_key(recorded):
        raise ValueError("果老目标时刻不能早于记录的出生时刻")

    g = payload["guolao"]
    mansion_frame = g.get("mansion_frame", "modern_equatorial")
    calendar_clock = _calendar_clock(instant, recorded)
    calendar_datetime = (
        None
        if is_unspecified_local_time(calendar_clock)
        else calendar_clock.isoformat()
    )

    target_scales = ephemeris_time(instant)
    target_jd_tt = target_scales.tt.as_float()
    birth_year_num = ephemeris.fast_lichun_year(recorded, g["profile"]["julian_day_tt"])
    target_year_num = ephemeris.fast_lichun_year(calendar_clock, target_jd_tt)
    year_stem, year_branch = BaZiCalendar.calculate_year_pillar(target_year_num)

    birth_gods = g["god_positions"]
    life = g["life_palace"]
    branch = classical.small_limit_branch(
        life["branch"], birth_gods["year_branch"], year_branch
    )
    palace_by_branch = {p["branch"]: p for p in g["palaces"]}
    palace = palace_by_branch[branch]

    context = replace(
        birth,
        local_datetime=instant,
        utc_datetime=target_utc or instant,
        recorded_datetime=instant,
        applied_true_solar=False,
        solar_datetime=None,
        solar_correction_minutes=0,
        clock_conversion=None,
        native_epoch=None,
    )
    raw = ephemeris.positions(
        context,
        hsys=0,
        zodiacal=zodiacal,
        observer_geometry=False,
        mansion_frame=mansion_frame,
    )
    bodies = []
    for name, state in list(raw["states"].items()) + list(raw["extra"].items()):
        body = guolao.body_placement(
            name,
            state,
            raw["boundaries"],
            raw["ayanamsha"],
            mansion_frame=mansion_frame,
        )
        body["natal_functional_palace"] = palace_by_branch[body["palace_branch"]][
            "palace"
        ]
        bodies.append(body)

    # 洞微大限 current period by elapsed Julian years
    target_age = (target_jd_tt - g["profile"]["julian_day_tt"]) / 365.25
    sun_deg_in_palace = next(
        b["zodiac_longitude"] % 30.0 for b in g["bodies"] if b["id"] == "Sun"
    )
    dongwei = classical.dongwei_daxian(
        life_branch_str=life["branch"],
        sun_degree_in_palace=sun_deg_in_palace,
        birth_year=birth_year_num,
        target_age=max(0.0, target_age),
    )

    small_limit = {
        "branch": branch,
        "natal_functional_palace": palace["palace"],
        "palace_lord": palace["lord"],
        "life_branch": life["branch"],
        "birth_year_stem": birth_gods["year_stem"],
        "birth_year_branch": birth_gods["year_branch"],
        "target_year_stem": year_stem,
        "target_year_branch": year_branch,
        "year_boundary_basis": birth_gods["year_boundary_basis"],
        "source_id": guolao.EDITION,
        "locator": "馆藏卷1–2·定小限例（图像9）",
        "method": "birth_year_branch_on_life_palace_reverse_to_target_year_branch",
        "placement_classical_acceptance": False,
    }

    g["timing"] = {
        "status": "complete",
        "analysis_datetime": target_calendar.isoformat(),
        "calendar_datetime": calendar_datetime,
        "calendar_timezone": birth.timezone,
        "calendar": "proleptic_gregorian",
        "small_limit": small_limit,
        "dongwei_daxian": dongwei,
        "transit_bodies": bodies,
        "mansion_boundaries": raw["boundaries"],
        "profile": {
            "julian_day_tt": raw["julian_day_tt"],
            "julian_day_ut1": raw["julian_day_ut1"],
            "time_conversion": raw["time_conversion"],
            "future_leap_seconds_assumed_unchanged": raw[
                "future_leap_seconds_assumed_unchanged"
            ],
            "ephemeris_models": raw["models"],
            "ayanamsha": raw["ayanamsha"],
            "zodiac": raw["zodiac_info"]["zodiac"],
            "position_basis": "geocentric_apparent_target_sky",
            "mansion_basis": g["lunar_mansion_system"],
            "purple_model": moira.PURPLE_CLOUDS_MODEL_ID,
        },
        "limitations": [],
    }
    g["rule_trace"].append(
        {
            "rule_id": "source_small_limit_reverse_count",
            "source_id": guolao.EDITION,
            "locator": small_limit["locator"],
            "inputs": {
                "life_branch": life["branch"],
                "birth_year_branch": birth_gods["year_branch"],
                "target_year_branch": year_branch,
                "analysis_datetime": target_calendar.isoformat(),
            },
            "outputs": {
                "small_limit_branch": branch,
                "natal_functional_palace": palace["palace"],
                "palace_lord": palace["lord"],
                "dongwei_current": dongwei.get("current_period"),
            },
            "placement_classical_acceptance": False,
        }
    )

    if month_basis == "jie_month":
        birth_sun_lon = next(b["longitude"] for b in g["bodies"] if b["id"] == "Sun")
        target_sun_lon = raw["states"]["Sun"]["longitude"]
        bm_num, bm_br = _jie_month_number(birth_sun_lon)
        tm_num, tm_br = _jie_month_number(target_sun_lon)
        m_branch = classical.month_limit_branch(branch, bm_num, tm_num)
        m_palace = palace_by_branch[m_branch]
        g["timing"]["month_limit"] = {
            "status": "complete",
            "model_id": "guolao_month_limit_jie_v1",
            "source_id": guolao.EDITION,
            "month_basis": month_basis,
            "annual_branch": branch,
            "birth_month": {"month_number": bm_num, "month_branch": bm_br},
            "target_month": {"month_number": tm_num, "month_branch": tm_br},
            "branch": m_branch,
            "natal_functional_palace": m_palace["palace"],
            "palace_lord": m_palace["lord"],
        }
    elif month_basis == "chinese_lunar_utc8":
        b_lunar = BaZiCalendar.solar_to_lunar(
            recorded.year, recorded.month, recorded.day
        )
        t_lunar = BaZiCalendar.solar_to_lunar(
            calendar_clock.year, calendar_clock.month, calendar_clock.day
        )
        bm_num = max(1, min(12, int(b_lunar.get("month", 1))))
        tm_num = max(1, min(12, int(t_lunar.get("month", 1))))
        m_branch = classical.month_limit_branch(branch, bm_num, tm_num)
        m_palace = palace_by_branch[m_branch]
        g["timing"]["month_limit"] = {
            "status": "complete",
            "model_id": "guolao_month_limit_lunar_utc8_v1",
            "source_id": guolao.EDITION,
            "month_basis": month_basis,
            "annual_branch": branch,
            "birth_month": {
                "month_number": bm_num,
                "is_leap_month": bool(b_lunar.get("is_leap")),
            },
            "target_month": {
                "month_number": tm_num,
                "is_leap_month": bool(t_lunar.get("is_leap")),
            },
            "branch": m_branch,
            "natal_functional_palace": m_palace["palace"],
            "palace_lord": m_palace["lord"],
        }
