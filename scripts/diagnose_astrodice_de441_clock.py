"""Bound geometric RA sensitivity of the five retained reference witnesses.

Both clock representations are diagnostics, not identified Horizons algorithms.
Geometric TDB directions cannot establish the actual apparent TT/TDB correction.
No original angles, printing constraints, certificates or grades are changed.
"""

import argparse
import hashlib
import json
import math
from fractions import Fraction as F
from pathlib import Path

from scripts.astrodice_de441_records import calendar_jd_tdb, geometric_states, header
from scripts.astrodice_interval_reference import system
from scripts.astrodice_reference_infeasibility import verify_incompatibility


def atan_bounds(value, terms):
    value = F(value)
    if not -1 <= value <= 1 or type(terms) is not int or terms < 1:
        raise ValueError("Invalid alternating arctangent domain")
    if value < 0:
        lo, hi = atan_bounds(-value, terms)
        return -hi, -lo
    partial = sum(
        ((-1) ** k * value ** (2 * k + 1) / (2 * k + 1) for k in range(terms)), F(0)
    )
    following = partial + (-1) ** terms * value ** (2 * terms + 1) / (2 * terms + 1)
    return min(partial, following), max(partial, following)


def pi_bounds():
    # Machin's identity; alternating-series remainders are exact inequalities.
    a, b = atan_bounds(F(1, 5), 32), atan_bounds(F(1, 239), 32)
    return 16 * a[0] - 4 * b[1], 16 * a[1] - 4 * b[0]


def scaled(bounds, factor):
    pair = [v * factor for v in bounds]
    return min(pair), max(pair)


def ra_shift_arcsec(original, shifted):
    x, y = original[:2]
    xx, yy = shifted[:2]
    denominator = x * xx + y * yy
    if denominator <= 0:
        raise ValueError("RA shift is not on the planned local branch")
    tangent = (x * yy - y * xx) / denominator
    if abs(tangent) > F(1, 2):
        raise ValueError("RA shift outside the small-angle diagnostic")
    lo, hi = atan_bounds(tangent, 2)
    pl, ph = pi_bounds()
    products = [
        angle * scale
        for angle in (lo, hi)
        for scale in (F(648000) / ph, F(648000) / pl)
    ]
    return min(products), max(products)


def describe(bounds):
    def canonical(value):
        return f"{value.numerator:x}/{value.denominator:x}"

    return {
        "outward_float_lower": math.nextafter(float(bounds[0]), -math.inf),
        "outward_float_upper": math.nextafter(float(bounds[1]), math.inf),
        "exact_interval_sha256": hashlib.sha256(
            (canonical(bounds[0]) + ":" + canonical(bounds[1])).encode()
        ).hexdigest(),
    }


def diagnose(run, original_fixture):
    source = json.loads((run / "geometric-reference.json").read_text())["rows"][2]
    metadata = header((run / "header.bin").read_bytes())
    raw = (run / source["source_record_file"]).read_bytes()[8144 : 2 * 8144]
    nominal = calendar_jd_tdb(source["date_tdb"])
    if source["date_tdb"] != "8103-07-26T18:51:11":
        raise ValueError("Clock diagnostic control changed")
    states = {}

    def xy(epoch):
        if epoch not in states:
            value = geometric_states(metadata, raw, epoch)
            states[epoch] = [a - e for a, e in zip(value["Venus"], value["Earth"])]
        return states[epoch]

    shifts = {}

    def shift(t, representation):
        key = (t, representation)
        if key not in shifts:
            epoch = nominal + F(t, 86400)
            quantized = (
                F(float(epoch))
                if representation == "binary64_absolute_jd"
                else F(2451545) + F(float((epoch - 2451545) * 86400)) / 86400
            )
            shifts[key] = (
                ra_shift_arcsec(xy(epoch), xy(quantized)),
                (quantized - epoch) * 86400,
            )
        return shifts[key][0]

    records = json.loads(
        (original_fixture / "exact-incompatibility-diagnostic.json").read_text()
    )["records"]
    if len(records) != 5:
        raise ValueError("Original contradiction population changed")
    results = []
    for record in records:
        path = original_fixture / (
            "parent/reference.json"
            if record["dataset"] == "parent"
            else "development-reference.json"
        )
        row = next(
            v for v in json.loads(path.read_text())["rows"] if v["id"] == record["case"]
        )
        a, b, _, scale = system(
            row,
            None,
            record["window_seconds"],
            record["odd_order"],
            record["axis"],
            step_seconds=record["grid_step_seconds"],
        )
        original = verify_incompatibility(a, b, record["witness"])
        hypotheses = {}
        for name in ("binary64_absolute_jd", "binary64_seconds_from_j2000"):
            contrast = (F(0), F(0))
            baseline_coefficient = F(0)
            for index, weight in zip(
                record["witness"]["support_indices"],
                map(F, record["witness"]["weights"]),
            ):
                t = (index // 2 + 1) * record["grid_step_seconds"]
                sign = 1 if index % 2 == 0 else -1
                plus, minus = shift(t, name), shift(-t, name)
                odd = ((plus[0] - minus[1]) / 2, (plus[1] - minus[0]) / 2)
                interval = scaled(odd, weight * sign / scale)
                contrast = contrast[0] + interval[0], contrast[1] + interval[1]
                baseline_coefficient += weight * sign * F(t, record["window_seconds"])
            if baseline_coefficient:
                raise ValueError("Witness baseline did not cancel exactly")
            adjusted = original - contrast[1], original - contrast[0]
            hypotheses[name] = {
                "geometric_clock_contrast_in_printing_scale_units": describe(contrast),
                "hypothetical_adjusted_witness_bound": describe(adjusted),
                "this_witness_still_strictly_negative_under_proxy": adjusted[1] < 0,
                "scope": "Sensitivity of this witness to a geometric clock proxy. Neither a new feasibility certificate nor the actual Horizons apparent-clock correction.",
            }
        results.append(
            {
                "case": record["case"],
                "dataset": record["dataset"],
                "window_seconds": record["window_seconds"],
                "odd_order": record["odd_order"],
                "original_exact_contradiction": str(original),
                "hypotheses": hypotheses,
            }
        )
    return {
        "method_id": "exact_geometric_ra_clock_sensitivity_of_retained_witnesses_v1",
        "records": results,
        "source_state_evaluations": len(states),
        "hypotheses": {
            name: {
                "maximum_absolute_epoch_rounding_seconds": float(
                    max(abs(v[1]) for k, v in shifts.items() if k[1] == name)
                ),
                "maximum_absolute_geometric_ra_shift_arcsec": max(
                    max(abs(float(x)) for x in v[0])
                    for k, v in shifts.items()
                    if k[1] == name
                ),
            }
            for name in ("binary64_absolute_jd", "binary64_seconds_from_j2000")
        },
        "original_five_incompatibility_proofs_retained": True,
        "printing_constraints_or_grades_changed": False,
        "actual_horizons_clock_identified": False,
        "apparent_ra_sensitivity_proved": False,
        "new_holdout_conditions": 0,
        "full_goal_complete": False,
        "scope": "Exact source-geometric angular changes for two hypothetical floating epoch representations. Nominal calendar numbers are treated as TDB; no physical TT/TDB equality or observational error bound is asserted.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--original-fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = diagnose(args.run, args.original_fixture)
    with args.output.open("x") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["hypotheses"]))
    for row in result["records"]:
        print(
            row["dataset"],
            row["window_seconds"],
            row["odd_order"],
            {
                k: v["this_witness_still_strictly_negative_under_proxy"]
                for k, v in row["hypotheses"].items()
            },
        )
