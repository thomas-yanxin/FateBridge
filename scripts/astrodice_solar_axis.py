"""Outward source-formula counterexample; no production coordinates are used.

Literal-decimal constants and mathematical pi define a real-arithmetic model,
not an oracle for the compiled binary64 implementation or observed positions.
The quadratic profile is an analytic control only, never a proposed repair.
"""

import argparse
import hashlib
import json
import re
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import I
from scripts.astrodice_source_slope_bounds import pi_bounds

PLAN_SHA = "07c7990ebec093e7c98f26a412c6949b3c56818575134d28cee56e7cec284bcc"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def box(value):
    return list(map(str, value.bounds()))


def atan(value, terms=6):
    if value.absolute_upper() > Q(1, 1000):
        raise ValueError("Outside the frozen small-argument proof")
    total, power, square = I(), value, value.square()
    for k in range(terms):
        total += power * Q((-1) ** k, 2 * k + 1)
        power *= square
    tail = value.absolute_upper() ** (2 * terms + 1) / (2 * terms + 1)
    return total + I(-tail, tail)


def premise(directory):
    plan_path = directory / "plan-before-analysis.json"
    if digest(plan_path) != PLAN_SHA:
        raise ValueError("Frozen pre-analysis plan changed")
    plan = json.loads(plan_path.read_text())
    source = directory / "authority/sweph.c"
    profile_path = directory / "authority/native-solar-mass-v1.json"
    if (
        digest(source) != plan["source_c_sha256"]
        or digest(profile_path) != plan["source_profile_sha256"]
    ):
        raise ValueError("Frozen primary source changed")
    header = directory / "authority/sweph.h"
    if (
        digest(header)
        != "8e44b9c00d23a0b583581f17fc6798ea376649d2517abbb556ee1b1aff6a138a"
    ):
        raise ValueError("Frozen source constants header changed")
    text = source.read_text()
    table = text.split("static const struct meff_ele eff_arr[]", 1)[1].split("};", 1)[0]
    pairs = [
        (Q(r), Q(m)) for r, m in re.findall(r"\{\s*([.\d]+)\s*,\s*([.\d]+)\s*\}", table)
    ]
    saved = [
        tuple(map(Q, row))
        for row in json.loads(profile_path.read_text())["radius_mass_pairs"]
    ]
    if len(pairs) != 101 or pairs != saved:
        raise ValueError("Native mass table transcription differs")
    if "m = eff_arr[i-1].m + f * (eff_arr[i].m - eff_arr[i-1].m);" not in text:
        raise ValueError("Linear mass interpolation premise absent")
    c = plan["constants"]
    if c != {
        "GM": "1.32712440017987e20",
        "c": "2.99792458e8",
        "AU": "1.49597870700e11",
        "solar_radius_arcsec": "959.63",
    }:
        raise ValueError(
            "Declared source constants differ from the pinned active header"
        )
    srs = Q(2) * Q(c["GM"]) / Q(c["c"]) ** 2 / Q(c["AU"])
    radius = I(c["solar_radius_arcsec"]) * I(*pi_bounds()) / 648000
    return plan, pairs, srs, radius


def direct(t, profile, pairs, srs, radius):
    """Native vector expression, retaining its cancellation-prone 1+q.e."""
    t = I(t)
    one_plus = 1 + t.square()
    q = [(t.square() - 1) / one_plus, 2 * t / one_plus]
    raw = [q[0] - 1, q[1]]
    length = (raw[0].square() + raw[1].square()).sqrt()
    u = [x / length for x in raw]
    impact = (1 - u[0].square()).sqrt() / radius
    r1, m1 = pairs[-2]
    if not 0 < impact.bounds()[0] <= impact.bounds()[1] < r1:
        raise ValueError("Frozen geometry is outside the first mass cell")
    mass = impact * m1 / r1
    if profile == "quadratic_analytic_control_only":
        mass *= impact / r1
    elif profile != "native_linear_first_cell":
        raise ValueError("Unplanned profile")
    uq = sum((a * b for a, b in zip(u, q)), I())
    g = srs * mass / (1 + q[0])
    v = [u[0] + g * (uq - u[0] * q[0]), u[1] - g * u[0] * q[1]]
    cross = u[0] * v[1] - u[1] * v[0]
    dot = sum((a * b for a, b in zip(u, v)), I())
    if dot.bounds()[0] <= 0:
        raise ValueError("Signed deflection is not on the declared atan branch")
    return atan(cross / dot) * (648000 / I(*pi_bounds()))


def evaluate(directory, split):
    plan, pairs, srs, radius = premise(directory)
    r1, m1 = pairs[-2]
    a = m1 / r1
    amplitude = srs * a / radius
    limit = atan(amplitude) * (648000 / I(*pi_bounds()))
    tmax = Q(plan["maximum_abs_t"])
    if not tmax / radius.bounds()[0] < r1:
        raise ValueError("Whole punctured interval is not in the first cell")
    bound = amplitude * (tmax * tmax / 2) * (648000 / I(*pi_bounds()))
    result = {
        "schema_version": 1,
        "plan_sha256": PLAN_SHA,
        "split": split,
        "model": plan["model"],
        "positive_axis_limit_magnitude_arcsec": box(limit),
        "two_sided_jump_magnitude_arcsec": box(2 * limit),
        "uniform_approach_error_upper_arcsec": str(bound.bounds()[1]),
        "uniform_domain": "0 < abs(t) <= 1/65536",
        "first_knot_left_mass_slope": str(a),
        "first_knot_right_mass_slope": str((pairs[-3][1] - m1) / (pairs[-3][0] - r1)),
        "samples": [],
        "new_astronomical_observations": 0,
        "new_production_accuracy_holdouts": 0,
        "production_coordinates_changed": False,
        "old_position_line_arcsec": plan["old_position_line_arcsec"],
        "old_rate_reference_line_arcsec_per_day": plan[
            "old_rate_reference_line_arcsec_per_day"
        ],
    }
    key = "development_exponents" if split == "development" else "heldout_exponents"
    for exponent in plan[key]:
        for sign in plan["all_signs"]:
            for profile in plan["profiles"]:
                t = Q(sign, 2**exponent)
                result["samples"].append(
                    {
                        "t": str(t),
                        "profile": profile,
                        "signed_deflection_arcsec": box(
                            direct(t, profile, pairs, srs, radius)
                        ),
                    }
                )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("split", choices=["development", "heldout"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.directory, args.split)
    with args.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": digest(args.output),
                "samples": len(result["samples"]),
            }
        )
    )


if __name__ == "__main__":
    main()
