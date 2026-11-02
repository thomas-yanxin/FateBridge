"""Retain both input paths and require every qualified reference to agree.

Only reference integrity/quality determines availability. Candidate failures
are never used to choose an encoding, and no planned case can be omitted.
"""

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_interval_reference import replay_interval
from scripts.audit_astrodice_local_motion import (
    FAIL,
    PASS,
    UNRESOLVED,
    require_declared_derivative,
)
from scripts.audit_astrodice_local_reference import replay

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.historical_source_identity import HistoricalSources

ENCODINGS = {"JD", "MJD"}
QUALIFIED = "qualified_under_declared_numerical_model"


def intersects(intervals):
    return all(
        max(value[axis][0] for value in intervals)
        <= min(value[axis][1] for value in intervals)
        for axis in (0, 1)
    )


def outcome(qualities, reports, intervals, center_boxes):
    if any(set(value) != ENCODINGS for value in [qualities, reports]):
        raise ValueError("Both declared encodings must remain present")
    qualified = [name for name in sorted(ENCODINGS) if qualities[name] == QUALIFIED]
    if set(intervals) != set(qualified):
        raise ValueError("Only independently qualified reference intervals are allowed")
    statuses = [
        value["status"] for report in reports.values() for value in report.values()
    ]
    # Even a failure in a path whose other layer is unavailable remains fatal.
    if FAIL in statuses:
        return FAIL
    if "candidate_error" in statuses:
        return "candidate_error"
    if (
        not qualified
        or not any(report["position"]["status"] == PASS for report in reports.values())
        or any(reports[name]["rate"]["status"] != PASS for name in qualified)
        or not center_boxes
        or not intersects(list(center_boxes.values()))
        or not intersects([intervals[name] for name in qualified])
    ):
        return UNRESOLVED
    return PASS


def center_box(row, origin):
    point = row["samples"].get("0")
    if point is None:
        return None
    boxes = []
    for axis, literal in enumerate(point["printed_angles"]):
        value = Q(literal)
        if axis == 0:
            value -= 360 * ((value - origin + 180) // 360)
        quantum = Q(Decimal(10) ** Decimal(literal).as_tuple().exponent)
        boxes.append([value - quantum, value + quantum])
    return boxes


def audit(run, plan_path, cohort):
    plan = json.loads(plan_path.read_text())
    root = Path(__file__).resolve().parents[1]
    originals = HistoricalSources(root)
    for name, expected in plan["checker_code_sha256"].items():
        if not originals.matches(root / name, expected):
            raise ValueError("Frozen envelope checker dependency changed: " + name)
    bundles = plan["bundles"][cohort]
    if set(bundles) != ENCODINGS:
        raise ValueError("Predeclared encoding coverage changed")
    loaded = {}
    for encoding, paths in bundles.items():
        paths = {k: run / v for k, v in paths.items()}
        protocol = json.loads(paths["protocol"].read_text())
        if protocol["reference_parameters"]["TLIST_TYPE"] != f"'{encoding}'":
            raise ValueError("Reference encoding identity changed")
        if (
            hashlib.sha256(paths["protocol"].read_bytes()).hexdigest()
            != plan["protocol_sha256"][cohort][encoding]
        ):
            raise ValueError("Frozen protocol changed")
        certificates = json.loads(paths["certificates"].read_text())
        quality = replay(
            paths["protocol"],
            paths["reference"],
            paths["material"],
            paths["seal"],
            certificates,
        )
        raw = json.loads(paths["reference"].read_text())
        native = json.loads(paths["native"].read_text())
        candidate = json.loads(paths["candidate_seal"].read_text())
        for name, expected_hash in plan["production_files_sha256"].items():
            if candidate["candidate_files"].get(name) != expected_hash:
                raise ValueError(
                    "Input paths were tested against different production sources"
                )
        if native["reference"] != quality:
            raise ValueError("Candidate result was bound to another reference")
        for row in native["rows"]:
            for frame in row["layers"]["rate"].get("frames", {}).values():
                require_declared_derivative(candidate, frame["policy"])
        if (
            native["fixed_position_arcsec"] != 0.02
            or native["fixed_rate_arcsec_per_day"] != 0.002
        ):
            raise ValueError("Candidate error lines changed")
        if [row["id"] for row in native["rows"]] != [
            case["id"] for case in protocol["cases"]
        ]:
            raise ValueError("Candidate case coverage changed")
        loaded[encoding] = (protocol, raw, quality, certificates, native)
    expected = plan["cases"][cohort]
    for protocol, raw, quality, certificates, native in loaded.values():
        if protocol["cases"] != expected or len(raw["rows"]) != len(expected):
            raise ValueError("A planned condition was changed or dropped")
    rows = []
    for i, case in enumerate(expected):
        qualities, reports, intervals, center_boxes = {}, {}, {}, {}
        points = [
            loaded[n][1]["rows"][i]["samples"].get("0") for n in sorted(ENCODINGS)
        ]
        origin = next((Q(p["printed_angles"][0]) for p in points if p), Q())
        for encoding, (_, raw, quality, certificates, native) in loaded.items():
            row, q = raw["rows"][i], quality["rows"][i]
            if any(row[key] != case[key] for key in ["id", "body", "date_tt", "role"]):
                raise ValueError("Reference row changed")
            if native["rows"][i]["reference_quality"] != q:
                raise ValueError(
                    "Candidate result is bound to another reference quality"
                )
            qualities[encoding] = q["status"]
            reports[encoding] = native["rows"][i]["layers"]
            box = center_box(row, origin)
            if box is not None:
                center_boxes[encoding] = box
            if q["status"] == QUALIFIED:
                chosen = next(
                    fit
                    for fit in certificates["rows"][i]["fits"]
                    if fit["window_seconds"] == q["selected_window_seconds"]
                    and fit["odd_order"] == q["selected_order"]
                )
                intervals[encoding] = replay_interval(row, chosen, step_seconds=5)
        status = outcome(qualities, reports, intervals, center_boxes)
        rows.append(
            {
                **case,
                "status": status,
                "reference_statuses": qualities,
                "all_qualified_encodings_used": sorted(intervals),
                "unresolved_alternative_encodings_retained": [
                    n for n in sorted(ENCODINGS) if qualities[n] != QUALIFIED
                ],
                "angular_rate_intervals_arcsec_per_day": {
                    n: [[str(lo), str(hi)] for lo, hi in boxes]
                    for n, boxes in intervals.items()
                },
                "center_printing_intervals_intersect": bool(center_boxes)
                and intersects(list(center_boxes.values())),
                "qualified_derivative_intervals_intersect": bool(intervals)
                and intersects(list(intervals.values())),
                "individual_candidate_layer_statuses": {
                    n: {k: v["status"] for k, v in value.items()}
                    for n, value in reports.items()
                },
            }
        )
    statuses = [row["status"] for row in rows]
    status = next(
        (s for s in [FAIL, "candidate_error", UNRESOLVED] if s in statuses), PASS
    )
    return {
        "method_id": "all_qualified_exact_TT_serializations_envelope_v1",
        "cohort": cohort,
        "status": status,
        "exit_code": (
            0 if status == PASS else 1 if status in [FAIL, "candidate_error"] else 2
        ),
        "rows": rows,
        "planned_conditions": len(expected),
        "fixed_position_arcsec": 0.02,
        "fixed_rate_arcsec_per_day": 0.002,
        "full_goal_complete": False,
        "individual_reference_failures_regraded": False,
        "scope": "Same exact TT cases and unchanged grids/LP constraints; all qualified encodings must agree and pass, unresolved alternatives remain visible. Conditional printed-angle polynomial and shared display-frame reference, not unconditional physical ephemeris accuracy.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = audit(args.run, args.plan, args.cohort)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(result["cohort"], result["status"])
    raise SystemExit(result["exit_code"])
