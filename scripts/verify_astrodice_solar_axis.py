"""Independent 288-bit reduced-form replay of the solar-axis counterexample.

No producer geometry, interval class or atan implementation is imported.
Analytic holdouts test a source-formula identity, not astronomical accuracy.
"""

import argparse
import hashlib
import json
import re
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_observer_clock import (
    add,
    cover,
    divide,
    independent_pi,
    mul,
    root,
    rounded,
    square,
)

PLAN_SHA = "07c7990ebec093e7c98f26a412c6949b3c56818575134d28cee56e7cec284bcc"


def atan8(x):
    if max(map(abs, x)) > Q(1, 1000):
        raise ValueError("Independent atan domain exceeded")
    result, power = rounded(0), x
    for n in range(8):
        result = add(result, mul(power, rounded(Q((-1) ** n, 2 * n + 1))))
        power = mul(power, square(x))
    error = max(map(abs, x)) ** 17 / 17
    return add(result, rounded(-error, error))


def verify(directory, candidate):
    raw = (directory / "plan-before-analysis.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA:
        raise ValueError("Independent pre-analysis plan binding failed")
    plan = json.loads(raw)
    header = (directory / "authority/sweph.h").read_bytes()
    if (
        hashlib.sha256(header).hexdigest()
        != "8e44b9c00d23a0b583581f17fc6798ea376649d2517abbb556ee1b1aff6a138a"
    ):
        raise ValueError("Independent source header identity failed")
    for path, key in [
        ("sweph.c", "source_c_sha256"),
        ("native-solar-mass-v1.json", "source_profile_sha256"),
    ]:
        if (
            hashlib.sha256((directory / "authority" / path).read_bytes()).hexdigest()
            != plan[key]
        ):
            raise ValueError("Independent source identity failed")
    text = (directory / "authority/sweph.c").read_text()
    table = text[text.index("static const struct meff_ele eff_arr[]") :]
    table = table[: table.index("};")]
    native = [
        [Q(v) for v in row.split(",")]
        for row in re.findall(r"\{([\d.]+,\s*[\d.]+)\}", table)
    ]
    saved = json.loads((directory / "authority/native-solar-mass-v1.json").read_text())[
        "radius_mass_pairs"
    ]
    if (
        len(native) != 101
        or native != [list(map(Q, x)) for x in saved]
        or native[-1] != [0, 0]
    ):
        raise ValueError("Independent literal mass-table proof failed")
    r1, m1 = native[-2]
    left, right = m1 / r1, (native[-3][1] - m1) / (native[-3][0] - r1)
    if left != Q("0.2767") or right != Q("0.6878") or left == right:
        raise ValueError("Independent nonmatching knot slopes not proved")
    c = plan["constants"]
    # The pinned header has an inactive historical GM in #if 0. Bind the
    # active definition after that block, not the first occurrence.
    active_gm = re.search(
        rb"#if 0\s*#define HELGRAVCONST[^\n]*\n#endif\s*#define HELGRAVCONST\s+([\d.e+]+)",
        header,
    )
    au = re.search(rb"(?m)^#define AUNIT\s+([\d.e+]+)", header)
    light = re.search(rb"(?m)^#define CLIGHT\s+([\d.e+]+)", header)
    rad = re.search(rb"#define SUN_RADIUS\s+\(([\d.]+) / 3600 \* DEGTORAD\)", header)
    if not all((active_gm, au, light, rad)) or [
        Q(x[1].decode()) for x in (active_gm, light, au, rad)
    ] != [Q(c[k]) for k in ("GM", "c", "AU", "solar_radius_arcsec")]:
        raise ValueError("Independent active-header constants do not match")
    srs = 2 * Q(c["GM"]) / Q(c["c"]) ** 2 / Q(c["AU"])
    pi = rounded(*independent_pi())
    radius = mul(rounded(Q(c["solar_radius_arcsec"]) / 648000), pi)
    factor = divide(rounded(648000), pi)
    amplitude = divide(rounded(srs * left), radius)
    limit = mul(atan8(amplitude), factor)
    result = json.loads(candidate.read_text())
    if result["plan_sha256"] != PLAN_SHA or result["model"] != plan["model"]:
        raise ValueError("Candidate model/plan was substituted")
    cover(limit, result["positive_axis_limit_magnitude_arcsec"])
    cover(mul(rounded(2), limit), result["two_sided_jump_magnitude_arcsec"])
    if limit[0] <= 0:
        raise ValueError("Distinct signed one-sided limits not proved")
    tmax = Q(plan["maximum_abs_t"])
    if tmax / radius[0] >= r1:
        raise ValueError("Universal first-cell containment not proved")
    bound = mul(mul(amplitude, rounded(tmax * tmax / 2)), factor)
    if bound[1] > Q(result["uniform_approach_error_upper_arcsec"]):
        raise ValueError("Universal Lipschitz remainder is not covered")
    if result["first_knot_left_mass_slope"] != str(left) or result[
        "first_knot_right_mass_slope"
    ] != str(right):
        raise ValueError("Knot evidence changed")
    for key in ["old_position_line_arcsec", "old_rate_reference_line_arcsec_per_day"]:
        if result[key] != plan[key]:
            raise ValueError("Old error line changed")
    if (
        result["new_astronomical_observations"] != 0
        or result["new_production_accuracy_holdouts"] != 0
        or result["production_coordinates_changed"] is not False
    ):
        raise ValueError("Analytic probe was promoted to production evidence")
    split = result["split"]
    if split not in {"development", "heldout"}:
        raise ValueError("Unknown split")
    exps = plan[
        "development_exponents" if split == "development" else "heldout_exponents"
    ]
    expected = [
        (Q(sign, 2**e), name)
        for e in exps
        for sign in plan["all_signs"]
        for name in plan["profiles"]
    ]
    actual = [(Q(x["t"]), x["profile"]) for x in result["samples"]]
    if actual != expected:
        raise ValueError("Frozen samples omitted, duplicated or replaced")
    for row, (t, profile) in zip(result["samples"], expected):
        # Exact reduction: cross(u,v)=-g1/t and dot(u,v)=1.
        # M=a*abs(t)/(R*sqrt(1+t*t)) in the native first cell.
        if profile == "native_linear_first_cell":
            x = divide(amplitude, root(rounded(1 + t * t)))
            x = mul(x, rounded(-1 if t > 0 else 1))
        elif profile == "quadratic_analytic_control_only":
            b = divide(rounded(srs * m1 / (r1 * r1)), square(radius))
            x = mul(b, rounded(-t / (1 + t * t)))
        else:
            raise ValueError("Independent profile is not frozen")
        computed = mul(atan8(x), factor)
        cover(computed, row["signed_deflection_arcsec"])
    return {
        "status": "independently_verified_declared_real_source_model",
        "samples": len(expected),
        "split": split,
        "jump_arcsec_approx": float(sum(limit)),
        "universal_error_upper_arcsec_approx": float(bound[1]),
        "new_astronomical_observations": 0,
        "new_production_accuracy_holdouts": 0,
        "old_gates_regraded": False,
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = verify(a.directory, a.candidate)
    with a.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
