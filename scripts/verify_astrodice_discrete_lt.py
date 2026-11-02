"""Independent direct-source, rational-inequality and IEEE-cell replay.

Does not import the discrete producer, its bit search, or Clenshaw evaluator.
The old joint contractor is checked independently before using its support.
"""

import argparse
import hashlib
import json
from decimal import Decimal
from fractions import Fraction as Q
from itertools import product
from pathlib import Path

from scripts.verify_astrodice_emission_epoch import (
    cell,
    enumerate_bits,
    from_raw,
    neighbor,
    relation,
    to_raw,
)
from scripts.verify_astrodice_joint_epoch import exact_state, verify_joint
from scripts.verify_astrodice_observer_timescale import inspect
from scripts.verify_astrodice_retarded_table import parse_vectors, wire

K = Q(149597870700, 299792458 * 86400)
AU = Q("149597870.7")
NAMES = ("one_round_source_norm", "two_round_source_norm")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def measured(printed, ulps):
    decimal = Decimal(printed)
    if not decimal.is_finite():
        raise ValueError("Nonfinite observation")
    value = abs(float(printed))
    spacing = Q(neighbor(value, True)) - Q(value)
    radius = Q(10) ** decimal.as_tuple().exponent + ulps * spacing
    return Q(printed) - radius, Q(printed) + radius


def square_membership(square, lo, hi, closed=True):
    if square < 0:
        raise ValueError("Negative source square")
    lower = lo < 0 or lo * lo < square or closed and lo * lo == square
    upper = hi >= 0 and (hi * hi > square or closed and hi * hi == square)
    return lower and upper


def radial_membership(numerator, square, bounds):
    if square <= 0:
        raise ValueError("Source direction undefined")
    lo, hi = bounds
    if numerator == 0:
        return lo <= 0 <= hi
    if numerator < 0:
        return radial_membership(-numerator, square, (-hi, -lo))
    return (
        hi > 0
        and numerator**2 <= hi**2 * square
        and (lo <= 0 or numerator**2 >= lo**2 * square)
    )


def check_candidate(source, case, vector, observer, ulps, model, tr_raw, te_raw, saved):
    epochs = [from_raw(v, model) for v in (tr_raw, te_raw)]
    earth, venus = [
        exact_state(source, case["window_index"], t, body)
        for t, body in zip(epochs, ("Earth", "Venus"))
    ]
    values = [v - e for e, v in zip(earth, venus)]
    square = sum(v**2 for v in values[:3])
    numerator = sum(a * b for a, b in zip(values[:3], values[3:]))
    flags = [
        a <= v <= b
        for v, (a, b) in zip(
            values, [measured(s, ulps) for s in vector["printed_state"]]
        )
    ]
    ranges = {
        name: square_membership(square, *measured(s, ulps))
        for name, s in (
            ("vector_RG", vector["range_AU"]),
            ("observer", observer["range_AU"]),
        )
    }
    rr = radial_membership(
        numerator, square, measured(vector["range_rate_AU_per_day"], ulps)
    )
    obsrr = radial_membership(
        numerator * AU / 86400, square, measured(observer["deldot_km_per_second"], ulps)
    )
    a, b, closed = cell(te_raw)
    scale = 1 if model == "absolute_JD_binary64" else 86400
    light_square = square * (K * scale) ** 2
    one = square_membership(light_square, Q(tr_raw) - b, Q(tr_raw) - a, closed)
    lt = float.fromhex(saved["rounded_light_time_hex"])
    c, d, is_closed = cell(lt)
    if lt < 0 or not square_membership(light_square, c, d, is_closed):
        raise ValueError("Rounded source light time is outside its exact IEEE cell")
    two = relation((Q(tr_raw) - Q(lt),) * 2, (a, b, closed))[1]
    low, high = measured(vector["light_time_days"], ulps)
    printed_image = Q(tr_raw) - high * scale, Q(tr_raw) - low * scale
    printed_flags = relation(printed_image, (a, b, closed))
    qualified = all(flags) and ranges["vector_RG"] and rr
    expected = {
        "reception_hex": tr_raw.hex(),
        "emission_hex": te_raw.hex(),
        "epochs_JD": list(map(str, epochs)),
        "source_difference_AU_and_AU_per_day": list(map(str, values)),
        "squared_range_AU2": str(square),
        "radial_numerator_AU2_per_day": str(numerator),
        "source_component_compatible": flags,
        "source_range_compatible": ranges,
        "source_RR_matches_vector": rr,
        "source_RR_matches_observer": obsrr,
        "source_vector_qualified": qualified,
        "emission_rounding_cell": {
            "bounds": list(map(str, (a, b))),
            "lower_included": closed,
            "upper_included": closed,
        },
        "light_time_coordinate_squared": str(light_square),
        "rounded_light_time_hex": lt.hex(),
        "rounding_hypotheses": dict(zip(NAMES, (one, two))),
        "qualified_hypotheses_not_refuted": {
            name: qualified and flag for name, flag in zip(NAMES, (one, two))
        },
        "printed_LT_image_raw": list(map(str, printed_image)),
        "printed_LT_cell_intersects_diagnostic": printed_flags[0],
        "printed_LT_cell_contains_diagnostic": printed_flags[1],
        "physical_or_internal_algorithm_certified": False,
    }
    if saved != expected:
        raise ValueError("Exact source state, rounding predicate or scope changed")
    return expected


def verify_profile(run, case, vector, observer, profile, family, saved, plan):
    joint = verify_joint(
        run / "source-records", case, vector, observer, profile, family, plan
    )
    if (
        family["status"] != "enclosed"
        or not family["selected_equations_parametric_unique_root_proved"]
    ):
        if saved != {"status": "input_family_unknown", "models": {}}:
            raise ValueError("Unproved source family promoted")
        return joint, 0
    if saved["status"] != "enumerated" or set(saved["models"]) != set(
        plan["lattice_coordinate_models"]
    ):
        raise ValueError("Source model omitted")
    count = 0
    ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    for model, value in saved["models"].items():
        found = [
            enumerate_bits(
                *[to_raw(Q(v), model) for v in family[k]],
                plan["maximum_lattice_points_per_model"],
            )
            for k in ("reception_JD", "emission_JD")
        ]
        pairs = len(found[0][1]) * len(found[1][1])
        complete = (
            all(status == "complete" for status, points in found)
            and pairs <= plan["maximum_pairs_per_model"]
        )
        expected_pairs = list(product(found[0][1], found[1][1])) if complete else []
        if len(value["candidates"]) != len(expected_pairs):
            raise ValueError("Incomplete source pair enumeration")
        checked = [
            check_candidate(
                run / "source-records", case, vector, observer, ulps, model, tr, te, c
            )
            for (tr, te), c in zip(expected_pairs, value["candidates"])
        ]
        count += len(checked)
        counts = {
            name: sum(c["qualified_hypotheses_not_refuted"][name] for c in checked)
            for name in NAMES
        }
        if value != {
            "enumeration_status": "complete" if complete else "enumeration_limit",
            "reception_points_hex": [v.hex() for v in found[0][1]],
            "emission_points_hex": [v.hex() for v in found[1][1]],
            "pairs": pairs,
            "candidates": checked,
            "qualified_hypotheses_not_refuted": counts,
            "conditional_refuted": {
                name: complete and number == 0 for name, number in counts.items()
            },
            "physical_or_internal_algorithm_certified": False,
        }:
            raise ValueError(
                "Grid, pair budget, model predicate or physical scope changed"
            )
    return joint, count


def verify(run, cohort):
    rawplan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(rawplan)
    for n, h in {
        **plan["inputs_sha256"],
        **json.loads((run / "implementation-before-queries.json").read_text()),
    }.items():
        if digest((run / n).read_bytes()) != h:
            raise ValueError("Frozen source or implementation drift: " + n)
    if plan["discrete_rounding_hypotheses"] != list(NAMES):
        raise ValueError("Declared rounding model set changed")
    raw = (run / (cohort + "-first-analysis.json")).read_bytes()
    data = json.loads(raw)
    if cohort == "B":
        binding = json.loads((run / "before-B-open-binding.json").read_text())
        collected = json.loads((run / "before-B-queries.json").read_text())
        generated = json.loads((run / "B-joint-first-process.json").read_text())
        if (
            binding["plan_sha256"] != digest(rawplan)
            or binding["A_analysis_sha256"]
            != digest((run / "A-first-analysis.json").read_bytes())
            or binding["A_proof_sha256"]
            != digest((run / "A-independent-replay-first.json").read_bytes())
            or collected["prior_A_analysis_sha256"] != binding["A_analysis_sha256"]
            or generated["exit_code"] != 0
            or generated["analysis_sha256"]
            != digest((run / "B-joint-first-analysis.json").read_bytes())
        ):
            raise ValueError("B source result or A-before-B binding changed")
    if (
        data["cohort"] != cohort
        or data["plan_sha256"] != digest(rawplan)
        or data["candidate_calls"]
        or data["new_candidate_holdouts"]
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
        or data["physical_time_model_certified"]
        or data["full_goal_complete"]
    ):
        raise ValueError("Discrete source diagnosis promoted to acceptance")
    expected = []
    for spec in plan["groups"][cohort]:
        sp = json.loads((run / spec["root"] / "plan-before-queries.json").read_text())
        jd = json.loads((run / spec["joint_analysis"]).read_text())
        for query in sp["queries"]:
            if (
                query["cohort"] == spec["source_cohort"]
                and query["kind"] == "LT_vector"
            ):
                old = next(
                    g
                    for g in jd["groups"]
                    if g["id"] == spec["joint_group"] and g["query"] == query["id"]
                )
                expected.append((spec, sp, query, old))
    if len(expected) != len(data["groups"]):
        raise ValueError("Frozen query group omitted")
    steps = boxes = pairs = 0
    summaries = []
    for (spec, sp, query, old), group in zip(expected, data["groups"]):
        if {
            k: group[k] for k in ("id", "query", "encoding", "joint_analysis_sha256")
        } != {
            "id": spec["id"],
            "query": query["id"],
            "encoding": query["encoding"],
            "joint_analysis_sha256": digest(
                (run / spec["joint_analysis"]).read_bytes()
            ),
        }:
            raise ValueError("Joint source identity changed")
        rawv, vr = wire(run / spec["root"], query)
        ob = sp["observer_bindings"][spec["source_cohort"]][query["encoding"]]
        oq = ob["query"]
        rawo, receipt = wire(run / spec["root"] / ob["root"], oq)
        for key in (
            "TIME_TYPE",
            "CAL_TYPE",
            "TIME_DIGITS",
            "CAL_FORMAT",
            "TLIST_TYPE",
            "TLIST",
        ):
            if query["parameters"][key] != oq["parameters"][key]:
                raise ValueError("Cross-batch source pairing")
        cases = sp["cohorts"][spec["source_cohort"]]
        vectors = parse_vectors(rawv, query, cases, sp)
        observed = inspect(rawo, receipt["status"], oq, cases, sp)
        if (
            vr["status"] != 200
            or observed["status"] != "supported"
            or len(vectors) != len(old["rows"])
            or len(vectors) != len(group["rows"])
        ):
            raise ValueError("Unavailable source table or omitted row")
        lookup = {r["case_id"]: r for r in observed["rows"]}
        stats = {
            p: {
                model: {
                    "primary": 0,
                    "input_family_unknown": 0,
                    "enumeration_limit": 0,
                    "source_vector_qualified": 0,
                    "source_range_matches_observer": 0,
                    "one_round_source_norm": 0,
                    "two_round_source_norm": 0,
                    "printed_LT_cell_contains_diagnostic": 0,
                }
                for model in plan["lattice_coordinate_models"]
            }
            for p in plan["numerical_tube_profiles"]
        }
        for vector, family_row, saved in zip(vectors, old["rows"], group["rows"]):
            observer = lookup[vector["case_id"]]
            if (
                family_row["vector"] != vector
                or family_row["observer"] != observer
                or saved["case_id"] != vector["case_id"]
                or saved["role"] != vector["role"]
            ):
                raise ValueError("Original source row identity changed")
            if set(saved["profiles"]) != set(plan["numerical_tube_profiles"]) or set(
                family_row["profiles"]
            ) != set(plan["numerical_tube_profiles"]):
                raise ValueError("Numerical tube omitted")
            case = next(c for c in cases if c["id"] == vector["case_id"])
            for p, stored in saved["profiles"].items():
                joint, number = verify_profile(
                    run,
                    case,
                    vector,
                    observer,
                    p,
                    family_row["profiles"][p],
                    stored,
                    plan,
                )
                steps += joint["steps"]
                boxes += joint["source_boxes"]
                pairs += number
                if vector["role"] == "auxiliary_not_primary":
                    continue
                for model, s in stats[p].items():
                    s["primary"] += 1
                    if model not in stored["models"]:
                        s["input_family_unknown"] += 1
                        continue
                    m = stored["models"][model]
                    s["enumeration_limit"] += m["enumeration_status"] != "complete"
                    candidates = m["candidates"]
                    s["source_vector_qualified"] += any(
                        c["source_vector_qualified"] for c in candidates
                    )
                    s["source_range_matches_observer"] += any(
                        c["source_range_compatible"]["observer"] for c in candidates
                    )
                    s["printed_LT_cell_contains_diagnostic"] += any(
                        c["source_vector_qualified"]
                        and c["printed_LT_cell_contains_diagnostic"]
                        for c in candidates
                    )
                    for name in NAMES:
                        s[name] += any(
                            c["qualified_hypotheses_not_refuted"][name]
                            for c in candidates
                        )
        summaries.append(
            {
                "id": spec["id"],
                "query": query["id"],
                "encoding": query["encoding"],
                "profiles": stats,
            }
        )
    return {
        "method": "independent_direct_source_rational_IEEE_cells_v1",
        "cohort": cohort,
        "analysis_sha256": digest(raw),
        "groups": summaries,
        "joint_steps_checked": steps,
        "source_boxes_checked": boxes,
        "exact_grid_pairs_checked": pairs,
        "exit_code": 0,
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "physical_time_model_certified": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    with a.output.open("x") as f:
        json.dump(verify(a.run, a.cohort), f, indent=2)
        f.write("\n")
