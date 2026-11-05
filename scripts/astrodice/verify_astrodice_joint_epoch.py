"""Independent direct-basis/Bernstein proof of joint epoch contractions.

No joint producer, Clenshaw, interval AD or ephemeris backend imports. A selected
two-equation parametric root never certifies the unused component or physics.
"""

import argparse
import hashlib
import json
import struct
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path

from scripts.astrodice.audit_astrodice_de441_reference import direct_state
from scripts.astrodice.verify_astrodice_emission_epoch import enumerate_bits, raw_source
from scripts.astrodice.verify_astrodice_observer_clock import (
    Source,
    add,
    cover,
    divide,
    length,
    mul,
    neg,
    observed,
    parse,
    rounded,
    sub,
)
from scripts.astrodice.verify_astrodice_observer_timescale import inspect
from scripts.astrodice.verify_astrodice_retarded_table import parse_vectors, wire

K = Q(149597870700, 299792458 * 86400)
AU_KM = Q("149597870.7")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def exact_state(source, window, epoch, body):
    au, emrat, pointers, records = raw_source(source, window)
    record = next(
        r
        for r in records
        if Q(struct.unpack_from("<d", r)[0])
        <= epoch
        < Q(struct.unpack_from("<d", r, 8)[0])
    )
    if body == "Venus":
        return [v / au for v in direct_state(record, pointers[1], epoch)]
    if body != "Earth":
        raise ValueError("Unplanned source body")
    emb, moon = [direct_state(record, pointers[g], epoch) for g in (2, 9)]
    return [(e - m / (1 + emrat)) / au for e, m in zip(emb, moon)]


def sum_boxes(values):
    total = rounded(0)
    for v in values:
        total = add(total, v)
    return total


def det(rows):
    return sub(mul(rows[0][0], rows[1][1]), mul(rows[0][1], rows[1][0]))


def overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def predicate_layers(name, reported, declared, independent, measured, refinements):
    """Validate the original enclosure predicate; preserve stronger refutations."""
    cover(independent, declared)
    original = overlap(parse(declared), measured)
    if reported != original:
        raise ValueError("Reported enclosure predicate changed: " + name)
    refined = overlap(independent, measured)
    if refined and not original:
        raise ValueError("Nested source refinement cannot reverse a refutation")
    if original and not refined:
        refinements.append(
            {"field": name, "reported_not_refuted": True, "independently_refuted": True}
        )
    return refined


def reported_rate_conversion(bounds):
    """Reconstruct only the producer's published 256-bit unit conversion."""
    scale = 1 << 256

    def product(a, b):
        values = [x * y for x in a for y in b]
        return rounded(min(values), max(values), scale=scale)

    return product(
        product(bounds, rounded(AU_KM, scale=scale)), rounded(Q(1, 86400), scale=scale)
    )


def source_support(source, centers, offsets, declared):
    if len(declared) != 2:
        raise ValueError("Source support dimension differs")
    allowance = Q(4, 1 << 256)
    states = []
    for c, x, claimed, body in zip(centers, offsets, declared, ["Earth", "Venus"]):
        true = (c + x[0] / 86400, c + x[1] / 86400)
        a, b = parse(claimed)
        if not (
            a <= true[0] <= true[1] <= b
            and true[0] - a <= allowance
            and b - true[1] <= allowance
        ):
            raise ValueError("Absolute epoch enclosure changed or excessive padding")
        states.append(source.state((a, b), body))
    J = [
        [
            divide(neg(states[0][a + 3]), rounded(86400)),
            divide(states[1][a + 3], rounded(86400)),
        ]
        for a in range(3)
    ]
    return states, J


def verify_joint(directory, case, vector, observer, profile, stored, plan):
    ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    measured = [observed(v, ulps) for v in vector["printed_state"]]
    centers = [Q(case["nominal_JD"]), Q(case["nominal_JD"]) - Q(vector["range_AU"]) * K]
    initial = [
        (
            -Q(plan["reception_search_radius_seconds"]),
            Q(plan["reception_search_radius_seconds"]),
        ),
        (
            -Q(plan["emission_search_radius_seconds"]),
            Q(plan["emission_search_radius_seconds"]),
        ),
    ]
    if (
        list(map(Q, stored["centers_JD"])) != centers
        or list(map(parse, stored["initial_offsets_seconds"])) != initial
        or stored["physical_time_model_certified"]
        or stored["full_three_component_root_certified"]
    ):
        raise ValueError("Frozen support or physical scope changed")
    source = Source(directory, case["window_index"])
    _, J = source_support(source, centers, initial, stored["initial_support_JD"])
    if len(stored["initial_jacobian"]) != 3 or any(
        len(r) != 2 for r in stored["initial_jacobian"]
    ):
        raise ValueError("Initial Jacobian dimensions changed")
    for actual, row in zip(J, stored["initial_jacobian"]):
        for a, b in zip(actual, row):
            cover(a, b)
    J = [list(map(parse, r)) for r in stored["initial_jacobian"]]
    choices = list(combinations(range(3), 2))
    if len(stored["axis_candidates"]) != 3:
        raise ValueError("Axis candidate omitted")
    conditioning = []
    for axes, c in zip(choices, stored["axis_candidates"]):
        if c["axes"] != list(axes):
            raise ValueError("Residual-based axis selection")
        cover(det([J[a] for a in axes]), c["determinant"])
        a, b = parse(c["determinant"])
        lower = min(abs(a), abs(b)) if a * b > 0 else Q(0)
        if Q(c["minimum_absolute_determinant"]) != lower:
            raise ValueError("Conditioning lower bound changed")
        conditioning.append(lower)
    chosen = max(range(3), key=conditioning.__getitem__)
    axes = list(choices[chosen])
    if stored["selected_axes"] != axes:
        raise ValueError("Source-only axis rule changed")
    if conditioning[chosen] <= 0:
        if (
            stored["status"] != "conditioning_unknown"
            or stored["history"]
            or stored["selected_equations_parametric_unique_root_proved"]
        ):
            raise ValueError("Singular source promoted")
        return {"steps": 0, "source_boxes": 6, "enclosed": False}
    e, v = [
        exact_state(directory, case["window_index"], t, b)
        for t, b in zip(centers, ["Earth", "Venus"])
    ]
    point = [[-e[a + 3] / 86400, v[a + 3] / 86400] for a in axes]
    d = point[0][0] * point[1][1] - point[0][1] * point[1][0]
    if d == 0:
        raise ValueError("Singular exact preconditioner")
    C = [[point[1][1] / d, -point[0][1] / d], [-point[1][0] / d, point[0][0] / d]]
    if [list(map(Q, row)) for row in stored["preconditioner"]] != C:
        raise ValueError("Independent exact preconditioner differs")
    offsets = initial
    proved = False
    source_boxes = 6
    empty = False
    if len(stored["history"]) > plan["joint_contractor_iterations"]:
        raise ValueError("Unplanned contractor work")
    for step in stored["history"]:
        if empty:
            raise ValueError("Iteration after empty source support")
        if list(map(parse, step["input_seconds"])) != offsets:
            raise ValueError("Contractor input changed")
        mid = [sum(x) / 2 for x in offsets]
        if list(map(Q, step["midpoint_seconds"])) != mid:
            raise ValueError("Residual-dependent midpoint")
        _, J = source_support(source, centers, offsets, step["support_JD"])
        for a, row in zip(axes, step["jacobian"]):
            for actual, declared in zip(J[a], row):
                cover(actual, declared)
                source_boxes += 1
        J = [list(map(parse, row)) for row in step["jacobian"]]
        exact = [
            exact_state(directory, case["window_index"], c + m / 86400, b)
            for c, m, b in zip(centers, mid, ["Earth", "Venus"])
        ]
        differences = [exact[1][a] - exact[0][a] for a in axes]
        if list(map(Q, step["point_difference_AU"])) != differences:
            raise ValueError("Exact direct-basis point differs")
        for difference, a, declared in zip(differences, axes, step["residual_AU"]):
            cover(sub(rounded(difference), measured[a]), declared)
        residual = list(map(parse, step["residual_AU"]))
        error = [
            [
                sub(
                    rounded(int(i == j)),
                    sum_boxes(mul(rounded(C[i][k]), J[k][j]) for k in range(2)),
                )
                for j in range(2)
            ]
            for i in range(2)
        ]
        if len(step["error_matrix"]) != 2 or any(
            len(r) != 2 for r in step["error_matrix"]
        ):
            raise ValueError("Preconditioned error matrix dimensions differ")
        for row, claimed in zip(error, step["error_matrix"]):
            for actual, declared in zip(row, claimed):
                cover(actual, declared)
        error = [list(map(parse, row)) for row in step["error_matrix"]]
        contraction = max(sum(max(abs(a), abs(b)) for a, b in row) for row in error)
        if Q(step["contraction_upper"]) != contraction:
            raise ValueError("Contraction norm understated")
        images = [
            add(
                sub(
                    rounded(mid[i]),
                    sum_boxes(mul(rounded(C[i][k]), residual[k]) for k in range(2)),
                ),
                sum_boxes(
                    mul(error[i][j], sub(offsets[j], rounded(mid[j]))) for j in range(2)
                ),
            )
            for i in range(2)
        ]
        for actual, declared in zip(images, step["image_seconds"]):
            cover(actual, declared)
        images = list(map(parse, step["image_seconds"]))
        inside = all(a < x and y < b for (a, b), (x, y) in zip(offsets, images))
        intersections = [
            (max(a, x), min(b, y)) for (a, b), (x, y) in zip(offsets, images)
        ]
        empty = any(a > b for a, b in intersections)
        if (
            step["strict_image_interior"] != inside
            or step["empty_intersection"] != empty
        ):
            raise ValueError("Krawczyk inclusion predicate changed")
        if empty:
            if (
                step["next_seconds"] is not None
                or proved
                or stored["status"] != "no_source_root_in_frozen_support"
            ):
                raise ValueError("Empty support hidden or proved family contradicted")
        else:
            if list(map(parse, step["next_seconds"])) != intersections:
                raise ValueError("Interval intersection shrunk or moved")
            proved |= inside and contraction < 1
            offsets = intersections
    if stored["selected_equations_parametric_unique_root_proved"] != proved:
        raise ValueError("Selected-equation theorem scope changed")
    if empty:
        return {
            "steps": len(stored["history"]),
            "source_boxes": source_boxes,
            "enclosed": False,
        }
    if (
        len(stored["history"]) != plan["joint_contractor_iterations"]
        or stored["status"] != "enclosed"
        or list(map(parse, stored["final_offsets_seconds"])) != offsets
    ):
        raise ValueError("Unfinished contractor promoted or final support changed")
    finalJD = [stored["reception_JD"], stored["emission_JD"]]
    states, _ = source_support(source, centers, offsets, finalJD)
    for actual, row in zip(states, stored["source_states_AU_and_AU_per_day"]):
        if len(row) != 6:
            raise ValueError("Final source state omitted")
        for a, b in zip(actual, row):
            cover(a, b)
            source_boxes += 1
    ray = [sub(v, e) for e, v in zip(states[0][:3], states[1][:3])]
    distance = length(ray)
    if len(stored["source_ray_AU"]) != 3:
        raise ValueError("Unused position component omitted")
    for actual, declared in zip(ray, stored["source_ray_AU"]):
        cover(actual, declared)
    cover(distance, stored["source_range_AU"])
    refinements = []
    original_flags = [
        overlap(parse(a), b) for a, b in zip(stored["source_ray_AU"], measured[:3])
    ]
    flags = [
        predicate_layers(
            "position." + str(i), reported, declared, actual, target, refinements
        )
        for i, (reported, declared, actual, target) in enumerate(
            zip(
                stored["source_position_components_compatible"],
                stored["source_ray_AU"],
                ray,
                measured[:3],
            )
        )
    ]
    if stored["source_position_components_compatible"] != original_flags or stored[
        "all_three_position_components_not_refuted"
    ] != all(original_flags):
        raise ValueError("Unused position contradiction hidden")
    rg, obs, lt = [
        observed(v, ulps)
        for v in [vector["range_AU"], observer["range_AU"], vector["light_time_days"]]
    ]
    refined_range_RG = predicate_layers(
        "range.vector_RG",
        stored["source_range_matches_vector_RG"],
        stored["source_range_AU"],
        distance,
        rg,
        refinements,
    )
    refined_range_observer = predicate_layers(
        "range.observer",
        stored["source_range_matches_observer"],
        stored["source_range_AU"],
        distance,
        obs,
        refinements,
    )
    rec, emit = map(parse, finalJD)
    relation = add(sub(emit, rec), lt)
    seconds = mul(relation, rounded(86400))
    cover(seconds, stored["emission_minus_reception_plus_LT_seconds"])
    if stored["continuous_LT_relation_not_refuted"] != overlap(relation, rounded(0)):
        raise ValueError("Continuous epoch relation changed")
    unit = [divide(p, distance) for p in ray]
    ev, vv = states[0][3:], states[1][3:]
    ratio = divide(
        add(
            rounded(1), mul(rounded(K), sum_boxes(mul(u, v) for u, v in zip(unit, ev)))
        ),
        add(
            rounded(1), mul(rounded(K), sum_boxes(mul(u, v) for u, v in zip(unit, vv)))
        ),
    )
    cover(ratio, stored["emission_rate_ratio"])
    models = {
        "naive_velocity_difference": [sub(v, e) for e, v in zip(ev, vv)],
        "continuous_Newtonian_reception_derivative": [
            sub(mul(v, ratio), e) for e, v in zip(ev, vv)
        ],
    }
    qualified = proved and all(flags)
    original_qualified = proved and all(original_flags)
    if stored["position_source_model_not_refuted"] != original_qualified or set(
        stored["velocity_models"]
    ) != set(models):
        raise ValueError("Partial position fit promoted or velocity model omitted")
    refined_velocities = {}
    refined_radial_RR = {}
    refined_radial_observer = {}
    for name, values in models.items():
        declared = stored["velocity_models"][name]
        if len(declared["AU_per_day"]) != 3:
            raise ValueError("Velocity component omitted")
        for actual, claimed in zip(values, declared["AU_per_day"]):
            cover(actual, claimed)
        original_compatible = [
            overlap(parse(a), b) for a, b in zip(declared["AU_per_day"], measured[3:])
        ]
        compatible = [
            predicate_layers(
                name + ".velocity." + str(i), reported, box, actual, target, refinements
            )
            for i, (reported, box, actual, target) in enumerate(
                zip(
                    declared["components_compatible"],
                    declared["AU_per_day"],
                    values,
                    measured[3:],
                )
            )
        ]
        if declared["components_compatible"] != original_compatible or declared[
            "joint_position_and_velocity_not_refuted"
        ] != (original_qualified and all(original_compatible)):
            raise ValueError(
                "Velocity predicate changed or position qualification lost"
            )
        radial = sum_boxes(mul(u, v) for u, v in zip(unit, values))
        cover(radial, declared["radial_rate_AU_per_day"])
        refined_radial_RR[name] = predicate_layers(
            name + ".radial.vector_RR",
            declared["radial_rate_matches_vector_RR"],
            declared["radial_rate_AU_per_day"],
            radial,
            observed(vector["range_rate_AU_per_day"], ulps),
            refinements,
        )
        reported_kms = reported_rate_conversion(
            parse(declared["radial_rate_AU_per_day"])
        )
        refined_radial_observer[name] = predicate_layers(
            name + ".radial.observer",
            declared["radial_rate_matches_observer"],
            list(map(str, reported_kms)),
            mul(radial, rounded(AU_KM / 86400)),
            observed(observer["deldot_km_per_second"], ulps),
            refinements,
        )
        refined_velocities[name] = qualified and all(compatible)
    original_full = (
        stored["velocity_models"]["continuous_Newtonian_reception_derivative"][
            "joint_position_and_velocity_not_refuted"
        ]
        and stored["continuous_LT_relation_not_refuted"]
        and stored["source_range_matches_vector_RG"]
        and stored["velocity_models"]["continuous_Newtonian_reception_derivative"][
            "radial_rate_matches_vector_RR"
        ]
    )
    if stored["continuous_Newtonian_LT_vector_model_not_refuted"] != original_full:
        raise ValueError("Epoch failure hidden in full-model predicate")
    full = (
        refined_velocities["continuous_Newtonian_reception_derivative"]
        and stored["continuous_LT_relation_not_refuted"]
        and refined_range_RG
        and refined_radial_RR["continuous_Newtonian_reception_derivative"]
    )
    if set(stored["lattices"]) != {"reception", "emission"}:
        raise ValueError("Epoch lattice role omitted")
    for role, epoch in zip(["reception", "emission"], [rec, emit]):
        if set(stored["lattices"][role]) != set(plan["lattice_coordinate_models"]):
            raise ValueError("Grid model omitted")
        for model, value in stored["lattices"][role].items():
            a, b = (
                epoch
                if model == "absolute_JD_binary64"
                else tuple((t - 2451545) * 86400 for t in epoch)
            )
            status, points = enumerate_bits(
                a, b, plan["maximum_lattice_points_per_model"]
            )
            if value != {
                "status": status,
                "point_hex": [v.hex() for v in points],
                "points": len(points),
                "internal_representation_certified": False,
            }:
                raise ValueError("Grid membership or physical scope changed")
    return {
        "steps": len(stored["history"]),
        "source_boxes": source_boxes,
        "enclosed": True,
        "two_axis_root_proved": proved,
        "position_model_not_refuted": qualified,
        "continuous_LT_relation_not_refuted": stored[
            "continuous_LT_relation_not_refuted"
        ],
        "source_range_matches_observer": refined_range_observer,
        "velocity_models": refined_velocities,
        "radial_vector_RR": refined_radial_RR,
        "radial_observer": refined_radial_observer,
        "original_enclosure_refinements": refinements,
        "continuous_full_model_not_refuted": full,
    }


def verify(run, cohort):
    rawplan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(rawplan)
    before = json.loads((run / ("before-" + cohort + "-queries.json")).read_text())
    if cohort == "B" and before["prior_A_analysis_sha256"] != digest(
        (run / "A-first-analysis.json").read_bytes()
    ):
        raise ValueError("B was not bound to the original A analysis")
    rawanalysis = (run / (cohort + "-first-analysis.json")).read_bytes()
    data = json.loads(rawanalysis)
    if (
        data["cohort"] != cohort
        or data["plan_sha256"] != digest(rawplan)
        or any(
            data[k]
            for k in [
                "candidate_calls",
                "new_candidate_holdouts",
                "numerical_tubes_certified",
                "physical_time_model_certified",
                "internal_algorithm_certified",
                "full_goal_complete",
            ]
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Joint source proof promoted to acceptance")
    expected = []
    for spec in plan["groups"][cohort]:
        sp = json.loads((run / spec["root"] / "plan-before-queries.json").read_text())
        expected.extend(
            (spec, sp, q)
            for q in sp["queries"]
            if q["cohort"] == spec["source_cohort"] and q["kind"] == "LT_vector"
        )
    if len(expected) != len(data["groups"]):
        raise ValueError("Original query group omitted")
    summaries = []
    refinement_rows = []
    steps = boxes = 0
    for (spec, sp, query), group in zip(expected, data["groups"]):
        raw, receipt = wire(run / spec["root"], query)
        obs_spec = sp["observer_bindings"][spec["source_cohort"]][query["encoding"]]
        oq = obs_spec["query"]
        oraw, oreceipt = wire(run / spec["root"] / obs_spec["root"], oq)
        if any(
            group[k] != v
            for k, v in {
                **spec,
                "query": query["id"],
                "encoding": query["encoding"],
                "vector_raw_sha256": digest(raw),
                "observer_raw_sha256": digest(oraw),
            }.items()
        ):
            raise ValueError("Original joint source/table identity changed")
        keys = (
            "TIME_TYPE",
            "CAL_TYPE",
            "TIME_DIGITS",
            "CAL_FORMAT",
            "TLIST_TYPE",
            "TLIST",
        )
        if any(query["parameters"][k] != oq["parameters"][k] for k in keys):
            raise ValueError("Cross-batch joint clock input")
        cases = sp["cohorts"][spec["source_cohort"]]
        vectors = parse_vectors(raw, query, cases, sp)
        obs = inspect(oraw, oreceipt["status"], oq, cases, sp)
        if (
            receipt["status"] != 200
            or obs["status"] != "supported"
            or len(group["rows"]) != len(vectors)
        ):
            raise ValueError("Unavailable table promoted or row omitted")
        lookup = {r["case_id"]: r for r in obs["rows"]}
        stats = {
            p: {
                "primary": 0,
                "statuses": {},
                "two_axis_root_proved": 0,
                "position_model_not_refuted": 0,
                "continuous_LT_relation_not_refuted": 0,
                "source_range_matches_observer": 0,
                "velocity_models": {
                    "naive_velocity_difference": 0,
                    "continuous_Newtonian_reception_derivative": 0,
                },
                "radial_vector_RR": {
                    "naive_velocity_difference": 0,
                    "continuous_Newtonian_reception_derivative": 0,
                },
                "radial_observer": {
                    "naive_velocity_difference": 0,
                    "continuous_Newtonian_reception_derivative": 0,
                },
                "continuous_full_model_not_refuted": 0,
            }
            for p in plan["numerical_tube_profiles"]
        }
        for vector, row in zip(vectors, group["rows"]):
            observer = lookup[vector["case_id"]]
            if (
                row["vector"] != vector
                or row["observer"] != observer
                or set(row["profiles"]) != set(plan["numerical_tube_profiles"])
            ):
                raise ValueError("Original values, case roles or profiles changed")
            case = next(c for c in cases if c["id"] == vector["case_id"])
            for p, stored in row["profiles"].items():
                result = verify_joint(
                    run / "source-records", case, vector, observer, p, stored, plan
                )
                steps += result["steps"]
                boxes += result["source_boxes"]
                if result.get("original_enclosure_refinements"):
                    refinement_rows.append(
                        {
                            "group": spec["id"],
                            "query": query["id"],
                            "case_id": vector["case_id"],
                            "role": vector["role"],
                            "profile": p,
                            "refinements": result["original_enclosure_refinements"],
                        }
                    )
                if vector["role"] == "auxiliary_not_primary":
                    continue
                stat = stats[p]
                stat["primary"] += 1
                status = stored["status"]
                stat["statuses"][status] = stat["statuses"].get(status, 0) + 1
                for key in [
                    "two_axis_root_proved",
                    "position_model_not_refuted",
                    "continuous_LT_relation_not_refuted",
                    "source_range_matches_observer",
                    "continuous_full_model_not_refuted",
                ]:
                    stat[key] += result.get(key, False)
                for name, v in result.get("velocity_models", {}).items():
                    stat["velocity_models"][name] += v
                for layer in ("radial_vector_RR", "radial_observer"):
                    for name, value in result.get(layer, {}).items():
                        stat[layer][name] += value
        summaries.append({**spec, "query": query["id"], "profiles": stats})
    return {
        "method": "independent_exact_basis_Bernstein_joint_epoch_Krawczyk_refinement_v2",
        "cohort": cohort,
        "analysis_sha256": digest(rawanalysis),
        "groups": summaries,
        "contractor_steps_checked": steps,
        "source_boxes_checked": boxes,
        "refinement_rows": refinement_rows,
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
