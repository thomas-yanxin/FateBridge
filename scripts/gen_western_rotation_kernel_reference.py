"""Freeze an independent ERFA numerical oracle for the IERS expression kernel.

TT/UT1 pairs are synthetic common inputs, not observed Earth orientation or
UTC conversion evidence. This generator never imports FateBridge or Swiss.
"""

import argparse
import importlib.metadata
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import erfa


def generate():
    if importlib.metadata.version("pyerfa") != "2.0.1.5":
        raise RuntimeError("Pinned pyerfa 2.0.1.5 required")
    rows = []
    for centuries in [-2, -1.75, -1.5, -1, -0.5, 0, 0.25, 0.5, 1, 1.5, 1.75, 2]:
        tt = 2451545.0 + centuries * 36525
        ut = tt - 78.9 / 86400
        dp, de = erfa.nut06a(2451545.0, tt - 2451545.0)
        rows.append(
            {
                "jd_tt": tt,
                "jd_ut1": ut,
                "nutation_longitude_degrees": math.degrees(dp),
                "mean_obliquity_degrees": math.degrees(
                    erfa.obl06(2451545.0, tt - 2451545.0)
                ),
                "gast_degrees": math.degrees(
                    erfa.gst06a(2451545.0, ut - 2451545.0, 2451545.0, tt - 2451545.0)
                )
                % 360,
                "arguments_radians": [
                    float(f(centuries))
                    for f in [
                        erfa.fal03,
                        erfa.falp03,
                        erfa.faf03,
                        erfa.fad03,
                        erfa.faom03,
                        erfa.fave03,
                        erfa.fae03,
                        erfa.fapa03,
                    ]
                ],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "independent_standard_expression_kernel_not_observational_astronomy",
        "pyerfa_version": importlib.metadata.version("pyerfa"),
        "erfa_version": erfa.version.erfa_version,
        "sofa_version": erfa.version.sofa_version,
        "gast_tolerance_arcseconds": 0.001,
        "scope": "Common TT/UT1 and nutation/mean-obliquity inputs; polynomial/ERA/complementary-series implementation check only",
        "cases": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(generate(), indent=2, allow_nan=False) + "\n")
