"""Audit actual OBSERVER time contracts and quantity-30/state-clock relations.

The current-leap hold is an explicit extrapolation hypothesis, not future UTC
or a certified internal-clock bound. Refusal, unknown and support stay distinct.
"""

import argparse
import csv
import json
import math
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from fractions import Fraction as Q
from pathlib import Path

import certifi

from scripts.astrodice_horizons_transport import open_horizons
from scripts.astrodice_vector_clock import check_inputs, save, sha, tube


def parse_observer(raw, query, cases, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("Service error: " + str(payload["error"]))
    text = payload["result"]
    if text.count("$$SOE") != 1 or text.count("$$EOE") != 1:
        raise ValueError("Missing/duplicate table delimiters")
    prefix, body = text.split("$$SOE")
    body, _ = body.split("$$EOE")
    tt = query["time_type"]
    patterns = [
        r"Target body name: Venus.*?\(299\).*?DE441",
        r"Center body name: Earth \(399\).*?DE441",
        r"Calendar mode\s*:\s*Gregorian",
        r"R\.A\._+\(ICRF\)",
        r"RA_\(ICRF-a-app\)",
        r"1-way_down_LT",
        r"TDB-UT",
        rf"Date__\({tt}\)",
        r"JD" + tt,
    ]
    if not all(re.search(p, prefix) for p in patterns):
        raise ValueError("Returned time/frame/quantity header mismatch")
    eop = re.search(r"^EOP file\s*:\s*(.+)$", prefix, re.M)
    coverage = re.search(r"^EOP coverage\s*:\s*(.+)$", prefix, re.M)
    rows = []
    seen = set()
    for c in csv.reader(body.strip().splitlines()):
        c = [v.strip() for v in c]
        if len(c) != 13 or c[-1]:
            raise ValueError("Quantity column contract changed")
        epoch = Q(c[1])
        near = [
            v
            for v in cases
            if abs(epoch - Q(v["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in seen:
            raise ValueError("Ambiguous/duplicate/unassigned row")
        case = near[0]
        seen.add(case["id"])
        if not all(math.isfinite(float(v)) for v in c[4:9] + c[10:12]):
            raise ValueError("Nonfinite position/range")
        delta = None if c[9].lower() in {"n.a.", "n/a"} else c[9]
        if delta is not None and not math.isfinite(float(delta)):
            raise ValueError("Nonfinite TDB-UT")
        error = epoch - Q(case["nominal_JD"])
        rows.append(
            {
                "case_id": case["id"],
                "role": case["role"],
                "nominal_JD": case["nominal_JD"],
                "printed_JD": c[1],
                "printed_calendar": c[0],
                "astrometric_angles": c[4:6],
                "range_AU": c[6],
                "deldot_km_per_second": c[7],
                "light_time_minutes": c[8],
                "TDB_minus_UT_seconds": delta,
                "apparent_angles": c[10:12],
                "label_error_seconds": str(error * 86400),
                "original_label_budget_pass": abs(error)
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {c["id"] for c in cases}:
        raise ValueError("Missing original cases")
    return {
        "rows": rows,
        "EOP_file": eop[1].strip() if eop else None,
        "EOP_coverage": coverage[1].strip() if coverage else None,
        "API_signature": payload.get("signature"),
        "actual_time_type": tt,
    }


def classify(raw, status, query, cases, plan):
    if status != 200:
        return {"status": "transport_unavailable", "http_status": status}
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return {"status": "invalid_response"}
    if not isinstance(payload, dict):
        return {"status": "invalid_response"}
    if payload.get("error"):
        message = str(payload["error"])
        explicit = re.search(
            r"(?:only.*(?:UT.*TT|TT.*UT)|(?:invalid|illegal|unsupported|not allowed).*(?:TIME_TYPE|time scale|TDB)|(?:TIME_TYPE|TDB).*(?:invalid|illegal|unsupported|not allowed|cannot))",
            message,
            re.I | re.S,
        )
        return {
            "status": "service_refused" if explicit else "service_error_unclassified",
            "service_error": message,
        }
    if not isinstance(payload.get("result"), str):
        return {"status": "invalid_response"}
    try:
        return {"status": "supported", **parse_observer(raw, query, cases, plan)}
    except (ValueError, KeyError) as error:
        return {"status": "contract_unverified", "error": repr(error)}


def selected_queries(plan, cohort, A=None):
    allow = cohort == "A" or A["TDB_OBSERVER_contract_status"] == "supported"
    return [
        (q, not q["conditional_on_A_TDB_support"] or allow)
        for q in plan["queries"]
        if q["cohort"] == cohort
    ]


def collect(run, cohort):
    plan, plan_hash = check_inputs(run)
    A = (
        json.loads((run / "A-first-analysis.json").read_text())
        if cohort == "B"
        else None
    )
    before = {
        "cohort": cohort,
        "plan_sha256": plan_hash,
        "collector_sha256": sha(Path(__file__).read_bytes()),
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "prior_A_analysis_sha256": (
            sha((run / "A-first-analysis.json").read_bytes()) if A else None
        ),
    }
    save(run / ("before-" + cohort + "-queries.json"), before)
    material = run / "responses"
    material.mkdir(exist_ok=True)
    context = ssl.create_default_context(cafile=certifi.where())
    receipts = []
    for query, dispatch in selected_queries(plan, cohort, A):
        if not dispatch:
            receipts.append(
                {
                    "id": query["id"],
                    "status": "not_dispatched_A_contract_unverified",
                    "A_TDB_status": A["TDB_OBSERVER_contract_status"],
                }
            )
            continue
        url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(
            query["parameters"]
        )
        if len(url.encode()) > plan["maximum_url_bytes"]:
            raise ValueError("Frozen URL exceeds budget")
        receipt = {"id": query["id"], "url": url, "attempt": 1}
        try:
            with open_horizons(
                urllib.request.Request(url),
                context=context,
                timeout=40,
                receipt=receipt,
            ) as response:
                raw = response.read()
                receipt.update(status=response.status, headers=dict(response.headers))
        except urllib.error.HTTPError as error:
            raw = error.read()
            receipt.update(
                status=error.code, headers=dict(error.headers), error=repr(error)
            )
        except (OSError, urllib.error.URLError) as error:
            raw = b""
            receipt.update(status=None, error=repr(error))
        with (material / (query["id"] + ".raw")).open("xb") as out:
            out.write(raw)
        receipt.update(raw_sha256=sha(raw), raw_bytes=len(raw))
        save(material / (query["id"] + ".receipt.json"), receipt)
        receipts.append(receipt)
        print(query["id"], receipt["status"], len(raw), flush=True)
    save(run / (cohort + "-collection.json"), {**before, "receipts": receipts})


def overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def compare_field(row, TT, TDB, profile, plan):
    left = TT["profiles"][profile]
    right = TDB["profiles"][profile]
    entry = {
        "TT_geometric_six_not_refuted": left.get("all_six_compatible", False),
        "TDB_geometric_six_not_refuted": right.get("all_six_compatible", False),
    }
    if left["status"] != "bracketed" or right["status"] != "bracketed":
        return {**entry, "status": "state_clock_unknown"}
    a, b = map(Q, left["effective_JD"])
    c, d = map(Q, right["effective_JD"])
    nominal = Q(row["nominal_JD"])
    absolute = ((a - nominal) * 86400, (b - nominal) * 86400)
    difference = ((a - d) * 86400, (b - c) * 86400)
    entry.update(
        TT_state_minus_nominal_seconds=list(map(str, absolute)),
        TT_minus_TDB_state_seconds=list(map(str, difference)),
    )
    if nominal < Q(plan["quantity30_modern_cutoff_JD"]):
        return {**entry, "status": "not_assessed_pre_1962"}
    if row["TDB_minus_UT_seconds"] is None:
        return {**entry, "status": "time_field_unavailable"}
    bounds = tube(
        row["TDB_minus_UT_seconds"],
        plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"],
    )
    hold = Q(plan["future_current_leap_hold_hypothesis_seconds"])
    field = (bounds[0] - hold, bounds[1] - hold)
    entry.update(
        status="conditional_leap_hold_comparison",
        reported_TDB_minus_TT_hypothesis_seconds=list(map(str, field)),
        overlap_nominal_state=overlap(field, absolute),
        overlap_paired_state=overlap(field, difference),
        field_minus_nominal_state_seconds=[
            str(field[0] - absolute[1]),
            str(field[1] - absolute[0]),
        ],
        field_minus_paired_state_seconds=[
            str(field[0] - difference[1]),
            str(field[1] - difference[0]),
        ],
        time_field_is_internal_clock_bound_certified=False,
    )
    return entry


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    A = (
        json.loads((run / "A-first-analysis.json").read_text())
        if cohort == "B"
        else None
    )
    cal_path = run / "vector-calibration" / (cohort + "-first-analysis.json")
    geometry = json.loads(cal_path.read_text())
    cal = {q["id"]: q for q in geometry["queries"]}
    collection = json.loads((run / (cohort + "-collection.json")).read_text())
    receipts = {v["id"]: v for v in collection["receipts"]}
    out = {
        "plan_sha256": digest,
        "cohort": cohort,
        "geometry_analysis_sha256": sha(cal_path.read_bytes()),
        "observer_queries": [],
        "clock_rows": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "physical_time_model_certified": False,
        "numerical_tubes_certified": False,
        "TT_OBSERVER_vector_clock_equivalence_certified": False,
        "full_goal_complete": False,
    }
    for query, dispatch in selected_queries(plan, cohort, A):
        receipt = receipts[query["id"]]
        if not dispatch:
            out["observer_queries"].append(
                {
                    "id": query["id"],
                    "status": "not_dispatched_A_contract_unverified",
                    "A_TDB_status": A["TDB_OBSERVER_contract_status"],
                }
            )
            continue
        raw = (run / "responses" / (query["id"] + ".raw")).read_bytes()
        if sha(raw) != receipt["raw_sha256"]:
            raise ValueError("Raw response changed")
        parsed = classify(raw, receipt["status"], query, plan["cohorts"][cohort], plan)
        entry = {
            "id": query["id"],
            "time_type": query["time_type"],
            "encoding": query["encoding"],
            "raw_sha256": sha(raw),
            **parsed,
        }
        out["observer_queries"].append(entry)
        if query["time_type"] != "TT" or parsed["status"] != "supported":
            continue
        tt = cal.get(query["id"])
        tdb = cal.get(cohort + "-TDB-" + query["encoding"])
        if (
            tt is None
            or tdb is None
            or tt["status"] != "diagnosed"
            or tdb["status"] != "diagnosed"
        ):
            continue
        ttrows = {v["case_id"]: v for v in tt["rows"]}
        tdbrows = {v["case_id"]: v for v in tdb["rows"]}
        for row in parsed["rows"]:
            item = {
                "query": query["id"],
                "case_id": row["case_id"],
                "role": row["role"],
                "TDB_minus_UT_seconds": row["TDB_minus_UT_seconds"],
                "original_label_budget_pass": row["original_label_budget_pass"],
                "EOP_file": parsed["EOP_file"],
                "profiles": {},
            }
            for p in plan["numerical_tube_profiles"]:
                item["profiles"][p] = compare_field(
                    row, ttrows[row["case_id"]], tdbrows[row["case_id"]], p, plan
                )
            out["clock_rows"].append(item)
    out["TDB_OBSERVER_contract_status"] = (
        next(v["status"] for v in out["observer_queries"] if v["time_type"] == "TDB")
        if cohort == "A"
        else A["TDB_OBSERVER_contract_status"]
    )
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["collect", "analyze"])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    args = parser.parse_args()
    if args.action == "collect":
        collect(args.run, args.cohort)
    else:
        save(
            args.run / (args.cohort + "-first-analysis.json"),
            analyze(args.run, args.cohort),
        )
