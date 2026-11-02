"""Bounded UTC leap-label acceptance against independent official SOFA C."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.human_design_birth_clock import resolve_birth_clock


def confirmed_leap_checks(root: Path) -> dict:
    plan_path = root / "tests/fixtures/human-design-leap-plan.json"
    reference_path = root / "tests/fixtures/human-design-leap-sofa.json"
    plan = json.loads(plan_path.read_bytes())
    reference = json.loads(reference_path.read_bytes())
    plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    reference_sha = hashlib.sha256(reference_path.read_bytes()).hexdigest()
    if (
        plan_sha != "88e529c6bf50525777148655da1bd948cc06c7ff72764627fd116f6a023220c7"
        or reference_sha
        != "9df7ea58de211dbaeac6e2c682e77dcbf0e493bf33db3316bd39f4c7844f09f3"
        or reference["plan_sha256"] != plan_sha
        or plan["tolerance_seconds"] != 0.0002
        or len(reference["cases"]) != 81
        or [r["utc_label"] for r in reference["cases"]] != plan["utc_labels"]
    ):
        raise ValueError(
            "Frozen SOFA plan/reference changed; do not rewrite acceptance"
        )
    results = []
    for row in reference["cases"]:
        label = row["utc_label"]
        clock = resolve_birth_clock(
            birth_year=int(label[:4]),
            birth_month=int(label[5:7]),
            birth_day=int(label[8:10]),
            birth_hour=int(label[11:13]),
            birth_minute=int(label[14:16]),
            birth_second=int(label[17:19]),
            birth_timezone="UTC",
        )
        tt = (
            clock.jd_tt if clock.leap_second else ephemeris_time(clock.utc_anchor).jd_tt
        )
        if tt is None:
            raise ValueError("No selected TT for a planned label")
        residual = float(
            (Fraction(tt) - Fraction(row["tt_jd1"]) - Fraction(row["tt_jd2"])) * 86400
        )
        results.append(
            {
                "utc_label": label,
                "actual_jd_tt": tt,
                "residual_seconds": residual,
                "is_inserted_second": clock.leap_second,
                "passed": abs(residual) <= 0.0002 and row["statuses"] == [0, 0, 0],
            }
        )
    return {
        "method_id": "human_design_all_known_leap_label_acceptance_v1",
        "status": (
            "bounded_81_sofa_labels_passed"
            if all(r["passed"] for r in results)
            else "failed"
        ),
        "source_url": reference["source_url"],
        "plan_sha256": plan_sha,
        "reference_sha256": reference_sha,
        "checked": len(results),
        "matched": sum(r["passed"] for r in results),
        "positive_leap_seconds": sum(r["is_inserted_second"] for r in results),
        "tolerance_seconds": 0.0002,
        "maximum_absolute_residual_seconds": max(
            abs(r["residual_seconds"]) for r in results
        ),
        "cases": results,
        "scope": "All27 published positive UTC leap seconds, preceding59 and following00; fixed0.2ms single-binary64-TT tolerance against official SOFA two-part TT. Does not certify historical civil clocks, actual UT1, planetary coordinates, future leaps, the full supported calendar, source doctrine or predictions.",
    }
