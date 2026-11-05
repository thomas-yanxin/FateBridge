"""Grade all actual complete tropical rates against the fixed named model."""

import argparse
import json
import math
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import I
from scripts.astrodice_display_frame import PLAN_SHA, load, pi_interval, sha
from scripts.verify_astrodice_display_reference import verify


def wire(value):
    lo, hi = value.bounds()
    return {"bounds": [str(lo), str(hi)], "lower": float(lo), "upper": float(hi)}


def audit(run, reference, sampler=None):
    """Compare fresh current states with every original independent source row."""
    from scripts.astrodice_current_sampling import sample

    sampler = sample if sampler is None else sampler
    protocol = load(run)
    saved = json.loads(reference.read_text())
    split = saved["split"]
    verify(run, reference)
    rows = []
    for backend in protocol["backends"]:
        for index, case in enumerate(protocol[split]):
            native = sampler(case, backend)
            if [r["body"] for r in native["rows"]] != case["bodies"]:
                raise ValueError("Actual target missing")
            for body, actual in zip(case["bodies"], native["rows"]):
                ref = next(
                    r
                    for r in saved["rows"]
                    if r["case_index"] == index and r["body"] == body
                )
                row = {
                    "case_index": index,
                    "label": case["label"],
                    "body": body,
                    "backend": backend,
                    "reference_status": ref["status"],
                    "candidate_status": actual["status"],
                    "qualified": False,
                }
                if ref["status"] != "ready" or actual["status"] != "ready":
                    row.update(
                        status="unavailable_retained",
                        reference_error=ref.get("error"),
                        candidate_error=actual.get("error"),
                    )
                    rows.append(row)
                    continue
                if Q(actual["native_numeric_jd"]) != Q(
                    ref["exact_binary64_numeric_jd"]
                ):
                    raise ValueError("Numeric time rebound")
                expected_model = "swieph" if backend == "swieph" else "jpl"
                bit = 2 if backend == "swieph" else 1
                physical_calls = [
                    c for c in actual["native_calls"] if c["args"][1] != -1
                ]
                if not physical_calls or any(
                    c["returned_flags"] & 7 != bit for c in physical_calls
                ):
                    raise ValueError("Returned physical backend differs")
                if actual["model"] != expected_model:
                    raise ValueError("Delivered model differs")
                trace = actual["trace"]
                if not trace["files"] or trace["has_unidentified_sources"]:
                    raise ValueError("Source trace incomplete")
                state = actual["state"]
                lon, lat = map(math.radians, (state["longitude"], state["latitude"]))
                u = [
                    math.cos(lat) * math.cos(lon),
                    math.cos(lat) * math.sin(lon),
                    math.sin(lat),
                ]
                direction = [I(*map(Q, x["value"])) for x in ref["displayed_direction"]]
                position = (
                    sum(
                        ((I(Q(a)) - b).square() for a, b in zip(u, direction)), I()
                    ).sqrt()
                    * 648000
                    / pi_interval()
                )
                reference_rate = I(*map(Q, ref["longitude_rate_arcsec_per_source_day"]))
                rate = I(Q(state["longitude_speed"]) * 3600) - reference_rate
                pos_pass = position.absolute_upper() <= Q(
                    protocol["position_line_arcsec"]
                )
                rate_pass = rate.absolute_upper() <= Q(
                    protocol["rate_line_arcsec_per_day"]
                )
                if body == "Moon":
                    policy = actual["metadata"]["lunar_light_time"][
                        "fixed_frame_source_derivative"
                    ]
                else:
                    policy = actual["metadata"]["complete_position_derivatives"][
                        body + ":tropical"
                    ]
                applied = policy["status"] == "applied"
                row.update(
                    status=(
                        "passed_declared_source_lines"
                        if pos_pass and rate_pass and applied
                        else "failed_declared_source_lines"
                    ),
                    qualified=pos_pass and rate_pass and applied,
                    position_pass=pos_pass,
                    rate_pass=rate_pass,
                    derivative_policy_applied=applied,
                    position_chord_error_arcsec=wire(position),
                    signed_complete_display_rate_error_arcsec_per_source_day=wire(rate),
                    final_displayed_longitude_speed_degrees_per_native_argument_day=state[
                        "longitude_speed"
                    ],
                )
                rows.append(row)
    numeric_failure = any(
        row.get("position_pass") is False
        or row.get("rate_pass", row.get("longitude_rate_pass")) is False
        or row.get("auxiliary_full_direction_rate_pass") is False
        for row in rows
    )
    gate = (
        1 if numeric_failure else 2 if any(not row["qualified"] for row in rows) else 0
    )
    return {
        "exit_code": gate,
        "declared_source_lines_satisfied": gate == 0,
        "physical_accuracy_certified": False,
        "protocol_sha256": PLAN_SHA,
        "split": split,
        "candidate_phase": "current_execution",
        "reference_sha256": sha(reference),
        "rows": rows,
        "position_line_arcsec": protocol["position_line_arcsec"],
        "rate_line_arcsec_per_day": protocol["rate_line_arcsec_per_day"],
        "scope": protocol["scope"],
        "old_gates": protocol["old_gates"],
        "physical_TT_equivalence_certified": False,
        "original_failure_records_regraded": False,
        "original_Horizons_model_equivalence_certified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run, args.reference)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    raise SystemExit(result["exit_code"])


if __name__ == "__main__":
    main()
