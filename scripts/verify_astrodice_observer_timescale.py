"""Independent raw-contract and exact-rational quantity-30 clock replay.

Imports no OBSERVER collector/analyzer. The geometric source arguments are
independently checked by the earlier direct-basis/Bernstein verifier.
"""

import argparse
import csv
import hashlib
import json
import re
import urllib.parse
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_vector_clock import (
    observed_bounds,
)
from scripts.verify_astrodice_vector_clock import verify as verify_vector


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect(raw, status, query, cases, plan):
    if status != 200:
        return {"status": "transport_unavailable", "http_status": status}
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return {"status": "invalid_response"}
    if not isinstance(payload, dict):
        return {"status": "invalid_response"}
    if payload.get("error"):
        text = str(payload["error"])
        refused = all(
            word in text.lower() for word in ("only", "ut", "tt", "allowed", "observer")
        )
        return {
            "status": "service_refused" if refused else "service_error_unclassified",
            "service_error": text,
        }
    text = payload.get("result")
    if not isinstance(text, str):
        return {"status": "invalid_response"}
    if text.count("$$SOE") != 1 or text.count("$$EOE") != 1:
        return {"status": "contract_unverified"}
    prefix, body = text.split("$$SOE")
    body, _ = body.split("$$EOE")
    tt = query["time_type"]
    patterns = [
        r"Target body name: Venus.*?\(299\).*?DE441",
        r"Center body name: Earth \(399\).*?DE441",
        r"Calendar mode\s*:\s*Gregorian",
        rf"Date__\({tt}\)",
        r"JD" + tt,
        r"R\.A\._+\(ICRF\)",
        r"RA_\(ICRF-a-app\)",
        r"1-way_down_LT",
        r"TDB-UT",
    ]
    if not all(re.search(p, prefix) for p in patterns):
        return {"status": "contract_unverified"}
    rows = []
    seen = set()
    for rawrow in csv.reader(body.strip().splitlines()):
        cells = [v.strip() for v in rawrow]
        if len(cells) != 13 or cells[-1]:
            raise ValueError("Independent quantity column identity differs")
        epoch = Q(cells[1])
        near = [
            c
            for c in cases
            if abs(epoch - Q(c["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in seen:
            raise ValueError("Independent raw row assignment failed")
        case = near[0]
        seen.add(case["id"])
        error = epoch - Q(case["nominal_JD"])
        rows.append(
            {
                "case_id": case["id"],
                "role": case["role"],
                "nominal_JD": case["nominal_JD"],
                "printed_JD": cells[1],
                "printed_calendar": cells[0],
                "astrometric_angles": cells[4:6],
                "range_AU": cells[6],
                "deldot_km_per_second": cells[7],
                "light_time_minutes": cells[8],
                "TDB_minus_UT_seconds": (
                    None if cells[9].lower() in {"n.a.", "n/a"} else cells[9]
                ),
                "apparent_angles": cells[10:12],
                "label_error_seconds": str(error * 86400),
                "original_label_budget_pass": abs(error)
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {c["id"] for c in cases}:
        raise ValueError("Original cases missing")

    def header(pattern):
        match = re.search(pattern, prefix, re.M)
        return match[1].strip() if match else None

    return {
        "status": "supported",
        "rows": rows,
        "EOP_file": header(r"^EOP file\s*:\s*(.+)$"),
        "EOP_coverage": header(r"^EOP coverage\s*:\s*(.+)$"),
        "API_signature": payload.get("signature"),
        "actual_time_type": tt,
    }


def overlaps(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def expected_clock(row, TT, TDB, profile, plan):
    left, right = TT["profiles"][profile], TDB["profiles"][profile]
    value = {
        "TT_geometric_six_not_refuted": left.get("all_six_compatible", False),
        "TDB_geometric_six_not_refuted": right.get("all_six_compatible", False),
    }
    if left["status"] != "bracketed" or right["status"] != "bracketed":
        return {**value, "status": "state_clock_unknown"}
    tlo, thi = map(Q, left["effective_JD"])
    dlo, dhi = map(Q, right["effective_JD"])
    label = Q(row["nominal_JD"])
    nominal = ((tlo - label) * 86400, (thi - label) * 86400)
    paired = ((tlo - dhi) * 86400, (thi - dlo) * 86400)
    value.update(
        TT_state_minus_nominal_seconds=list(map(str, nominal)),
        TT_minus_TDB_state_seconds=list(map(str, paired)),
    )
    if label < Q(plan["quantity30_modern_cutoff_JD"]):
        return {**value, "status": "not_assessed_pre_1962"}
    if row["TDB_minus_UT_seconds"] is None:
        return {**value, "status": "time_field_unavailable"}
    low, high = observed_bounds(
        row["TDB_minus_UT_seconds"],
        plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"],
    )
    hold = Q(plan["latest_known_TAI_minus_UTC_seconds"]) + Q(
        plan["TT_minus_TAI_seconds"]
    )
    if hold != Q(plan["future_current_leap_hold_hypothesis_seconds"]):
        raise ValueError("Declared leap-hold sum changed")
    field = (low - hold, high - hold)
    value.update(
        status="conditional_leap_hold_comparison",
        reported_TDB_minus_TT_hypothesis_seconds=list(map(str, field)),
        overlap_nominal_state=overlaps(field, nominal),
        overlap_paired_state=overlaps(field, paired),
        field_minus_nominal_state_seconds=[
            str(field[0] - nominal[1]),
            str(field[1] - nominal[0]),
        ],
        field_minus_paired_state_seconds=[
            str(field[0] - paired[1]),
            str(field[1] - paired[0]),
        ],
        time_field_is_internal_clock_bound_certified=False,
    )
    return value


def verify(run, cohort):
    plan_raw = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(plan_raw)
    for name, expected in {
        **plan["inputs_sha256"],
        **json.loads((run / "implementation-before-queries.json").read_text()),
    }.items():
        if digest((run / name).read_bytes()) != expected:
            raise ValueError("Frozen input changed: " + name)
    source = json.loads((run / "tai-utc-source.json").read_text())
    if (
        source["original_raw_download_available"]
        or source["original_raw_sha256"] is not None
        or source["future_UTC_certified"]
        or source["excerpt_sha256"]
        != digest((run / "tai-utc-source-excerpt.txt").read_bytes())
    ):
        raise ValueError("Excerpt/source scope was promoted")
    verify_vector(run / "vector-calibration", cohort)
    cal_path = run / "vector-calibration" / (cohort + "-first-analysis.json")
    cal = {q["id"]: q for q in json.loads(cal_path.read_text())["queries"]}
    data_raw = (run / (cohort + "-first-analysis.json")).read_bytes()
    data = json.loads(data_raw)
    if (
        data["plan_sha256"] != digest(plan_raw)
        or data["cohort"] != cohort
        or data["geometry_analysis_sha256"] != digest(cal_path.read_bytes())
        or any(
            data[k]
            for k in [
                "candidate_calls",
                "new_candidate_holdouts",
                "physical_time_model_certified",
                "numerical_tubes_certified",
                "TT_OBSERVER_vector_clock_equivalence_certified",
                "full_goal_complete",
            ]
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Clock diagnostics were promoted to acceptance")
    A = None
    Astatus = None
    if cohort == "B":
        A = json.loads((run / "A-first-analysis.json").read_text())
        aq = next(
            q for q in plan["queries"] if q["cohort"] == "A" and q["time_type"] == "TDB"
        )
        ar = (run / "responses" / (aq["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (run / "responses" / (aq["id"] + ".receipt.json")).read_text()
        )
        Astatus = inspect(ar, receipt["status"], aq, plan["cohorts"]["A"], plan)[
            "status"
        ]
        if Astatus != A["TDB_OBSERVER_contract_status"]:
            raise ValueError("A support status differs from actual response")
    before = json.loads((run / ("before-" + cohort + "-queries.json")).read_text())
    if before["plan_sha256"] != digest(plan_raw) or before[
        "collector_sha256"
    ] != digest(
        (run / "frozen-source/scripts/astrodice_observer_timescale.py").read_bytes()
    ):
        raise ValueError("Actual collector or plan binding changed")
    if cohort == "B" and before["prior_A_analysis_sha256"] != digest(
        (run / "A-first-analysis.json").read_bytes()
    ):
        raise ValueError("B lost its original A binding")
    expected = [q for q in plan["queries"] if q["cohort"] == cohort]
    if [q["id"] for q in data["observer_queries"]] != [q["id"] for q in expected]:
        raise ValueError("Original query population changed")
    collection = json.loads((run / (cohort + "-collection.json")).read_text())
    receipts = {r["id"]: r for r in collection["receipts"]}
    expected_clock_rows = []
    summary = []
    same_eop = set()
    dispatched = 0
    skipped = 0
    for query, stored in zip(expected, data["observer_queries"]):
        dispatch = not query["conditional_on_A_TDB_support"] or Astatus == "supported"
        receipt = receipts[query["id"]]
        if not dispatch:
            expected_skip = {
                "id": query["id"],
                "status": "not_dispatched_A_contract_unverified",
                "A_TDB_status": Astatus,
            }
            if (
                stored != expected_skip
                or receipt != expected_skip
                or (run / "responses" / (query["id"] + ".raw")).exists()
            ):
                raise ValueError("Unsupported branch was substituted or miscounted")
            skipped += 1
            summary.append(expected_skip)
            continue
        raw = (run / "responses" / (query["id"] + ".raw")).read_bytes()
        if (
            receipt["attempt"] != 1
            or receipt["verification_disabled"]
            or receipt["url"]
            != "https://ssd.jpl.nasa.gov/api/horizons.api?"
            + urllib.parse.urlencode(query["parameters"])
            or digest(raw) != receipt["raw_sha256"]
            or digest(raw) != stored["raw_sha256"]
        ):
            raise ValueError("Actual raw request or transport identity differs")
        parsed = inspect(raw, receipt["status"], query, plan["cohorts"][cohort], plan)
        if stored["status"] != parsed["status"]:
            raise ValueError("Refusal/unknown/support status changed")
        for key, value in parsed.items():
            if stored.get(key) != value:
                raise ValueError("Independent raw OBSERVER replay differs: " + key)
        dispatched += 1
        summary.append(
            {
                "id": query["id"],
                "status": parsed["status"],
                "rows": len(parsed.get("rows", [])),
            }
        )
        if cohort == "A" and query["time_type"] == "TDB":
            Astatus = parsed["status"]
        if parsed["status"] == "supported" and parsed["EOP_file"] is not None:
            same_eop.add(parsed["EOP_file"])
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
                "profiles": {
                    p: expected_clock(
                        row, ttrows[row["case_id"]], tdbrows[row["case_id"]], p, plan
                    )
                    for p in plan["numerical_tube_profiles"]
                },
            }
            expected_clock_rows.append(item)
    if (
        data["TDB_OBSERVER_contract_status"] != Astatus
        or data["clock_rows"] != expected_clock_rows
    ):
        raise ValueError(
            "Clock field values, case coverage, or mismatch results changed"
        )
    counts = {}
    primary = [r for r in expected_clock_rows if r["role"] != "auxiliary_not_primary"]
    for profile in plan["numerical_tube_profiles"]:
        values = [r["profiles"][profile] for r in primary]
        counts[profile] = {
            "primary_rows": len(values),
            "conditional_model_assessed": sum(
                v["status"] == "conditional_leap_hold_comparison" for v in values
            ),
            "not_assessed_pre_1962": sum(
                v["status"] == "not_assessed_pre_1962" for v in values
            ),
            "overlap_nominal_state": sum(
                v.get("overlap_nominal_state", False) for v in values
            ),
            "overlap_paired_state": sum(
                v.get("overlap_paired_state", False) for v in values
            ),
            "TT_state_six_not_refuted": sum(
                v["TT_geometric_six_not_refuted"] for v in values
            ),
            "TDB_state_six_not_refuted": sum(
                v["TDB_geometric_six_not_refuted"] for v in values
            ),
        }
    return {
        "method_id": "independent_raw_time_contract_and_rational_quantity30_replay_v1",
        "cohort": cohort,
        "analysis_sha256": digest(data_raw),
        "TDB_OBSERVER_contract_status": Astatus,
        "observer_dispatched_requests": dispatched,
        "observer_skipped_unverified_requests": skipped,
        "observer_queries": summary,
        "profiles": counts,
        "EOP_files": sorted(same_eop),
        "exact_clock_comparisons_replayed": sum(
            len(r["profiles"]) for r in expected_clock_rows
        ),
        "exit_code": 0,
        "candidate_calls": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "physical_time_model_certified": False,
        "numerical_tubes_certified": False,
        "TT_OBSERVER_vector_clock_equivalence_certified": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.run, args.cohort)
    with args.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
