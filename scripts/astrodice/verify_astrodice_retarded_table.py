"""Independent raw LT table, units and 288-bit relational replay.

Imports neither the LT table producer nor its 256-bit interval class. Relations
are computed independently, not inferred from producer diagnostic boxes.
"""

import argparse
import csv
import hashlib
import json
import re
import urllib.parse
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice.verify_astrodice_observer_clock import (
    add,
    cover,
    divide,
    length,
    mul,
    observed,
    observed_direction,
    rounded,
    sub,
)
from scripts.astrodice.verify_astrodice_observer_timescale import inspect

K = Q(149597870700, 299792458 * 86400)
AU_KM = Q("149597870.7")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(root, query):
    raw = (root / "responses" / (query["id"] + ".raw")).read_bytes()
    receipt = json.loads(
        (root / "responses" / (query["id"] + ".receipt.json")).read_text()
    )
    if (
        receipt["raw_sha256"] != digest(raw)
        or receipt["attempt"] != 1
        or receipt["verification_disabled"]
        or receipt["url"]
        != "https://ssd.jpl.nasa.gov/api/horizons.api?"
        + urllib.parse.urlencode(query["parameters"])
    ):
        raise ValueError("Raw response/query provenance changed")
    return raw, receipt


def parse_vectors(raw, query, cases, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("Service error")
    text = payload["result"]
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
            raise ValueError(
                "Independent correction/frame/time/column identity mismatch"
            )
    rows = []
    seen = set()
    for rawrow in csv.reader(body.strip().splitlines()):
        c = [v.strip() for v in rawrow]
        if len(c) != 12 or c[-1]:
            raise ValueError("LT vector columns changed")
        near = [
            v
            for v in cases
            if abs(Q(c[0]) - Q(v["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in seen:
            raise ValueError("Raw case binding differs")
        case = near[0]
        seen.add(case["id"])
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
                "original_label_budget_pass": abs(Q(c[0]) - Q(case["nominal_JD"]))
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {c["id"] for c in cases}:
        raise ValueError("Original case coverage reduced")
    return rows


def overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def independent_relations(vector, observer, ulps):
    def value(text):
        return rounded(*observed(text, ulps))

    state = list(map(value, vector["printed_state"]))
    distance = length(state[:3])
    if distance[0] <= 0:
        raise ValueError("Nonpositive LT distance")
    dot = rounded(0)
    for p, v in zip(state[:3], state[3:]):
        dot = add(dot, mul(p, v))
    projected = divide(dot, distance)
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
    obs_light = divide(value(observer["light_time_minutes"]), rounded(1440))
    unit = [divide(p, distance) for p in state[:3]]
    obs_direction = observed_direction(observer["astrometric_angles"], ulps)
    rate = mul(rr, rounded(AU_KM / 86400))
    projected_rate = mul(projected, rounded(AU_KM / 86400))
    fields = {
        "position_norm_AU": distance,
        "state_projection_AU_per_day": projected,
        "vector_minus_observer_range_meters": mul(
            sub(rg, obs_range), rounded(AU_KM * 1000)
        ),
        "vector_minus_observer_rate_millimeters_per_second": mul(
            sub(rate, obs_rate), rounded(1000000)
        ),
        "vector_LT_minus_RG_over_c_seconds": mul(
            sub(light, mul(rg, rounded(K))), rounded(86400)
        ),
        "vector_LT_minus_norm_over_c_seconds": mul(
            sub(light, mul(distance, rounded(K))), rounded(86400)
        ),
    }
    checks = {
        "vector_RG_matches_position_norm": overlap(rg, distance),
        "vector_LT_matches_norm_over_c": overlap(light, mul(distance, rounded(K))),
        "vector_LT_matches_RG_over_c": overlap(light, mul(rg, rounded(K))),
        "vector_RR_matches_state_projection": overlap(rr, projected),
        "observer_range_matches_vector_RG": overlap(obs_range, rg),
        "observer_range_matches_vector_position_norm": overlap(obs_range, distance),
        "observer_light_time_matches_vector_LT": overlap(obs_light, light),
        "observer_RR_matches_vector_RR": overlap(obs_rate, rate),
        "observer_RR_matches_state_projection": overlap(obs_rate, projected_rate),
        "observer_direction_components_match_LT_vector": [
            overlap(a, b) for a, b in zip(obs_direction, unit)
        ],
    }
    return fields, unit, obs_direction, checks


def verify(run, cohort):
    rawplan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(rawplan)
    before = json.loads((run / ("before-" + cohort + "-queries.json")).read_text())
    if cohort == "B" and before["prior_A_analysis_sha256"] != digest(
        (run / "A-first-analysis.json").read_bytes()
    ):
        raise ValueError("B lost A binding")
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
                "full_goal_complete",
            ]
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Table relations promoted to acceptance")
    cases = plan["cohorts"][cohort]
    queries = [
        q for q in plan["queries"] if q["cohort"] == cohort and q["kind"] == "LT_vector"
    ]
    if [g["query"] for g in data["groups"]] != [q["id"] for q in queries]:
        raise ValueError("Original LT table query omitted")
    summary = []
    scalar_enclosures = 0
    for query, group in zip(queries, data["groups"]):
        raw, receipt = wire(run, query)
        spec = plan["observer_bindings"][cohort][query["encoding"]]
        oq = spec["query"]
        oraw, oreceipt = wire(run / spec["root"], oq)
        keys = (
            "TIME_TYPE",
            "CAL_TYPE",
            "TIME_DIGITS",
            "CAL_FORMAT",
            "TLIST_TYPE",
            "TLIST",
        )
        if any(
            not isinstance(parameters.get(k), str) or not parameters[k].strip()
            for parameters in (oq["parameters"], query["parameters"])
            for k in keys
        ) or any(oq["parameters"][k] != query["parameters"][k] for k in keys):
            raise ValueError("Cross-batch table comparison")
        if (
            group["encoding"] != query["encoding"]
            or group["raw_sha256"] != digest(raw)
            or group["observation_raw_sha256"] != digest(oraw)
        ):
            raise ValueError("Actual table binding differs")
        obs = inspect(oraw, oreceipt["status"], oq, cases, plan)
        try:
            if receipt["status"] != 200 or obs["status"] != "supported":
                raise ValueError("Unavailable table")
            rows = parse_vectors(raw, query, cases, plan)
        except (ValueError, KeyError, TypeError):
            if group["status"] != "unavailable_or_contract_unverified":
                raise ValueError("Unavailable table promoted")
            summary.append({"query": query["id"], "status": group["status"]})
            continue
        if group["status"] != "diagnosed" or len(rows) != len(group["rows"]):
            raise ValueError("Valid raw table lost rows or unproved analysis error")
        lookup = {r["case_id"]: r for r in obs["rows"]}
        counts = {p: {} for p in plan["numerical_tube_profiles"]}
        primary = 0
        for vector, record in zip(rows, group["rows"]):
            observer = lookup[vector["case_id"]]
            if (
                record["vector"] != vector
                or record["observer"] != observer
                or set(record["profiles"]) != set(plan["numerical_tube_profiles"])
            ):
                raise ValueError(
                    "Original values, roles, profiles or label line changed"
                )
            selected = vector["role"] != "auxiliary_not_primary"
            primary += selected
            for profile, settings in plan["numerical_tube_profiles"].items():
                stored = record["profiles"][profile]
                fields, unit, obs_direction, checks = independent_relations(
                    vector, observer, settings["extra_binary64_ULPs"]
                )
                for name, computed in fields.items():
                    cover(computed, stored[name])
                    scalar_enclosures += 1
                for computed, declared in zip(unit, stored["vector_unit_direction"]):
                    cover(computed, declared)
                    scalar_enclosures += 1
                for computed, declared in zip(
                    obs_direction, stored["observed_unit_direction"]
                ):
                    cover(computed, declared)
                    scalar_enclosures += 1
                if (
                    stored["checks"] != checks
                    or stored[
                        "physical_internal_algorithm_or_velocity_derivative_certified"
                    ]
                ):
                    raise ValueError(
                        "Independent relational predicate or physical scope differs"
                    )
                if selected:
                    for name, v in checks.items():
                        counts[profile][name] = counts[profile].get(name, 0) + (
                            all(v) if isinstance(v, list) else v
                        )
        summary.append({"query": query["id"], "primary": primary, "profiles": counts})
    return {
        "method": "independent_raw_units_and_288bit_LT_table_relations_v1",
        "cohort": cohort,
        "analysis_sha256": digest(rawanalysis),
        "groups": summary,
        "scalar_enclosures_checked": scalar_enclosures,
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
