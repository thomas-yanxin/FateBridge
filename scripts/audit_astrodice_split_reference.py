"""Independently replay frozen split-TDB records with scalar arithmetic.

No ERFA, CALCEPH, Swiss or FateBridge import is needed for this verifier.
The ERFA physical formulas are evaluated from the saved source states with
an independent scalar path; light-time recurrence and all stencils replay.
Passing this check does not turn this TDB study into a TT reference.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime
from fractions import Fraction
from pathlib import Path

PROTOCOL_SHA256 = "18326d8e5f5e9b56e2b877863a744dbb14205b7bb31c6aa7cac6c38ddcfa93c4"
GENERATOR_SHA256 = "7a9b8956dd8bf2b4eb891bcd7bf0277800d571e3d46470a7039713e80b5e7934"
REFERENCE_SHA256 = "67263619df8893717d5940d0e9b0d1a21acbca17ed3d08c68535be9e070c267f"
C_AU_DAY = 299792458.0 * 86400.0 / 149597870700.0
SRS = 1.97412574336e-8


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def normalize(v):
    norm = math.sqrt(dot(v, v))
    return [x / norm for x in v]


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def exact_split(epoch, delta):
    # Reproduce the collector's correctly rounded small-part sum using exact
    # rationals, then normalize its carry. Never add the full Julian date.
    small = float(Fraction(epoch[1]) + Fraction(delta))
    carry = math.floor(small)
    return [epoch[0] + carry, float(Fraction(small) - carry)]


def proper_direction(natural, beta, solar_distance):
    scalar = dot(natural, beta)
    reciprocal_gamma = math.sqrt(1 - dot(beta, beta))
    k = 1 + scalar / (1 + reciprocal_gamma)
    potential = SRS / solar_distance
    return normalize(
        [
            reciprocal_gamma * p + k * v + potential * (v - scalar * p)
            for p, v in zip(natural, beta)
        ]
    )


def verify_sample(sample, epoch, protocol):
    if [sample["jd0_tdb"], sample["fraction_tdb"]] != epoch:
        raise ValueError("Split observation epoch changed")
    for name in ["earth_barycentric_pv", "moon_geometric_pv", "sun_barycentric_pv"]:
        if len(sample[name]) != 6 or not all(math.isfinite(v) for v in sample[name]):
            raise ValueError("Malformed physical source state")
    for name in ["selected_direction", "without_finite_solar_deflection"]:
        if len(sample[name]) != 3 or not all(math.isfinite(v) for v in sample[name]):
            raise ValueError("Malformed independent direction")
    earth = sample["earth_barycentric_pv"]
    delay = (
        math.sqrt(dot(sample["moon_geometric_pv"][:3], sample["moon_geometric_pv"][:3]))
        / C_AU_DAY
    )
    history = sample["reception_iterations"]
    if not 1 <= len(history) <= protocol["maximum_light_time_iterations"]:
        raise ValueError("Reception iteration count changed")
    for index, iteration in enumerate(history):
        if abs(iteration["delay_days"] - delay) > 1e-18:
            raise ValueError("Reception delay recurrence changed")
        emission = exact_split(epoch, -iteration["delay_days"])
        if [
            iteration["emission_jd0_tdb"],
            iteration["emission_fraction_tdb"],
        ] != emission:
            raise ValueError("Split emission epoch changed")
        moon = iteration["moon_barycentric_pv"]
        if len(moon) != 6 or not all(math.isfinite(v) for v in moon):
            raise ValueError("Malformed retarded source state")
        ray = [m - e for m, e in zip(moon[:3], earth[:3])]
        next_delay = math.sqrt(dot(ray, ray)) / C_AU_DAY
        if abs(iteration["next_delay_days"] - next_delay) > 1e-18:
            raise ValueError("Reception path length changed")
        if (
            index < len(history) - 1
            and abs(next_delay - delay) <= protocol["light_time_convergence_days"]
        ):
            raise ValueError("Reception continued after declared convergence")
        if (
            index == len(history) - 1
            and abs(next_delay - delay) > protocol["light_time_convergence_days"]
        ):
            raise ValueError("Unconverged reception state")
        delay = next_delay
    natural = normalize(ray)
    sun = sample["sun_barycentric_pv"]
    observer_from_sun = [a - b for a, b in zip(earth[:3], sun[:3])]
    target_from_sun = [a - b for a, b in zip(moon[:3], sun[:3])]
    solar_distance = math.sqrt(dot(observer_from_sun, observer_from_sun))
    e, q = normalize(observer_from_sun), normalize(target_from_sun)
    coefficient = (
        SRS
        / solar_distance
        / max(
            dot(q, [a + b for a, b in zip(q, e)]), protocol["solar_deflection_limiter"]
        )
    )
    bend = cross(natural, cross(e, q))
    deflected = normalize([a + coefficient * b for a, b in zip(natural, bend)])
    beta = [v / C_AU_DAY for v in earth[3:]]
    expected = proper_direction(deflected, beta, solar_distance)
    without = proper_direction(natural, beta, solar_distance)
    residual = max(abs(a - b) for a, b in zip(expected, sample["selected_direction"]))
    if (
        len(sample["selected_direction"]) != 3
        or residual > 2e-14
        or max(
            abs(a - b)
            for a, b in zip(without, sample["without_finite_solar_deflection"])
        )
        > 2e-14
    ):
        raise ValueError("Independent scalar direction replay failed")
    return residual


def validate(protocol, reference):
    if protocol["time_scale"] != "TDB" or protocol["tt_tdb_conversion_applied"]:
        raise ValueError("A split-TDB study cannot be relabeled as TT")
    if (
        reference["protocol_sha256"] != PROTOCOL_SHA256
        or reference["generator_sha256"] != GENERATOR_SHA256
    ):
        raise ValueError("Frozen split-reference identity changed")
    if (
        reference["time_scale"] != "TDB"
        or reference["tt_tdb_conversion_applied"]
        or reference["candidate_imported"]
        or reference["candidate_compared"]
    ):
        raise ValueError("Reference time contract or separation changed")
    for field in ["kernel_sha256", "reader_library_sha256"]:
        if reference[field + "_before_and_after"] != protocol[field]:
            raise ValueError("Physical source identity changed")
    if reference["dependency_versions"] != protocol["dependency_versions"]:
        raise ValueError("Numerical dependency identity changed")
    if [
        {k: r[k] for k in ["date_tdb", "cohort"]} for r in reference["rows"]
    ] != protocol["centers"]:
        raise ValueError("Frozen split cohort changed")
    exact_weights = {
        k: (
            Fraction((-1) ** (k + 1), k)
            * Fraction(math.comb(12, 6 - k), math.comb(12, 6))
        )
        for k in range(1, 7)
    }
    for degree in range(13):
        moment = sum(w * (k**degree - (-k) ** degree) for k, w in exact_weights.items())
        if moment != int(degree == 1):
            raise ValueError("Reference stencil polynomial identity failed")
    weights = {k: float(w) for k, w in exact_weights.items()}
    count, maximum, outside = 0, 0.0, 0
    failures = []
    for row in reference["rows"]:
        date = datetime.fromisoformat(row["date_tdb"])
        whole = date.toordinal() + 1721424
        small = 0.5 + (date.hour * 3600 + date.minute * 60 + date.second) / 86400
        epoch = exact_split([whole, small], 0)
        if epoch != [row["jd0_tdb"], row["fraction_tdb"]]:
            raise ValueError("Gregorian split calendar changed")
        wanted = {
            str(d)
            for d in sorted(
                {0, *(k * h for h in protocol["steps_days"] for k in range(-6, 7) if k)}
            )
        }
        if set(row["samples"]) != wanted:
            raise ValueError("Split sample coverage changed")
        for offset, sample in row["samples"].items():
            at = exact_split(epoch, float(offset))
            maximum = max(maximum, verify_sample(sample, at, protocol))
            position = Fraction(at[0]) + Fraction(at[1])
            if (
                not reference["coverage"]["start_jd_tdb"]
                <= position
                <= reference["coverage"]["end_jd_tdb"]
            ):
                raise ValueError("Probe outside the frozen source")
            outside += position < Fraction(3442851, 2) or position >= Fraction(
                10746969, 2
            )
            count += 1
        rates = {
            str(h): [
                math.fsum(
                    weights[k]
                    * (
                        row["samples"][str(k * h)]["selected_direction"][axis]
                        - row["samples"][str(-k * h)]["selected_direction"][axis]
                    )
                    for k in range(1, 7)
                )
                / h
                for axis in range(3)
            ]
            for h in protocol["steps_days"]
        }
        difference = math.degrees(math.dist(*rates.values())) * 3600
        if (
            rates != row["derivatives_per_tdb_day"]
            or row["selected_direction_derivative_per_tdb_day"]
            != rates[str(protocol["chosen_step_days"])]
            or abs(difference - row["step_difference_arcsec_per_day"]) > 1e-12
        ):
            raise ValueError("Frozen derivative replay changed")
        if difference > 0.002:
            failures.append(row["date_tdb"])
    return {
        "centers": len(reference["rows"]),
        "fresh_holdout_centers": sum(
            c["cohort"] == "holdout" for c in protocol["centers"]
        ),
        "samples": count,
        "max_scalar_direction_replay_difference": maximum,
        "probes_outside_AD1_through_AD9999": outside,
        "template_failures": failures,
        "maximum_template_step_difference_arcsec_per_day": max(
            r["step_difference_arcsec_per_day"] for r in reference["rows"]
        ),
        "fixed_reference_line_arcsec_per_day": 0.002,
        "tt_calendar_acceptance": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["protocol", "reference", "output"]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if digest(args.protocol) != PROTOCOL_SHA256:
        raise ValueError("Split protocol bytes changed")
    if digest(args.reference) != REFERENCE_SHA256:
        raise ValueError("Split reference bytes changed")
    validation = validate(
        json.loads(args.protocol.read_text()), json.loads(args.reference.read_text())
    )
    result = {
        "status": (
            "reference_quality_unresolved"
            if validation["template_failures"]
            else "declared_TDB_reference_quality_lines_satisfied"
        ),
        "validation": validation,
        "exit_code": 2 if validation["template_failures"] else 0,
        "inputs": {
            "protocol_sha256": digest(args.protocol),
            "reference_sha256": digest(args.reference),
        },
        "scope": "Independent scalar replay of a declared split-TDB model. No TT acceptance,old failure promotion,observation validation,or authority certification.",
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(result["exit_code"])
