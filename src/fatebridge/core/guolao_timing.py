"""Explicit target sky and the collated ordinal 小限 rule, without event claims."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any

from fatebridge.core import guolao, guolao_classical
from fatebridge.core.almanac import get_bazi_year
from fatebridge.core.astro.birth import (
    AstroBirthInfo,
    NativeSolarBirthInfo,
    require_resolved_birth_timezone,
)
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.guolao_epoch import native_birth_epoch, year_context_for_epoch
from fatebridge.utils.civil_time import utc_calendar, utc_ordering_key


def _calendar_clock(instant: datetime, recorded: datetime) -> datetime:
    """Keep a representable fixed-offset label without visiting UTC year0."""
    zone = recorded.tzinfo
    if not isinstance(zone, timezone):
        return instant.astimezone(zone)
    offset = zone.utcoffset(None)
    assert offset is not None
    offset_us = (offset.days * 86400 + offset.seconds) * 1_000_000 + offset.microseconds
    clock = utc_calendar(instant)
    carry, microseconds = divmod(clock.microseconds_of_day + offset_us, 86_400_000_000)
    ordinal = clock.ordinal + carry
    if not 1 <= ordinal <= datetime.max.toordinal():
        raise ValueError("目标时刻在出生时区的日历标签超出datetime范围")
    return (
        datetime.fromordinal(ordinal) + timedelta(microseconds=microseconds)
    ).replace(tzinfo=zone)


def enrich_guolao_timing(
    payload: dict[str, Any],
    birth: AstroBirthInfo,
    analysis_datetime: datetime | None,
    *,
    zodiacal: Any = None,
    month_basis: str | None = None,
) -> None:
    """No implicit present, no borrowed birth clock and no synthetic 大限."""
    if analysis_datetime is None:
        if month_basis is not None:
            raise ValueError("月限须显式提供目标时刻")
        return
    require_resolved_birth_timezone(birth.timezone_source)
    if month_basis is not None and month_basis not in {
        "jie_month",
        "chinese_lunar_utc8",
    }:
        raise ValueError("须显式选择jie_month或chinese_lunar_utc8月序政策")
    if analysis_datetime.tzinfo is None or analysis_datetime.utcoffset() is None:
        raise ValueError("果老目标时刻 analysis_datetime 须带明确时区偏移")
    target_calendar = utc_calendar(analysis_datetime)
    target_utc = target_calendar.as_datetime()
    if target_utc is None:
        # Request parsers may supply a tzinfo implementation whose existence
        # check round-trips through UTC datetime. The geocentric sky needs only
        # this absolute instant: retain its label and exact offset in a fixed
        # zone, avoiding a range-limited UTC intermediate.
        offset = analysis_datetime.utcoffset()
        assert offset is not None
        instant = analysis_datetime.replace(tzinfo=timezone(offset))
    else:
        instant = target_utc
    recorded = birth.recorded_datetime or birth.local_datetime
    native = native_birth_epoch(birth)
    order_evidence = native_year_evidence = None
    if native is not None:
        target_scales = ephemeris_time(instant)
        assert native.time.jd_tt is not None and target_scales.jd_tt is not None
        difference = float(
            (Fraction(target_scales.jd_tt) - Fraction(native.time.jd_tt)) * 86400
        )
        if abs(difference) <= 0.0002:
            raise ValueError("目标与原生出生历元的先后落入数值区间，不能认证顺序")
        if difference < 0:
            raise ValueError("果老目标时刻不能早于记录的出生时刻")
        order_evidence = {
            "comparison_basis": "primary_TT_not_solar_label_or_UTC_surrogate",
            "nominal_TT_difference_seconds": difference,
            "numerical_order_guard_seconds": 0.0002,
            "physical_clock_precision_certified": False,
        }
    elif utc_ordering_key(instant) < utc_ordering_key(recorded):
        raise ValueError("果老目标时刻不能早于记录的出生时刻")

    g = payload["guolao"]
    if native is not None:
        calendar_clock = target_utc
        target_epoch = PhysicalEpoch(
            target_scales, target_calendar.isoformat(), target_utc, False
        )
        target_year, native_year_evidence = year_context_for_epoch(
            target_epoch,
            analysis_datetime.year,
            reference_year_basis="analysis_civil_label_year_selects_crossing_only",
        )
    else:
        calendar_clock = _calendar_clock(instant, recorded)
        target_year = get_bazi_year(calendar_clock, birth.timezone)
    # A small limit needs the target year, not its month/day/hour pillars.
    year_stem, year_branch = BaZiCalendar.calculate_year_pillar(target_year)
    birth_year = g["god_positions"]
    life = g["life_palace"]
    branch = guolao_classical.small_limit_branch(
        life["branch"], birth_year["year_branch"], year_branch
    )
    palace_by_branch = {p["branch"]: p for p in g["palaces"]}
    palace = palace_by_branch[branch]
    # UTC retains the exact requested instant even in a repeated local DST hour.
    # Geometry is disabled: a geocentric target sky needs no target location.
    target_birth = (
        replace(birth, native_epoch=None)
        if isinstance(birth, NativeSolarBirthInfo)
        else birth
    )
    context = replace(
        target_birth,
        local_datetime=instant,
        utc_datetime=target_utc,
        recorded_datetime=instant,
        applied_true_solar=False,
        solar_datetime=None,
        solar_correction_minutes=0,
        clock_conversion=None,
    )
    raw = guolao.positions(context, hsys=0, zodiacal=zodiacal, observer_geometry=False)
    bodies = []
    for name, state in list(raw["states"].items()) + list(raw["extra"].items()):
        body = guolao.body_placement(name, state, raw["boundaries"], raw["ayanamsha"])
        body["natal_functional_palace"] = palace_by_branch[body["palace_branch"]][
            "palace"
        ]
        bodies.append(body)
    small_limit = {
        "branch": branch,
        "natal_functional_palace": palace["palace"],
        "palace_lord": palace["lord"],
        "life_branch": life["branch"],
        "birth_year_stem": birth_year["year_stem"],
        "birth_year_branch": birth_year["year_branch"],
        "target_year_stem": year_stem,
        "target_year_branch": year_branch,
        "year_boundary_basis": birth_year["year_boundary_basis"],
        "source_id": guolao.EDITION,
        "locator": "馆藏卷1–2·定小限例（图像9）",
        "method": "birth_year_branch_on_life_palace_reverse_to_target_year_branch",
        "placement_classical_acceptance": False,
    }
    g["timing"] = {
        "status": "research_partial",
        "analysis_datetime": target_calendar.isoformat(),
        "calendar_datetime": (
            calendar_clock.isoformat()
            if calendar_clock is not None
            else target_calendar.isoformat()
        ),
        "calendar_timezone": birth.timezone,
        "calendar": "proleptic_gregorian",
        "small_limit": small_limit,
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
            "ephemeris_provenance": raw["ephemeris_provenance"],
            "longitude_motion": raw["longitude_motion"],
            "catalogue_sha256": raw["catalogue_sha256"],
            "ayanamsha": raw["ayanamsha"],
            "zodiac": raw["zodiac_info"]["zodiac"],
            "position_basis": "geocentric_apparent_target_sky_not_symbolic_direction",
            "observer_geometry": "not_computed_no_target_location_required",
            "mansion_basis": "modern_equatorial_research_anchors_v1",
            "purple_model": "horosa_linear_fit_not_classical_calibrated",
        },
        "limitations": [
            "小限逆数条文已核对；立春换年及现代安命输入仍为明示研究约定",
            "目标位置为七政及所列四余模型，不是完整流年吉凶或岗位变动判断",
            "原典命度、洞微大限、童限尚未重建；现代宿界和紫气历元尚未通过原典验收",
            "未使用独立现实事件样本验证，不返回事件成功概率",
        ],
    }
    if birth.clock_conversion is not None:
        g["timing"][
            "calendar_timezone_role"
        ] = "UTC_reference_for_explicit_solar_input_not_original_civil_zone"
    if native is not None:
        g["timing"]["native_year_comparison"] = native_year_evidence
        g["timing"]["target_order_evidence"] = order_evidence
    g["rule_trace"].append(
        {
            "rule_id": "source_small_limit_reverse_count",
            "source_id": guolao.EDITION,
            "locator": small_limit["locator"],
            "inputs": {
                "life_branch": life["branch"],
                "birth_year_branch": birth_year["year_branch"],
                "target_year_branch": year_branch,
                "analysis_datetime": target_calendar.isoformat(),
                "year_boundary_basis": small_limit["year_boundary_basis"],
            },
            "outputs": {
                "small_limit_branch": branch,
                "natal_functional_palace": palace["palace"],
                "palace_lord": palace["lord"],
            },
            "placement_classical_acceptance": False,
        }
    )
    if month_basis is not None:
        from typing import cast

        from fatebridge.core.guolao_monthly import MonthBasis, build_month_limit

        monthly = build_month_limit(
            annual_branch=branch,
            birth_instant=native if native is not None else recorded,
            target_instant=instant,
            basis=cast(MonthBasis, month_basis),
            palaces=g["palaces"],
        )
        g["timing"]["month_limit"] = monthly
        g["rule_trace"].append(
            {
                "rule_id": monthly["model_id"],
                "source_id": monthly["source_id"],
                "locator": monthly["locator"],
                "inputs": {
                    "annual_branch": branch,
                    "year_boundary_basis": small_limit["year_boundary_basis"],
                    "month_basis": month_basis,
                    "birth_month": monthly["birth_month"],
                    "target_month": monthly["target_month"],
                },
                "outputs": {
                    "status": monthly["status"],
                    "month_limit_branch": monthly["branch"],
                    "natal_functional_palace": monthly["natal_functional_palace"],
                },
                "placement_classical_acceptance": False,
            }
        )
        g["rulesets"].append(
            {
                "id": monthly["model_id"],
                "edition_id": monthly["source_id"],
                "title": monthly["source_title"],
                "source_url": monthly["source_url"],
                "verified_subset": "影像十二月序逆转；现代月制、年界和闰月未验收",
            }
        )
