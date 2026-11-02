"""Derive all-grid source slope caps without certifying reference equivalence."""

import argparse
import hashlib
import json
import sys
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import I, Reader, apparent
from scripts.astrodice_de441_records import calendar_jd_tdb
from scripts.astrodice_source_slope_bounds import angular_rate_bounds, pi_bounds


def audit(run):
    plan = json.loads((run / "source-slope-plan-before-evaluation.json").read_text())
    for name, digest in plan["inputs_sha256"].items():
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen slope dependency changed: " + name)
    original = json.loads((run / "plan-before-source-evaluation.json").read_text())
    for name, digest in original["inputs_sha256"].items():
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen original input changed: " + name)
    if (
        plan["segments_seconds"] != list(range(-1440, 1440, 5))
        or plan["epoch_error_hypothesis_days"] != "1/1000000000"
    ):
        raise ValueError("Source support or epoch hypothesis changed")
    profile = json.loads((run / "source-solar-profile.json").read_text())[
        "radius_mass_pairs"
    ]
    rows = []
    for date in plan["case_dates"]:
        center = calendar_jd_tdb(date)
        reader = Reader(run / "source-records", 2)
        margin = Q(plan["enlarge_each_segment_each_side_days"])
        segments = []
        for offset in plan["segments_seconds"]:
            lower = center + Q(offset, 86400) - margin
            upper = center + Q(offset + 5, 86400) + margin
            row = {
                "offset_seconds": offset,
                "exact_lower_nominal_TDB": str(lower),
                "exact_upper_nominal_TDB": str(upper),
            }
            try:
                vector, cells = apparent(reader, "Venus", I(lower, upper), profile)
                rates = angular_rate_bounds(vector)
                row.update(
                    status="outward_source_slope_enclosure",
                    absolute_RA_DEC_bounds_arcsec_per_day=list(map(str, rates)),
                    direction=[v.v.record() for v in vector],
                    derivative=[v.d.record() for v in vector],
                    **cells,
                )
            except ValueError as error:
                row.update(status="source_slope_unresolved", message=str(error))
            segments.append(row)
        qualified = all(
            s["status"] == "outward_source_slope_enclosure" for s in segments
        )
        maxima = (
            [
                max(
                    Q(s["absolute_RA_DEC_bounds_arcsec_per_day"][axis])
                    for s in segments
                )
                for axis in (0, 1)
            ]
            if qualified
            else None
        )
        maximum = max(maxima) if maxima else None
        cap = (
            -(-maximum.numerator // maximum.denominator)
            if maximum is not None
            else None
        )
        rows.append(
            {
                "date_tt": date,
                "status": (
                    "declared_source_model_slope_enclosed"
                    if qualified
                    else "source_slope_unresolved"
                ),
                "scalar_cap_arcsec_per_day": cap,
                "maximum_RA_DEC_bounds_arcsec_per_day": (
                    list(map(str, maxima)) if maxima else None
                ),
                "segments": segments,
            }
        )
        print(date, "source_model_scalar_cap", cap, flush=True)
    if any(
        n == "swisseph" or n == "fatebridge" or n.startswith("fatebridge.")
        for n in sys.modules
    ):
        raise ValueError("Reference-only slope study imported candidate")
    return {
        "method_id": plan["id"],
        "rows": rows,
        "pi_lower_upper_rational": list(map(str, pi_bounds())),
        "candidate_values_read": False,
        "old_H1_results_unchanged": True,
        "actual_Horizons_epoch_error_bound_certified": False,
        "source_Horizons_derivative_equivalence_certified": False,
        "physical_ephemeris_slope_bound_certified": False,
        "production_acceptance_exit_code": 2,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    result = audit(args.run)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
