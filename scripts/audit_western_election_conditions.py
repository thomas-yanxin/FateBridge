"""Recheck the retained kinematic failure and existing JPL event integration."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.astrology_election import (
    _moon_void_of_course,
    build_election_payload,
)
from fatebridge.core.predictive.native_chart import build_native_subject

ROOT = Path(__file__).resolve().parents[1]


def audit():
    protocol_path = ROOT / "tests/fixtures/western-election-conditions-protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, digest in protocol["reference_files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    retained = json.loads(
        (ROOT / "docs/validation/western-election-motion-open.json").read_text()
    )
    observed = _moon_void_of_course(
        retained["input"]["moon"], retained["input"]["others"]
    )
    reference = json.loads(
        (ROOT / "tests/fixtures/western-horary-horizons.json").read_text()
    )
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
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(
            (ROOT / "tests/fixtures/western-horary-horizons.json").read_bytes()
        ).hexdigest(),
        "retained_prior_failure": "western-election-motion-open.json",
        "prior_observed_void_of_course": retained["observed_void_of_course"],
        "current_observed_void_of_course": observed,
        "expected_geometric_void_of_course": False,
        "prior_geometric_failure_closed": observed is False,
        "cases": cases,
        "new_independent_astronomy_cases": 0,
        "event_tolerance_seconds": 30,
        "scope": "Posthoc election integration reuse of three existing independent JPL windows, not new observations; direct domain TT conversion retains sub-minute time. Counterexample is synthetic kinematics, not original-text VoC equivalence or outcome efficacy.",
        "full_original_text_acceptance": False,
        "passed": observed is False
        and all(c["passed"] and c["nominal_epoch_matches_motion"] for c in cases),
        "source_sha256": {
            r: hashlib.sha256((ROOT / r).read_bytes()).hexdigest()
            for r in [
                "src/fatebridge/core/astrology_election.py",
                "src/fatebridge/core/astrology_horary.py",
                "scripts/audit_western_election_conditions.py",
            ]
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Retained geometric failure closed={report['prior_geometric_failure_closed']}; three reused JPL windows passed={report['passed']}"
    )
    raise SystemExit(0 if report["passed"] else 1)
