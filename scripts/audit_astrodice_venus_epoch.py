"""Replay complete encoding experiments without promoting partial diagnostics.

Old Farkas witnesses remain valid for their original data. Applying their
weights to new support observations does not certify feasibility of a complete
new curve, candidate accuracy, or the service's internal clock implementation.
"""

import argparse
import copy
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_interval_reference import system
from scripts.astrodice_reference_infeasibility import verify_incompatibility
from scripts.audit_astrodice_local_reference import replay
from scripts.gen_astrodice_horizons_wide import ticks

ENCODINGS = ("JD", "MJD", "CAL")
OLD_MANIFEST = "7d69cadeefc9d5621765c0dd509feefb52971afc4f951e93953557cf1e9572a2"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coverage_summary(reference, journal):
    # The collector's batch summary does not copy a final HTTP error status.
    # Use the actual attempt journal, preserving retry failures separately.
    terminal = {entry["batch"]: entry for entry in journal}
    if set(terminal) != {entry["batch"] for entry in reference["batches"]}:
        raise ValueError("Attempt journal and planned batches differ")
    return {
        "conditions": len(reference["rows"]),
        "planned_primary_points": sum(len(row["samples"]) for row in reference["rows"]),
        "accepted_primary_points": sum(
            sum(value is not None for value in row["samples"].values())
            for row in reference["rows"]
        ),
        "rejected_epoch_rows": sum(
            len(row.get("rejected_epoch_rows", [])) for row in reference["batches"]
        ),
        "http_503_attempts": sum(row.get("http_status") == 503 for row in journal),
        "http_503_terminal_batches": sum(
            row.get("http_status") == 503 for row in terminal.values()
        ),
        "request_attempts": len(journal),
        "network_attempts": sum(
            row.get("network_request_performed", True) for row in journal
        ),
        "reused_batches": sum(
            row.get("network_request_performed") is False for row in journal
        ),
    }


def support_comparison(run):
    old = run / "astrodice-grid5-reference-v2"
    if digest(old / "manifest.json") != OLD_MANIFEST:
        raise ValueError("Historical source manifest changed")
    for name, expected in read(old / "manifest.json")["files"].items():
        if digest(old / name) != expected:
            raise ValueError("Historical reference or proof changed: " + name)
    plan = read(run / "support-plan-before-queries.json")
    center = ticks(plan["date_tt"])
    proofs = read(old / "exact-incompatibility-diagnostic.json")["records"]
    expected_offsets = sorted(
        {0}
        | {
            sign * (i // 2 + 1) * record["grid_step_seconds"]
            for record in proofs
            for i in record["witness"]["support_indices"]
            for sign in [-1, 1]
        }
    )
    if len(proofs) != 5 or plan["all_diagnostic_offsets_seconds"] != expected_offsets:
        raise ValueError("Original witness population or support coverage changed")
    baseline = read(old / "development-reference.json")["rows"][0]
    results = {}
    for encoding in ENCODINGS:
        receipt = read(run / "support-first" / (encoding + "-receipt.json"))
        raw = run / "support-first" / (encoding + "-raw.json")
        if digest(raw) != receipt["raw_sha256"]:
            raise ValueError("Raw support observation changed")
        # Recompute the encoding diagnostic, rather than trust its stored rows.
        from scripts.diagnose_astrodice_epoch_serialization import assess, requests_for

        assessment = assess(raw.read_bytes(), plan)
        if (
            receipt["parameters"] != requests_for(plan)[encoding]
            or assessment != receipt["assessment"]
        ):
            raise ValueError("Support query or epoch replay changed")
        observations = {
            (value["requested_tick"] - center) // 1000000: value
            for value in assessment["rows"]
            if value["requested_tick"] != plan["auxiliary_tick"]
        }
        if sorted(observations) != expected_offsets or not all(
            value["epoch_within_original_budget"] for value in observations.values()
        ):
            raise ValueError("Support subset is incomplete or outside the fixed budget")
        records = []
        for record in proofs:
            path = old / (
                "parent/reference.json"
                if record["dataset"] == "parent"
                else "development-reference.json"
            )
            row = next(v for v in read(path)["rows"] if v["id"] == record["case"])
            args = [None, record["window_seconds"], record["odd_order"], record["axis"]]
            kwargs = {"step_seconds": record["grid_step_seconds"]}
            a, b, _, scale = system(row, *args, **kwargs)
            original = verify_incompatibility(a, b, record["witness"])
            new = copy.deepcopy(row)
            for offset, value in observations.items():
                if str(offset) in new["samples"]:
                    new["samples"][str(offset)]["printed_angles"] = value[
                        "printed_angles"
                    ]
            aa, bb, _, new_scale = system(new, *args, **kwargs)
            indices = record["witness"]["support_indices"]
            weights = list(map(Q, record["witness"]["weights"]))
            # Unqueried endpoint baselines cancel exactly in each old witness.
            baseline_coefficient = sum(
                (
                    w
                    * (1 if i % 2 == 0 else -1)
                    * Q(
                        (i // 2 + 1) * record["grid_step_seconds"],
                        record["window_seconds"],
                    )
                    for i, w in zip(indices, weights)
                ),
                Q(),
            )
            if a != aa or scale != new_scale or baseline_coefficient:
                raise ValueError("Witness coefficients or canceled baseline changed")
            bound = sum((w * bb[i] for i, w in zip(indices, weights)), Q())
            records.append(
                {
                    "dataset": record["dataset"],
                    "window_seconds": record["window_seconds"],
                    "order": record["odd_order"],
                    "original_exact_contradiction": str(original),
                    "new_support_weighted_bound": str(bound),
                    "same_support_still_strictly_negative": bound < 0,
                    "new_curve_feasibility_certified": False,
                }
            )
        results[encoding] = {
            "primary_points": len(observations),
            "changed_printed_pairs_from_old": sum(
                value["printed_angles"]
                != baseline["samples"][str(offset)]["printed_angles"]
                for offset, value in observations.items()
            ),
            "witnesses": records,
        }
    return results


def audit(run):
    initial = read(run / "before-source-seal.json")
    chains, coverage = {}, {}
    for cohort in ("A", "B"):
        for encoding in ENCODINGS:
            prefix = cohort + "-" + encoding
            protocol = run / (prefix + "-protocol.json")
            if digest(protocol) != initial["full_protocols_sha256"][
                protocol.name
            ] or read(protocol)["reference_parameters"]["TLIST_TYPE"] != repr(encoding):
                raise ValueError("Predeclared complete protocol changed")
            result = replay(
                protocol,
                run / (prefix + "-reference-first.json"),
                run / (prefix + "-raw"),
                run / (prefix + "-reference-seal.json"),
                read(run / (prefix + "-first-certificates.json")),
            )
            if result != read(run / (prefix + "-first-quality.json")):
                raise ValueError("First complete reference quality changed")
            chains[prefix] = result
            journal = [
                json.loads(line)
                for line in (run / (prefix + "-raw/requests.jsonl"))
                .read_text()
                .splitlines()
            ]
            coverage[prefix] = coverage_summary(
                read(run / (prefix + "-reference-first.json")), journal
            )
    return {
        "method_id": "complete_venus_epoch_path_replay_v1",
        "support_diagnostics": support_comparison(run),
        "complete_reference_chains": chains,
        "complete_coverage": coverage,
        "original_five_proofs_regraded": False,
        "partial_support_improvement_is_acceptance": False,
        "candidate_accuracy_passes": 0,
        "full_goal_complete": False,
    }


def recovery_comparison(first, recovered):
    """Validate same-parameter transport recovery without replacing firsts."""
    results = {}
    for encoding in ENCODINGS:
        prefix = "B-" + encoding
        protocol = recovered / (prefix + "-protocol.json")
        if digest(protocol) != digest(first / protocol.name):
            raise ValueError("Recovery moved an original condition or protocol")
        original = [
            json.loads(line)
            for line in (first / (prefix + "-raw/requests.jsonl"))
            .read_text()
            .splitlines()
        ]
        journal = [
            json.loads(line)
            for line in (recovered / (prefix + "-raw/requests.jsonl"))
            .read_text()
            .splitlines()
        ]

        def key(entry):
            return json.dumps([entry["body"], entry["parameters"]], sort_keys=True)

        successes = {
            key(entry): entry
            for entry in original
            if entry.get("http_status") == 200 and "raw_file" in entry
        }
        planned = {key(entry) for entry in original}
        if {key(entry) for entry in journal} != planned:
            raise ValueError("Recovery request set changed")
        reused, new_keys = 0, set()
        for entry in journal:
            if entry.get("network_request_performed") is False:
                previous = successes.get(key(entry))
                if previous is None or any(
                    entry[field] != previous["raw_sha256"]
                    for field in ["raw_sha256", "reused_raw_sha256"]
                ):
                    raise ValueError("A reused success differs from the original bytes")
                old_path = first / (prefix + "-raw") / previous["raw_file"]
                if digest(old_path) != entry["raw_sha256"]:
                    raise ValueError("Original cached success changed")
                reused += 1
            else:
                if key(entry) in successes:
                    raise ValueError("Recovery unnecessarily re-requested a success")
                if entry.get("transport_method_id") != "jpl_horizons_serial_backoff_v1":
                    raise ValueError("Recovery bypassed serial transport")
                new_keys.add(key(entry))
        if new_keys != planned - set(successes):
            raise ValueError("A failed original request was silently omitted")
        reference = recovered / (prefix + "-reference.json")
        quality = replay(
            protocol,
            reference,
            recovered / (prefix + "-raw"),
            recovered / (prefix + "-reference-seal.json"),
            read(recovered / (prefix + "-certificates.json")),
        )
        if quality != read(recovered / (prefix + "-quality.json")):
            raise ValueError("Recovery quality does not replay")
        results[encoding] = {
            "original_success_batches_reused": reused,
            "failed_original_batches_resubmitted": len(new_keys),
            "coverage": coverage_summary(read(reference), journal),
            "first_reference_exit_code": read(first / (prefix + "-first-quality.json"))[
                "exit_code"
            ],
            "followup_reference_exit_code": quality["exit_code"],
            "followup_rows": quality["rows"],
        }
    return {
        "encodings": results,
        "first_failures_replaced": False,
        "new_holdout_conditions": 0,
        "physical_time_conversion_certified": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        {
            name: result["exit_code"]
            for name, result in result["complete_reference_chains"].items()
        }
    )
