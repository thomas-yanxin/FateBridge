"""Compare physical positions and lunar-event roots to the frozen JPL corpus."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.time_scales import ut1_from_tt
from fatebridge.core.horary_motion import native_lunar_contacts

ROOT = Path(__file__).resolve().parents[2]


def audit():
    protocol_path = ROOT / "tests/fixtures/western-horary-motion-protocol.json"
    reference_path = ROOT / "tests/fixtures/western-horary-horizons.json"
    protocol = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    assert (
        hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        == reference["protocol_sha256"]
    )
    assert len(reference["cases"]) == len(protocol["reference_cases_tt"]) == 3
    trace = PhysicalEphemerisTrace()
    cases = []
    coordinate_count = 0
    for case in reference["cases"]:
        max_lon = max_lat = 0.0
        for planet, samples in case["samples"].items():
            for tt, longitude, latitude in samples:
                native = _swisseph_planet_state(
                    planet, ut1_from_tt(tt), julian_day_tt=tt, source_trace=trace
                )
                if native is None:
                    raise RuntimeError("Native comparison unavailable")
                state, _ = native
                lon_error = (
                    abs((state["longitude"] - longitude + 180) % 360 - 180) * 3600
                )
                lat_error = abs(state["latitude"] - latitude) * 3600
                max_lon, max_lat = max(max_lon, lon_error), max(max_lat, lat_error)
                coordinate_count += 1
        result = native_lunar_contacts(
            SimpleNamespace(
                julian_day_tt=case["start_julian_day_tt"], zodiac_type="Tropic"
            )
        )
        expected = case["expected"]
        if result["status"] != "computed":
            raise RuntimeError(result)
        actual_keys = [(r["other"], r["ray_degrees"]) for r in result["contacts"]]
        expected_keys = [(r["other"], r["ray_degrees"]) for r in expected["contacts"]]
        identity = (
            actual_keys == expected_keys
            and result["void_of_course"] == expected["void_of_course"]
        )
        errors = [
            abs(a["julian_day_tt"] - b["julian_day_tt"]) * 86400
            for a, b in zip(result["contacts"], expected["contacts"])
        ]
        exit_error = (
            abs(result["sign_exit_julian_day_tt"] - expected["sign_exit_julian_day_tt"])
            * 86400
        )
        passed = (
            identity
            and max(max_lon, max_lat) <= protocol["comparison_tolerance_arcseconds"]
            and max([exit_error, *errors])
            <= protocol["comparison_tolerance_event_seconds"]
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "start_tt": case["start_tt_calendar"],
                "maximum_longitude_residual_arcseconds": max_lon,
                "maximum_latitude_residual_arcseconds": max_lat,
                "sign_exit_time_residual_seconds": exit_error,
                "contact_time_residuals_seconds": errors,
                "ordered_contact_membership_matches": identity,
                "actual": result,
                "expected": expected,
                "passed": passed,
            }
        )
    sources = trace.finish()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": reference["protocol_sha256"],
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "coordinate_pairs": coordinate_count,
        "comparison_tolerance_arcseconds": protocol["comparison_tolerance_arcseconds"],
        "comparison_tolerance_event_seconds": protocol[
            "comparison_tolerance_event_seconds"
        ],
        "native_sources": sources,
        "cases": cases,
        "passed": all(r["passed"] for r in cases),
        "scope": "Three predeclared TT windows, seven geocentric bodies on a ten-minute JPL grid; independent sampled interpolation vs native bisection. No full Lilly judgement, actual-model behaviour or event outcome certification.",
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        "JPL coordinate pairs",
        result["coordinate_pairs"],
        "windows",
        len(result["cases"]),
        "passed",
        result["passed"],
    )
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
