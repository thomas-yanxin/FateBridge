"""Compare the complete frozen Canping projection cohort; never collect answers."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from fatebridge.core import analytic_solar, de440_solar
from fatebridge.core.solar_model_policy import DE440_SOFTWARE_YEARS

ROOT = Path(__file__).resolve().parents[1]


def audit() -> dict:
    folder = ROOT / "tests/fixtures/canping_projection_v1"
    protocol = json.loads((folder / "protocol.json").read_bytes())
    freeze = json.loads((folder / "freeze.json").read_bytes())
    failures = []
    for name, digest in freeze["files"].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "frozen_projection_identity", "file": name})
    for name, digest in protocol["preserve_existing_profiles"].items():
        path = ROOT / "src/fatebridge/data/astronomy" / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            failures.append({"kind": "existing_solar_profile_changed", "file": name})
    reference = json.loads((folder / "reference.json").read_bytes())
    states = json.loads((folder / "states.json").read_bytes())
    years = list(range(2201, 2321))
    if [r["year"] for r in reference["rows"]] != years or len(states["rows"]) != 1440:
        failures.append({"kind": "complete_projection_cohort"})
    roots = []
    tolerance = protocol["reference_evaluator"]["root_tolerance_seconds"]
    for row in reference["rows"]:
        year = row["year"]
        low = date(year, 2, 1).toordinal() + 1721424.5
        high = date(year, 2, 12).toordinal() + 1721424.5
        for mode in ("de440", "analytic"):
            root = (
                de440_solar.longitude_crossing_tt(
                    315.0, low, high, profile_id=de440_solar.CANPING_MODEL_ID
                )
                if mode == "de440"
                else analytic_solar.longitude_crossing_tt(315.0, low, high)
            )
            error = (root["jd_tt"] - row["jd_tt"]) * 86400
            roots.append({"year": year, "mode": mode, "residual_seconds_tt": error})
            if abs(error) > tolerance:
                failures.append({"kind": "projection_root_residual", **roots[-1]})
    position, velocity = [], []
    for row in states["rows"]:
        p, v = de440_solar.state(
            (row["center"], row["target"]),
            row["tdb_jd"] - 2451545.0,
            profile_id=de440_solar.CANPING_MODEL_ID,
        )
        position.append(max(abs(a - b) for a, b in zip(p, row["position_km"])))
        velocity.append(max(abs(a - b) for a, b in zip(v, row["velocity_km_per_day"])))
    if (
        max(position) > protocol["state_sampling"]["position_tolerance_km"]
        or max(velocity) > protocol["state_sampling"]["velocity_tolerance_km_per_day"]
    ):
        failures.append({"kind": "projection_original_state_residual"})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "event_years": [2201, 2320],
        "new_reference_tt_roots": len(reference["rows"]),
        "new_reference_state_rows": len(states["rows"]),
        "comparison_roots": roots,
        "maximum_root_residual_seconds_tt": {
            m: max(abs(r["residual_seconds_tt"]) for r in roots if r["mode"] == m)
            for m in ("de440", "analytic")
        },
        "root_tolerance_seconds_tt": tolerance,
        "maximum_position_residual_km": max(position),
        "maximum_velocity_residual_km_per_day": max(velocity),
        "reference_lineage": "Full original DE440 with Skyfield/jplephem, independent evaluator; shared orbit lineage, not independent physical observations",
        "new_original_horoscopes": 0,
        "new_real_world_outcomes": 0,
        "independent_second_review_completed": False,
        "public_model_years_extended": list(DE440_SOFTWARE_YEARS)
        != protocol["origin_civil_years"],
        "registered_public_de440_input_years": list(DE440_SOFTWARE_YEARS),
        "public_range_comparison_baseline": protocol["origin_civil_years"],
        "this_projection_permission_extends_public_year_grid": False,
        "legacy_new_reference_counter_scope": "Original frozen cohort counts, not new queries or observations this run.",
        "new_reference_tt_roots_this_run": 0,
        "new_reference_state_rows_this_run": 0,
        "future_utc_certified": False,
        "goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "comparison_roots"},
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if report["checks_passed"] else 1)
