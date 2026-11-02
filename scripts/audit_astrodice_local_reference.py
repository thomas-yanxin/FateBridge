"""Collect/replay local reference LP certificates without trusting solver flags."""

import argparse
import hashlib
import json
from pathlib import Path

from scripts.astrodice_interval_reference import (
    GRID_METHODS,
    ORDERS,
    WINDOWS,
    quality,
    solve_row,
)
from scripts.audit_astrodice_horizons_wide_reference import validate

METHOD = "local_printed_angle_interval_lp_v1"


def reference_grid(plan):
    method = plan["local_interval_method_id"]
    if method not in GRID_METHODS:
        raise ValueError("Unplanned local reference method")
    step = GRID_METHODS[method]
    if (
        plan.get("local_grid_step_seconds", 10) != step
        or plan["local_windows_seconds"] != list(WINDOWS)
        or plan["local_orders"] != list(ORDERS)
        or any(
            v != list(range(-1440, 1441, step))
            for v in plan["explicit_offsets_seconds"].values()
        )
        or plan["fixed_position_arcsec"] != 0.02
        or plan["fixed_rate_arcsec_per_day"] != 0.002
        or plan["fixed_reference_convergence_arcsec_per_day"] != 0.002
    ):
        raise ValueError("Frozen local reference policy changed")
    return method, step


def parent_from_args(args):
    values = {
        key: getattr(args, "parent_" + key, None)
        for key in ["protocol", "reference", "material", "seal"]
    }
    if any(v is not None for v in values.values()):
        if any(v is None for v in values.values()):
            raise ValueError("All four parent source paths are required")
        return values
    return None


def parent_preservation(plan, raw, bundle):
    parent = plan.get("densification_parent")
    if parent is None:
        if bundle is not None:
            raise ValueError("Undeclared densification parent")
        return {}, None
    if (
        plan["local_interval_method_id"] != "local_printed_angle_interval_lp_grid5_v2"
        or bundle is None
        or set(parent) != {"reference_sha256", "case_map"}
        or set(parent["case_map"]) != {r["id"] for r in raw["rows"]}
        or hashlib.sha256(bundle["reference"].read_bytes()).hexdigest()
        != parent["reference_sha256"]
    ):
        raise ValueError("Densification parent identity or coverage changed")
    parent_validation = validate(
        bundle["protocol"], bundle["reference"], bundle["material"], bundle["seal"]
    )
    old_rows = json.loads(bundle["reference"].read_text())["rows"]
    result = {}
    for row in raw["rows"]:
        old = next(
            (r for r in old_rows if r["id"] == parent["case_map"][row["id"]]), None
        )
        if old is None or any(old[k] != row[k] for k in ["body", "date_tt", "jd_tt"]):
            raise ValueError("Densification changed the parent condition")
        if set(old["samples"]) != set(map(str, range(-1440, 1441, 10))):
            raise ValueError("Densification parent grid changed")
        conflicts = []
        for t, observation in old["samples"].items():
            dense = row["samples"].get(t)
            if (
                observation is None
                or dense is None
                or any(
                    observation[k] != dense[k]
                    for k in ["printed_angles", "returned_jd_tt_string"]
                )
            ):
                conflicts.append(
                    {
                        "offset_seconds": t,
                        "parent": observation,
                        "dense": dense,
                    }
                )
        result[row["id"]] = {
            "parent_case_id": old["id"],
            "parent_observations_checked": len(old["samples"]),
            "matching_parent_observations": len(old["samples"]) - len(conflicts),
            "conflicts": conflicts,
            "status": "preserved" if not conflicts else "observation_conflict",
        }
    return result, parent_validation


def replay(protocol, reference, material, seal, certificates, *, parent_bundle=None):
    baseline = validate(protocol, reference, material, seal)
    plan = json.loads(protocol.read_text())
    raw = json.loads(reference.read_text())
    method, step = reference_grid(plan)
    parent_checks, parent_validation = parent_preservation(plan, raw, parent_bundle)
    if (
        certificates["method_id"] != method
        or certificates["reference_sha256"]
        != hashlib.sha256(reference.read_bytes()).hexdigest()
        or len(certificates["rows"]) != len(raw["rows"])
    ):
        raise ValueError("Local certificate dataset identity changed")
    rows = []
    for row, record in zip(raw["rows"], certificates["rows"]):
        if row["id"] != record["id"]:
            raise ValueError("Local certificate case changed")
        calculated = quality(row, record["fits"], step_seconds=step)
        if calculated != record["quality"]:
            raise ValueError(
                "Declared local quality differs from exact certificate replay"
            )
        combined = {"id": row["id"], "role": row["role"], **calculated}
        if row["id"] in parent_checks:
            check = parent_checks[row["id"]]
            combined["parent_preservation"] = check
            if check["status"] != "preserved":
                combined.update(
                    status="reference_quality_unresolved",
                    dense_model_quality=calculated,
                    selected_window_seconds=None,
                    selected_order=None,
                    selected=None,
                )
        rows.append(combined)
    failures = [
        r["id"]
        for r in rows
        if r["status"] != "qualified_under_declared_numerical_model"
    ]
    result = {
        "status": (
            "reference_quality_unresolved"
            if failures
            else "declared_local_numerical_quality_satisfied"
        ),
        "exit_code": 2 if failures else 0,
        "raw_integrity_and_baseline_quality": baseline,
        "rows": rows,
        "unqualified_case_ids": failures,
        "candidate_outputs_used_for_reference_selection": False,
        "scope": "Exact LP certificates for declared localoddpolynomial/printing model plus empirical crosssupport checks;not independent observational truth or a physical truncation bound.",
        "full_goal_complete": False,
    }
    if step != 10:
        result["grid_step_seconds"] = step
    if parent_validation is not None:
        result["parent_raw_integrity_and_baseline_quality"] = parent_validation
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["protocol", "reference", "material", "seal", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--certificates", type=Path, required=True)
    p.add_argument("--solve", action="store_true")
    for name in ["protocol", "reference", "material", "seal"]:
        p.add_argument("--parent-" + name, type=Path)
    args = p.parse_args()
    if args.solve:
        # A raw replay runs before optional SciPy; no solver claim replaces it.
        validate(args.protocol, args.reference, args.material, args.seal)
        raw = json.loads(args.reference.read_text())
        plan = json.loads(args.protocol.read_text())
        method, step = reference_grid(plan)
        parent_preservation(plan, raw, parent_from_args(args))
        data = {
            "method_id": method,
            "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
            "rows": [solve_row(r, step_seconds=step) for r in raw["rows"]],
        }
        with args.certificates.open("x") as f:
            f.write(json.dumps(data, indent=2, allow_nan=False) + "\n")
    else:
        data = json.loads(args.certificates.read_text())
    result = replay(
        args.protocol,
        args.reference,
        args.material,
        args.seal,
        data,
        parent_bundle=parent_from_args(args),
    )
    with args.output.open("x") as f:
        f.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "exit_code": result["exit_code"],
                "unqualified_case_ids": result["unqualified_case_ids"],
            }
        )
    )
    raise SystemExit(result["exit_code"])
