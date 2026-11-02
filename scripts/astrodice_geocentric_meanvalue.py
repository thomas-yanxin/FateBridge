"""Mean-value geocentric receiver enclosure and complete monotone pair rejection.

Every original pair remains covered by a checked boundary exclusion or by an
exact candidate proof. Physical and numerical premises are unchanged.
"""

import argparse
import math
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import A, I, Reader
from scripts.astrodice_discrete_lt import nearest_sqrt, sqrt_in_interval
from scripts.astrodice_emission_epoch import (
    cell_relations,
    coordinate,
    epoch_from_coordinate,
    lattice_points,
    rounding_cell,
)
from scripts.astrodice_geocentric_partition import partition_pairs
from scripts.astrodice_joint_epoch import exact_state
from scripts.astrodice_observer_clock import parse_observer
from scripts.astrodice_observer_radius_clock import (
    FAMILIES,
    HYPOTHESES,
    K,
    angle_proof,
)
from scripts.astrodice_vector_clock import check_inputs, save, tube
from scripts.verify_astrodice_earth_clock import wire


def delay_support(row, ulps, family, nominal):
    lo, hi = [v / 1440 for v in tube(row["light_time_minutes"], ulps)]
    if not 0 < lo <= hi < 1:
        raise ValueError("Printed light-time outside declared one-day domain")
    scale = Q(1 if family == FAMILIES[0] else 86400)
    # The fixed +/-2 day enclosure contains all emitted epochs for receiver
    # +/-1 second and light time <1 day. Endpoint max-ULP bounds every binade.
    emitter_ulp = max(
        Q(math.ulp(float(coordinate(nominal + d, family)))) for d in (-2, 2)
    )
    delay_ulp = max(Q(math.ulp(float(v * scale))) for v in (lo, hi))
    padding = (emitter_ulp + delay_ulp) / (2 * scale)
    return {
        "printed_delay_days": list(map(str, (lo, hi))),
        "emission_raw_ULP_bound": str(emitter_ulp),
        "delay_raw_ULP_bound": str(delay_ulp),
        "both_rounding_models_padding_days": str(padding),
        "elapsed_delay_support_days": list(map(str, (lo - padding, hi + padding))),
    }


def source_range(reader, tr, delay):
    dl, dh = delay
    a, b = tr.bounds()
    earth = reader.state(A(tr, 1), "Earth")
    venus = reader.state(A(I(a - dh, b - dl), 1), "Venus")
    return sum(((v - e) * (v - e) for e, v in zip(earth[:3], venus[:3])), A())


def mean_value_enclosure(center, target, center_bounds, derivative, support):
    image = I(center) + (I(*target) - I(*center_bounds)) / I(*derivative)
    image_low, image_high = image.bounds()
    a, b = max(support[0], image_low), min(support[1], image_high)
    return {
        "method": "uniform_mean_value_necessary_enclosure_v1",
        "center_JD": str(center),
        "center_range_squared_bounds": list(map(str, center_bounds)),
        "mean_value_time_image_JD": list(map(str, (image_low, image_high))),
        "root_existence_or_uniqueness_proved": False,
        "status": "necessary_enclosure" if a <= b else "excluded_over_original_support",
        "effective_reception_JD": list(map(str, (a, b))) if a <= b else None,
    }


def candidate(source, case, row, ulps, family, tr, te):
    receiver, emitter = [epoch_from_coordinate(v, family) for v in (tr, te)]
    earth = exact_state(source, case["window_index"], receiver, "Earth")
    venus = exact_state(source, case["window_index"], emitter, "Venus")
    ray = [v - e for e, v in zip(earth, venus)]
    square = sum(v * v for v in ray[:3])
    angular = angle_proof(ray, row["astrometric_angles"], ulps)
    rg = sqrt_in_interval(square, *tube(row["range_AU"], ulps))
    lt = sqrt_in_interval(
        square * (K * 1440) ** 2, *tube(row["light_time_minutes"], ulps)
    )
    scale = Q(1 if family == FAMILIES[0] else 86400)
    delay_square = square * (K * scale) ** 2
    cell = rounding_cell(te)
    a, b = map(Q, cell["bounds"])
    rounded = nearest_sqrt(delay_square)
    one = sqrt_in_interval(delay_square, Q(tr) - b, Q(tr) - a, cell["lower_included"])
    two = cell_relations((Q(tr) - Q(rounded),) * 2, cell)[1]
    qualified = (
        rg
        and lt
        and angular["sufficient_angular_membership_proved"]
        and row["original_label_budget_pass"]
    )
    return {
        "receiver_hex": tr.hex(),
        "emitter_hex": te.hex(),
        "epochs_JD_TDB": list(map(str, (receiver, emitter))),
        "source_ray_AU_and_velocity_difference": list(map(str, ray)),
        "range_squared_AU2": str(square),
        "range_matches": rg,
        "printed_light_time_matches": lt,
        "angle_proof": angular,
        "emission_rounding_cell": cell,
        "delay_raw_squared": str(delay_square),
        "rounded_delay_hex": rounded.hex(),
        "rounding_hypotheses": dict(zip(HYPOTHESES, (one, two))),
        "source_observables_qualified": qualified,
        "radial_rate_used_for_clock_qualification": False,
    }


def infer(source, case, row, plan):
    nominal = Q(case["nominal_JD"])
    radius = Q(plan["receiver_search_radius_seconds"]) / 86400
    support = (nominal - radius, nominal + radius)
    reader = Reader(source, case["window_index"])
    output = {"receiver_support_JD": list(map(str, support)), "profiles": {}}
    for profile, settings in plan["numerical_tube_profiles"].items():
        ulps = settings["extra_binary64_ULPs"]
        output["profiles"][profile] = models = {}
        rg = tube(row["range_AU"], ulps)
        if rg[0] <= 0:
            raise ValueError("Nonpositive range")
        for family in FAMILIES:
            delay = delay_support(row, ulps, family, nominal)
            elapsed = tuple(map(Q, delay["elapsed_delay_support_days"]))
            derivative = source_range(reader, I(*support), elapsed).d.bounds()
            found = {
                "delay": delay,
                "range_squared_derivative_AU2_per_day": list(map(str, derivative)),
                "candidates": [],
                "receiver_grid_hex": [],
                "emitter_grids": [],
                "qualified_pairs_by_hypothesis": {h: [] for h in HYPOTHESES},
            }
            models[family] = found
            if derivative[0] * derivative[1] <= 0 or min(map(abs, derivative)) < Q(
                plan["minimum_squared_range_derivative_AU2_per_day"]
            ):
                found["status"] = "conditioning_unknown"
                continue

            point_bounds = source_range(reader, I(nominal), elapsed).v.bounds()
            enclosure = mean_value_enclosure(
                nominal, (rg[0] ** 2, rg[1] ** 2), point_bounds, derivative, support
            )
            found["enclosure"] = enclosure
            if enclosure["status"] == "excluded_over_original_support":
                found["status"] = "excluded_over_original_support"
                continue
            a, b = map(Q, enclosure["effective_reception_JD"])
            receivers = lattice_points(
                coordinate(a, family),
                coordinate(b, family),
                plan["maximum_lattice_points_per_model"],
            )
            found["receiver_grid_hex"] = [v.hex() for v in receivers["points"]]
            found["receiver_grid_status"] = receivers["status"]
            pairs = []
            complete = receivers["status"] == "complete"
            scale = Q(1 if family == FAMILIES[0] else 86400)
            for tr in receivers["points"] if complete else []:
                emitters = lattice_points(
                    Q(tr) - elapsed[1] * scale,
                    Q(tr) - elapsed[0] * scale,
                    plan["maximum_lattice_points_per_model"],
                )
                found["emitter_grids"].append(
                    {
                        "receiver_hex": tr.hex(),
                        "status": emitters["status"],
                        "points_hex": [v.hex() for v in emitters["points"]],
                    }
                )
                complete &= emitters["status"] == "complete"
                pairs.extend((tr, te) for te in emitters["points"])
            found["enumerated_pair_count"] = len(pairs)
            complete &= len(pairs) <= plan["maximum_pairs_per_model"]
            found["status"] = "complete" if complete else "enumeration_limit"
            if complete:

                def range_at_pair(tr, elapsed_raw):
                    epoch = epoch_from_coordinate(tr, family)
                    delay_days = elapsed_raw / scale
                    return source_range(
                        reader, I(epoch), (delay_days, delay_days)
                    ).v.bounds()

                found["partition"] = partition_pairs(
                    pairs, derivative[0] > 0, (rg[0] ** 2, rg[1] ** 2), range_at_pair
                )
                found["candidates"] = [
                    candidate(source, case, row, ulps, family, *pairs[i])
                    for i in found["partition"]["retained_pair_indices"]
                ]
                for h in HYPOTHESES:
                    found["qualified_pairs_by_hypothesis"][h] = [
                        [c["receiver_hex"], c["emitter_hex"]]
                        for c in found["candidates"]
                        if c["source_observables_qualified"]
                        and c["rounding_hypotheses"][h]
                    ]
    return output


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    output = {
        "cohort": cohort,
        "plan_sha256": digest,
        "queries": [],
        "candidate_calls": 0,
        "monotone_pair_partition": True,
        "receiver_enclosure_method": "uniform_mean_value_necessary_enclosure_v1",
        "new_candidate_holdouts": 0,
        "numerical_tubes_certified": False,
        "physical_time_model_certified": False,
        "internal_algorithm_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for query in plan["queries"]:
        if query["cohort"] != cohort:
            continue
        raw, receipt = wire(run, query)
        if receipt["status"] != 200:
            raise ValueError("Observer response unavailable")
        rows = parse_observer(raw, query, query["cases"], plan)
        output["queries"].append(
            {
                "id": query["id"],
                "encoding": query["encoding"],
                "rows": [
                    {
                        "observation": row,
                        "inference": infer(
                            run / "source-records",
                            next(
                                c for c in query["cases"] if c["id"] == row["case_id"]
                            ),
                            row,
                            plan,
                        ),
                    }
                    for row in rows
                ],
            }
        )
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--cohort", required=True, choices=("A", "B"))
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    save(args.output, analyze(args.run, args.cohort))


if __name__ == "__main__":
    main()
