"""Conditional transfer from a geometric TT clock to OBSERVER quantities.

Maintenance evidence only. No candidate imports; no calibration, source model
or numerical allowance here certifies the service's internal physical clock.
"""

import argparse
import csv
import json
import math
import re
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import A, I, Reader
from scripts.astrodice_source_slope_bounds import pi_bounds
from scripts.astrodice_vector_clock import check_inputs, save, sha, tube

LIGHT_DAYS_PER_AU = Q(149597870700, 299792458 * 86400)


def box(value):
    return list(map(str, value.bounds()))


def interval(bounds):
    return I(*map(Q, bounds))


def norm(values):
    return sum((v.square() for v in values), I()).sqrt()


def state(reader, epoch, body):
    return [v.v for v in reader.state(A(epoch), body)]


def subtract(a, b):
    return [x - y for x, y in zip(a, b)]


def emission_budget(t, initial_delay, ulps):
    if ulps not in (0, 1):
        raise ValueError("Unplanned emission argument hypothesis")
    low, high = t.bounds()
    et = [(v - 2451545) * 86400 for v in (low - initial_delay, high)]
    return ulps * max(Q(math.ulp(float(v))) for v in et) / 86400


def trig_point(angle_degrees, terms):
    """Point sine/cosine with rigorous Taylor tails and a Machin pi interval."""
    if abs(angle_degrees) > 360 or terms != 80:
        raise ValueError("Unplanned trigonometric domain or order")
    x = angle_degrees * I(*pi_bounds()) / 180
    sn, cs = I(), I()
    sin_term, cos_term = x, I(1)
    square = -x.square()
    for k in range(terms):
        if k:
            sin_term = sin_term * square / ((2 * k) * (2 * k + 1))
            cos_term = cos_term * square / ((2 * k - 1) * (2 * k))
        sn, cs = sn + sin_term, cs + cos_term
    # |x|<7. Use Lagrange tails, independent of any alternating-tail shortcut.
    s_tail = Q(7) ** (2 * terms + 1) / math.factorial(2 * terms + 1)
    c_tail = Q(7) ** (2 * terms) / math.factorial(2 * terms)
    return sn + I(-s_tail, s_tail), cs + I(-c_tail, c_tail)


def observed_direction(angles, ulps, terms):
    if not 0 <= Q(angles[0]) < 360 or not -90 <= Q(angles[1]) <= 90:
        raise ValueError("Observed astrometric RA/DEC outside their domains")
    pairs = []
    for printed in angles:
        center = Q(printed)
        low, high = tube(printed, ulps)
        sn, cs = trig_point(center, terms)
        radius = max(center - low, high - center) * pi_bounds()[1] / 180
        pairs.append((sn + I(-radius, radius), cs + I(-radius, radius)))
    (sa, ca), (sd, cd) = pairs
    return [cd * ca, cd * sa, sd]


def forward(reader, reception, model, plan):
    initial = Q(plan["light_time_initial_interval_days"][1])
    earth = state(reader, reception, "Earth")[:3]
    history = []
    epsilon = Q(0)
    q_upper = None
    if model == "legacy_two_linearized_delays":
        now = state(reader, reception, "Venus")
        rough = now[:3]
        delay = I()
        for _ in range(2):
            delay = norm(subtract(rough, earth)) * LIGHT_DAYS_PER_AU
            history.append({"delay_days": box(delay)})
            rough = [p - v * delay for p, v in zip(now[:3], now[3:])]
    elif model in {
        "converged_Newtonian_24",
        "converged_Newtonian_24_emission_ET_ULP_hypothesis",
    }:
        if model.endswith("ULP_hypothesis"):
            epsilon = emission_budget(
                reception, initial, plan["emission_error_full_binary64_ET_ULPs"]
            )
        broad = state(reader, reception - I(0, initial) + I(-epsilon, epsilon), "Venus")
        q_upper = norm(broad[3:]).absolute_upper() * LIGHT_DAYS_PER_AU
        if q_upper >= 1:
            raise ValueError("Declared light-time family is not contractive")
        delay = I(0, initial)
        for _ in range(plan["fixed_point_iterations"]):
            emitted = state(reader, reception - delay + I(-epsilon, epsilon), "Venus")
            image = norm(subtract(emitted[:3], earth)) * LIGHT_DAYS_PER_AU
            lo, hi = image.bounds()
            if not 0 <= lo <= hi <= initial:
                raise ValueError("Source light-time image leaves fixed initial support")
            old_low, old_high = delay.bounds()
            updated = I(max(old_low, lo), min(old_high, hi))
            history.append(
                {
                    "input_days": box(delay),
                    "image_days": box(image),
                    "next_days": box(updated),
                }
            )
            delay = updated
    else:
        raise ValueError("Unplanned source light-time model")
    emitted = state(reader, reception - delay + I(-epsilon, epsilon), "Venus")
    ray = subtract(emitted[:3], earth)
    distance = norm(ray)
    direction = [v / distance for v in ray]
    return {
        "range_AU": box(distance),
        "light_time_minutes": box(delay * 1440),
        "direction_ICRF": [box(v) for v in direction],
        "history": history,
        "emission_argument_radius_days": str(epsilon),
        "continuous_family_contraction_upper": (
            str(q_upper) if q_upper is not None else None
        ),
        "internal_iteration_algorithm_certified": False,
    }


def parse_observer(raw, query, cases, plan):
    data = json.loads(raw)
    if data.get("error"):
        raise ValueError("Horizons service error: " + str(data["error"]))
    text = data["result"]
    if text.count("$$SOE") != 1 or text.count("$$EOE") != 1:
        raise ValueError("Missing/duplicate OBSERVER delimiters")
    prefix, body = text.split("$$SOE")
    body, _ = body.split("$$EOE")
    patterns = [
        r"Target body name: Venus.*?\(299\).*?DE441",
        r"Center body name: Earth \(399\).*?DE441",
        r"Date__\(TT\)",
        r"Calendar mode\s*:\s*Gregorian",
        r"R\.A\._+\(ICRF\)",
        r"RA_\(ICRF-a-app\)",
        r"1-way_down_LT",
        r"delta,\s*deldot",
    ]
    if not all(re.search(p, prefix) for p in patterns):
        raise ValueError("OBSERVER source, clock, frame or quantity contract differs")
    rows, seen = [], set()
    for cells in csv.reader(body.strip().splitlines()):
        cells = [v.strip() for v in cells]
        if len(cells) != 12 or cells[-1]:
            raise ValueError("OBSERVER quantity column contract differs")
        epoch = Q(cells[1])
        near = [
            c
            for c in cases
            if abs(epoch - Q(c["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in seen:
            raise ValueError("Ambiguous/missing/duplicate OBSERVER case")
        if not all(math.isfinite(float(v)) for v in cells[4:11]):
            raise ValueError("Nonfinite OBSERVER quantity")
        case = near[0]
        seen.add(case["id"])
        error = epoch - Q(case["nominal_JD"])
        rows.append(
            {
                "case_id": case["id"],
                "role": case["role"],
                "printed_JD": cells[1],
                "printed_calendar": cells[0],
                "astrometric_angles": cells[4:6],
                "range_AU": cells[6],
                "deldot_km_per_second": cells[7],
                "light_time_minutes": cells[8],
                "apparent_angles": cells[9:11],
                "label_error_seconds": str(error * 86400),
                "original_label_budget_pass": abs(error)
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {c["id"] for c in cases}:
        raise ValueError("OBSERVER planned population incomplete")
    return rows


def overlaps(a, b):
    x, y = a.bounds()
    u, v = b.bounds()
    return x <= v and u <= y


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    calibration_path = run / (
        "vector-controls/A-first-analysis.json"
        if cohort == "A"
        else "B-vector-calibration/B-first-analysis.json"
    )
    calibrations = json.loads(calibration_path.read_text())
    cal_queries = {q["id"]: q for q in calibrations["queries"]}
    cases = {c["id"]: c for c in plan["cohorts"][cohort]}
    result = {
        "plan_sha256": digest,
        "calibration_sha256": sha(calibration_path.read_bytes()),
        "cohort": cohort,
        "queries": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "TT_observer_clock_equivalence_certified": False,
        "physical_time_model_certified": False,
        "numerical_tubes_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for query in plan["queries"]:
        if query["cohort"] != cohort:
            continue
        raw = (run / "responses" / (query["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (run / "responses" / (query["id"] + ".receipt.json")).read_text()
        )
        output = {"id": query["id"], "raw_sha256": sha(raw), "rows": []}
        if output["raw_sha256"] != receipt["raw_sha256"]:
            raise ValueError("Raw OBSERVER response drift")
        try:
            if receipt["status"] != 200:
                raise ValueError(
                    "Unavailable OBSERVER response: " + str(receipt["status"])
                )
            rows = parse_observer(raw, query, list(cases.values()), plan)
            calibration = cal_queries[query["id"]]
            if calibration["status"] != "diagnosed":
                raise ValueError("Geometric calibration unavailable")
            lookup = {v["case_id"]: v for v in calibration["rows"]}
            for row in rows:
                case = cases[row["case_id"]]
                cal = lookup[row["case_id"]]
                row.update(
                    calibration_original_label_pass=cal["original_label_budget_pass"],
                    profiles={},
                )
                for profile, settings in plan["numerical_tube_profiles"].items():
                    c = cal["profiles"][profile]
                    entry = {
                        "calibration_all_six_not_refuted": c.get(
                            "all_six_compatible", False
                        ),
                        "models": {},
                    }
                    if c["status"] != "bracketed":
                        entry.update(status="calibration_unknown")
                        row["profiles"][profile] = entry
                        continue
                    reception = interval(c["effective_JD"])
                    entry["reception_JD_TDB"] = c["effective_JD"]
                    observed = {
                        "range_AU": I(
                            *tube(row["range_AU"], settings["extra_binary64_ULPs"])
                        ),
                        "light_time_minutes": I(
                            *tube(
                                row["light_time_minutes"],
                                settings["extra_binary64_ULPs"],
                            )
                        ),
                    }
                    direction = observed_direction(
                        row["astrometric_angles"],
                        settings["extra_binary64_ULPs"],
                        plan["interval_trig_terms"],
                    )
                    entry.update(
                        observed_bounds={k: box(v) for k, v in observed.items()},
                        observed_direction_ICRF=[box(v) for v in direction],
                    )
                    for model in plan["source_models"]:
                        try:
                            reader = Reader(
                                run / "source-records", case["window_index"]
                            )
                            computed = forward(reader, reception, model, plan)
                            checked = {
                                k: overlaps(interval(computed[k]), v)
                                for k, v in observed.items()
                            }
                            checked["astrometric_direction_components"] = [
                                overlaps(interval(v), obs)
                                for v, obs in zip(computed["direction_ICRF"], direction)
                            ]
                            computed.update(
                                checks=checked,
                                all_selected_observables_not_refuted=checked["range_AU"]
                                and checked["light_time_minutes"]
                                and all(checked["astrometric_direction_components"]),
                                deldot_not_assessed=True,
                                apparent_angles_not_assessed=True,
                            )
                            entry["models"][model] = computed
                        except (ValueError, StopIteration) as error:
                            entry["models"][model] = {
                                "status": "source_model_unknown",
                                "error": repr(error),
                            }
                    row["profiles"][profile] = entry
                output["rows"].append(row)
            output["status"] = "diagnosed"
        except (ValueError, KeyError) as error:
            output.update(status="unavailable_or_invalid", error=repr(error))
        result["queries"].append(output)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    args = parser.parse_args()
    save(
        args.run / (args.cohort + "-first-analysis.json"),
        analyze(args.run, args.cohort),
    )
