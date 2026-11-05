"""Freeze limb-neighbour TT labels from independent, unbent source geometry.

The nominal source time is TDB; treating its numeric date as a TT selection
label does not certify a physical TT/TDB conversion. No apparent residual or
candidate is used to choose either cohort.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN
from decimal import Decimal as N
from decimal import localcontext
from pathlib import Path

from scripts.astrodice_apparent_source_reference import Reader
from scripts.astrodice_de441_records import calendar_jd_tdb
from scripts.gen_astrodice_knot_neighbours import check_source
from scripts.select_astrodice_source_boundaries import geometry


def select(run, fixture):
    check_source(fixture)
    plan = json.loads((run / "selection-plan.json").read_text())
    bases = json.loads((fixture / "geometric-reference.json").read_text())["rows"]
    results = {name: [] for name in plan["cohort_impact_radius_fractions"]}
    roots = []
    with localcontext() as context:
        context.prec = plan["source_decimal_precision"]
        for window in plan["windows"]:
            index, body = window["index"], window["body"]
            base_label = bases[index]["date_tdb"]
            rational = calendar_jd_tdb(base_label)
            epoch = N(rational.numerator) / N(rational.denominator)
            reader = Reader(fixture, index)
            scan = []
            for seconds in range(
                -plan["search_radius_seconds"],
                plan["search_radius_seconds"] + 1,
                plan["scan_step_seconds"],
            ):
                impact, background = geometry(reader, body, epoch + N(seconds) / 86400)
                scan.append((N(seconds), impact))
            for cohort, levels in plan["cohort_impact_radius_fractions"].items():
                for level in levels:
                    target = N(level)
                    brackets = [
                        (a, b)
                        for a, b in zip(scan, scan[1:])
                        if (a[1] - target) * (b[1] - target) < 0
                    ]
                    if len(brackets) != plan["root_crossings_per_fraction"]:
                        raise ValueError(
                            "Planned solar limb crossing count unavailable"
                        )
                    for crossing, (left, right) in enumerate(brackets):
                        lo, hi, flo = left[0], right[0], left[1] - target
                        for _ in range(100):
                            mid = (lo + hi) / 2
                            impact, background = geometry(
                                reader, body, epoch + mid / 86400
                            )
                            if not background:
                                raise ValueError(
                                    "Selected limb ray is not behind the Sun"
                                )
                            value = impact - target
                            if flo * value <= 0:
                                hi = mid
                            else:
                                lo, flo = mid, value
                            if hi - lo <= N(plan["root_width_seconds"]):
                                break
                        if hi - lo > N(plan["root_width_seconds"]):
                            raise ValueError(
                                "Source geometry root bracket did not converge"
                            )
                        micros = int(
                            (((lo + hi) / 2) * 1000000).to_integral_value(
                                rounding=ROUND_HALF_EVEN
                            )
                        )
                        label = (
                            datetime.fromisoformat(base_label)
                            + timedelta(microseconds=micros)
                        ).isoformat(timespec="microseconds")
                        jd = calendar_jd_tdb(label)
                        actual, background = geometry(
                            reader, body, N(jd.numerator) / N(jd.denominator)
                        )
                        if not background or abs(actual - target) > N("1e-8"):
                            raise ValueError(
                                "Rounded selection lost declared source geometry"
                            )
                        case = {
                            "id": f"solar-limb-{cohort}-{index}-{level}-{crossing}",
                            "body": body,
                            "date_tt": label,
                            "role": "first_limb_model_discrimination_condition",
                            "window_index": index,
                            "target_impact_radius_fraction": level,
                            "crossing": crossing,
                            "exact_numeric_JD_fraction": str(jd),
                            "nominal_source_impact_radius_fraction": str(actual),
                            "nominal_source_background_ray": background,
                        }
                        results[cohort].append(case)
                        roots.append(
                            {
                                "id": case["id"],
                                "offset_lower_seconds": str(lo),
                                "offset_upper_seconds": str(hi),
                                "rounded_offset_microseconds": micros,
                            }
                        )
    if any(
        n == "swisseph" or n == "fatebridge" or n.startswith("fatebridge.")
        for n in sys.modules
    ):
        raise ValueError("Independent selector imported candidate")
    identities = [
        (case["body"], case["exact_numeric_JD_fraction"])
        for cases in results.values()
        for case in cases
    ]
    if len(set(identities)) != len(identities):
        raise ValueError("Source selection duplicated a condition")
    return {
        "plan_sha256": hashlib.sha256(
            (run / "selection-plan.json").read_bytes()
        ).hexdigest(),
        "cohorts": results,
        "roots": roots,
        "candidate_or_apparent_residual_used": False,
        "physical_TT_TDB_conversion_certified": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "fixture", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = select(args.run, args.fixture)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print("Frozen limb conditions", {k: len(v) for k, v in result["cohorts"].items()})
