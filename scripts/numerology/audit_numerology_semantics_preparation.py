"""Validate a frozen numerology preparation; never invoke or grade a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
# Support both the documented standalone CLI and import-based regression tests.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fatebridge.validation.agent_capture import read_capture  # noqa: E402
from scripts.evaluate_agent import model_prompt, source_manifest  # noqa: E402

DATASET = ROOT / "tests/fixtures/agent_behavior/numerology_semantic_cases_v1.json"
PROTOCOL = ROOT / "tests/fixtures/numerology_semantics_v1/protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_reference(
    record: dict[str, Any], artifact: dict[str, Any], case: dict[str, Any]
) -> list[str]:
    failures = []
    expected = {
        **case["reference_request"]["arguments"],
        "fields": None,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    if (
        artifact.get("tool") != case["reference_request"]["tool"]
        or artifact.get("arguments") != expected
    ):
        failures.append("reference_request_mismatch")
    if record.get("reference_profile") != {
        "scenarios": "onda-xingpan",
        "tool_scope": "topic",
    }:
        failures.append("reference_scope_widened")
    body = artifact.get("structured_content")
    if artifact.get("is_error") is not False or not isinstance(body, dict):
        return [*failures, "reference_not_successful"]
    metadata = body.get("run_metadata", {})
    if (
        not isinstance(metadata.get("run_id"), str)
        or not metadata.get("run_id")
        or metadata.get("run_id") != record.get("run_id")
    ):
        failures.append("reference_run_identity_mismatch")
    if metadata.get("tool_name") != case["reference_request"]["tool"]:
        failures.append("reference_tool_identity_mismatch")
    # The business digest precedes projection/snapshot removal. It must not be
    # recomputed from this snapshot-less response and falsely called verified.
    if body.get("snapshot_text") is not None:
        failures.append("unexpected_snapshot_text")
    if (
        not isinstance(metadata.get("business_output_sha256"), str)
        or len(metadata["business_output_sha256"]) != 64
    ):
        failures.append("missing_original_business_identity")
    return failures


def check_pending_worksheet(
    worksheet: dict[str, Any], cases: list[dict[str, Any]]
) -> list[str]:
    failures = []
    if (
        type(worksheet.get("model_invocations")) is not int
        or worksheet["model_invocations"] != 0
    ):
        failures.append("preparation_promoted_to_model_execution")
    rows = worksheet.get("cases", [])
    if [r.get("case") for r in rows] != [c["id"] for c in cases]:
        return [*failures, "worksheet_case_set_changed"]
    for row, case in zip(rows, cases):
        if (
            row.get("model_status") != "not_run"
            or row.get("semantic_status") != "pending"
        ):
            failures.append("preparation_promoted_to_semantic_acceptance:" + case["id"])
        checks = row.get("checks", [])
        if [c.get("criterion") for c in checks] != case["manual_review"]:
            failures.append("criterion_changed:" + case["id"])
        if any(
            c.get("status") != "pending"
            or any(
                c.get(k) is not None
                for k in ("answer_quote", "actual_model_run_id", "reviewer")
            )
            or c.get("evidence_paths") != []
            for c in checks
        ):
            failures.append("unsupported_semantic_credit:" + case["id"])
    return failures


def audit(
    prepared: Path, dataset: Path = DATASET, protocol: Path = PROTOCOL
) -> dict[str, Any]:
    cases = json.loads(dataset.read_bytes())["cases"]
    plan = json.loads(protocol.read_bytes())
    preparation = json.loads((prepared / "preparation.json").read_bytes())
    failures = []
    if (
        len(cases) != plan["case_count"]
        or len({c["id"] for c in cases}) != len(cases)
        or sum(len(c["manual_review"]) for c in cases) != plan["criterion_count"]
    ):
        failures.append("predeclared_cohort_or_criteria_changed")
    if (
        sha(dataset) != plan["dataset_sha256"]
        or (prepared / "case-dataset.json").read_bytes() != dataset.read_bytes()
        or preparation["dataset_sha256"] != sha(dataset)
    ):
        failures.append("dataset_identity_mismatch")
    if (
        type(preparation.get("model_invocations")) is not int
        or preparation.get("model_invocations") != 0
        or preparation.get("semantic_acceptance") != "not_run"
        or preparation.get("real_world_observations") != 0
    ):
        failures.append("preparation_claims_execution_or_outcomes")
    manifest = json.loads((prepared / "source-manifest.json").read_bytes())
    if (
        preparation["source_manifest_sha256"] != sha(prepared / "source-manifest.json")
        or source_manifest(
            prepared / "source", profile=preparation["source_snapshot_profile"]
        )
        != manifest
    ):
        failures.append("frozen_runtime_identity_mismatch")
    proposal = json.loads((prepared / "proposed-execution.json").read_bytes())
    if proposal.get("requires_session_authorization_for_independent_model") is not True:
        failures.append("independent_model_authorization_gate_missing")
    references = preparation["references"]
    if [r["case"] for r in references] != [c["id"] for c in cases]:
        failures.append("reference_case_set_changed")
    records = read_capture(prepared / "reference-mcp.jsonl")
    calls = [r for r in records if r.get("event") == "tool_call"]
    run_ids = []
    for ref, case in zip(references, cases):
        prompt_file = prepared / "model-prompts" / (case["id"] + ".txt")
        if prompt_file.read_text() != model_prompt(case):
            failures.append("model_prompt_changed:" + case["id"])
        file = (prepared / ref["payload_file"]).resolve()
        if (
            not file.is_relative_to(prepared.resolve())
            or sha(file) != ref["payload_sha256"]
        ):
            failures.append("reference_file_identity:" + case["id"])
            continue
        artifact = json.loads(file.read_bytes())
        failures.extend(
            f + ":" + case["id"] for f in check_reference(ref, artifact, case)
        )
        run_ids.append(ref["run_id"])
        matches = [
            r
            for r in calls
            if r.get("tool") == artifact["tool"]
            and r.get("arguments") == artifact["arguments"]
            and (r.get("result") or {}).get("structured_content")
            == artifact["structured_content"]
        ]
        if len(matches) != 1:
            failures.append("reference_not_exactly_one_captured_reply:" + case["id"])
    if len(calls) != len(cases) or len(set(run_ids)) != len(cases):
        failures.append("missing_or_reused_reference_run")
    failures.extend(
        check_pending_worksheet(
            json.loads((prepared / "review-worksheet.json").read_bytes()), cases
        )
    )
    return dict(
        audit_id="numerology_semantics_preparation_v1",
        preparation_integrity_passed=not failures,
        failures=failures,
        case_count=len(cases),
        criterion_count=plan["criterion_count"],
        reference_tool_profile=dict(scenarios="onda-xingpan", tool_scope="topic"),
        reference_runs=len(set(run_ids)),
        capture_records=len(records),
        model_invocations=0,
        semantic_acceptance="not_run",
        real_world_observations=0,
        independent_calendar_or_classical_oracles_added=0,
        raw_reference_integrity="file SHA and exact hash-chained captured reply; hashes detect changes, not authenticity",
        original_business_digest_status="retained, not recomputed from snapshot-less responses",
        dataset_sha256=sha(dataset),
        protocol_sha256=sha(protocol),
        source_manifest_sha256=sha(prepared / "source-manifest.json"),
        scope="Preparation and real MCP references only; no model trajectory, answer grading, blind holdout or full-domain certification.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.prepared.resolve())
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["preparation_integrity_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
