"""Compare LT vector-table algebra and matching-batch OBSERVER quantities.

Maintenance relational evidence, not a certified source clock or candidate
accuracy. Printed-state velocity semantics are tested, not assumed identical.
"""

import argparse
import csv
import json
import math
import re
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_batch_binding import require_matching_time_batches
from scripts.astrodice_clock_interval import I
from scripts.astrodice_observer_clock import box, norm, observed_direction
from scripts.astrodice_observer_timescale import classify
from scripts.astrodice_vector_clock import check_inputs, save, sha, tube

K = Q(149597870700, 299792458 * 86400)
AU_KM = Q("149597870.7")


def parse(raw, query, cases, plan):
    data = json.loads(raw)
    if data.get("error"):
        raise ValueError("Service error: " + str(data["error"]))
    text = data["result"]
    prefix, body = text.split("$$SOE")
    body, _ = body.split("$$EOE")
    for pattern in [
        r"Target body name: Venus.*?\(299\).*?DE441",
        r"Center body name: Earth \(399\).*?DE441",
        r"Output units\s*:\s*AU-D",
        r"Reference frame\s*:\s*ICRF",
        r"Output type\s*:\s*LT CORRECTED cartesian states",
        r"Calendar mode\s*:\s*Gregorian",
        r"JDTT",
        r"\bLT\s*,\s*RG\s*,\s*RR\s*,",
    ]:
        if not re.search(pattern, prefix):
            raise ValueError("LT vector identity/units/time/column header changed")
    rows = []
    seen = set()
    for cells in csv.reader(body.strip().splitlines()):
        c = [v.strip() for v in cells]
        if (
            len(c) != 12
            or c[-1]
            or not all(math.isfinite(float(v)) for v in c[:1] + c[2:11])
        ):
            raise ValueError("Nonfinite or unplanned LT vector columns")
        near = [
            x
            for x in cases
            if abs(Q(c[0]) - Q(x["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in seen:
            raise ValueError("Ambiguous LT vector row")
        case = near[0]
        seen.add(case["id"])
        error = Q(c[0]) - Q(case["nominal_JD"])
        rows.append(
            {
                "case_id": case["id"],
                "role": case["role"],
                "nominal_JD": case["nominal_JD"],
                "printed_JD": c[0],
                "printed_calendar": c[1],
                "printed_state": c[2:8],
                "light_time_days": c[8],
                "range_AU": c[9],
                "range_rate_AU_per_day": c[10],
                "original_label_budget_pass": abs(error)
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {c["id"] for c in cases}:
        raise ValueError("Original LT vector cases missing")
    return rows


def overlap(a, b):
    x, y = a.bounds()
    u, v = b.bounds()
    return x <= v and u <= y


def compare(vector, observer, profile, plan):
    ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]

    def value(s):
        return I(*tube(s, ulps))

    states = list(map(value, vector["printed_state"]))
    distance = norm(states[:3])
    if distance.bounds()[0] <= 0:
        raise ValueError("Nonpositive LT vector distance")
    projection = sum((p * v for p, v in zip(states[:3], states[3:])), I()) / distance
    light, rg, rr = map(
        value,
        [
            vector["light_time_days"],
            vector["range_AU"],
            vector["range_rate_AU_per_day"],
        ],
    )
    obs_range = value(observer["range_AU"])
    obs_rate = value(observer["deldot_km_per_second"])
    obs_light = value(observer["light_time_minutes"]) / 1440
    direction = observed_direction(
        observer["astrometric_angles"], ulps, plan["interval_trig_terms"]
    )
    unit = [x / distance for x in states[:3]]
    checks = {
        "vector_RG_matches_position_norm": overlap(rg, distance),
        "vector_LT_matches_norm_over_c": overlap(light, distance * K),
        "vector_LT_matches_RG_over_c": overlap(light, rg * K),
        "vector_RR_matches_state_projection": overlap(rr, projection),
        "observer_range_matches_vector_RG": overlap(obs_range, rg),
        "observer_range_matches_vector_position_norm": overlap(obs_range, distance),
        "observer_light_time_matches_vector_LT": overlap(obs_light, light),
        "observer_RR_matches_vector_RR": overlap(obs_rate, rr * AU_KM / 86400),
        "observer_RR_matches_state_projection": overlap(
            obs_rate, projection * AU_KM / 86400
        ),
        "observer_direction_components_match_LT_vector": [
            overlap(x, y) for x, y in zip(direction, unit)
        ],
    }
    return {
        "position_norm_AU": box(distance),
        "state_projection_AU_per_day": box(projection),
        "vector_unit_direction": [box(x) for x in unit],
        "observed_unit_direction": [box(x) for x in direction],
        "vector_minus_observer_range_meters": box((rg - obs_range) * AU_KM * 1000),
        "vector_minus_observer_rate_millimeters_per_second": box(
            (rr * AU_KM / 86400 - obs_rate) * 1000000
        ),
        "vector_LT_minus_RG_over_c_seconds": box((light - rg * K) * 86400),
        "vector_LT_minus_norm_over_c_seconds": box((light - distance * K) * 86400),
        "checks": checks,
        "physical_internal_algorithm_or_velocity_derivative_certified": False,
    }


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    result = {
        "plan_sha256": digest,
        "cohort": cohort,
        "groups": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "numerical_tubes_certified": False,
        "physical_time_model_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    cases = plan["cohorts"][cohort]
    for query in plan["queries"]:
        if query["cohort"] != cohort or query["kind"] != "LT_vector":
            continue
        raw = (run / "responses" / (query["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (run / "responses" / (query["id"] + ".receipt.json")).read_text()
        )
        group = {
            "query": query["id"],
            "encoding": query["encoding"],
            "raw_sha256": sha(raw),
            "rows": [],
        }
        if sha(raw) != receipt["raw_sha256"]:
            raise ValueError("Original vector changed")
        spec = plan["observer_bindings"][cohort][query["encoding"]]
        oq = spec["query"]
        obsroot = run / spec["root"]
        oraw = (obsroot / "responses" / (oq["id"] + ".raw")).read_bytes()
        oreceipt = json.loads(
            (obsroot / "responses" / (oq["id"] + ".receipt.json")).read_text()
        )
        require_matching_time_batches(oq, query)
        if sha(oraw) != oreceipt["raw_sha256"]:
            raise ValueError("Original observation changed")
        group["observation_raw_sha256"] = sha(oraw)
        obs = classify(oraw, oreceipt["status"], oq, cases, plan)
        try:
            if receipt["status"] != 200 or obs["status"] != "supported":
                raise ValueError("Unavailable vector or observation")
            rows = parse(raw, query, cases, plan)
            lookup = {r["case_id"]: r for r in obs["rows"]}
            for row in rows:
                observed = lookup[row["case_id"]]
                group["rows"].append(
                    {
                        "vector": row,
                        "observer": observed,
                        "profiles": {
                            p: compare(row, observed, p, plan)
                            for p in plan["numerical_tube_profiles"]
                        },
                    }
                )
            group["status"] = "diagnosed"
        except (ValueError, KeyError, TypeError) as error:
            group.update(status="unavailable_or_contract_unverified", error=repr(error))
        result["groups"].append(group)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    a = p.parse_args()
    save(a.run / (a.cohort + "-first-analysis.json"), analyze(a.run, a.cohort))
