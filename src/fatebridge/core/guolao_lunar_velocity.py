"""Gujin45's discrete printed lunar velocities and named table research.

All 168 numeric rows are retained, including irregular cells. Index168 is
explicitly empty. This is a four-decimal printed-table reconstruction, not a
claim to have recovered the author's internal precision or civil calendar.
"""

from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, STEMS
from fatebridge.core.guolao_conjunctions import GUJIN_COMPONENTS, source_conjunction
from fatebridge.core.guolao_four_extras import four_extras_source_days
from fatebridge.core.guolao_lunations import gujin_four_extras_lunations

DATA = (
    Path(__file__).resolve().parents[1] / "data/guolao/gujin45-lunar-velocity-v1.json"
)
PROFILE = "gujin36_37_45_floor_table_research"


def _table() -> tuple[dict[str, Any], str]:
    blob = DATA.read_bytes()
    table = json.loads(blob)
    rows = table["rows"]
    if len(rows) != 169 or [r["limit_index"] for r in rows] != list(range(169)):
        raise ValueError("卷45行度表须保留169格，不能补格、删格或改序")
    for row in rows:
        for key in ["fast_ancient_du_per_limit", "slow_ancient_du_per_limit"]:
            value = row[key]
            if row["limit_index"] == 168:
                if value is not None:
                    raise ValueError("卷45末限原刊为空，不能按周期回填")
            elif (
                not isinstance(value, str)
                or not re.fullmatch(r"[01]\.\d{4}", value)
                or Fraction(value) <= 0
            ):
                raise ValueError("卷45行度须为原刊四位小数正值；不代填缺数")
    if (
        table["profile_id"] != PROFILE
        or table["angular_profile_id"] != GUJIN_COMPONENTS
    ):
        raise ValueError("具名行度与角差参数不符，不能混参")
    if (
        Fraction(table["anomalistic_month_days"]),
        Fraction(table["half_anomalistic_month_days"]),
        Fraction(table["limits_per_day"]),
        Fraction(table["limit_duration_in_correction_days"]),
    ) != (
        Fraction("27.5546"),
        Fraction("13.7773"),
        Fraction("12.2"),
        Fraction("0.0820"),
    ):
        raise ValueError("卷45周期、限率或定朔单位不符，不重新缩放")
    return table, hashlib.sha256(blob).hexdigest()


def gujin45_lunar_velocity(anomaly_days: Fraction) -> dict[str, Any]:
    """Look up the unreflected whole limit; never interpolate or mirror rows."""
    if not isinstance(anomaly_days, Fraction):
        raise TypeError("入转须为Fraction原历日数，不接收现代JD浮点值")
    table, digest = _table()
    phase = anomaly_days % Fraction(table["anomalistic_month_days"])
    half = Fraction(table["half_anomalistic_month_days"])
    fast = phase <= half
    within = phase if fast else phase - half
    limit = within * Fraction(table["limits_per_day"])
    index = limit // 1
    row = table["rows"][index]
    key = "fast_ancient_du_per_limit" if fast else "slow_ancient_du_per_limit"
    velocity = row[key]
    reflection = None
    if index < 168:
        opposite_key = (
            "slow_ancient_du_per_limit" if fast else "fast_ancient_du_per_limit"
        )
        opposite = table["rows"][167 - index]
        reflected_value = opposite[opposite_key]
        reflection = {
            "opposite_index": 167 - index,
            "opposite_column": opposite_key,
            "opposite_printed_velocity": reflected_value,
            "selected_minus_opposite_ancient_du_per_limit_exact": str(
                Fraction(velocity) - Fraction(reflected_value)
            ),
            "agrees": Fraction(velocity) == Fraction(reflected_value),
            "comparison_used_to_replace_selected_value": False,
        }
    return {
        "model_id": table["model_id"],
        "profile_id": PROFILE,
        "source_data_sha256": digest,
        "source_url": table["source_url"],
        "anomaly_phase_days_exact": str(phase),
        "phase": "疾" if fast else "遲",
        "within_half_days_exact": str(within),
        "unreflected_limit_exact": str(limit),
        "whole_limit_index": index,
        "discarded_fraction_of_limit_exact": str(limit - index),
        "printed_velocity_ancient_du_per_limit": velocity,
        "velocity_ancient_du_per_limit_exact": (
            str(Fraction(velocity)) if velocity is not None else None
        ),
        "source_locator": {
            "djvu_page": row["djvu_page"],
            "half": row["half"],
            "limit_index": index,
            "column": key,
        },
        "index_policy": table["index_policy"],
        "reflection_comparison_diagnostic": reflection,
        "status": (
            "printed_cell"
            if velocity is not None
            else "printed_empty_endpoint_no_value"
        ),
        "interpolated": False,
        "reflected_or_periodically_filled": False,
        "unrounded_velocity_reconstructed": False,
        "used_in_native_birth_chart": False,
    }


def gujin45_time_correction(
    solar_signed_du: Fraction, lunar_signed_du: Fraction, anomaly_days: Fraction
) -> dict[str, Any]:
    """The source's820/day周 conversion using a printed lunar velocity cell."""
    for value in [solar_signed_du, lunar_signed_du]:
        if not isinstance(value, Fraction):
            raise TypeError("盈缩、迟疾须为Fraction有符号原历古度")
    velocity = gujin45_lunar_velocity(anomaly_days)
    v = velocity["velocity_ancient_du_per_limit_exact"]
    correction = (
        Fraction(".082") * (solar_signed_du + lunar_signed_du) / Fraction(v)
        if v is not None
        else None
    )
    return {
        "profile_id": PROFILE,
        "solar_signed_ancient_du_exact": str(solar_signed_du),
        "lunar_signed_ancient_du_exact": str(lunar_signed_du),
        "lunar_velocity": velocity,
        "time_correction_days_exact": (
            str(correction) if correction is not None else None
        ),
        "formula": "820 * (signed_solar_du + signed_lunar_du) / (10000 * lunar_du_per_limit)",
        "sun_daily_motion_subtracted_from_denominator": False,
        "printed_shortcut_column_used": False,
        "rounded_table_internal_precision_reconstructed": False,
    }


def gujin_table_conjunction(
    zhongji_days: Fraction, lunation_index: int
) -> dict[str, Any]:
    """Complete the named36/37 angular chain with45's printed velocity column."""
    angles = source_conjunction(
        zhongji_days, lunation_index, profile_id=GUJIN_COMPONENTS
    )
    return _table_event_from_angles(zhongji_days, lunation_index, angles)


def _table_event_from_angles(
    zhongji_days: Fraction, lunation_index: int, angles: dict[str, Any]
) -> dict[str, Any]:
    """Apply the same printed velocity and correction to the supplied mean event."""
    moon = angles["lunar"]
    velocity = gujin45_lunar_velocity(Fraction(moon["anomaly_phase_days_exact"]))
    correction = None
    if (
        moon["signed_correction_ancient_du_exact"] is not None
        and velocity["velocity_ancient_du_per_limit_exact"] is not None
    ):
        step = gujin45_time_correction(
            Fraction(angles["solar"]["signed_correction_ancient_du_exact"]),
            Fraction(moon["signed_correction_ancient_du_exact"]),
            Fraction(moon["anomaly_phase_days_exact"]),
        )
        correction = Fraction(step["time_correction_days_exact"])
    offset = Fraction(angles["mean_conjunction_offset_from_winter_days_exact"])
    mean_total = zhongji_days + Fraction("55.06") + offset
    total = mean_total + correction if correction is not None else None
    cycle = total % 60 if total is not None else None
    day = cycle // 1 if cycle is not None else None
    return {
        "model_id": "gujin_named_printed_table_conjunction_v1",
        "profile_id": PROFILE,
        "zhongji_days_exact": str(zhongji_days),
        "lunation_index": lunation_index,
        "angular_components": angles,
        "lunar_velocity": velocity,
        "time_correction_days_exact": (
            str(correction) if correction is not None else None
        ),
        "research_conjunction_offset_from_winter_days_exact": (
            str(offset + correction) if correction is not None else None
        ),
        "research_conjunction_day_cycle_exact": (
            str(cycle) if cycle is not None else None
        ),
        "research_conjunction_sexagenary_day": (
            STEMS[day % 10] + BRANCHES[day % 12] if day is not None else None
        ),
        "midnight_displacement_from_mean_days": (
            total // 1 - mean_total // 1 if total is not None else None
        ),
        "status": (
            "printed_table_formula_research"
            if correction is not None
            else "missing_or_out_of_limit_source_value_not_filled"
        ),
        "lunar_date": None,
        "complete_source_calendar_accepted": False,
        "intercalation_reconstructed": False,
        "modern_epoch_calibrated": False,
        "used_in_native_birth_chart": False,
    }


def gujin_four_extras_table_days(zhongji_days: Fraction) -> dict[str, Any]:
    """Event-day diagnostics after the table conjunction, with no month assignment.

    The mean-lunation index is a candidate. Check it against the next civil
    midnight start, so a nearby true conjunction cannot silently shift the
    event into an unexamined month. Missing required neighbors remain missing.
    """
    mean = gujin_four_extras_lunations(zhongji_days)
    entries = four_extras_source_days(zhongji_days)
    winter = zhongji_days + Fraction("55.06")
    factors = {}
    for key, context in mean["factors"].items():
        index = context["mean_lunation_index"]
        current = gujin_table_conjunction(zhongji_days, index)
        following = gujin_table_conjunction(zhongji_days, index + 1)
        start = current["research_conjunction_offset_from_winter_days_exact"]
        stop = following["research_conjunction_offset_from_winter_days_exact"]
        event_total = winter + Fraction(
            entries["factors"][key]["days_until_next_entry_exact"]
        )
        valid = False
        diagnostic_day = None
        length = None
        if start is not None and stop is not None:
            first = (winter + Fraction(start)) // 1
            last = (winter + Fraction(stop)) // 1
            valid = first <= event_total // 1 < last
            length = last - first
            if valid:
                diagnostic_day = event_total // 1 - first + 1
        factors[key] = {
            "mean_lunation_candidate_index": index,
            "candidate_contains_event_civil_day": valid,
            "diagnostic_day_after_table_conjunction": diagnostic_day,
            "diagnostic_candidate_month_length_days": length,
            "entry_event_cycle_days_exact": str(event_total % 60),
            "conjunction": current,
            "next_conjunction": following,
            "assigned_lunar_month": None,
            "lunar_date": None,
        }
    return {
        "profile_id": PROFILE,
        "zhongji_days_exact": str(zhongji_days),
        "factors": factors,
        "printed_calendar_dates_used_as_algorithm_inputs": False,
        "lunar_dates_assigned": False,
        "intercalation_reconstructed": False,
        "modern_epoch_calibrated": False,
        "used_in_native_birth_chart": False,
    }
