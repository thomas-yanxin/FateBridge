"""OBSERVER-native SSB range inversion, with explicit finite clock hypotheses.

The source radius is inverted before any geometric reception clock is read.
Norm, angle, delay and rounding constraints remain separate. The two numerical
tubes are hypotheses; this never certifies a physical TT/TDB conversion.
"""

import argparse
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import A, I, Reader
from scripts.astrodice_discrete_lt import nearest_sqrt, sqrt_in_interval
from scripts.astrodice_earth_clock import diagnose as geometry_diagnose
from scripts.astrodice_earth_clock import parse as geometry_parse
from scripts.astrodice_emission_epoch import (
    cell_relations,
    coordinate,
    epoch_from_coordinate,
    lattice_points,
    rounding_cell,
)
from scripts.astrodice_joint_epoch import exact_state
from scripts.astrodice_observer_clock import trig_point
from scripts.astrodice_observer_origin import classify
from scripts.astrodice_vector_clock import check_inputs, inverse, save, tube
from scripts.verify_astrodice_earth_clock import wire

K = Q(149597870700, 299792458 * 86400)
FAMILIES = ("absolute_JD_binary64", "seconds_from_J2000_binary64")
HYPOTHESES = ("one_round_source_norm", "two_round_source_norm")


def box(value):
    return list(map(str, value.bounds()))


def radius_square(source, window, epoch):
    return sum((v * v for v in exact_state(source, window, epoch, "Earth")[:3]), Q())


def angle_proof(state, printed, ulps):
    """Sufficient cone/sine membership, not componentwise overlap of a box."""
    ra = Q(printed[0])
    lo, hi = tube(printed[0], ulps)
    shift = 360 if ra >= 180 else 0
    sl, cl = trig_point(lo - shift, 80)
    su, cu = trig_point(hi - shift, 80)
    sm, cm = trig_point(ra - shift, 80)
    x, y, z = map(I, state[:3])
    squared = sum((Q(v) * Q(v) for v in state[:3]), Q())
    unit_z = z / I(squared).sqrt()
    dl, du = tube(printed[1], ulps)
    if not -90 <= dl <= du <= 90:
        raise ValueError("Declination tube crosses the pole")
    sdl, _ = trig_point(dl, 80)
    sdu, _ = trig_point(du, 80)
    lower = cl * y - sl * x
    upper = cu * y - su * x
    front = cm * x + sm * y
    checks = {
        "RA_lower_cross": box(lower),
        "RA_upper_cross": box(upper),
        "RA_front_dot": box(front),
        "DEC_sine": box(unit_z),
        "DEC_lower_sine": box(sdl),
        "DEC_upper_sine": box(sdu),
    }
    a, b = lower.bounds()
    c, d = upper.bounds()
    e, f = front.bounds()
    zl, zh = unit_z.bounds()
    ll, lh = sdl.bounds()
    ul, uh = sdu.bounds()
    inside = a >= 0 and d <= 0 and e > 0 and zl >= lh and zh <= ul
    refuted = b < 0 or c > 0 or f <= 0 or zh < ll or zl > uh
    return {
        "status": (
            "proved_inside" if inside else "refuted" if refuted else "boundary_unknown"
        ),
        "bounds": checks,
        "sufficient_angular_membership_proved": inside,
    }


def candidate(source, case, row, profile, family, te, plan):
    epoch = epoch_from_coordinate(te, family)
    state = exact_state(source, case["window_index"], epoch, "Earth")
    squared = sum(v * v for v in state[:3])
    ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    angle = angle_proof(state, row["astrometric_angles"], ulps)
    range_ok = sqrt_in_interval(squared, *tube(row["range_AU"], ulps))
    lt_ok = sqrt_in_interval(
        squared * (K * 1440) ** 2, *tube(row["light_time_minutes"], ulps)
    )
    scale = Q(1 if family == "absolute_JD_binary64" else 86400)
    light_square = squared * (K * scale) ** 2
    cell = rounding_cell(te)
    a, b = map(Q, cell["bounds"])
    light = I(light_square).sqrt()
    rounded_lt = nearest_sqrt(light_square)
    lo, hi = light.bounds()
    lo = min(lo, Q(rounded_lt))
    hi = max(hi, Q(rounded_lt))
    found = lattice_points(a + lo, b + hi, plan["maximum_lattice_points_per_model"])
    receivers = []
    for tr in found["points"]:
        one = sqrt_in_interval(
            light_square, Q(tr) - b, Q(tr) - a, cell["lower_included"]
        )
        two = cell_relations((Q(tr) - Q(rounded_lt),) * 2, cell)[1]
        within = abs(
            epoch_from_coordinate(tr, family) - Q(case["nominal_JD"])
        ) * 86400 <= Q(plan["receiver_search_radius_seconds"])
        receivers.append(
            {
                "reception_hex": tr.hex(),
                "within_original_receiver_support": within,
                "rounding_hypotheses": dict(zip(HYPOTHESES, (one, two))),
            }
        )
    qualified = (
        range_ok
        and lt_ok
        and angle["sufficient_angular_membership_proved"]
        and row["original_label_budget_pass"]
        and found["status"] == "complete"
    )
    return {
        "emission_hex": te.hex(),
        "emission_JD_TDB": str(epoch),
        "source_state_AU_and_AU_per_day": list(map(str, state)),
        "source_radius_squared_AU2": str(squared),
        "range_matches": range_ok,
        "printed_light_time_matches": lt_ok,
        "angle_proof": angle,
        "emission_rounding_cell": cell,
        "light_time_coordinate_squared": str(light_square),
        "rounded_light_time_hex": rounded_lt.hex(),
        "receiver_support_raw": [str(a + lo), str(b + hi)],
        "receiver_grid_status": found["status"],
        "receiver_grid_hex": [v.hex() for v in found["points"]],
        "receivers": receivers,
        "source_observables_qualified": qualified,
        "radial_rate_used_for_clock_qualification": False,
    }


def diagnose(source, case, row, plan):
    center = Q(case["nominal_JD"]) - Q(row["range_AU"]) * K
    radius = Q(plan["emission_search_radius_seconds"]) / 86400
    reader = Reader(source, case["window_index"])
    state = reader.state(A(I(center - radius, center + radius), 1), "Earth")
    squared = sum((v * v for v in state[:3]), A())
    derivative = squared.d.bounds()
    result = {
        "emission_search_center_JD": str(center),
        "emission_search_support_JD": [str(center - radius), str(center + radius)],
        "radius_squared_derivative_AU2_per_day": list(map(str, derivative)),
        "profiles": {},
    }
    if derivative[0] * derivative[1] <= 0 or min(map(abs, derivative)) < Q(
        plan["minimum_radius_squared_derivative_AU2_per_day"]
    ):
        return {**result, "status": "conditioning_unknown"}
    result["status"] = "monotone_source_radius"
    for profile, settings in plan["numerical_tube_profiles"].items():
        low, high = tube(row["range_AU"], settings["extra_binary64_ULPs"])
        if low <= 0:
            raise ValueError("Nonpositive range tube")
        saved = inverse(
            lambda t: radius_square(source, case["window_index"], t),
            center,
            (low * low, high * high),
            derivative[0] > 0,
            radius,
            plan["inverse_iterations"],
        )
        saved["families"] = {}
        if saved["status"] == "bracketed":
            a, b = map(Q, saved["effective_JD"])
            for family in FAMILIES:
                grid = lattice_points(
                    coordinate(a, family),
                    coordinate(b, family),
                    plan["maximum_lattice_points_per_model"],
                )
                records = (
                    [
                        candidate(source, case, row, profile, family, p, plan)
                        for p in grid["points"]
                    ]
                    if grid["status"] == "complete"
                    else []
                )
                clocks = {
                    h: sorted(
                        {
                            r["reception_hex"]
                            for c in records
                            if c["source_observables_qualified"]
                            for r in c["receivers"]
                            if r["within_original_receiver_support"]
                            and r["rounding_hypotheses"][h]
                        }
                    )
                    for h in HYPOTHESES
                }
                saved["families"][family] = {
                    "grid_status": grid["status"],
                    "emission_grid_hex": [p.hex() for p in grid["points"]],
                    "candidates": records,
                    "qualified_reception_points_by_hypothesis": clocks,
                }
        result["profiles"][profile] = saved
    return result


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    output = {
        "cohort": cohort,
        "plan_sha256": digest,
        "observer_queries": [],
        "geometry_queries": [],
        "new_candidate_holdouts": 0,
        "physical_time_model_certified": False,
        "Earth_view_clock_equivalence_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for query in plan["queries"]:
        if query["cohort"] != cohort:
            continue
        raw, receipt = wire(run, query)
        if query["kind"] == "geometry":
            if receipt["status"] != 200:
                raise ValueError("Unavailable geometric comparison")
            rows = geometry_parse(raw, query, query["cases"], plan)
            output["geometry_queries"].append(
                {
                    "id": query["id"],
                    "encoding": query["encoding"],
                    "rows": [
                        geometry_diagnose(
                            run / "source-records",
                            next(c for c in query["cases"] if c["id"] == r["case_id"]),
                            r,
                            "Earth",
                            plan,
                        )
                        for r in rows
                    ],
                }
            )
            continue
        parsed = classify(raw, receipt["status"], query, plan)
        if parsed["status"] != "supported":
            raise ValueError("Required OBSERVER SSB contract unavailable")
        rows = []
        for row in parsed["rows"]:
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            rows.append(
                {
                    "observation": row,
                    "inference": diagnose(run / "source-records", case, row, plan),
                }
            )
        output["observer_queries"].append(
            {"id": query["id"], "encoding": query["encoding"], "rows": rows}
        )
    output["clock_comparisons"] = []
    for group in output["observer_queries"]:
        geometry = next(
            q for q in output["geometry_queries"] if q["encoding"] == group["encoding"]
        )
        query = next(q for q in plan["queries"] if q["id"] == group["id"])
        for row in group["rows"]:
            observation = row["observation"]
            inference = row["inference"]
            case = next(c for c in query["cases"] if c["id"] == observation["case_id"])
            geo = next(
                r for r in geometry["rows"] if r["case_id"] == observation["case_id"]
            )
            if inference["status"] != "monotone_source_radius":
                continue
            for profile, inv in inference["profiles"].items():
                for family, found in inv["families"].items():
                    for hypothesis, points in found[
                        "qualified_reception_points_by_hypothesis"
                    ].items():
                        checks = []
                        for point in points:
                            epoch = epoch_from_coordinate(float.fromhex(point), family)
                            state = exact_state(
                                run / "source-records",
                                case["window_index"],
                                epoch,
                                "Earth",
                            )
                            bounds = [
                                tube(
                                    v,
                                    plan["numerical_tube_profiles"][profile][
                                        "extra_binary64_ULPs"
                                    ],
                                )
                                for v in geo["printed_state"]
                            ]
                            flags = [a <= v <= b for v, (a, b) in zip(state, bounds)]
                            checks.append(
                                {
                                    "reception_hex": point,
                                    "source_components_match_geometry": flags,
                                    "same_argument_qualified": all(flags)
                                    and geo["original_label_budget_pass"],
                                }
                            )
                        output["clock_comparisons"].append(
                            {
                                "case_id": case["id"],
                                "role": case["role"],
                                "encoding": group["encoding"],
                                "profile": profile,
                                "coordinate_family": family,
                                "rounding_hypothesis": hypothesis,
                                "observer_receiver_points": points,
                                "geometric_label_budget_pass": geo[
                                    "original_label_budget_pass"
                                ],
                                "checks": checks,
                                "physical_or_internal_clock_identity_certified": False,
                            }
                        )
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--cohort", choices=("A", "B"), required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    save(args.output, analyze(args.run, args.cohort))


if __name__ == "__main__":
    main()
