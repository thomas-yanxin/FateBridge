"""Independent unscaled angular replay; no producer, solver or candidate imports."""

import argparse
import hashlib
import json
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def verify(fixture):
    plan = read(fixture / "plan-before-any-new-LP.json")
    data = read(fixture / "outer-first-certificates.json")
    hypothesis = plan["hypotheses"]["H1_bounded_epoch_hypothesis"]
    epsilon = F(hypothesis["epoch_uncertainty_days"])
    cap = F(hypothesis["absolute_each_angle_slope_bound_arcsec_per_day"])
    if epsilon != F(1, 10**9) or cap != 3600:
        raise ValueError("Predeclared diagnostic hypothesis changed")
    sources = [
        row
        for entry in plan["cases"]
        for row in read(fixture / entry["dataset"] / entry["file"])["rows"]
    ]
    if len(sources) != 3 or len(data["rows"]) != 3:
        raise ValueError("Incomplete reference experiment")
    records, primal_checks, dual_checks = [], 0, 0
    for source, result in zip(sources, data["rows"]):
        if source["id"] != result["id"] or len(result["fits"]) != 22:
            raise ValueError("Condition or full window/order coverage changed")
        for fit in result["fits"]:
            if fit["status"] != "exact_angular_outer_interval":
                raise ValueError("No exact angular outer interval")
            window, degree = fit["window_seconds"], fit["order"]
            for coordinate, axis in enumerate(fit["axes"]):
                differences, noises = {}, {}
                for t in range(5, window + 1, 5):
                    plus = source["samples"][str(t)]["printed_angles"][coordinate]
                    minus = source["samples"][str(-t)]["printed_angles"][coordinate]
                    difference = F(plus) - F(minus)
                    if coordinate == 0:
                        difference = (difference + 180) % 360 - 180
                    differences[t] = difference * 1800
                    noises[t] = sum(
                        (
                            F(10) ** Decimal(value).as_tuple().exponent * 1800
                            for value in (plus, minus)
                        ),
                        F(),
                    )
                baseline = differences[window]
                unit = max(noises.values())
                for position, certificate in enumerate(axis["certificates"]):
                    sign = 1 if position == 0 else -1
                    if certificate["objective_sign"] != sign:
                        raise ValueError("Objective polarity changed")
                    z = list(map(F, certificate["primal"]))
                    coefficients = [value * unit for value in z]
                    coefficients[0] += baseline
                    for t, observation in differences.items():
                        x = F(t, window)
                        predicted = sum(
                            (
                                value * x**power
                                for value, power in zip(
                                    coefficients, range(1, degree + 1, 2)
                                )
                            ),
                            F(),
                        )
                        if abs(predicted - observation) > noises[t] + cap * epsilon:
                            raise ValueError("Direct unscaled primal inequality failed")
                        primal_checks += 1
                    indices = certificate["active"]
                    multipliers = list(map(F, certificate["dual"]))
                    if (
                        len(indices) != len(z)
                        or len(multipliers) != len(z)
                        or any(v > 0 for v in multipliers)
                    ):
                        raise ValueError("Invalid independent dual dimensions/signs")
                    dual_value = F()
                    for index, multiplier in zip(indices, multipliers):
                        t = (index // 2 + 1) * 5
                        side = 1 if index % 2 == 0 else -1
                        if t not in differences:
                            raise ValueError("Dual support outside the window")
                        bound = (
                            side * (differences[t] - baseline * F(t, window))
                            + noises[t]
                            + cap * epsilon
                        ) / unit
                        dual_value += multiplier * bound
                    for power in range(1, degree + 1, 2):
                        coefficient = sum(
                            (
                                multiplier
                                * (1 if index % 2 == 0 else -1)
                                * F((index // 2 + 1) * 5, window) ** power
                                for index, multiplier in zip(indices, multipliers)
                            ),
                            F(),
                        )
                        if coefficient != (sign if power == 1 else 0):
                            raise ValueError("Independent dual moment identity failed")
                    if (
                        dual_value != F(certificate["optimum"])
                        or dual_value != sign * z[0]
                    ):
                        raise ValueError("Independent primal/dual equality failed")
                    angular_rate = coefficients[0] * F(86400, window)
                    key = (
                        "lower_arcsec_per_day"
                        if position == 0
                        else "upper_arcsec_per_day"
                    )
                    if angular_rate != F(axis[key]):
                        raise ValueError("Unscaled angular derivative changed")
                    dual_checks += 1
                records.append(
                    {
                        "id": source["id"],
                        "window_seconds": window,
                        "order": degree,
                        "axis": coordinate,
                        "lower_arcsec_per_day": axis["lower_arcsec_per_day"],
                        "upper_arcsec_per_day": axis["upper_arcsec_per_day"],
                    }
                )
    return {
        "method_id": "independent_unscaled_angular_epoch_envelope_replay_v1",
        "certificate_file_sha256": hashlib.sha256(
            (fixture / "outer-first-certificates.json").read_bytes()
        ).hexdigest(),
        "records": records,
        "direct_unscaled_primal_inequalities_checked": primal_checks,
        "exact_dual_optima_checked": dual_checks,
        "producer_or_candidate_imported": False,
        "actual_epoch_envelope_certified": False,
        "candidate_accuracy_passes": 0,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.fixture)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        {
            key: result[key]
            for key in [
                "direct_unscaled_primal_inequalities_checked",
                "exact_dual_optima_checked",
            ]
        }
    )
