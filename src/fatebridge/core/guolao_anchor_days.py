"""Explicit apparent-solar-day interpretations of Lu Wei's seasonal anchors.

The printed day endpoints and the winter-day inclusion question are separate
from the historical local-clock calibration. No policy is selected by fit.
"""

from __future__ import annotations

import math
from fractions import Fraction as F
from itertools import product
from typing import Any, Callable

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    PhysicalSourceCohort,
)
from fatebridge.core.astro.time_scales import tt_from_ut1
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.guolao_birth_clock import apparent_clock_required
from fatebridge.core.guolao_clock import METHOD_ID as CLOCK_METHOD
from fatebridge.core.guolao_clock import apparent_solar_clock
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError

POLICIES = (
    "term_instants",
    "source_solar_days_winter_exclusive",
    "source_solar_days_winter_inclusive",
)
DAY_RULESET = "guolao_research_v8"
METHOD_ID = "guolao_same_sky_apparent_solar_day_anchor_v1"
_RESOLUTION_DAYS = F(1, 86_400_000)  # 0.001 second of the modeled UT1 axis.


def anchor_from_day_longitudes(start: F, end: F, *, include_winter_day: bool) -> str:
    """Explicit whole-day hypothesis, not an astronomical accuracy claim."""
    if not isinstance(start, F) or not isinstance(end, F):
        raise TypeError("太阳日边界黄经须明确提供Fraction")
    if type(include_winter_day) is not bool:
        raise TypeError("须明确冬至日是否计入，不采用隐式真假值")
    if not (0 <= start < 360 and 0 <= end < 360):
        raise ValueError("太阳日边界黄经须在0至360度")
    advance = (end - start) % 360
    if not 0 < advance < 2:
        raise ValueError("一个真太阳日的太阳前行量异常，不猜年界或修正端点")
    unwrapped_end = start + advance
    winter = (
        unwrapped_end > 270 if include_winter_day else start > 270
    ) and start <= 300
    summer = unwrapped_end > 90 and start <= 105
    return "辰" if winter else "寅" if summer else "卯"


def _day_brackets(
    birth_ut1: float,
    serial: F,
    evaluate: Callable[[float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[float]]:
    """Scan the full3-day window, then keep signed root brackets for both edges."""
    if type(birth_ut1) not in (int, float) or not math.isfinite(birth_ut1):
        raise ValueError("出生UT1须为有限数")
    if not isinstance(serial, F):
        raise TypeError("真太阳日日序须为Fraction")
    ordinal = serial.numerator // serial.denominator
    grid = [float(birth_ut1 - 1.5 + i / 4) for i in range(13)]
    values = [F(evaluate(t)["apparent_solar_label_serial_exact"]) for t in grid]
    if not all(a < b for a, b in zip(values, values[1:])):
        raise ValueError("完整搜索窗口内真太阳钟未单调前行，不能夹逼日界")
    roots: list[dict[str, Any]] = []
    for target in (ordinal, ordinal + 1):
        candidates = [
            (a, b)
            for a, b, x, y in zip(grid, grid[1:], values, values[1:])
            if x < target <= y
        ]
        if len(candidates) != 1:
            raise ValueError("固定窗口无唯一真太阳日界，不扩大窗口凑结果")
        low, high = candidates[0]
        while F(high) - F(low) > _RESOLUTION_DAYS:
            mid = low + (high - low) / 2
            if not low < mid < high:
                raise ValueError("UT1浮点分辨率不足，无法满足已声明数值夹逼")
            if F(evaluate(mid)["apparent_solar_label_serial_exact"]) < target:
                low = mid
            else:
                high = mid
        lower = evaluate(low)
        upper = evaluate(high)
        if (
            not F(lower["apparent_solar_label_serial_exact"])
            < target
            <= F(upper["apparent_solar_label_serial_exact"])
        ):
            raise ValueError("真太阳日界端点未保留符号夹逼")
        roots.append(
            dict(
                target_solar_label_ordinal=target,
                lower=lower,
                upper=upper,
                bracket_width_UT1_seconds_exact=str((F(high) - F(low)) * 86400),
                clock_coordinate_span_seconds_exact=str(
                    (
                        F(upper["apparent_solar_label_serial_exact"])
                        - F(lower["apparent_solar_label_serial_exact"])
                    )
                    * 86400
                ),
            )
        )
    if (
        not F(roots[0]["upper"]["julian_day_ut1_exact"])
        < F(birth_ut1)
        < F(roots[1]["lower"]["julian_day_ut1_exact"])
    ):
        raise ValueError("出生瞬间落入数值日界夹逼，不能认证单一真太阳日标签")
    return roots, grid


def apparent_solar_day_anchor(
    birth: AstroBirthInfo,
    *,
    birth_clock: dict[str, Any],
    birth_ut1: float,
    expected_sun_model: str,
    birth_sun_source: dict[str, Any],
    policy: str,
) -> dict[str, Any]:
    """Same native Sun backend and modeled UT1 as this birth, without UTC rebasing."""
    if policy not in POLICIES[1:]:
        raise ValueError("太阳日法须显式选择冬至日纳入或排除政策")
    if not apparent_clock_required(birth):
        raise ValueError("太阳日安命须明确use_true_solar_time=true")
    if (
        birth_clock.get("method_id") != CLOCK_METHOD
        or birth_clock.get("julian_day_ut1") != birth_ut1
        or birth_clock.get("longitude") != birth.longitude
    ):
        raise ValueError("太阳日须衔接同次出生钟面和UT1，不能混用另一盘")
    if expected_sun_model not in {"moshier", "swieph", "jpl"}:
        raise ValueError("须有本次太阳实际星历模型")
    if runtime.swe is None:
        raise ValueError("太阳日安命需要原生星历")
    reference_ordinal = birth.local_datetime.toordinal()
    serial = F(reference_ordinal + birth_clock["solar_day_offset_from_civil"]) + F(
        birth_clock["apparent_day_fraction_exact"]
    )
    selected_path = configured_ephemeris_path()
    selected_jpl = configured_jpl_file()
    evaluated: dict[float, dict[str, Any]] = {}
    with runtime.preserve_ephemeris_path():
        swe = runtime.swe
        swe.set_ephe_path(selected_path or "")
        sources = PhysicalEphemerisTrace()
        source_cohort = PhysicalSourceCohort()
        natal_factor = birth_sun_source["by_factor"]["Sun"]
        natal_files = [
            f for f in birth_sun_source["files"] if f["id"] in natal_factor["file_ids"]
        ]
        source_cohort.add(
            {
                **birth_sun_source,
                "by_factor": {"Sun": natal_factor},
                "files": natal_files,
            }
        )

        def evaluate(at: float) -> dict[str, Any]:
            if at not in evaluated:
                tt = tt_from_ut1(at)
                flags = swe.FLG_SWIEPH | swe.FLG_SPEED
                pos, flag = runtime.ephemeris_call("calc", tt, swe.SUN, flags)
                longitude, _, _ = require_spherical_coordinates(pos, flag, native=swe)
                require_longitude_speed(pos, flag, swe.FLG_SPEED)
                model = runtime.ephemeris_model_from_retflag(flag)
                sources.observe("Sun", model)
                eq, eqflag = runtime.ephemeris_call(
                    "calc", tt, swe.SUN, flags | swe.FLG_EQUATORIAL
                )
                ra, _, _ = require_spherical_coordinates(
                    eq, eqflag, native=swe, equatorial=True
                )
                eqmodel = runtime.ephemeris_model_from_retflag(eqflag)
                sources.observe("Sun", eqmodel)
                if model != expected_sun_model or eqmodel != expected_sun_model:
                    raise EphemerisSourceError("coordinate_model_changed")
                current_source = sources.snapshot()
                if current_source["has_unidentified_sources"]:
                    raise ValueError("太阳日星历来源无法识别，不能保持本命数据版本")
                source_cohort.add(current_source)
                if not 0 < pos[3] < 2:
                    raise ValueError("太阳未按声明速率前行")
                gast = float(runtime.ephemeris_call("sidtime", at) * 15) % 360
                # The civil reference is only the shared helper's ordinal
                # anchor. No correction relative to this placeholder is used
                # or exposed as an epoch-specific civil correction.
                clock = apparent_solar_clock(
                    julian_day_ut1=at,
                    sun_right_ascension=ra,
                    greenwich_apparent_sidereal_degrees=gast,
                    longitude=birth.longitude,
                    civil_datetime=birth.local_datetime,
                )
                label = F(reference_ordinal + clock["solar_day_offset_from_civil"]) + F(
                    clock["apparent_day_fraction_exact"]
                )
                evaluated[at] = dict(
                    julian_day_ut1_exact=str(F(at)),
                    julian_day_tt_exact=str(F(tt)),
                    apparent_solar_label_serial_exact=str(label),
                    solar_tropical_longitude_exact=str(F(longitude)),
                    sun_apparent_right_ascension_exact=str(F(ra)),
                    greenwich_apparent_sidereal_degrees_exact=str(F(gast)),
                    ecliptic_return_flags=int(flag),
                    equatorial_return_flags=int(eqflag),
                    actual_sun_model=model,
                )
            return evaluated[at]

        roots, grid = _day_brackets(birth_ut1, serial, evaluate)
        include = policy == POLICIES[2]
        start = [
            F(roots[0][side]["solar_tropical_longitude_exact"])
            for side in ["lower", "upper"]
        ]
        end = [
            F(roots[1][side]["solar_tropical_longitude_exact"])
            for side in ["lower", "upper"]
        ]
        candidates = {
            anchor_from_day_longitudes(a, b, include_winter_day=include)
            for a, b in product(start, end)
        }
        if len(candidates) != 1:
            raise ValueError(
                "太阳日端点夹逼跨越安命交节界，须保留数值未定，不能暗取一侧"
            )
        receipt = sources.finish()
        if (
            configured_ephemeris_path() != selected_path
            or configured_jpl_file() != selected_jpl
        ):
            raise EphemerisSourceError("physical_configuration_changed")
    return dict(
        method_id=METHOD_ID,
        policy=policy,
        anchor_branch=next(iter(candidates)),
        source_id="tohoku_luwei_10020000001141",
        source_image=9,
        clock_method_id=CLOCK_METHOD,
        clock_basis="modeled_local_apparent_solar_day",
        apparent_solar_date_label=(
            birth_clock["display"].split("T")[0] if birth_clock.get("display") else None
        ),
        birth_solar_label_serial_exact=str(serial),
        birth_julian_day_ut1_exact=str(F(birth_ut1)),
        source_day_interpretation=dict(
            winter_start=(
                "winter_solstice_day_included"
                if include
                else "day_after_winter_solstice_day"
            ),
            winter_end="major_cold_day_included",
            summer_start="summer_solstice_day_included",
            summer_end="minor_heat_day_included",
        ),
        day_edge_brackets=roots,
        full_search_UT1_window_exact=[str(F(grid[0])), str(F(grid[-1]))],
        complete_coarse_clock_scan_monotonic=True,
        evaluated_epochs=len(evaluated),
        numerical_bracket_limit_seconds_exact="1/1000",
        numerical_resolution_is_physical_accuracy=False,
        physical_ephemeris_source=receipt,
        same_birth_source_cohort_checked=True,
        actual_sun_model=expected_sun_model,
        inverse_UT1_to_TT_policy="shared_selected_IERS_or_modeled_DeltaT",
        UTC_day_edge_labels_assigned=False,
        leap_second_labels_represented=False,
        historical_local_day_boundary_accepted=False,
        actual_sunrise_used_for_anchor=False,
        source_sunrise_geometry_adjudicated=False,
        winter_day_inclusion_adjudicated=False,
        policy_selected_by_prediction_fit=False,
        physical_time_accuracy_certified=False,
    )
