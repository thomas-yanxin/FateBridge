"""Replay all independently frozen additional projection queries, no collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from fatebridge.core import canping_solar, de440_solar
from fatebridge.core.solar_model_policy import DE440_SOFTWARE_YEARS

ROOT = Path(__file__).resolve().parents[1]


def audit() -> dict:
    folder = ROOT / "tests/fixtures/canping_extended_projection_v1"
    protocol = json.loads((folder / "protocol.json").read_bytes())
    freeze = json.loads((folder / "freeze.json").read_bytes())
    failures = []
    for n, h in freeze["files"].items():
        if hashlib.sha256((folder / n).read_bytes()).hexdigest() != h:
            failures.append(
                {"kind": "extended_projection_reference_identity", "file": n}
            )
    data = ROOT / "src/fatebridge/data/astronomy"
    for n, h in protocol["preserve_existing_profiles"].items():
        if hashlib.sha256((data / n).read_bytes()).hexdigest() != h:
            failures.append({"kind": "existing_profile_changed", "file": n})
    if list(DE440_SOFTWARE_YEARS) != protocol["public_input_years_preserved"]:
        failures.append({"kind": "public_range_changed_without_requalification"})
    refs = json.loads((folder / "reference.json").read_bytes())
    states = json.loads((folder / "states.json").read_bytes())
    if [r["year"] for r in refs["rows"]] != protocol["reference_years"] or len(
        states["rows"]
    ) != 1452:
        failures.append({"kind": "complete_reference_cohort"})
    env_names = ["FATEBRIDGE_SOLAR_TERM_MODEL", "FATEBRIDGE_JPL_FILE"]
    original = {n: os.environ.get(n) for n in env_names}
    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = "de440"
    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    roots = []
    state_errors = []
    try:
        for expected in refs["rows"]:
            year = expected["year"]
            low = year == 1699
            row = canping_solar.projection_boundary(
                year,
                "UTC",
                origin_civil_year=1700 if low else 2300,
                origin_bazi_year=1699 if low else 2300,
                horizon=120,
            )
            detail = row["record"]["solar_model_details"]
            error = abs(detail["selected_crossing_jd_tt"] - expected["jd_tt"]) * 86400
            roots.append(
                {
                    "year": year,
                    "expected_tt": expected["jd_tt"],
                    "actual_tt": detail["selected_crossing_jd_tt"],
                    "residual_seconds_tt": error,
                    "model": row["record"]["ephemeris_model"],
                }
            )
            if error > protocol["reference_evaluator"]["root_tolerance_seconds"]:
                failures.append({"kind": "extended_projection_root_error", **roots[-1]})
            wanted = (
                "fatebridge_de440_solar_extended_v1" if low else protocol["model_id"]
            )
            if (
                row["record"]["ephemeris_model"] != wanted
                or detail["selection_policy"] != protocol["new_policy_id"]
            ):
                failures.append(
                    {"kind": "extended_projection_source_substitution", "year": year}
                )
        for row in states["rows"]:
            profile = (
                "fatebridge_de440_solar_extended_v1"
                if row["tdb_jd"] < 2400000
                else protocol["model_id"]
            )
            pos, vel = de440_solar.state(
                (row["center"], row["target"]),
                row["tdb_jd"] - 2451545.0,
                profile_id=profile,
            )
            ep = max(abs(a - b) for a, b in zip(pos, row["position_km"]))
            ev = max(abs(a - b) for a, b in zip(vel, row["velocity_km_per_day"]))
            item = {
                "center": row["center"],
                "target": row["target"],
                "tdb_jd": row["tdb_jd"],
                "position_residual_km": ep,
                "velocity_residual_km_per_day": ev,
            }
            state_errors.append(item)
            if (
                ep > protocol["state_sampling"]["position_tolerance_km"]
                or ev > protocol["state_sampling"]["velocity_tolerance_km_per_day"]
            ):
                failures.append(
                    {"kind": "extended_projection_original_state_error", **item}
                )
    finally:
        for n, v in original.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v
    return {
        "checks_passed": not failures,
        "failures": failures,
        "comparison_mode": "explicit_de440_control; caller environment restored",
        "replayed_frozen_tt_queries": len(roots),
        "replayed_frozen_state_queries": len(state_errors),
        "queries_overlapping_prior_projection_root_cohort": 20,
        "additional_queries_relative_to_that_cohort": 101,
        "root_tolerance_seconds_tt": 1.0,
        "maximum_root_residual_seconds_tt": max(
            r["residual_seconds_tt"] for r in roots
        ),
        "maximum_position_residual_km": max(
            r["position_residual_km"] for r in state_errors
        ),
        "maximum_velocity_residual_km_per_day": max(
            r["velocity_residual_km_per_day"] for r in state_errors
        ),
        "roots": roots,
        "state_residuals": state_errors,
        "registered_public_packaged_input_years": list(DE440_SOFTWARE_YEARS),
        "this_event_permission_extends_public_year_grid": False,
        "new_physical_observations": 0,
        "new_original_birth_examples": 0,
        "new_real_world_outcomes": 0,
        "future_utc_certified": False,
        "goal_complete": False,
        "scope": "Full predeclared additional event cohort and original coefficient queries; independent evaluator, shared DE440 orbit lineage. Not independent physical accuracy, all public calendar inputs or classical/predictive certification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print({k: v for k, v in result.items() if k not in ["roots", "state_residuals"]})
    raise SystemExit(0 if result["checks_passed"] else 1)
