"""Replay all old Farkas weights with independently rebuilt Taylor allowances.

No jet, constraint producer or solver import. A surviving negative combination
excludes Taylor remainder ALONE under the stated source derivative bound. It
does not prove source/Horizons equivalence or an actual evaluation-time bound.
"""

import argparse
import hashlib
import json
from decimal import Decimal
from fractions import Fraction as Q
from pathlib import Path


def validate_enclosures(plan, source):
    if (
        plan["jet_degree"] != 7
        or plan["jet_coefficient_convention"] != "f^(k)/k!"
        or plan["grid_offsets_seconds"] != list(range(-1440, 1441, 5))
        or source["source_Horizons_high_derivative_bound_equivalence_certified"]
        or source["physical_TT_TDB_conversion_certified"]
        or [row["date_tt"] for row in source["rows"]] != plan["cases"]
    ):
        raise ValueError("Taylor support, normalization or physical premises changed")
    for row in source["rows"]:
        if (
            row["status"] != "complete_source_Taylor_enclosures"
            or [s["offset_seconds"] for s in row["segments"]]
            != list(range(-1440, 1440, 5))
            or any(
                s["status"] != "outward_source_Taylor_enclosure"
                for s in row["segments"]
            )
        ):
            raise ValueError("Complete ordered source support required")
        for degree in (5, 7):
            for axis in (0, 1):
                values = []
                for segment in row["segments"]:
                    record = segment["angular_coefficients_arcsec"][axis][degree - 1]
                    if record["denominator_power_two"] != 256:
                        raise ValueError("Taylor box precision changed")
                    lo, hi = [
                        Q(int(record[key]), 2**256)
                        for key in ("lower_numerator", "upper_numerator")
                    ]
                    if lo > hi:
                        raise ValueError("Reversed high-order Taylor box")
                    values.append(max(abs(lo), abs(hi)))
                if max(values) != Q(
                    row["global_normalized_coefficient_bounds_arcsec"][str(degree)][
                        axis
                    ]
                ):
                    raise ValueError(
                        "Declared source coefficient was not the complete global maximum"
                    )


def verify(run, enclosures):
    plan = json.loads((run / "plan-before-high-order-evaluation.json").read_text())
    source = json.loads(enclosures.read_text())
    validate_enclosures(plan, source)
    proofs = json.loads(
        (run / "old-proofs/exact-incompatibility-diagnostic.json").read_text()
    )["records"]
    if (
        len(proofs) != 5
        or len(source["rows"]) != 3
        or plan["odd_polynomial_orders"] != [3, 5]
        or plan["fixed_rate_and_reference_arcsec_per_day"] != 0.002
    ):
        raise ValueError("Original proof population or numerical line changed")
    rows = []
    for proof in proofs:
        name = (
            "parent/reference.json"
            if proof["dataset"] == "parent"
            else "development-reference.json"
        )
        old = json.loads((run / "old-proofs" / name).read_text())
        row = next(r for r in old["rows"] if r["id"] == proof["case"])
        bound = next(r for r in source["rows"] if r["date_tt"] == row["date_tt"])
        if (
            bound["status"] != "complete_source_Taylor_enclosures"
            or len(bound["segments"]) != 576
        ):
            raise ValueError("Unqualified source remainder cannot be substituted")
        axis = proof["axis"]
        order = proof["odd_order"]
        degree = order + 2
        records = [
            segment["angular_coefficients_arcsec"][axis][degree - 1]
            for segment in bound["segments"]
        ]
        coefficient = max(
            abs(Q(int(r[key]), 2**256))
            for r in records
            for key in ["lower_numerator", "upper_numerator"]
        )
        if coefficient != Q(
            bound["global_normalized_coefficient_bounds_arcsec"][str(degree)][axis]
        ):
            raise ValueError(
                "Declared source coefficient was not the complete global maximum"
            )
        center = Q(row["samples"]["0"]["printed_angles"][axis])
        step, window = proof["grid_step_seconds"], proof["window_seconds"]
        observations = {}
        noises = {}
        for t in range(step, window + 1, step):
            values = [
                row["samples"][str(s * t)]["printed_angles"][axis] for s in (1, -1)
            ]
            angles = [Q(value) for value in values]
            if axis == 0:
                angles = [a - 360 * ((a - center + 180) // 360) for a in angles]
            observations[t] = (angles[0] - angles[1]) * 1800
            noises[t] = sum(
                (Q(10) ** Decimal(v).as_tuple().exponent * 1800 for v in values), Q()
            )
        baseline = observations[window]
        scale = max(noises.values())
        a = []
        b = []
        for t in observations:
            for sign in (1, -1):
                a.append([sign * Q(t, window) ** p for p in range(1, order + 1, 2)])
                b.append(
                    (sign * (observations[t] - baseline * Q(t, window)) + noises[t])
                    / scale
                )
        digest = hashlib.sha256(
            json.dumps(
                {"a": [[str(v) for v in r] for r in a], "b": [str(v) for v in b]},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        witness = proof["witness"]
        indices = witness["support_indices"]
        weights = list(map(Q, witness["weights"]))
        if (
            digest != witness["matrix_sha256"]
            or len(indices) != len(set(indices))
            or len(indices) != len(weights)
            or any(w < 0 for w in weights)
            or sum(weights, Q()) != 1
        ):
            raise ValueError("Original exact proof identity or weights changed")
        if any(
            sum((w * a[i][j] for i, w in zip(indices, weights)), Q())
            for j in range(len(a[0]))
        ):
            raise ValueError("Original weights do not annihilate the polynomial")
        original = sum((w * b[i] for i, w in zip(indices, weights)), Q())
        if original >= 0 or original != Q(witness["contradiction_bound"]):
            raise ValueError("Original contradiction did not replay exactly")
        extra = sum(
            (
                w * coefficient * Q((i // 2 + 1) * step, 86400) ** degree / scale
                for i, w in zip(indices, weights)
            ),
            Q(),
        )
        relaxed = original + extra
        rows.append(
            {
                "dataset": proof["dataset"],
                "case": proof["case"],
                "date_tt": row["date_tt"],
                "window_seconds": window,
                "odd_order": order,
                "axis": axis,
                "source_coefficient_order": degree,
                "global_normalized_source_coefficient_arcsec": str(coefficient),
                "original_scaled_contradiction": str(original),
                "additional_scaled_Taylor_allowance": str(extra),
                "relaxed_scaled_combination": str(relaxed),
                "relaxed_combination_still_strictly_negative": relaxed < 0,
                "meaning": (
                    "Taylor remainder alone is insufficient under the declared source high-derivative bound"
                    if relaxed < 0
                    else "This old witness no longer proves incompatibility; feasibility is not certified"
                ),
            }
        )
    return {
        "method_id": "independent_Taylor_relaxed_original_witness_replay_v1",
        "rows": rows,
        "old_exact_proofs_verified": 5,
        "old_weights_or_printed_values_changed": False,
        "source_Horizons_high_derivative_bound_equivalence_certified": False,
        "epoch_perturbation_allowance_included": False,
        "old_epoch_envelope_study_replaced": False,
        "candidate_or_jet_imported": False,
        "production_acceptance_exit_code": 2,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--enclosures", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = verify(a.run, a.enclosures)
    with a.output.open("x") as h:
        json.dump(result, h, indent=2)
        h.write("\n")
    print(
        "old witnesses replayed5; still negative",
        sum(r["relaxed_combination_still_strictly_negative"] for r in result["rows"]),
    )
