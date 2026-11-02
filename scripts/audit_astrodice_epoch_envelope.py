"""Freeze and replay an epoch-envelope hypothesis; never certify its premises."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from scripts.astrodice_epoch_envelope import METHOD, binding, quality, solve_fit
from scripts.audit_astrodice_venus_epoch import audit as replay_first
from scripts.audit_astrodice_venus_epoch import recovery_comparison


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(run):
    plan_path = run / "plan-before-any-new-LP.json"
    plan = read(plan_path)
    if (
        plan["method_id"] != METHOD
        or plan["fixed_reference_line_arcsec_per_day"] != 0.002
        or plan["hypotheses"]["H1_bounded_epoch_hypothesis"]
        != {
            "epoch_uncertainty_days": "1/1000000000",
            "absolute_each_angle_slope_bound_arcsec_per_day": "3600",
        }
        or plan["actual_epoch_envelope_certified"]
        or plan["new_candidate_conditions"] != 0
        or plan["new_online_requests"] != 0
    ):
        raise ValueError("Uncertified hypothesis was changed or promoted")
    root = Path(__file__).resolve().parents[1]
    for name, expected in plan["source_files"].items():
        if digest(root / name) != expected:
            raise ValueError("Frozen reference dependency changed: " + name)
    code = read(run / "experiment-code-before.json")
    for name, expected in code["files"].items():
        if digest(root / name) != expected:
            raise ValueError("Experimental checker changed: " + name)
    if code["plan_sha256"] != digest(plan_path):
        raise ValueError("Pre-LP plan changed")
    first = replay_first(run / "old-first")
    recovered = recovery_comparison(
        run / "old-first", run / "old-recovery/recovery-first"
    )
    rows = []
    for item in plan["cases"]:
        path = run / item["dataset"] / item["file"]
        for row in read(path)["rows"]:
            rows.append(
                (row, {"path": str(path.relative_to(run)), "sha256": digest(path)})
            )
    if len(rows) != 3:
        raise ValueError("All three already-seen conditions must remain")
    return plan, rows, first, recovered


def replay(run, certificates):
    plan, rows, first, recovered = inputs(run)
    if (
        certificates["method_id"] != METHOD
        or certificates["plan_sha256"] != digest(run / "plan-before-any-new-LP.json")
        or len(certificates["rows"]) != len(rows)
    ):
        raise ValueError("Outer certificate dataset changed")
    hypothesis = plan["hypotheses"]["H1_bounded_epoch_hypothesis"]
    evaluated = []
    for (row, source), record in zip(rows, certificates["rows"]):
        if record["id"] != row["id"] or record["row_binding_sha256"] != binding(row):
            raise ValueError("A source condition was changed or dropped")
        value = quality(
            row,
            record["fits"],
            hypothesis["epoch_uncertainty_days"],
            hypothesis["absolute_each_angle_slope_bound_arcsec_per_day"],
        )
        if value != record["quality"]:
            raise ValueError("Outer quality differs from rational replay")
        evaluated.append({"id": row["id"], "source": source, "quality": value})
    return {
        "method_id": METHOD,
        "rows": evaluated,
        "original_complete_first_replay": first,
        "original_complete_recovery_replay": recovered,
        "numerical_outer_quality_exit_code": (
            0
            if all(
                row["quality"]["status"]
                == "outer_reference_numerical_quality_satisfied"
                for row in evaluated
            )
            else 2
        ),
        "production_acceptance_exit_code": 2,
        "actual_epoch_envelope_certified": False,
        "slope_bound_physically_certified": False,
        "physical_polynomial_truncation_bound_certified": False,
        "old_Farkas_proofs_or_scores_regraded": False,
        "candidate_accuracy_passes": 0,
        "new_holdout_conditions": 0,
        "full_goal_complete": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--certificates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--solve", action="store_true")
    args = parser.parse_args()
    if args.solve:
        plan, rows, _, _ = inputs(args.run)
        hypothesis = plan["hypotheses"]["H1_bounded_epoch_hypothesis"]
        data = {
            "method_id": METHOD,
            "plan_sha256": digest(args.run / "plan-before-any-new-LP.json"),
            "rows": [],
        }
        for row, _ in rows:
            fits = [
                solve_fit(
                    row,
                    window,
                    order,
                    hypothesis["epoch_uncertainty_days"],
                    hypothesis["absolute_each_angle_slope_bound_arcsec_per_day"],
                )
                for window in plan["windows_seconds"]
                for order in plan["orders"]
            ]
            value = quality(
                row,
                fits,
                hypothesis["epoch_uncertainty_days"],
                hypothesis["absolute_each_angle_slope_bound_arcsec_per_day"],
            )
            data["rows"].append(
                {
                    "id": row["id"],
                    "row_binding_sha256": binding(row),
                    "fits": fits,
                    "quality": value,
                }
            )
            print(row["id"], value["status"], flush=True)
        with args.certificates.open("x") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
    else:
        data = read(args.certificates)
    result = replay(args.run, data)
    if any(
        name == "swisseph" or name == "fatebridge" or name.startswith("fatebridge.")
        for name in sys.modules
    ):
        raise ValueError("Reference-only experiment imported the candidate")
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        {
            k: result[k]
            for k in [
                "numerical_outer_quality_exit_code",
                "production_acceptance_exit_code",
            ]
        }
    )
    return result["production_acceptance_exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
