"""Compare the candidate with a sealed independent mathematical reduction.

The physical ephemeris and frame inputs are shared. This is source-model
numerical validation, separate from independent JPL astronomical validation.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

PROTOCOL_SHA256 = "e090a6be08a5bad2ff2c9d767f1c72b39de6f586e0dca3059a82768ceb94e393"
REFERENCE_SHA256 = "096a8ee3f7235f59bdff6163c76fca83190ac0f385052cb56cf67171e33fc16b"


def validate_reference(protocol_path, reference_path):
    if hashlib.sha256(protocol_path.read_bytes()).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("Source-model protocol changed")
    if hashlib.sha256(reference_path.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Independent reduction bytes changed")
    protocol = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    if (
        reference["candidate_imports"]
        or reference["independent_ephemeris"]
        or not reference["independent_model_reduction"]
        or reference["precision_decimal_digits"] != 70
        or reference["protocol_sha256"] != PROTOCOL_SHA256
    ):
        raise ValueError("Reference independence or precision classification changed")
    wanted = {
        (c["body"], c["julian_day_tt"], f)
        for c in protocol["cases"]
        for f in protocol["frames"]
    }
    actual = [(r["body"], r["julian_day_tt"], r["frame"]) for r in reference["rows"]]
    if len(set(actual)) != len(actual) or set(actual) != wanted:
        raise ValueError("Source-model reference coverage changed")
    for row in reference["rows"]:
        a, b = [float(e["rate_degrees_per_day"]) for e in row["estimates"]]
        disagreement = abs(a - b) * 3600
        if (
            not all(math.isfinite(x) for x in (a, b, disagreement))
            or disagreement > protocol["reference_agreement_line_arcsec_per_day"]
        ):
            raise ValueError("Reference interpolation models do not agree")
    return protocol, reference


def audit(protocol_path, reference_path):
    from fatebridge.core.astro import position_motion, runtime
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace

    protocol, reference = validate_reference(protocol_path, reference_path)
    swe = runtime.swe
    trace = PhysicalEphemerisTrace()
    rows = []
    with runtime.preserve_ephemeris_path():
        for row in reference["rows"]:
            sidereal = row["frame"] == "Sidereal"
            runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
            flags = (
                swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if sidereal else 0)
            )
            raw, returned = runtime.ephemeris_call(
                "calc", row["julian_day_tt"], getattr(swe, row["body"].upper()), flags
            )
            model = runtime.ephemeris_model_from_retflag(returned)
            if model != "swieph":
                raise ValueError(
                    "Source-model reference requires the same Swiss backend"
                )
            trace.observe(row["body"], model)
            candidate, policy = position_motion.complete_position_rate(
                row["body"],
                row["julian_day_tt"],
                raw,
                model,
                sidereal=sidereal,
                source_trace=trace,
            )
            expected = float(row["estimates"][-1]["rate_degrees_per_day"])
            difference = abs(candidate - expected) * 3600
            rows.append(
                {
                    "body": row["body"],
                    "julian_day_tt": row["julian_day_tt"],
                    "frame": row["frame"],
                    "source_model_rate_degrees_per_day": expected,
                    "candidate_rate_degrees_per_day": candidate,
                    "error_arcsec_per_day": difference,
                    "passed": difference <= protocol["candidate_line_arcsec_per_day"],
                    "policy": policy,
                }
            )
        source = trace.finish()
    observed = {r["sha256"] for r in source["files"]}
    if not {r["sha256"] for r in reference["physical_files"]} <= observed:
        raise ValueError("Candidate and reference physical file cohorts differ")
    root = Path(__file__).resolve().parents[1]
    files = [
        "src/fatebridge/core/astro/position_motion.py",
        "src/fatebridge/core/astro/retarded_epoch.py",
    ]
    return {
        "status": (
            "passed" if all(r["passed"] for r in rows) else "candidate_line_failed"
        ),
        "protocol_sha256": PROTOCOL_SHA256,
        "reference_sha256": REFERENCE_SHA256,
        "cases_compared": len(rows),
        "cases_passed": sum(r["passed"] for r in rows),
        "stabilized_cases": sum(
            bool(r["policy"]["sampling_stabilization"]) for r in rows
        ),
        "maximum_error_arcsec_per_day": max(r["error_arcsec_per_day"] for r in rows),
        "candidate_line_arcsec_per_day": protocol["candidate_line_arcsec_per_day"],
        "candidate_source_sha256": {
            f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files
        },
        "physical_sources": source,
        "scope": "Post-discovery development cases. Independent high-precision reduction of shared native geometric/frame inputs; not an independent ephemeris, unseen holdout, or universal precision certificate.",
        "rows": rows,
        "all_three_full_marks_established": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    for key in ("protocol", "reference", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.protocol, args.reference)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "cases_compared",
                    "cases_passed",
                    "stabilized_cases",
                    "maximum_error_arcsec_per_day",
                )
            }
        )
    )
    raise SystemExit(0 if result["status"] == "passed" else 1)
