"""Audit all frozen source-model rows, retaining unavailable candidates as failures."""

import argparse
import hashlib
import json
import math
from pathlib import Path

PROTOCOL_SHA256 = "1df6532ce9914a4f67380bf90896c94f4c221e445bd60db21994055b9ca92497"
REFERENCE_SHA256 = "2679711e81a769c22dfeee8a75d327d543f0d9aa7eaad1b876d4895fe04096b1"


def audit(protocol_path, reference_path):
    from fatebridge.core.astro import position_motion, runtime
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
    from fatebridge.utils.errors import EphemerisSourceError

    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert hashlib.sha256(reference_path.read_bytes()).hexdigest() == REFERENCE_SHA256
    protocol = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    assert reference["protocol_sha256"] == PROTOCOL_SHA256
    assert reference["candidate_imports"] is False
    assert reference["independent_ephemeris"] is False
    assert reference["independent_model_reduction"] is True
    wanted = {
        (c["body"], c["julian_day_tt"], f)
        for c in protocol["cases"]
        for f in protocol["frames"]
    }
    actual = [(r["body"], r["julian_day_tt"], r["frame"]) for r in reference["rows"]]
    assert len(actual) == len(set(actual)) == protocol["expected_rows"]
    assert set(actual) == wanted
    swe = runtime.swe
    trace = PhysicalEphemerisTrace()
    rows = []
    with runtime.preserve_ephemeris_path():
        for row in reference["rows"]:
            estimates = [float(e["rate_degrees_per_day"]) for e in row["estimates"]]
            assert all(math.isfinite(v) for v in estimates)
            assert (
                abs(estimates[0] - estimates[1]) * 3600
                <= protocol["reference_agreement_line_arcsec_per_day"]
            )
            sidereal = row["frame"] == "Sidereal"
            runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
            raw, returned = runtime.ephemeris_call(
                "calc",
                row["julian_day_tt"],
                getattr(swe, row["body"].upper()),
                swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if sidereal else 0),
            )
            model = runtime.ephemeris_model_from_retflag(returned)
            assert (
                model == "swieph"
            ), "Matched-model source reference requires Swiss files"
            trace.observe(row["body"], model)
            result = {k: row[k] for k in ["body", "julian_day_tt", "frame"]}
            result["source_model_rate_degrees_per_day"] = estimates[-1]
            try:
                candidate, policy = position_motion.complete_position_rate(
                    row["body"],
                    row["julian_day_tt"],
                    raw,
                    model,
                    sidereal=sidereal,
                    source_trace=trace,
                )
                assert candidate is not None
                difference = abs(candidate - estimates[-1]) * 3600
                result.update(
                    status="applied",
                    candidate_rate_degrees_per_day=candidate,
                    error_arcsec_per_day=difference,
                    passed=difference <= protocol["candidate_line_arcsec_per_day"],
                    policy={k: v for k, v in policy.items() if k != "source_contexts"},
                )
            except EphemerisSourceError as exc:
                result.update(status="unavailable", reason=exc.reason, passed=False)
                if exc.reason != "position_motion_not_converged":
                    raise
            rows.append(result)
        physical = trace.finish()
    compared = [r for r in rows if r["status"] == "applied"]
    root = Path(__file__).resolve().parents[1]
    return {
        "status": (
            "passed"
            if len(compared) == protocol["expected_rows"]
            and all(r["passed"] for r in rows)
            else "failed"
        ),
        "protocol_sha256": PROTOCOL_SHA256,
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "cases_expected": protocol["expected_rows"],
        "cases_compared": len(compared),
        "cases_passed": sum(r["passed"] for r in rows),
        "cases_unavailable": len(rows) - len(compared),
        "maximum_error_arcsec_per_day": max(
            (r["error_arcsec_per_day"] for r in compared), default=None
        ),
        "candidate_line_arcsec_per_day": protocol["candidate_line_arcsec_per_day"],
        "physical_sources": physical,
        "rows": rows,
        "candidate_source_sha256": hashlib.sha256(
            (root / "src/fatebridge/core/astro/position_motion.py").read_bytes()
        ).hexdigest(),
        "scope": "Independent 70-digit source-model reduction of shared double physical/frame inputs. Post-discovery development set; not blind, independent ephemeris, full astronomy or original-method acceptance. Per-row source contexts summarized by global physical-source receipt.",
        "all_four_full_marks_established": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["protocol", "reference", "output"]:
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.protocol, args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                in [
                    "status",
                    "cases_expected",
                    "cases_compared",
                    "cases_passed",
                    "cases_unavailable",
                    "maximum_error_arcsec_per_day",
                ]
            }
        )
    )
    raise SystemExit(0 if result["status"] == "passed" else 1)
