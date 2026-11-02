"""Verify all first model replies and developer review, retaining budget misses."""

from __future__ import annotations

import argparse
import ast
import gzip
import json
from pathlib import Path
from typing import Any

from scripts.audit_bazi_dayun_integer import digest, frozen, write_summary
from scripts.audit_bazi_semantic_batch import audit as audit_index
from scripts.evaluate_agent import observations

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_semantic_refresh_v1"
ARTIFACTS = ROOT / "tests/fixtures/bazi_semantic_run_v4"
REVIEW = ROOT / "docs/validation/bazi-semantic-refresh-first-review-v1.json"


def at(value: Any, path: str) -> Any:
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def same(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            same(left[k], right[k]) for k in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return bool(left == right)


def audit() -> dict[str, Any]:
    protocol = frozen(FIXTURE / "protocol.json")
    for name, expected in protocol["original_bindings"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("An original report, dataset or grader changed: " + name)
    review = frozen(REVIEW)
    index = audit_index(ARTIFACTS, REVIEW)
    # The .py.txt archive is plain text, not a JSON document.
    source_path = FIXTURE / "grader-before.py.txt"
    if digest(source_path) != Path(str(source_path) + ".sha256").read_text().strip():
        raise ValueError("First grader source changed")
    tree = ast.parse(source_path.read_text())
    for name, expected in protocol["original_legacy_grader_asts"].items():
        node = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        if ast.dump(node, include_attributes=False) != expected:
            raise ValueError("Registered original grader AST changed")
    checked = 0
    overrides = []
    actual_replies = 0
    formatting = 0
    policies = set()
    metadata_variants: dict[str, Any] = {}
    for case in review["cases"]:
        folder = ARTIFACTS / case["id"]
        grade = json.loads((folder / "grade.json").read_bytes())
        policies.add(grade["grading_policy"])
        packets = json.loads((folder / case["review_payloads_file"]).read_bytes())
        events = [
            json.loads(line)
            for line in (folder / "events.jsonl").read_text().splitlines()
        ]
        calls, _ = observations(events)
        for call in calls:
            if call["server"] != "fatebridge":
                continue
            limit = call["arguments"].get("response_char_limit")
            if type(limit) is int and (limit == 0 or limit > 8192):
                overrides.append(
                    {
                        "case": case["id"],
                        "tool": call["tool"],
                        "requested_response_char_limit": limit,
                    }
                )
        for claim in case["direct_field_claims"]:
            actual = at(packets[claim["packet"]]["payload"], claim["path"])
            if not same(actual, claim["value"]):
                raise ValueError(
                    "First answer value/type differs from actual reply: "
                    + case["id"]
                    + " "
                    + claim["path"]
                )
            if "representation_normalization" in claim:
                if (
                    claim["value"] != "庚（金）"
                    or claim.get("answer_stem") != "庚"
                    or claim.get("answer_element") != "金"
                    or "庚金" not in (folder / "answer.txt").read_text()
                ):
                    raise ValueError(
                        "Declared display normalization changed the answer facts"
                    )
            checked += 1
        formatting += sum(
            unit["category"] == "formatting_only" for unit in case["sentence_reviews"]
        )
        for packet in packets:
            metadata = packet["payload"].get("run_metadata", {})
            runtime = metadata.get("runtime", {})
            if runtime.get("environment_sha256"):
                metadata_variants[runtime["environment_sha256"]] = runtime
            actual_replies += 1
    expected_overrides = [
        {k: row[k] for k in ("case", "tool", "requested_response_char_limit")}
        for row in review["budget_overrides"]
    ]
    if (
        overrides != expected_overrides
        or len(overrides) != review["explicit_budget_override_count"]
    ):
        raise ValueError("Actual execution budget overrides differ from review")
    if (
        policies != {"observable_tools_v1"}
        or checked != review["direct_field_claim_count"]
    ):
        raise ValueError("Original grader or direct-check coverage changed")
    old = json.loads(
        gzip.decompress(
            (
                ROOT / "tests/fixtures/bazi_passage_relations_v1/before-source.json.gz"
            ).read_bytes()
        )
    )
    gate_path = "tests/test_classical_passage_transports.py"
    if (ROOT / gate_path).read_text() != old[gate_path]:
        raise ValueError("The original8192 gate source changed")
    return {
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "runner_sha256": digest(Path(__file__)),
        "review_sha256": digest(REVIEW),
        "index_audit": index,
        "case_count": len(review["cases"]),
        "actual_captured_replies": actual_replies,
        "direct_typed_field_claims_verified": checked,
        "answer_units": review["sentence_and_table_unit_count"],
        "formatting_units_included": formatting,
        "automated_semantic_grading": False,
        "developer_semantic_review_scope": "All first-answer sentences/table rows under original criteria; hashes and paths only verify quotations/evidence, not independent semantic or source correctness.",
        "original_mechanical_grading_policy": sorted(policies),
        "original_mechanical_score": "11/11",
        "actual_budget_overrides": overrides,
        "all_actual_model_calls_respect8192": not overrides,
        "strict_default8192_component_acceptance": "failed_budget_overrides_retained",
        "original_no_paging8192_gate_passed": False,
        "original8192_assertions_unchanged": True,
        "actual_model_runtime_variants": metadata_variants,
        "runtime_scope": "Model workspaces used the observed runtime inventory, including empty native ephemeris inventories; not a claim that the original37file inventory gate was solved.",
        "original_nineteen_unresolved": 19,
        "new_independent_classical_cases": 0,
        "new_model_executions": 11,
        "independent_expert_acceptance": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve first outputs; choose a new path")
    result = audit()
    write_summary(args.output, result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "case_count",
                    "actual_captured_replies",
                    "direct_typed_field_claims_verified",
                    "answer_units",
                    "all_actual_model_calls_respect8192",
                    "full_goal_complete",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
