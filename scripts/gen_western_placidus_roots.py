"""Independent monotone semiarc roots; no FateBridge/Swiss numerical imports.

The input geometry comes from frozen ERFA results. Reading those common
UT1/TT pairs is not independent calendar or observed-EOP verification.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path


def solve_cusps(armc, latitude, obliquity, tolerance, maximum_iterations):
    a = math.tan(math.radians(latitude)) * math.tan(math.radians(obliquity))
    if abs(a) >= 1:
        return {"status": "outside_full_ecliptic_rise_set_domain", "a": a}
    eps = math.radians(obliquity)
    diagnostics = []

    def longitude(alpha):
        alpha = math.radians(alpha)
        return (
            math.degrees(math.atan2(math.sin(alpha), math.cos(eps) * math.cos(alpha)))
            % 360
        )

    def root(q, upper):
        if upper:
            low, high = armc, armc + q * 180
        else:
            low, high = armc + 180 - q * 180, armc + 180

        def residual(alpha):
            h0 = math.degrees(math.acos(-a * math.sin(math.radians(alpha))))
            return (
                alpha - armc - q * h0 if upper else alpha - armc - 180 + q * (180 - h0)
            )

        if residual(low) > 0 or residual(high) < 0:
            raise RuntimeError("The predeclared monotone root bracket failed")
        for iteration in range(maximum_iterations):
            if high - low <= tolerance:
                break
            middle = (low + high) / 2
            if residual(middle) > 0:
                high = middle
            else:
                low = middle
        else:
            raise RuntimeError("The predeclared bisection limit did not converge")
        alpha = (low + high) / 2
        diagnostics.append(
            {
                "q": q,
                "upper": upper,
                "iterations": iteration,
                "bracket_width_degrees": high - low,
                "equation_residual_arcseconds": residual(alpha) * 3600,
            }
        )
        return longitude(alpha)

    asc, h11, h12 = root(1, True), root(1 / 3, True), root(2 / 3, True)
    h2, h3 = root(2 / 3, False), root(1 / 3, False)
    mc = longitude(armc)
    cusps = [
        asc,
        h2,
        h3,
        (mc + 180) % 360,
        (h11 + 180) % 360,
        (h12 + 180) % 360,
        (asc + 180) % 360,
        (h2 + 180) % 360,
        (h3 + 180) % 360,
        mc,
        h11,
        h12,
    ]
    return {"status": "solved", "a": a, "cusps": cusps, "roots": diagnostics}


def generate(reference_path, protocol_path):
    reference = json.loads(reference_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    if (
        hashlib.sha256(reference_path.read_bytes()).hexdigest()
        != protocol["common_geometry_fixture_sha256"]
    ):
        raise ValueError("Common geometry fixture differs from frozen protocol")
    return {
        "protocol": protocol,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": [
            {
                "input": c["input"],
                "armc": c["armc"],
                "true_obliquity": c["true_obliquity"],
                **solve_cusps(
                    c["armc"],
                    c["input"]["latitude"],
                    c["true_obliquity"],
                    protocol["root_bracket_tolerance_degrees"],
                    protocol["maximum_iterations"],
                ),
            }
            for c in reference["cases"]
        ],
        "external_oracle_values_read_for_solving": False,
        "all_three_full_marks_established": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(
            generate(args.reference, args.protocol),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
