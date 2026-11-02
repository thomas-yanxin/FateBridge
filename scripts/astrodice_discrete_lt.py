"""Finite source-epoch pairs and exact nearest-even LT subtraction hypotheses.

Maintenance diagnosis only. Source-vector fit and a rounding fixed point do not
certify a service algorithm, a physical clock or an angular daily derivative.
"""

import argparse
import json
import math
import struct
from fractions import Fraction as Q
from itertools import product
from pathlib import Path

from scripts.astrodice_emission_epoch import (
    cell_relations,
    coordinate,
    epoch_from_coordinate,
    lattice_points,
    rounding_cell,
)
from scripts.astrodice_joint_epoch import exact_state
from scripts.astrodice_retarded_table import AU_KM, K
from scripts.astrodice_vector_clock import check_inputs, save, sha, tube

HYPOTHESES = ("one_round_source_norm", "two_round_source_norm")


def compare_sqrt(square, value):
    if square < 0:
        raise ValueError("Negative squared source quantity")
    if value < 0:
        return 1
    difference = square - value * value
    return (difference > 0) - (difference < 0)


def sqrt_in_interval(square, low, high, closed=True):
    lower, upper = compare_sqrt(square, low), compare_sqrt(square, high)
    return (lower > 0 or lower == 0 and closed) and (upper < 0 or upper == 0 and closed)


def nearest_sqrt(square):
    """Round sqrt(nonnegative rational) by exact search over positive IEEE bits."""
    if square < 0:
        raise ValueError("Negative square")

    def value(bits):
        return struct.unpack(">d", struct.pack(">Q", bits))[0]

    lo, hi = 0, 0x7FEFFFFFFFFFFFFF
    if compare_sqrt(square, Q(value(hi))) > 0:
        raise ValueError("Finite binary64 source model exceeded")
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if compare_sqrt(square, Q(value(mid))) >= 0:
            lo = mid
        else:
            hi = mid - 1
    if Q(value(lo)) ** 2 == square:
        return value(lo)
    midpoint = (Q(value(lo)) + Q(value(lo + 1))) / 2
    relation = compare_sqrt(square, midpoint)
    return value(lo if relation < 0 or relation == 0 and lo % 2 == 0 else lo + 1)


def ratio_in_interval(numerator, square, bounds):
    """Check numerator/sqrt(square) exactly, including both signs."""
    if square <= 0:
        raise ValueError("Zero length source ray")

    def compare(value):
        if numerator >= 0 > value:
            return 1
        if numerator < 0 <= value:
            return -1
        delta = numerator * numerator - value * value * square
        result = (delta > 0) - (delta < 0)
        return -result if numerator < 0 else result

    return compare(bounds[0]) >= 0 and compare(bounds[1]) <= 0


def candidate(source, window, vector, observer, ulps, model, reception, emission):
    tr, te = [epoch_from_coordinate(v, model) for v in (reception, emission)]
    earth, venus = [
        exact_state(source, window, t, body)
        for t, body in ((tr, "Earth"), (te, "Venus"))
    ]
    state = [v - e for e, v in zip(earth, venus)]
    measured = [tube(v, ulps) for v in vector["printed_state"]]
    component_flags = [a <= v <= b for v, (a, b) in zip(state, measured)]
    squared = sum(v * v for v in state[:3])
    radial = sum(p * v for p, v in zip(state[:3], state[3:]))
    distance_flags = {}
    for name, printed in (
        ("vector_RG", vector["range_AU"]),
        ("observer", observer["range_AU"]),
    ):
        distance_flags[name] = sqrt_in_interval(squared, *tube(printed, ulps))
    rr = ratio_in_interval(radial, squared, tube(vector["range_rate_AU_per_day"], ulps))
    observer_rr = ratio_in_interval(
        radial * AU_KM / 86400,
        squared,
        tube(observer["deldot_km_per_second"], ulps),
    )
    c = rounding_cell(emission)
    lower, upper = map(Q, c["bounds"])
    scale = Q(1 if model == "absolute_JD_binary64" else 86400)
    light_square = squared * (K * scale) ** 2
    one = sqrt_in_interval(
        light_square,
        Q(reception) - upper,
        Q(reception) - lower,
        c["lower_included"],
    )
    rounded_lt = nearest_sqrt(light_square)
    two = cell_relations((Q(reception) - Q(rounded_lt),) * 2, c)[1]
    ltlow, lthigh = tube(vector["light_time_days"], ulps)
    printed_image = (Q(reception) - lthigh * scale, Q(reception) - ltlow * scale)
    printed_intersects, printed_contained = cell_relations(printed_image, c)
    qualified = all(component_flags) and distance_flags["vector_RG"] and rr
    return {
        "reception_hex": reception.hex(),
        "emission_hex": emission.hex(),
        "epochs_JD": list(map(str, (tr, te))),
        "source_difference_AU_and_AU_per_day": list(map(str, state)),
        "squared_range_AU2": str(squared),
        "radial_numerator_AU2_per_day": str(radial),
        "source_component_compatible": component_flags,
        "source_range_compatible": distance_flags,
        "source_RR_matches_vector": rr,
        "source_RR_matches_observer": observer_rr,
        "source_vector_qualified": qualified,
        "emission_rounding_cell": c,
        "light_time_coordinate_squared": str(light_square),
        "rounded_light_time_hex": rounded_lt.hex(),
        "rounding_hypotheses": dict(zip(HYPOTHESES, (one, two))),
        "qualified_hypotheses_not_refuted": {
            name: qualified and flag for name, flag in zip(HYPOTHESES, (one, two))
        },
        "printed_LT_image_raw": list(map(str, printed_image)),
        "printed_LT_cell_intersects_diagnostic": printed_intersects,
        "printed_LT_cell_contains_diagnostic": printed_contained,
        "physical_or_internal_algorithm_certified": False,
    }


def infer(source, case, vector, observer, profile, family, plan):
    if (
        family["status"] != "enclosed"
        or not family["selected_equations_parametric_unique_root_proved"]
    ):
        return {"status": "input_family_unknown", "models": {}}
    models = {}
    ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    for model in plan["lattice_coordinate_models"]:
        found = [
            lattice_points(
                *[coordinate(Q(v), model) for v in family[key]],
                plan["maximum_lattice_points_per_model"],
            )
            for key in ("reception_JD", "emission_JD")
        ]
        complete = all(f["status"] == "complete" for f in found)
        pairs = math.prod(len(f["points"]) for f in found)
        within_budget = pairs <= plan["maximum_pairs_per_model"]
        candidates = (
            [
                candidate(
                    source, case["window_index"], vector, observer, ulps, model, tr, te
                )
                for tr, te in product(*[f["points"] for f in found])
            ]
            if complete and within_budget
            else []
        )
        complete = complete and within_budget
        counts = {
            name: sum(c["qualified_hypotheses_not_refuted"][name] for c in candidates)
            for name in HYPOTHESES
        }
        models[model] = {
            "enumeration_status": "complete" if complete else "enumeration_limit",
            "reception_points_hex": [v.hex() for v in found[0]["points"]],
            "emission_points_hex": [v.hex() for v in found[1]["points"]],
            "pairs": pairs,
            "candidates": candidates,
            "qualified_hypotheses_not_refuted": counts,
            "conditional_refuted": {
                name: complete and count == 0 for name, count in counts.items()
            },
            "physical_or_internal_algorithm_certified": False,
        }
    return {"status": "enumerated", "models": models}


def groups(run, cohort, plan):
    for spec in plan["groups"][cohort]:
        source_plan = json.loads(
            (run / spec["root"] / "plan-before-queries.json").read_text()
        )
        data = json.loads((run / spec["joint_analysis"]).read_text())
        for query in source_plan["queries"]:
            if query["cohort"] != spec["source_cohort"] or query["kind"] != "LT_vector":
                continue
            group = next(
                g
                for g in data["groups"]
                if g["id"] == spec["joint_group"] and g["query"] == query["id"]
            )
            yield spec, source_plan, query, group


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    output = {
        "cohort": cohort,
        "plan_sha256": digest,
        "groups": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "physical_time_model_certified": False,
        "full_goal_complete": False,
    }
    for spec, sp, query, group in groups(run, cohort, plan):
        cases = sp["cohorts"][spec["source_cohort"]]
        rows = []
        for row in group["rows"]:
            case = next(c for c in cases if c["id"] == row["vector"]["case_id"])
            rows.append(
                {
                    "case_id": case["id"],
                    "role": row["vector"]["role"],
                    "profiles": {
                        p: infer(
                            run / "source-records",
                            case,
                            row["vector"],
                            row["observer"],
                            p,
                            family,
                            plan,
                        )
                        for p, family in row["profiles"].items()
                    },
                }
            )
        output["groups"].append(
            {
                "id": spec["id"],
                "query": query["id"],
                "encoding": query["encoding"],
                "joint_analysis_sha256": sha(
                    (run / spec["joint_analysis"]).read_bytes()
                ),
                "rows": rows,
            }
        )
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    a = p.parse_args()
    save(a.run / (a.cohort + "-first-analysis.json"), analyze(a.run, a.cohort))
