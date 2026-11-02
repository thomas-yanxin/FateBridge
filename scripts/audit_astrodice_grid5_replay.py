"""Replay the sealed grid5 experiment without resampling or regrading history.

The aggregate remains unresolved (exit 2). A valid incompatibility proof is
evidence against the declared reference model, never a numeric acceptance pass.
No solver or candidate ephemeris is called by this replay.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.astrodice_interval_reference import replay_interval, system
from scripts.astrodice_reference_infeasibility import verify_incompatibility
from scripts.audit_astrodice_local_reference import replay

MANIFEST_SHA256 = "7d69cadeefc9d5621765c0dd509feefb52971afc4f951e93953557cf1e9572a2"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/astrodice-grid5-reference-v2"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(fixture=FIXTURE):
    manifest_path = fixture / "manifest.json"
    if digest(manifest_path) != MANIFEST_SHA256:
        raise ValueError("Frozen grid5 manifest changed")
    manifest = read(manifest_path)
    for name, expected in manifest["files"].items():
        if digest(fixture / name) != expected:
            raise ValueError("Frozen grid5 artifact changed: " + name)

    results = {}
    for name in ("development", "fresh"):
        parent = (
            {
                k: fixture / "parent" / v
                for k, v in {
                    "protocol": "protocol.json",
                    "reference": "reference.json",
                    "material": "raw",
                    "seal": "seal.json",
                }.items()
            }
            if name == "development"
            else None
        )
        result = replay(
            fixture / (name + "-protocol.json"),
            fixture / (name + "-reference.json"),
            fixture / (name + "-raw"),
            fixture / (name + "-reference-seal.json"),
            read(fixture / (name + "-first-certificates.json")),
            parent_bundle=parent,
        )
        if result != read(fixture / (name + "-first-quality.json")):
            raise ValueError("First reference result no longer replays: " + name)
        results[name] = result

    proofs = []
    for record in read(fixture / "exact-incompatibility-diagnostic.json")["records"]:
        reference_path = fixture / (
            "parent/reference.json"
            if record["dataset"] == "parent"
            else "development-reference.json"
        )
        row = next(r for r in read(reference_path)["rows"] if r["id"] == record["case"])
        a, b, _, scale = system(
            row,
            None,
            record["window_seconds"],
            record["odd_order"],
            record["axis"],
            step_seconds=record["grid_step_seconds"],
        )
        contradiction = verify_incompatibility(a, b, record["witness"])
        if str(contradiction) != record["verified_contradiction"]:
            raise ValueError("First exact contradiction changed")
        # For Ax <= b + epsilon*1, the normalized Farkas weights imply
        # epsilon >= -y.b. Multiplication by scale restores arcseconds of
        # half the symmetric angular difference. This necessary lower bound
        # neither proves sufficiency nor licenses changing the noise model.
        proofs.append(
            {
                **{k: v for k, v in record.items() if k != "witness"},
                "reference_sha256": digest(reference_path),
                "symmetric_support_offsets_seconds": sorted(
                    {
                        sign * (i // 2 + 1) * record["grid_step_seconds"]
                        for i in record["witness"]["support_indices"]
                        for sign in (-1, 1)
                    }
                ),
                "necessary_extra_uniform_half_difference_bound_arcsec": str(
                    -contradiction * scale
                ),
                "original_printing_constraints_changed": False,
                "physical_cause_proved": False,
            }
        )

    counts = {"checked": 0, "strictly_tighter": 0}
    rows = read(fixture / "fresh-reference.json")["rows"]
    dense = read(fixture / "fresh-first-certificates.json")["rows"]
    coarse = read(fixture / "fresh-coarse-comparator.json")["rows"]
    for row, d, c in zip(rows, dense, coarse):
        if row["id"] != d["id"] or row["id"] != c["id"]:
            raise ValueError("Coarse/dense condition identity changed")
        old = {
            **row,
            "samples": {t: v for t, v in row["samples"].items() if int(t) % 10 == 0},
        }
        for df, cf in zip(d["fits"], c["fits"]):
            if any(df[k] != cf[k] for k in ("window_seconds", "odd_order")):
                raise ValueError("Coarse/dense geometry changed")
            if (
                df["status"]
                == cf["status"]
                == "exact_angular_interval_under_odd_polynomial_assumption"
            ):
                for (dl, dh), (cl, ch) in zip(
                    replay_interval(row, df, step_seconds=5), replay_interval(old, cf)
                ):
                    if not cl <= dl <= dh <= ch:
                        raise ValueError(
                            "Dense interval escaped the coarse constraints"
                        )
                    counts["checked"] += 1
                    counts["strictly_tighter"] += int(cl < dl or dh < ch)

    start = read(fixture / "start-seal.json")
    prior_files = {}
    for name, expected in start["files"].items():
        path = fixture / name
        prior_files[name] = {
            "recorded_sha256": expected,
            "available_in_portable_fixture": path.is_file(),
            "digest_matches": digest(path) == expected if path.is_file() else None,
        }
    source_names = (
        "scripts/audit_astrodice_grid5_replay.py",
        "scripts/astrodice_interval_reference.py",
        "scripts/astrodice_reference_infeasibility.py",
        "scripts/astrodice_reference_math.py",
        "scripts/audit_astrodice_local_reference.py",
        "scripts/audit_astrodice_horizons_wide_reference.py",
        "scripts/gen_astrodice_horizons_wide.py",
    )
    return {
        "method_id": "sealed_grid5_reference_and_incompatibility_replay_v1",
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "known_reference_unresolved_historical_archive_incomplete",
        "exit_code": 2,
        "fixture_manifest_sha256": MANIFEST_SHA256,
        "fixture_artifacts_verified": len(manifest["files"]),
        "replay_source_sha256": {name: digest(ROOT / name) for name in source_names},
        "fixed_lines": {
            "position_arcsec": 0.02,
            "rate_arcsec_per_day": 0.002,
            "reference_arcsec_per_day": 0.002,
        },
        "new_holdout_conditions_in_this_replay": 0,
        "historical_frozen_new_conditions": manifest["new_numeric_conditions"],
        "first_reference_results_reproduced": True,
        "reference_results": results,
        "exact_incompatibility_proofs": proofs,
        "exact_coarse_dense_containment": counts,
        "candidate_history": {
            "retained_first_summary": read(fixture / "first-candidate-summary.json"),
            "candidate_recomputed": False,
            "full_candidate_outputs_available_in_portable_fixture": False,
            "linux_logs_available_in_portable_fixture": False,
            "historical_full_source_available_in_portable_fixture": False,
            "recorded_source_file_count": start["source_files"],
            "prequery_artifact_availability": prior_files,
            "scope": "Hash-bound first summary only. Missing full outputs, source manifest and platform logs cannot be reconstructed from this summary; no fresh native or cross-platform acceptance is claimed.",
        },
        "remaining_goal_dimensions": {
            "calendar_and_numerical_accuracy": "partial",
            "original_text_conformance": "not_assessed_in_this_replay",
            "interpretation_fidelity": "not_assessed_in_this_replay",
            "real_world_prediction": "not_assessed",
        },
        "full_goal_complete": False,
        "scope": "Exact replay of printed-angle polynomial constraints and preserved first outcomes. Does not establish a physical truncation bound, independent orientation accuracy, full calendar correctness or predictive efficacy. Baseline failures and known unqualified references remain visible.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Fail before doing work if a previous result would be overwritten.
    if args.output.exists():
        raise FileExistsError(args.output)
    result = audit(args.fixture)
    with args.output.open("x") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(result["status"], "exit", result["exit_code"])
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
