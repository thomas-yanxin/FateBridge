"""Retain a cross-file lunar request-order counterexample; exit1 on failure.

Cold and physically primed native calls use identical flags/epoch/backend.
This is a diagnostic, NOT permission to choose whichever agrees with a reference.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path


def angle_arcsec(a, b):
    x = [v / math.hypot(*a) for v in a]
    y = [v / math.hypot(*b) for v in b]
    cross = [
        x[1] * y[2] - x[2] * y[1],
        x[2] * y[0] - x[0] * y[2],
        x[0] * y[1] - x[1] * y[0],
    ]
    return (
        math.degrees(
            math.atan2(math.hypot(*cross), math.fsum(p * q for p, q in zip(x, y)))
        )
        * 3600
    )


def diagnose(reference):
    from fatebridge.core.astro import runtime
    from fatebridge.core.astro.lunar_motion import LIGHT_SPEED_AU_PER_DAY as C
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace

    frozen = json.loads(reference.read_text())
    row = next(r for r in frozen["rows"] if r["date_tt"] == "9600-01-01T00:00:00")
    swe = runtime.swe
    t = row["jd_tt"]
    trace = PhysicalEphemerisTrace()
    rows = []
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_SPEED
        | swe.FLG_ICRS
        | swe.FLG_J2000
        | swe.FLG_EQUATORIAL
        | swe.FLG_XYZ
    )
    for primed in [False, True]:
        runtime.ephemeris_call("close")
        if primed:
            geo, r = runtime.ephemeris_call(
                "calc", t, swe.MOON, flags | swe.FLG_TRUEPOS
            )
            tau = math.hypot(*geo[:3]) / C
            runtime.ephemeris_call(
                "calc", t - tau, swe.MOON, flags | swe.FLG_TRUEPOS | swe.FLG_BARYCTR
            )
        position, returned = runtime.ephemeris_call("calc", t, swe.MOON, flags)
        model = runtime.ephemeris_model_from_retflag(returned)
        trace.observe("physically_primed" if primed else "cold", model)
        rows.append(
            {
                "primed_with_retarded_barycentric_state": primed,
                "state": position,
                "returned_flags": returned,
                "model": model,
                "position_error_arcsec": angle_arcsec(
                    position[:3], row["icrf_unit_direction"]
                ),
            }
        )
    difference = angle_arcsec(rows[0]["state"][:3], rows[1]["state"][:3])
    failed = difference > 0.02 or any(r["position_error_arcsec"] > 0.02 for r in rows)
    return {
        "status": (
            "numeric_acceptance_failed"
            if failed
            else "limited_diagnostic_lines_satisfied"
        ),
        "exit_code": 1 if failed else 0,
        "date_tt": row["date_tt"],
        "epoch_jd_tt": t,
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "fixed_position_line_arcsec": 0.02,
        "request_order_position_difference_arcsec": difference,
        "cases": rows,
        "physical_sources": trace.finish(),
        "scope": "Post-discovery counterexample. Priming is not shipped as a fix. Source identities are contexts, not a complete native read-set proof. Both outcomes and the failed position remain recorded.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = diagnose(a.reference)
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ["cases", "physical_sources"]},
            indent=2,
        )
    )
    raise SystemExit(result["exit_code"])
