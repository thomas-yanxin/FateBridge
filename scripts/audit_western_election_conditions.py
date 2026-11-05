"""Recheck the retained kinematic failure and existing JPL event integration."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.astrology_election import build_election_payload
from fatebridge.core.horary_motion import solve_lunar_contacts
from fatebridge.core.predictive.native_chart import build_native_subject

ROOT = Path(__file__).resolve().parents[1]


def audit():
    def sample(planet, at):
        if planet == "Moon":
            return {"longitude": 13 * at, "speed": 13.0}
        return {"longitude": 0.1, "speed": 0.0}

    motion = solve_lunar_contacts(0.0, sample, bodies=("Mercury",))
    observed = motion["void_of_course"]
    expected_contact_days = Fraction(0.1) / 13
    expected_ingress_days = Fraction(30, 13)
    assert 0 < expected_contact_days < expected_ingress_days
    reference_path = ROOT / "tests/fixtures/western-horary-horizons.json"
    reference_bytes = reference_path.read_bytes()
    reference_sha256 = hashlib.sha256(reference_bytes).hexdigest()
    if (
        reference_sha256
        != "fddfbe44f8e9db2b71e62f6fec07a2c958705f8fd05b7f43fd5d2f7ec44a034f"
    ):
        raise ValueError("Independent JPL lunar-event reference changed")
    reference = json.loads(reference_bytes)
    if len(reference["cases"]) != 3:
        raise ValueError("All three independent JPL windows are required")
    cases = []
    for case in reference["cases"]:
        subject = build_native_subject(
            name="Election JPL integration",
            local_datetime=datetime_from_tt(case["start_julian_day_tt"]),
            longitude=0.0,
            latitude=31.0,
            timezone_name="UTC",
            house_system="R",
        )
        result = build_election_payload(subject, topic_id="general")
        actual = result["moon"]["motion_basis"]
        if actual["status"] != "computed":
            cases.append(
                {
                    "case_id": case["case_id"],
                    "status": actual["status"],
                    "unavailable_reason": actual.get("unavailable_reason"),
                    "nominal_epoch_matches_motion": False,
                    "passed": False,
                }
            )
            continue
        expected = case["expected"]
        keys = [(e["other"], e["ray_degrees"]) for e in actual["contacts"]]
        ref_keys = [(e["other"], e["ray_degrees"]) for e in expected["contacts"]]
        errors = [
            abs(a["julian_day_tt"] - z["julian_day_tt"]) * 86400
            for a, z in zip(actual["contacts"], expected["contacts"])
        ]
        exit_error = (
            abs(actual["sign_exit_julian_day_tt"] - expected["sign_exit_julian_day_tt"])
            * 86400
        )
        passed = (
            keys == ref_keys
            and actual["void_of_course"] == expected["void_of_course"]
            and max([exit_error, *errors]) <= 30
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "start_julian_day_tt": actual["start_julian_day_tt"],
                "nominal_epoch_matches_motion": actual["start_julian_day_tt"]
                == result["calculation_basis"]["julian_day_tt"],
                "expected_contact_keys": ref_keys,
                "actual_contact_keys": keys,
                "ingress_residual_seconds": exit_error,
                "contact_residuals_seconds": errors,
                "actual_void_of_course": actual["void_of_course"],
                "native_physical_sources": actual["physical_ephemeris_source"],
                "passed": passed,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference_sha256": reference_sha256,
        "synthetic_contact_after_days_exact": str(expected_contact_days),
        "synthetic_ingress_after_days_exact": str(expected_ingress_days),
        "current_observed_void_of_course": observed,
        "expected_geometric_void_of_course": False,
        "synthetic_contact_precedes_ingress": observed is False,
        "cases": cases,
        "new_independent_astronomy_cases": 0,
        "event_tolerance_seconds": 30,
        "scope": "Posthoc election integration reuse of three existing independent JPL windows, not new observations; direct domain TT conversion retains sub-minute time. Counterexample is synthetic kinematics, not original-text VoC equivalence or outcome efficacy.",
        "full_original_text_acceptance": False,
        "passed": observed is False
        and all(c["passed"] and c["nominal_epoch_matches_motion"] for c in cases),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Retained geometric failure closed={report['synthetic_contact_precedes_ingress']}; three reused JPL windows passed={report['passed']}"
    )
    raise SystemExit(0 if report["passed"] else 1)
