"""Supplement C5 visibility and budget checks; retain original JSON-only failure."""

from __future__ import annotations

import argparse
import ast
import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.validation.agent_capture import read_capture


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def same(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def response(record: dict[str, Any]) -> dict[str, Any]:
    result = record["result"]
    value = result.get("structured_content")
    if value is None:
        value = next(
            json.loads(block["text"])
            for block in result["content"]
            if block["type"] == "text"
        )
    if not isinstance(value, dict):
        raise ValueError("Missing response object")
    return value


def at(value: Any, path: str) -> Any:
    for part in path.split("."):
        value = value[part]
    return value


def decode_full_stdout(raw: str) -> tuple[dict[str, Any], bool]:
    """Recognize full JSON, optionally preceded by one exact hash display line.

    The display hash is not treated as a delivery digest. Same-run payload bytes
    must independently match result_delivery.sha256 in audit_index.
    """
    prefixed = False
    if raw.startswith("file_sha256 "):
        line, separator, body = raw.partition("\n")
        if not separator or re.fullmatch(r"file_sha256 [0-9a-f]{64}", line) is None:
            raise ValueError("Unknown stdout prefix")
        raw = body
        prefixed = True
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get("payload"), dict):
        raise ValueError("Not a full payload wrapper")
    return value, prefixed


def audit_index(folder: Path, review_path: Path) -> dict[str, Any]:
    provenance = json.loads((folder / "provenance.json").read_text())
    if (
        digest(folder / "provenance.json")
        != (folder / "provenance.sha256").read_text().strip()
    ):
        raise ValueError("Original artifact provenance changed")
    for relative, expected in provenance["files"].items():
        if digest(folder / relative) != expected:
            raise ValueError("Original first artifact changed: " + relative)
    original = json.loads((folder / "report.json").read_text())
    dataset = json.loads((folder / "case-dataset.json").read_text())["cases"]
    review = json.loads(review_path.read_text())
    if review["dataset_sha256"] != digest(folder / "case-dataset.json") or review[
        "run_report_sha256"
    ] != digest(folder / "report.json"):
        raise ValueError("Review uses another dataset or run")
    if [c["id"] for c in review["cases"]] != [c["id"] for c in dataset]:
        raise ValueError("Case disappeared or changed order")
    packets_count = units_count = verified_files = catalogs_count = 0
    for spec, grade, case in zip(
        dataset, original["cases"], review["cases"], strict=True
    ):
        if case["id"] != grade["case"] or not same(
            case["original_failures"], grade["failures"]
        ):
            raise ValueError("First grade changed")
        path = folder / case["id"]
        if (
            digest(path / "answer.txt") != case["answer_sha256"]
            or digest(path / "mcp-calls.jsonl") != case["capture_sha256"]
        ):
            raise ValueError("Original answer or capture changed")
        packet_path = path / case.get("review_payloads_file", "review-payloads.json")
        if digest(packet_path) != case["review_payloads_sha256"]:
            raise ValueError("Derived receipt packet changed")
        packets = json.loads(packet_path.read_text())
        journal = read_capture(path / "mcp-calls.jsonl")
        events = [
            json.loads(line)
            for line in (path / "events.jsonl").read_text().splitlines()
        ]
        expected_indices = [
            i
            for i, c in enumerate(journal)
            if c["event"] == "tool_call" and c.get("outcome") == "returned"
        ]
        if [p["journal_index"] for p in packets] != expected_indices:
            raise ValueError("Actual response omitted")
        catalogs_count += sum(c["event"] == "tool_list" for c in journal)
        for packet in packets:
            record = journal[packet["journal_index"]]
            native = response(record)
            payload = packet["payload"]
            if packet["tool"] != record["tool"] or not same(
                packet["arguments"], record["arguments"]
            ):
                raise ValueError("Another tool or input substituted")
            if packet["run_id"] != native.get("run_metadata", {}).get(
                "run_id"
            ) or packet["run_id"] != payload.get("run_metadata", {}).get("run_id"):
                raise ValueError("Another run substituted")
            delivery = native.get("result_delivery", {})
            if delivery.get("mode") == "paged":
                encoded = json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":")
                ).encode()
                if sha256(encoded).hexdigest() != delivery["sha256"]:
                    raise ValueError("Deferred same-run delivery hash changed")
                observed = [
                    e["item"]
                    for e in events
                    if e.get("type") == "item.completed"
                    and e.get("item", {}).get("type") == "command_execution"
                    and e["item"].get("exit_code") == 0
                    and delivery["file_path"] in e["item"].get("command", "")
                ]
                if not observed or packet["model_file_read_commands"] != [
                    e["command"] for e in observed
                ]:
                    raise ValueError("Deferred file not read in actual model events")
                full_read = False
                json_only_read = False
                for item in observed:
                    raw = item.get("aggregated_output", "")
                    try:
                        stdout, prefixed = decode_full_stdout(raw)
                    except ValueError:
                        continue
                    if same(stdout.get("payload"), payload):
                        full_read = True
                        json_only_read |= not prefixed
                # Preserve the first collector's JSON-only observation. A prefix
                # is accepted solely when the entire remaining JSON contains the
                # exact same-run payload whose delivery hash was checked above.
                if json_only_read is not packet["full_file_stdout_preserved"]:
                    raise ValueError("Full model-visible file read was misrepresented")
                if not full_read:
                    fragments = packet.get("model_read_fragments", [])
                    if not fragments:
                        raise ValueError(
                            "Selective read needs actual stdout field mappings"
                        )
                    visible = []
                    for fragment in fragments:
                        event = events[fragment["event_index"]]
                        item = event.get("item", {})
                        if item not in observed or not same(
                            json.loads(item["aggregated_output"]),
                            fragment["stdout_json"],
                        ):
                            raise ValueError("Selective-read stdout changed")
                        for mapping in fragment["field_mappings"]:
                            if not same(
                                at(fragment["stdout_json"], mapping["output_path"]),
                                at(payload, mapping["source_path"]),
                            ):
                                raise ValueError(
                                    "Selective-read field differs from source"
                                )
                            visible.append(mapping["source_path"])
                    packet["verified_visible_paths"] = visible
                verified_files += 1
            elif not same(payload, native):
                raise ValueError("Response payload differs from actual captured reply")
            if packet["projection"] is not (
                record["arguments"].get("fields") is not None
            ):
                raise ValueError("Projection status differs from the actual request")
            if packet["complete_business_hash_verified"] is not False:
                raise ValueError(
                    "This index audit does not verify the complete business hash"
                )
            packets_count += 1
        answer = (path / "answer.txt").read_text()
        previous = 0
        for unit in case["sentence_reviews"]:
            start, end = unit["start"], unit["end"]
            if (
                not previous <= start < end <= len(answer)
                or answer[previous:start].strip()
                or answer[start:end] != unit["quote"]
            ):
                raise ValueError("Quotation changed or answer sentence skipped")
            previous = end
            for ref in unit["evidence_paths"]:
                packet = packets[ref["packet"]]
                visible_paths = packet.get("verified_visible_paths")
                if visible_paths is not None and not any(
                    ref["path"] == p or ref["path"].startswith(p + ".")
                    for p in visible_paths
                ):
                    raise ValueError("Review cites a field the model did not read")
                try:
                    at(packet["payload"], ref["path"])
                except (KeyError, TypeError):
                    raise ValueError(
                        "Path absent from the actual same-run receipt"
                    ) from None
            units_count += 1
        if answer[previous:].strip():
            raise ValueError("Last answer sentence skipped")
        if [c["criterion"] for c in case["manual_criteria"]] != spec["manual_review"]:
            raise ValueError("Frozen semantic criteria changed")
        if spec.get("no_calculation") and any(
            p["tool"].startswith("bazi_") for p in packets
        ):
            raise ValueError("Unknown birth hour was calculated")
    return {
        "cases": len(dataset),
        "actual_receipt_packets": packets_count,
        "verified_deferred_files": verified_files,
        "catalog_receipts": catalogs_count,
        "sentence_units": units_count,
        "first_artifact_and_index_integrity": True,
        "automatic_semantic_judgment": False,
        "complete_business_hash_verification_claimed": False,
        "reality_prediction_efficacy": "not_tested",
        "independent_external_review": "not_completed",
    }


def typed_same(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            typed_same(left[k], right[k]) for k in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            typed_same(a, b) for a, b in zip(left, right)
        )
    return bool(left == right)


def typed_at(value: Any, path: str) -> Any:
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def audit(root: Path) -> dict[str, Any]:
    fixture = root / "tests/fixtures/bazi_budget_guide_v1"
    artifacts = root / "tests/fixtures/bazi_semantic_run_v5"
    review_path = root / "docs/validation/bazi-budget-guide-first-review-v1.json"
    protocol_path = fixture / "protocol.json"
    if (
        digest(protocol_path)
        != Path(str(protocol_path) + ".sha256").read_text().strip()
    ):
        raise ValueError("Frozen protocol changed")
    protocol = json.loads(protocol_path.read_bytes())
    for name, expected in protocol["original_bindings"].items():
        if digest(root / name) != expected:
            raise ValueError("Original evidence changed: " + name)
    index = audit_index(artifacts, review_path)
    manifest = json.loads((artifacts / "source-manifest.json").read_bytes())
    if manifest != json.loads((fixture / "runtime-source-manifest.json").read_bytes()):
        raise ValueError("Prepared/model source differs")
    proof = json.loads((fixture / "controlled-change-proof.json").read_bytes())
    baseline = json.loads((fixture / "baseline-source-manifest.json").read_bytes())
    changed = [n for n in baseline if manifest[n] != baseline[n]]
    if set(manifest) != set(baseline) or set(changed) != {
        "skills/_shared/consultation-core.md",
        "src/fatebridge/data/agent_scenarios.json",
    }:
        raise ValueError("Uncontrolled runtime change")
    del proof  # Retained as provenance; the manifests above are rechecked directly.
    # Compare actual saved runtime scorer ASTs, not the mutable live-tree module.
    import tarfile

    with tarfile.open(fixture / "runtime-source.tar.gz") as archive:
        raw = archive.extractfile("scripts/evaluate_agent.py")
        if raw is None:
            raise ValueError("Actual runtime grader absent")
        tree = ast.parse(raw.read())
    for name, expected in protocol["original_legacy_grader_asts"].items():
        node = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        if ast.dump(node, include_attributes=False) != expected:
            raise ValueError("Legacy grader changed")
    review = json.loads(review_path.read_bytes())
    claims = formatting = prefixed_reads = 0
    calls = []
    from scripts.evaluate_agent import observations

    for case in review["cases"]:
        folder = artifacts / case["id"]
        packets = json.loads((folder / case["review_payloads_file"]).read_bytes())
        events = [
            json.loads(line)
            for line in (folder / "events.jsonl").read_text().splitlines()
        ]
        observed_calls, _ = observations(events)
        for call in observed_calls:
            if call["server"] != "fatebridge":
                continue
            args = call["arguments"]
            limit = args.get("response_char_limit")
            respected = (
                "response_char_limit" not in args
                or type(limit) is int
                and 1 <= limit <= 8192
            )
            calls.append(
                {
                    "case": case["id"],
                    "tool": call["tool"],
                    "limit_present": "response_char_limit" in args,
                    "requested_limit": limit,
                    "strict_default_budget_respected": respected,
                }
            )
        for claim in case["direct_field_claims"]:
            if not typed_same(
                typed_at(packets[claim["packet"]]["payload"], claim["path"]),
                claim["value"],
            ):
                raise ValueError("Typed first-answer field mismatch")
            claims += 1
        formatting += sum(
            u["category"] == "formatting_only" for u in case["sentence_reviews"]
        )
        for packet in packets:
            for event in events:
                item = event.get("item", {})
                if (
                    event.get("type") != "item.completed"
                    or item.get("command") not in packet["model_file_read_commands"]
                ):
                    continue
                try:
                    stdout, prefixed = decode_full_stdout(
                        item.get("aggregated_output", "")
                    )
                except ValueError:
                    continue
                if prefixed and same(stdout["payload"], packet["payload"]):
                    prefixed_reads += 1
    native_sizes = []
    for case in review["cases"]:
        folder = artifacts / case["id"]
        for i, record in enumerate(read_capture(folder / "mcp-calls.jsonl")):
            if record["event"] == "tool_call" and record.get("outcome") == "returned":
                chars = len(
                    json.dumps(
                        response(record), ensure_ascii=False, separators=(",", ":")
                    )
                )
                native_sizes.append(
                    {
                        "case": case["id"],
                        "journal_index": i,
                        "tool": record["tool"],
                        "actual_structured_reply_chars": chars,
                        "within8192": chars <= 8192,
                    }
                )
    if claims != review["direct_field_claim_count"]:
        raise ValueError("Typed-claim count changed")
    legacy_log = (
        root
        / "docs/validation/bazi-budget-guide-local-files-v1/legacy-index-audit-first.log"
    ).read_text()
    if (
        "ValueError: Selective read needs actual stdout field mappings"
        not in legacy_log
    ):
        raise ValueError("Original index parser failure missing")
    return {
        "protocol_sha256": digest(protocol_path),
        "runner_sha256": digest(Path(__file__)),
        "index_audit": index,
        "case_count": len(review["cases"]),
        "answer_units": review["sentence_and_table_unit_count"],
        "formatting_units_included": formatting,
        "direct_typed_field_claims_verified": claims,
        "actual_budget_calls": calls,
        "actual_native_replies": native_sizes,
        "all_actual_model_calls_respect_default8192": all(
            c["strict_default_budget_respected"] for c in calls
        ),
        "all_actual_native_replies_within8192": all(
            c["within8192"] for c in native_sizes
        ),
        "hash_prefixed_full_reads_verified": prefixed_reads,
        "original_json_only_index_audit_passed": False,
        "original_json_only_failure_preserved": True,
        "reviewer_stdout_format_repair_scope": "One explicit hash line plus complete JSON; no partial/trailing/truncated stdout accepted, no delivery-hash bypass or model answer/grade change.",
        "runtime_source_files": len(manifest),
        "controlled_changed_paths": changed,
        "original_legacy_grader_asts_unchanged": True,
        "original_no_paging8192_gate_passed": False,
        "original_nineteen_unresolved": 19,
        "new_classical_accuracy_credit": 0,
        "real_world_predictive_validity": "not_tested",
        "independent_expert_acceptance": "not_completed",
        "automated_semantic_grading": False,
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve first outputs; choose a new path")
    result = audit(Path(__file__).resolve().parents[1])
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    import gzip

    args.output.write_bytes(
        gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw
    )
    Path(str(args.output) + ".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "case_count",
                    "answer_units",
                    "direct_typed_field_claims_verified",
                    "hash_prefixed_full_reads_verified",
                    "all_actual_model_calls_respect_default8192",
                    "all_actual_native_replies_within8192",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
