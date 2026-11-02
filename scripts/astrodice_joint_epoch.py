"""Joint reception/emission inversion from LT position components.

Conditional exact-DE441 source model. Two selected equations can have a proved
parametric root while the unused position component or a velocity model fails.
No physical clock, internal representation or candidate acceptance is certified.
"""

import argparse
import json
import struct
from fractions import Fraction as Q
from functools import lru_cache
from itertools import combinations
from pathlib import Path

from scripts.astrodice_clock_batch_binding import require_matching_time_batches
from scripts.astrodice_clock_interval import A, I, Reader
from scripts.astrodice_de441_records import group_state, header
from scripts.astrodice_emission_epoch import coordinate, lattice_points
from scripts.astrodice_observer_clock import box, norm
from scripts.astrodice_observer_timescale import classify
from scripts.astrodice_retarded_table import AU_KM, K, parse
from scripts.astrodice_vector_clock import check_inputs, save, sha, tube


@lru_cache(maxsize=16)
def source_bundle(source, window):
    meta = header((source / "header.bin").read_bytes())
    raw = (source / f"record-responses/case-{window:02}.bin").read_bytes()
    if len(raw) != 3 * 8144:
        raise ValueError("Incomplete source records")
    return meta, [raw[k : k + 8144] for k in range(0, len(raw), 8144)]


def exact_state(source, window, epoch, body):
    meta, records = source_bundle(source, window)
    record = next(
        r
        for r in records
        if Q(struct.unpack_from("<d", r)[0])
        <= epoch
        < Q(struct.unpack_from("<d", r, 8)[0])
    )
    if body == "Venus":
        values = group_state(meta, record, epoch, 1)
    elif body == "Earth":
        emb, moon = [group_state(meta, record, epoch, g) for g in (2, 9)]
        values = [
            e - m / (1 + Q(meta["earth_moon_mass_ratio"])) for e, m in zip(emb, moon)
        ]
    else:
        raise ValueError("Unplanned source body")
    return [v / Q(meta["au_km"]) for v in values]


def source_states(reader, centers, offsets):
    epochs = [I(c) + x / 86400 for c, x in zip(centers, offsets)]
    states = [
        [v.v for v in reader.state(A(t), body)]
        for t, body in zip(epochs, ["Earth", "Venus"])
    ]
    jac = [[-states[0][a + 3] / 86400, states[1][a + 3] / 86400] for a in range(3)]
    return epochs, states, jac


def determinant(rows):
    return rows[0][0] * rows[1][1] - rows[0][1] * rows[1][0]


def krawczyk_step(offsets, C, J, residual):
    mid = [sum(x.bounds()) / 2 for x in offsets]
    error = [
        [
            I(int(i == j)) - sum((I(C[i][k]) * J[k][j] for k in range(2)), I())
            for j in range(2)
        ]
        for i in range(2)
    ]
    contraction = max(sum(x.absolute_upper() for x in row) for row in error)
    image = [
        I(mid[i])
        - sum((I(C[i][k]) * residual[k] for k in range(2)), I())
        + sum((error[i][j] * (offsets[j] - mid[j]) for j in range(2)), I())
        for i in range(2)
    ]
    inside = all(
        a < x and y < b
        for (a, b), (x, y) in zip(
            [x.bounds() for x in offsets], [x.bounds() for x in image]
        )
    )
    intersections = [
        (max(x.bounds()[0], y.bounds()[0]), min(x.bounds()[1], y.bounds()[1]))
        for x, y in zip(offsets, image)
    ]
    empty = any(a > b for a, b in intersections)
    return {
        "midpoint_seconds": list(map(str, mid)),
        "error_matrix": [[box(x) for x in row] for row in error],
        "contraction_upper": str(contraction),
        "image_seconds": [box(x) for x in image],
        "strict_image_interior": inside,
        "empty_intersection": empty,
        "next_seconds": None if empty else [list(map(str, v)) for v in intersections],
    }


def overlaps(a, b):
    x, y = a.bounds()
    u, v = b.bounds()
    return x <= v and u <= y


def infer_joint(source, case, vector, observer, profile, plan):
    ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    measured = [I(*tube(v, ulps)) for v in vector["printed_state"]]
    centers = [Q(case["nominal_JD"]), Q(case["nominal_JD"]) - Q(vector["range_AU"]) * K]
    radii = [
        Q(plan["reception_search_radius_seconds"]),
        Q(plan["emission_search_radius_seconds"]),
    ]
    offsets = [I(-v, v) for v in radii]
    reader = Reader(source, case["window_index"])
    epochs, states, jac = source_states(reader, centers, offsets)
    candidates = []
    for axes in combinations(range(3), 2):
        d = determinant([jac[a] for a in axes])
        a, b = d.bounds()
        lower = min(abs(a), abs(b)) if a * b > 0 else Q(0)
        candidates.append(
            {
                "axes": list(axes),
                "determinant": box(d),
                "minimum_absolute_determinant": str(lower),
            }
        )
    chosen = max(candidates, key=lambda c: Q(c["minimum_absolute_determinant"]))
    result = {
        "centers_JD": list(map(str, centers)),
        "initial_offsets_seconds": [box(x) for x in offsets],
        "initial_support_JD": [box(x) for x in epochs],
        "initial_jacobian": [[box(x) for x in row] for row in jac],
        "axis_candidates": candidates,
        "selected_axes": chosen["axes"],
        "history": [],
        "selected_equations_parametric_unique_root_proved": False,
        "physical_time_model_certified": False,
        "full_three_component_root_certified": False,
    }
    if Q(chosen["minimum_absolute_determinant"]) <= 0:
        return {**result, "status": "conditioning_unknown"}
    axes = chosen["axes"]
    e, v = [
        exact_state(source, case["window_index"], t, body)
        for t, body in zip(centers, ["Earth", "Venus"])
    ]
    point = [[-e[a + 3] / 86400, v[a + 3] / 86400] for a in axes]
    det = point[0][0] * point[1][1] - point[0][1] * point[1][0]
    if det == 0:
        raise ValueError("Source interval monotonicity contradicts exact Jacobian")
    C = [
        [point[1][1] / det, -point[0][1] / det],
        [-point[1][0] / det, point[0][0] / det],
    ]
    result["preconditioner"] = list(map(lambda row: list(map(str, row)), C))
    for _ in range(plan["joint_contractor_iterations"]):
        epochs, states, jac = source_states(reader, centers, offsets)
        mid = [sum(x.bounds()) / 2 for x in offsets]
        exact = [
            exact_state(source, case["window_index"], c + m / 86400, body)
            for c, m, body in zip(centers, mid, ["Earth", "Venus"])
        ]
        differences = [exact[1][a] - exact[0][a] for a in axes]
        residual = [I(d) - measured[a] for d, a in zip(differences, axes)]
        step = krawczyk_step(offsets, C, [jac[a] for a in axes], residual)
        step.update(
            input_seconds=[box(x) for x in offsets],
            support_JD=[box(x) for x in epochs],
            jacobian=[[box(x) for x in jac[a]] for a in axes],
            point_difference_AU=list(map(str, differences)),
            residual_AU=[box(x) for x in residual],
        )
        result["history"].append(step)
        if step["empty_intersection"]:
            if result["selected_equations_parametric_unique_root_proved"]:
                raise ValueError("Proved source-root family became empty")
            return {**result, "status": "no_source_root_in_frozen_support"}
        result["selected_equations_parametric_unique_root_proved"] |= (
            step["strict_image_interior"] and Q(step["contraction_upper"]) < 1
        )
        offsets = [I(*map(Q, x)) for x in step["next_seconds"]]
    epochs, states, _ = source_states(reader, centers, offsets)
    ray = [v - e for e, v in zip(states[0][:3], states[1][:3])]
    distance = norm(ray)
    flags = [overlaps(x, y) for x, y in zip(ray, measured[:3])]
    direction = [x / distance for x in ray]
    ev, vv = states[0][3:], states[1][3:]
    naive = [v - e for e, v in zip(ev, vv)]
    ratio = (1 + K * sum((u * v for u, v in zip(direction, ev)), I())) / (
        1 + K * sum((u * v for u, v in zip(direction, vv)), I())
    )
    differentiated = [v * ratio - e for e, v in zip(ev, vv)]
    velocity_models = {
        name: {
            "AU_per_day": [box(x) for x in values],
            "components_compatible": [
                overlaps(x, y) for x, y in zip(values, measured[3:])
            ],
        }
        for name, values in [
            ("naive_velocity_difference", naive),
            ("continuous_Newtonian_reception_derivative", differentiated),
        ]
    }
    lt = I(*tube(vector["light_time_days"], ulps))
    obs = I(*tube(observer["range_AU"], ulps))
    rg = I(*tube(vector["range_AU"], ulps))
    result.update(
        status="enclosed",
        final_offsets_seconds=[box(x) for x in offsets],
        reception_JD=box(epochs[0]),
        emission_JD=box(epochs[1]),
        source_states_AU_and_AU_per_day=[[box(x) for x in row] for row in states],
        source_ray_AU=[box(x) for x in ray],
        source_position_components_compatible=flags,
        all_three_position_components_not_refuted=all(flags),
        source_range_AU=box(distance),
        source_range_matches_vector_RG=overlaps(distance, rg),
        source_range_matches_observer=overlaps(distance, obs),
        emission_minus_reception_plus_LT_seconds=box(
            (epochs[1] - epochs[0] + lt) * 86400
        ),
        continuous_LT_relation_not_refuted=overlaps(epochs[1] - epochs[0] + lt, I()),
        emission_rate_ratio=box(ratio),
        velocity_models=velocity_models,
        lattices={},
    )
    for role, epoch in zip(["reception", "emission"], epochs):
        result["lattices"][role] = {}
        a, b = epoch.bounds()
        for model in plan["lattice_coordinate_models"]:
            found = lattice_points(
                coordinate(a, model),
                coordinate(b, model),
                plan["maximum_lattice_points_per_model"],
            )
            result["lattices"][role][model] = {
                "status": found["status"],
                "point_hex": [p.hex() for p in found["points"]],
                "points": len(found["points"]),
                "internal_representation_certified": False,
            }
    qualified = result["selected_equations_parametric_unique_root_proved"] and all(
        flags
    )
    result["position_source_model_not_refuted"] = qualified
    for name, model in result["velocity_models"].items():
        values = naive if name == "naive_velocity_difference" else differentiated
        radial = sum((u * v for u, v in zip(direction, values)), I())
        model["radial_rate_AU_per_day"] = box(radial)
        model["radial_rate_matches_vector_RR"] = overlaps(
            radial, I(*tube(vector["range_rate_AU_per_day"], ulps))
        )
        model["radial_rate_matches_observer"] = overlaps(
            radial * AU_KM / 86400, I(*tube(observer["deldot_km_per_second"], ulps))
        )
        model["joint_position_and_velocity_not_refuted"] = qualified and all(
            model["components_compatible"]
        )
    result["continuous_Newtonian_LT_vector_model_not_refuted"] = (
        result["velocity_models"]["continuous_Newtonian_reception_derivative"][
            "joint_position_and_velocity_not_refuted"
        ]
        and result["continuous_LT_relation_not_refuted"]
        and result["source_range_matches_vector_RG"]
        and result["velocity_models"]["continuous_Newtonian_reception_derivative"][
            "radial_rate_matches_vector_RR"
        ]
    )
    return result


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    output = {
        "plan_sha256": digest,
        "cohort": cohort,
        "groups": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "numerical_tubes_certified": False,
        "physical_time_model_certified": False,
        "internal_algorithm_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for spec in plan["groups"][cohort]:
        source_plan = json.loads(
            (run / spec["root"] / "plan-before-queries.json").read_text()
        )
        cases = source_plan["cohorts"][spec["source_cohort"]]
        for query in source_plan["queries"]:
            if query["cohort"] != spec["source_cohort"] or query["kind"] != "LT_vector":
                continue
            root = run / spec["root"]
            raw = (root / "responses" / (query["id"] + ".raw")).read_bytes()
            receipt = json.loads(
                (root / "responses" / (query["id"] + ".receipt.json")).read_text()
            )
            obs_spec = source_plan["observer_bindings"][spec["source_cohort"]][
                query["encoding"]
            ]
            oq = obs_spec["query"]
            obsroot = root / obs_spec["root"]
            oraw = (obsroot / "responses" / (oq["id"] + ".raw")).read_bytes()
            oreceipt = json.loads(
                (obsroot / "responses" / (oq["id"] + ".receipt.json")).read_text()
            )
            require_matching_time_batches(query, oq)
            if sha(raw) != receipt["raw_sha256"] or sha(oraw) != oreceipt["raw_sha256"]:
                raise ValueError("Original table bytes changed")
            rows = parse(raw, query, cases, source_plan)
            observed = classify(oraw, oreceipt["status"], oq, cases, source_plan)
            if receipt["status"] != 200 or observed["status"] != "supported":
                raise ValueError(
                    "Unavailable table cannot be a joint source constraint"
                )
            lookup = {r["case_id"]: r for r in observed["rows"]}
            group = {
                **spec,
                "query": query["id"],
                "encoding": query["encoding"],
                "vector_raw_sha256": sha(raw),
                "observer_raw_sha256": sha(oraw),
                "rows": [],
            }
            for vector in rows:
                case = next(c for c in cases if c["id"] == vector["case_id"])
                observer = lookup[case["id"]]
                group["rows"].append(
                    {
                        "vector": vector,
                        "observer": observer,
                        "profiles": {
                            p: infer_joint(
                                run / "source-records", case, vector, observer, p, plan
                            )
                            for p in plan["numerical_tube_profiles"]
                        },
                    }
                )
            output["groups"].append(group)
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    a = p.parse_args()
    save(a.run / (a.cohort + "-first-analysis.json"), analyze(a.run, a.cohort))
