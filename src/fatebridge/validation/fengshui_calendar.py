"""Independent Li Chun TT comparisons, distinct from UTC and prediction truth."""

import math
from datetime import datetime
from typing import Any, Dict

from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.fengshui.calendar import lichun_resolution


def audit_lichun_reference(reference: Dict[str, Any]) -> Dict[str, Any]:
    protocol = reference["protocol"]
    tolerance = protocol["numeric_implementation_tolerance_seconds"]
    spans = {
        "fengshui_lichun_de440_tt_v1": (1800, 2200),
        "fengshui_lichun_de440_tt_v2": (1784, 2204),
    }
    if protocol["id"] not in spans or isinstance(tolerance, bool) or tolerance != 1.0:
        raise ValueError(
            "The frozen Li Chun protocol and one-second gate must be retained"
        )
    first, last = spans[protocol["id"]]
    rows = reference["rows"]
    if [r["year"] for r in rows] != list(range(first, last + 1)):
        raise ValueError("Retain every distinct ordered year, including both endpoints")
    for row in rows:
        if type(row["year"]) is not int:
            raise ValueError("Reference years must be literal integers")
        for key in ("jd_tt", "bracket_width_seconds"):
            value = row[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError("Reference values must be finite real numbers")
        if not 0 <= row["bracket_width_seconds"] <= 0.001:
            raise ValueError(
                "Reference crossing must retain the precise bisection bracket"
            )
    comparisons = []
    for row in rows:
        resolved = lichun_resolution(row["year"], "UTC")
        difference = None
        if not resolved["approximate"]:
            tt = ephemeris_time(datetime.fromisoformat(resolved["moment"])).jd_tt
            if tt is not None:
                difference = (tt - row["jd_tt"]) * 86400
        comparisons.append(
            {
                "year": row["year"],
                "reference_jd_tt": row["jd_tt"],
                "difference_seconds": difference,
                "resolution": resolved,
                "within_tolerance": difference is not None
                and abs(difference) <= tolerance,
            }
        )
    failed = sum(not row["within_tolerance"] for row in comparisons)
    differences = [
        abs(row["difference_seconds"])
        for row in comparisons
        if row["difference_seconds"] is not None
    ]
    return {
        "protocol_id": protocol["id"],
        "rows": len(comparisons),
        "tolerance_seconds": tolerance,
        "matched": len(comparisons) - failed,
        "failed_count": failed,
        "maximum_absolute_difference_seconds": max(differences, default=None),
        "all_scoped_tt_checks_passed": failed == 0,
        "scope": "Complete protocol range of geocentric apparent solar crossings in TT; not absolute UTC accuracy, all solar terms, or real-world Feng Shui validity",
        "comparisons": comparisons,
        "reality_prediction": "not_tested",
    }
