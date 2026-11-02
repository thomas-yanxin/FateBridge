"""Same-order, same-data nominal-node control; separate from original scores."""

import argparse
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_interval_reference import WINDOWS
from scripts.astrodice_nonuniform_reference import DEGREES, fit, quality
from scripts.astrodice_vector_clock import check_inputs, save
from scripts.verify_astrodice_nonuniform_reference import (
    bound_proof,
    independent_system,
    inspect_angles,
)


def control(run, cohort):
    plan, digest = check_inputs(run)
    angles = inspect_angles(run, cohort, plan)
    epochs = {o: Q(o) for o in angles}
    fits = [fit(angles, epochs, w, d) for w in WINDOWS for d in DEGREES]
    certificates = 0
    for item in fits:
        for axis, row in enumerate(item["axes"]):
            a, b, base, scale = independent_system(
                angles, epochs, item["window_seconds"], item["full_degree"], axis
            )
            if (
                row["baseline"] != list(map(str, base))
                or Q(row["scale_arcsec"]) != scale
            ):
                raise ValueError("Control baseline changed")
            if all(
                c["status"] == "exact_primal_dual_optimum" for c in row["certificates"]
            ):
                low = (
                    (base[1] + scale * bound_proof(a, b, row["certificates"][0]))
                    * 86400
                    / item["window_seconds"]
                )
                high = (
                    (base[1] - scale * bound_proof(a, b, row["certificates"][1]))
                    * 86400
                    / item["window_seconds"]
                )
                if row["derivative_interval_arcsec_per_TDB_day"] != list(
                    map(str, (low, high))
                ):
                    raise ValueError("Control interval changed")
                certificates += 2
    assessed_quality = quality(fits)
    assessed_quality.pop("TDB_day_not_certified_TT_day")
    assessed_quality["requested_TT_axis_not_internal_time_certified"] = True
    for row in fits:
        for axis in row["axes"]:
            key = "derivative_interval_arcsec_per_TDB_day"
            if key in axis:
                axis["derivative_interval_arcsec_per_nominal_TT_day"] = axis.pop(key)
    return {
        "cohort": cohort,
        "source_plan_sha256": digest,
        "kind": "same_full_degrees_and_printed_angles_nominal_node_control",
        "full_degrees": [5, 7],
        "primary_nodes": 577,
        "fits": fits,
        "quality": assessed_quality,
        "independent_exact_certificates_checked": certificates,
        "nominal_axis_is_requested_TT_seconds": True,
        "original_scores_replaced": False,
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--cohort", required=True, choices=("A", "B"))
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    save(args.output, control(args.run, args.cohort))


if __name__ == "__main__":
    main()
