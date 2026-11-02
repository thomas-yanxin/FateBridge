"""Check all original answers, actual receipts and manual-review quotations."""

from __future__ import annotations

import argparse
import json
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


def audit(folder: Path, review_path: Path) -> dict[str, Any]:
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
                for item in observed:
                    try:
                        stdout = json.loads(item.get("aggregated_output", ""))
                    except ValueError:
                        continue
                    if isinstance(stdout, dict) and same(
                        stdout.get("payload"), payload
                    ):
                        full_read = True
                if full_read is not packet["full_file_stdout_preserved"]:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.artifacts, args.review), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
