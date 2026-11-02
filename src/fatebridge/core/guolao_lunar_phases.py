"""Named Gujin quarter/full-moon calculations and their separate source-day rule.

An explicit source sunrise is required for non-new-moon day labels. A computed
phase instant is neither a modern ephemeris root nor an accepted lunar date.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, STEMS
from fatebridge.core.guolao_conjunctions import (
    GUJIN_COMPONENTS,
    _source_phase_components,
)
from fatebridge.core.guolao_lunar_velocity import _table_event_from_angles

DATA = Path(__file__).resolve().parents[1] / "data/guolao/gujin37-lunar-phases-v1.json"
PROFILE = "gujin36_37_45_floor_table_lunar_phases_research"
KINDS = ("new_moon", "first_quarter", "full_moon", "last_quarter")


def _profile() -> tuple[dict[str, Any], str]:
    raw = DATA.read_bytes()
    p = json.loads(raw)
    if (
        p["profile_id"] != PROFILE
        or tuple(p["phase_kinds"]) != KINDS
        or p["phase_names"] != ["朔", "上弦", "望", "下弦"]
        or F(p["mean_synodic_month_days"]) != F("29.530593")
        or 4 * F(p["mean_quarter_step_days"]) != F(p["mean_synodic_month_days"])
        or F(p["source_circle_ancient_du"]) != F("365.2575")
        or [F(v) for v in p["phase_targets_ancient_du"]]
        != [i * F("365.2575") / 4 for i in range(4)]
        or p["sunrise_rollback_kinds"] != list(KINDS[1:])
        or p["sunrise_comparison"] != "event_fraction_le_source_sunrise_fraction"
        or p["sunrise_default"] is not None
    ):
        raise ValueError("具名弦策、古度及日出退日规则不符，不自动混参或补日出分")
    return p, hashlib.sha256(raw).hexdigest()


def assign_source_phase_day(
    total_source_days: F | None,
    phase_kind: str,
    *,
    source_sunrise_fraction: F | None = None,
) -> dict[str, Any]:
    """Inclusive 已下 applies to 弦望 only; a missing threshold stays missing."""
    if phase_kind not in KINDS:
        raise ValueError("须明确为朔、上弦、望或下弦")
    if total_source_days is not None and not isinstance(total_source_days, F):
        raise TypeError("加时须为Fraction原历未折回日数，缺值须为None")
    if source_sunrise_fraction is not None:
        if not isinstance(source_sunrise_fraction, F):
            raise TypeError("日出分须为Fraction原历日内份额，不套现代日出")
        if not 0 <= source_sunrise_fraction < 1:
            raise ValueError("日出份额须在0至1之间，不接收日周分原整数或自动取模")
    requires_sunrise = phase_kind != "new_moon"
    midnight = total_source_days // 1 if total_source_days is not None else None
    fraction = total_source_days % 1 if total_source_days is not None else None
    rollback = assigned = None
    if total_source_days is None:
        status = "phase_time_unavailable"
    elif requires_sunrise and source_sunrise_fraction is None:
        status = "requires_explicit_source_sunrise"
    else:
        assert midnight is not None and fraction is not None
        if requires_sunrise:
            assert source_sunrise_fraction is not None
            rollback = fraction <= source_sunrise_fraction
        else:
            rollback = False
        assigned = midnight - int(rollback)
        status = (
            "assigned_under_printed_quarter_full_moon_sunrise_rule"
            if requires_sunrise
            else "new_moon_midnight_without_sunrise_rollback"
        )
    return {
        "phase_kind": phase_kind,
        "status": status,
        "civil_midnight_source_day_integer": midnight,
        "event_fraction_of_source_day_exact": (
            str(fraction) if fraction is not None else None
        ),
        "source_sunrise_fraction_supplied_exact": (
            str(source_sunrise_fraction)
            if source_sunrise_fraction is not None
            else None
        ),
        "source_sunrise_required_for_phase_date": requires_sunrise,
        "sunrise_comparison": (
            "event_fraction_le_source_sunrise_fraction" if requires_sunrise else None
        ),
        "sunrise_rollback_applied": rollback,
        "assigned_source_phase_day_integer": assigned,
        "assigned_source_phase_sexagenary_day": (
            STEMS[assigned % 10] + BRANCHES[assigned % 12]
            if assigned is not None
            else None
        ),
        "sunrise_computed_or_defaulted": False,
        "supplied_sunrise_location_or_ephemeris_verified": False,
        "modern_calendar_date_assigned": False,
    }


def source_lunar_phase(
    zhongji_days: F,
    phase_index: int,
    *,
    source_sunrise_fraction: F | None = None,
) -> dict[str, Any]:
    """Compute an exact quarter-step from initial mean new moon, not interpolation."""
    if isinstance(phase_index, bool) or not isinstance(phase_index, int):
        raise TypeError("朔弦望序号须为非负整数，0为天正经朔")
    if phase_index < 0:
        raise ValueError("朔弦望序号须非负，不以负序号推定上考")
    p, digest = _profile()
    lunation, quarter = divmod(phase_index, 4)
    components = _source_phase_components(
        zhongji_days, lunation, F(quarter, 4), profile_id=GUJIN_COMPONENTS
    )
    raw = _table_event_from_angles(zhongji_days, lunation, components)
    offset = raw["research_conjunction_offset_from_winter_days_exact"]
    total = zhongji_days + F("55.06") + F(offset) if offset is not None else None
    kind = KINDS[quarter]
    assigned = assign_source_phase_day(
        total, kind, source_sunrise_fraction=source_sunrise_fraction
    )
    return {
        "model_id": p["model_id"],
        "profile_id": PROFILE,
        "source_data_sha256": digest,
        "calculation_profile_id": raw["profile_id"],
        "source_url": p["source_url"],
        "source_locators": p["locators"],
        "zhongji_days_exact": str(zhongji_days),
        "phase_index": phase_index,
        "mean_lunation_index": lunation,
        "quarter_within_mean_lunation": quarter,
        "phase_kind": kind,
        "phase_name": p["phase_names"][quarter],
        "mean_quarter_step_days_exact": str(F(p["mean_quarter_step_days"])),
        "source_target_separation_ancient_du_exact": str(
            F(p["phase_targets_ancient_du"][quarter])
        ),
        "mean_phase_offset_from_winter_days_exact": components[
            "mean_conjunction_offset_from_winter_days_exact"
        ],
        "mean_phase_day_cycle_exact": components["mean_conjunction_day_cycle_exact"],
        "runyu_days_exact": components["runyu_days_exact"],
        "angular_components": {
            "profile_id": components["profile_id"],
            "source_data_sha256": components["source_data_sha256"],
            "mean_lunation_source_data_sha256": components[
                "mean_lunation_source_data_sha256"
            ],
            "solar": components["solar"],
            "lunar": components["lunar"],
        },
        "lunar_velocity": raw["lunar_velocity"],
        "time_correction_days_exact": raw["time_correction_days_exact"],
        "research_phase_offset_from_winter_days_exact": offset,
        "research_phase_day_cycle_exact": raw["research_conjunction_day_cycle_exact"],
        "research_phase_midnight_sexagenary_day": raw[
            "research_conjunction_sexagenary_day"
        ],
        "midnight_displacement_from_mean_days": raw[
            "midnight_displacement_from_mean_days"
        ],
        "calculation_status": raw["status"],
        "source_phase_day_assignment": assigned,
        "status": (
            "source_phase_time_unavailable"
            if total is None
            else "named_phase_time_research_with_separate_day_assignment"
        ),
        "phase_instants_interpolated_between_new_moons": False,
        "sunrise_shift_applied_to_new_moon": kind == "new_moon"
        and assigned["sunrise_rollback_applied"] is True,
        "lunar_date": None,
        "modern_epoch_calibrated": False,
        "physical_phase_time_validated": False,
        "complete_source_calendar_accepted": False,
        "used_in_native_birth_chart": False,
    }
