"""Full twelve-jie TT comparisons; no implicit promotion to actual UTC truth."""

import math
from collections import Counter
from datetime import datetime
from typing import Any

from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.fengshui.calendar import solar_term_resolution

CIVIL_JIE = (
    ("小寒", 285),
    ("立春", 315),
    ("惊蛰", 345),
    ("清明", 15),
    ("立夏", 45),
    ("芒种", 75),
    ("小暑", 105),
    ("立秋", 135),
    ("白露", 165),
    ("寒露", 195),
    ("立冬", 225),
    ("大雪", 255),
)


def audit_monthly_calendar_reference(reference: dict[str, Any]) -> dict[str, Any]:
    protocol = reference["protocol"]
    if (
        protocol["id"] != "fengshui_monthly_jie_de440_tt_v1"
        or type(protocol["year_min"]) is not int
        or protocol["year_min"] != 1800
        or type(protocol["year_max"]) is not int
        or protocol["year_max"] != 2200
        or type(protocol["numeric_implementation_tolerance_seconds"])
        not in (int, float)
        or protocol["numeric_implementation_tolerance_seconds"] != 1.0
        or protocol["gate_selected_before_collection"] is not True
    ):
        raise ValueError(
            "Retain the complete twelve-jie range and fixed one-second gate"
        )
    rows = reference["rows"]
    expected = [
        (year, name, degree) for year in range(1800, 2201) for name, degree in CIVIL_JIE
    ]
    if len(rows) != len(expected) or any(
        type(r["year"]) is not int
        or type(r["longitude_degrees"]) is not int
        or (r["year"], r["term"], r["longitude_degrees"]) != e
        for r, e in zip(rows, expected)
    ):
        raise ValueError(
            "Retain all 4812 ordered crossings, including failed endpoints"
        )
    for row in rows:
        if (
            any(
                type(row[k]) not in (int, float) or not math.isfinite(row[k])
                for k in ("jd_tt", "bracket_width_seconds")
            )
            or not 0 <= row["bracket_width_seconds"] <= 0.001
        ):
            raise ValueError(
                "Finite TT values and original sub-millisecond brackets required"
            )
    comparisons = []
    for row in rows:
        resolution = solar_term_resolution(row["year"], row["term"], "UTC")
        difference = None
        if not resolution["approximate"]:
            clock = ephemeris_time(datetime.fromisoformat(resolution["moment"]))
            difference = (clock.jd_tt - row["jd_tt"]) * 86400
        comparisons.append(
            {
                "year": row["year"],
                "term": row["term"],
                "reference_jd_tt": row["jd_tt"],
                "difference_seconds": difference,
                "within_tolerance": difference is not None and abs(difference) <= 1.0,
                "resolution": resolution,
            }
        )
    failed = [r for r in comparisons if not r["within_tolerance"]]
    measured = [
        abs(r["difference_seconds"])
        for r in comparisons
        if r["difference_seconds"] is not None
    ]
    return {
        "protocol_id": protocol["id"],
        "rows": len(rows),
        "tolerance_seconds": 1.0,
        "matched": len(rows) - len(failed),
        "failed_count": len(failed),
        "maximum_absolute_difference_seconds": max(measured, default=None),
        "all_scoped_tt_checks_passed": not failed,
        "actual_models": dict(
            Counter(
                r["resolution"].get("ephemeris_model", "not_astronomically_solved")
                for r in comparisons
            )
        ),
        "comparisons": comparisons,
        "scope": "All twelve jie in the fixed 1800..2200 TT range; not all 24 terms, absolute UTC, physical inputs, whole-book Feng Shui, or real-world predictions",
        "real_world_prediction": "not_tested",
    }
