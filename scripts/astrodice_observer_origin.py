"""Contract probes for an OBSERVER-native source clock, never calibration transfer."""

import argparse
import csv
import json
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_vector_clock import check_inputs, save
from scripts.verify_astrodice_earth_clock import wire


def classify(raw, status, query, plan):
    if status != 200:
        return {"status": "transport_unavailable", "HTTP_status": status}
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return {"status": "invalid_response"}
    if not isinstance(payload, dict):
        return {"status": "invalid_response"}
    if payload.get("error"):
        return {"status": "service_error", "service_error": str(payload["error"])}
    if not isinstance(payload.get("result"), str):
        return {"status": "invalid_response"}
    text = payload["result"]
    if text.count("$$SOE") != 1 or text.count("$$EOE") != 1:
        return {"status": "contract_unverified", "reason": "table_delimiters"}
    prefix, data = text.split("$$SOE")
    data, _ = data.split("$$EOE")
    origin = query["origin"]
    centers = {"SSB": r"Solar System Barycenter \(0\)", "Sun": r"Sun \(10\)"}
    if origin not in centers:
        raise ValueError("Undeclared observer origin")
    expressions = [
        r"Target body name: Earth.*?\(399\).*?DE441",
        "Center body name: " + centers[origin] + r".*?DE441",
        r"Calendar mode\s*:\s*Gregorian",
        r"Date__\(TT\)",
        r"JDTT",
        r"R\.A\._+\(ICRF\)",
        r"RA_\(ICRF-a-app\)",
        r"1-way_down_LT",
        r"delta,\s*deldot",
    ]
    if not all(re.search(e, prefix) for e in expressions):
        return {
            "status": "contract_unverified",
            "reason": "origin_target_time_or_quantities",
        }
    rows, seen = [], set()
    for values in csv.reader(data.strip().splitlines()):
        c = [v.strip() for v in values]
        if len(c) != 12 or c[-1]:
            return {"status": "contract_unverified", "reason": "quantity_columns"}
        try:
            finite = all(Decimal(v).is_finite() for v in c[4:11])
            stamp = Q(c[1])
        except (InvalidOperation, ValueError):
            return {"status": "contract_unverified", "reason": "nonnumeric_quantity"}
        if not finite:
            return {"status": "contract_unverified", "reason": "nonfinite_quantity"}
        matches = [
            case
            for case in query["cases"]
            if abs(stamp - Q(case["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(matches) != 1 or matches[0]["id"] in seen:
            return {"status": "contract_unverified", "reason": "row_identity"}
        case = matches[0]
        seen.add(case["id"])
        if (
            not 0 <= Q(c[4]) < 360
            or not -90 <= Q(c[5]) <= 90
            or Q(c[6]) <= 0
            or Q(c[8]) <= 0
        ):
            return {"status": "contract_unverified", "reason": "quantity_domain"}
        rows.append(
            {
                "case_id": case["id"],
                "role": case["role"],
                "nominal_JD_TT": case["nominal_JD"],
                "printed_JD_TT": c[1],
                "printed_calendar": c[0],
                "astrometric_angles": c[4:6],
                "range_AU": c[6],
                "radial_km_per_second": c[7],
                "light_time_minutes": c[8],
                "apparent_angles": c[9:11],
                "original_label_budget_pass": abs(Q(c[1]) - Q(case["nominal_JD"]))
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {c["id"] for c in query["cases"]}:
        return {"status": "contract_unverified", "reason": "incomplete_population"}
    return {
        "status": "supported",
        "rows": rows,
        "API_signature": payload.get("signature"),
        "physical_time_model_certified": False,
        "observer_origin_not_clock_transfer": True,
    }


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    results = []
    for query in plan["queries"]:
        if query["cohort"] != cohort:
            continue
        raw, receipt = wire(run, query)
        results.append(
            {
                "id": query["id"],
                "origin": query["origin"],
                "encoding": query["encoding"],
                **classify(raw, receipt["status"], query, plan),
            }
        )
    return {
        "cohort": cohort,
        "plan_sha256": digest,
        "queries": results,
        "new_candidate_holdouts": 0,
        "physical_time_model_certified": False,
        "OBSERVER_Earth_view_clock_equivalence_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--cohort", required=True, choices=("A", "B"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    save(args.output, analyze(args.run, args.cohort))


if __name__ == "__main__":
    main()
