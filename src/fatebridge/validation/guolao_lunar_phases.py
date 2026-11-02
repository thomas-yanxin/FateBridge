"""Declared mean-quarter coverage, keeping source-time gaps and date gaps apart."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_lunar_phases import KINDS, PROFILE, source_lunar_phase


def audit_lunar_phase_grid(start: int, stop: int) -> dict[str, Any]:
    if any(type(v) is not int for v in (start, stop)) or not 0 <= start < stop <= 400:
        raise ValueError("诊断范围须为0至400内的非空整数区间，前含后不含")
    rows = []
    missing = []
    totals: Counter[str] = Counter()
    for year in range(start, stop):
        middle = shoushi_winter_cycle(year).zhongji_days
        counts: Counter[str] = Counter()
        for index in range(72):
            event = source_lunar_phase(middle, index)
            available = (
                event["research_phase_offset_from_winter_days_exact"] is not None
            )
            kind = event["phase_kind"]
            counts["declared_positions"] += 1
            counts[
                "source_time_available" if available else "source_time_unavailable"
            ] += 1
            counts[
                kind + ("_time_available" if available else "_time_unavailable")
            ] += 1
            assignment = event["source_phase_day_assignment"]
            assigned = assignment["assigned_source_phase_day_integer"] is not None
            counts[
                (
                    "source_phase_day_assigned"
                    if assigned
                    else "source_phase_day_unresolved"
                )
            ] += 1
            if assignment["status"] == "requires_explicit_source_sunrise":
                counts["source_time_available_but_sunrise_missing"] += 1
            if event["sunrise_shift_applied_to_new_moon"]:
                raise AssertionError("弦望退日不能套于朔")
            if not available:
                missing.append(
                    {
                        "elapsed_years": year,
                        "phase_index": index,
                        "phase_kind": kind,
                        "calculation_status": event["calculation_status"],
                        "lunar_argument_within_printed_limits": event[
                            "angular_components"
                        ]["lunar"]["argument_within_printed_limits"],
                        "velocity_limit_index": event["lunar_velocity"][
                            "whole_limit_index"
                        ],
                        "velocity_status": event["lunar_velocity"]["status"],
                    }
                )
        totals.update(counts)
        rows.append({"elapsed_years": year, "counts": dict(sorted(counts.items()))})
    return {
        "model_id": "gujin_lunar_phase_internal_coverage_v1",
        "profile_id": PROFILE,
        "elapsed_year_range": [start, stop],
        "phase_index_range": [0, 72],
        "phase_kinds": list(KINDS),
        "declared_positions": (stop - start) * 72,
        "counts": dict(sorted(totals.items())),
        "rows": rows,
        "missing_time_positions": missing,
        "source_sunrise_supplied_or_defaulted": False,
        "missing_time_or_date_positions_counted_as_accepted": False,
        "internal_coverage_only": True,
        "independent_historical_phase_reference_facts_added": 0,
        "physical_phase_time_validated": False,
        "complete_source_calendar_accepted": False,
        "real_world_prediction_subjects": 0,
    }
