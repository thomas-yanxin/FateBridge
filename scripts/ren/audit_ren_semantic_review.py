"""Check first-answer quotations and same-run evidence; never grade meaning."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.services.replay_metadata import digest
from fatebridge.validation.agent_capture import read_capture


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def response(record: dict[str, Any]) -> dict[str, Any]:
    value = record["result"].get("structured_content")
    if value is None:
        for block in record["result"].get("content", []):
            if block.get("type") == "text":
                try:
                    value = json.loads(block["text"])
                    break
                except ValueError:
                    continue
    if not isinstance(value, dict):
        raise ValueError("Actual tool response is missing")
    return value


def lookup(value: Any, path: str) -> Any:
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def audit(run_dir: Path, review_path: Path) -> dict[str, Any]:
    review = json.loads(review_path.read_text())
    dataset_path, report_path = run_dir / "case-dataset.json", run_dir / "report.json"
    if file_digest(dataset_path) != review["dataset_sha256"]:
        raise ValueError("Frozen dataset changed")
    if file_digest(report_path) != review["original_run_report_sha256"]:
        raise ValueError("First run report changed")
    specs = json.loads(dataset_path.read_text())["cases"]
    report = json.loads(report_path.read_text())
    if [c["id"] for c in review["cases"]] != [c["id"] for c in specs]:
        raise ValueError("First cohort disappeared or changed order")
    completed = {c["case"]: c for c in report["cases"]}
    ordered_ids = [c["id"] for c in specs]
    if [c["case"] for c in report["cases"]] != ordered_ids[: len(completed)] or report[
        "unrun_case_ids"
    ] != ordered_ids[len(completed) :]:
        raise ValueError("First execution queue changed")
    unit_count = receipt_count = full_business_count = 0
    statuses: Counter[str] = Counter()
    for case, spec in zip(review["cases"], specs, strict=True):
        case_id = case["id"]
        if case_id not in completed:
            if case["status"] != "not_run" or case_id not in report["unrun_case_ids"]:
                raise ValueError("Unrun case relabeled")
            if case.get("units"):
                raise ValueError("Unrun case has answer quotations")
            continue
        original = completed[case_id]
        if (
            case["status"] != "reviewed"
            or case["mechanical_checks_passed"]
            is not original["mechanical_checks_passed"]
            or case["original_mechanical_failures"] != original["failures"]
        ):
            raise ValueError("First mechanical result changed")
        folder = run_dir / case_id
        answer_path, capture_path = folder / "answer.txt", folder / "mcp-calls.jsonl"
        if file_digest(answer_path) != case["answer_sha256"]:
            raise ValueError("First answer changed")
        if file_digest(capture_path) != case["capture_sha256"]:
            raise ValueError("First capture changed")
        records = read_capture(capture_path)
        packets = {
            i: response(r)
            for i, r in enumerate(records)
            if r["event"] == "tool_call" and r.get("outcome") == "returned"
        }
        receipt_count += len(packets)
        for item in case["preserved_deliveries"]:
            projected = packets[item["journal_index"]]
            delivery = projected["result_delivery"]
            path = folder / item["file"]
            if path.parent != folder or file_digest(path) != item["file_sha256"]:
                raise ValueError("Preserved delivery changed")
            payload = json.loads(path.read_text())["payload"]
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            if (
                sha256(encoded.encode()).hexdigest() != delivery["sha256"]
                or len(encoded) != delivery["total_chars"]
                or len(encoded.encode()) != delivery["total_bytes"]
                or payload["run_metadata"]["run_id"]
                != projected["run_metadata"]["run_id"]
                or payload["run_metadata"]["business_output_sha256"]
                != projected["run_metadata"]["business_output_sha256"]
            ):
                raise ValueError("Delivery is not the actual same-run payload")
            body = {k: v for k, v in payload.items() if k != "run_metadata"}
            verified = (
                digest(body) == projected["run_metadata"]["business_output_sha256"]
            )
            if verified is not item["complete_business_hash_verified"]:
                raise ValueError(
                    "Projected delivery promoted to complete business result"
                )
            full_business_count += verified
            packets[item["journal_index"]] = payload
        answer = answer_path.read_text()
        previous = 0
        for unit in case["units"]:
            start, end = unit["start"], unit["end"]
            if (
                not (previous <= start < end <= len(answer))
                or answer[previous:start].strip()
                or answer[start:end] != unit["quote"]
            ):
                raise ValueError("First-answer quotation changed or text omitted")
            previous = end
            for evidence in unit["evidence"]:
                packet = packets[evidence["journal_index"]]
                if packet["run_metadata"]["run_id"] != evidence["run_id"]:
                    raise ValueError("Evidence substituted another run")
                try:
                    lookup(packet, evidence["path"])
                except (KeyError, IndexError, TypeError, ValueError) as error:
                    raise ValueError(
                        "Evidence path absent from actual reply"
                    ) from error
            unit_count += 1
        if answer[previous:].strip():
            raise ValueError("End of first answer omitted")
        criteria = case["manual_criteria"]
        if [c["criterion"] for c in criteria] != spec["manual_review"]:
            raise ValueError("Preregistered semantic criteria changed")
        for criterion in criteria:
            if criterion["status"] not in {"pass", "fail", "partial", "not_covered"}:
                raise ValueError("Unknown manual decision")
            if any(not 0 <= i < len(case["units"]) for i in criterion["unit_indices"]):
                raise ValueError("Manual decision points outside first answer")
            statuses[criterion["status"]] += 1
    return {
        "review_sha256": file_digest(review_path),
        "cases_in_original_cohort": len(specs),
        "executed_cases": len(completed),
        "actual_tool_receipts": receipt_count,
        "quotation_units": unit_count,
        "complete_business_hashes_verified": full_business_count,
        "manual_criterion_status_counts": dict(statuses),
        "quotation_and_same_run_index_verified": True,
        "automatic_semantic_acceptance": False,
        "independent_external_review": "not_completed",
        "scope": "Artifact and quotation integrity only. Manual meaning judgments remain reviewable decisions; hashes do not establish truth or prediction efficacy.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.run_dir, args.review), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
