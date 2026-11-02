"""Verify review quotations against the first model run, without grading semantics."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_semantic_run_v1"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def same_json(left: Any, right: Any) -> bool:
    """Python equality alone would equate True with 1 inside a receipt."""
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def payload(record: dict[str, Any]) -> dict[str, Any]:
    result = record.get("result", {})
    value = result.get("structured_content")
    if value is None:
        for block in result.get("content", []):
            if block.get("type") == "text":
                try:
                    value = json.loads(block["text"])
                    break
                except ValueError:
                    continue
    if not isinstance(value, dict):
        raise ValueError("Missing actual response object")
    return value


def audit(review_path: Path) -> dict[str, Any]:
    review = json.loads(review_path.read_text())
    if digest(FIXTURE / "case-dataset.json") != review["dataset_sha256"]:
        raise ValueError("Frozen dataset changed")
    if digest(FIXTURE / "report.json") != review["original_run_report_sha256"]:
        raise ValueError("Original model report changed")
    dataset = json.loads((FIXTURE / "case-dataset.json").read_text())["cases"]
    run = json.loads((FIXTURE / "report.json").read_text())["cases"]
    if [r["id"] for r in review["cases"]] != [r["id"] for r in dataset]:
        raise ValueError("First cases disappeared or changed order")
    units = receipts = 0
    for case, spec, grade in zip(review["cases"], dataset, run, strict=True):
        if (
            case["id"] != grade["case"]
            or not same_json(
                case["mechanical_checks_passed"], grade["mechanical_checks_passed"]
            )
            or case["original_mechanical_failures"] != grade["failures"]
        ):
            raise ValueError("First mechanical grade changed")
        folder = FIXTURE / case["id"]
        answer_path, journal_path = folder / "answer.txt", folder / "mcp-calls.jsonl"
        if digest(answer_path) != case["answer_sha256"]:
            raise ValueError("First answer changed")
        if digest(journal_path) != case["capture_sha256"]:
            raise ValueError("First captured journal changed")
        actual = [json.loads(line) for line in journal_path.read_text().splitlines()]
        if len(actual) != len(case["source_packets"]):
            raise ValueError("Actual response omitted from review")
        if spec["tool_scope"] == "no_calculation" and actual:
            raise ValueError("Unknown-hour case unexpectedly calculated")
        responses = []
        for index, (original, supplied) in enumerate(
            zip(actual, case["source_packets"], strict=True)
        ):
            response = payload(original)
            if (
                supplied["journal_index"] != index
                or not same_json(supplied["actual_projected_payload"], response)
                or not same_json(supplied["input_arguments"], original["arguments"])
                or supplied["run_id"] != response["run_metadata"]["run_id"]
                or supplied["tool"] != original["tool"]
            ):
                raise ValueError("Review substituted another response or run")
            responses.append(response)
            receipts += 1
        answer = answer_path.read_text()
        previous = 0
        for unit in case["sentence_and_table_row_reviews"]:
            start, end = unit["answer_character_start"], unit["answer_character_end"]
            if (
                not (previous <= start < end <= len(answer))
                or answer[previous:start].strip()
                or answer[start:end] != unit["quote"]
            ):
                raise ValueError("Quotation changed or first answer text skipped")
            previous = end
            for path in unit["actual_receipt_paths"]:
                found = False
                for response in responses:
                    value: Any = response
                    try:
                        for part in path.split("."):
                            value = value[part]
                        found = True
                    except (KeyError, TypeError):
                        continue
                if not found:
                    raise ValueError("Review path absent from actual response: " + path)
            units += 1
        if answer[previous:].strip():
            raise ValueError("End of first answer omitted")
        if [r["criterion"] for r in case["manual_criteria"]] != spec["manual_review"]:
            raise ValueError("Frozen semantic criteria changed")
    return {
        "review_sha256": digest(review_path),
        "cases": len(review["cases"]),
        "actual_receipts": receipts,
        "sentence_and_table_units": units,
        "quotation_and_receipt_index_verified": True,
        "automatic_semantic_acceptance": False,
        "independent_external_review": "not_completed",
        "scope": "Index and first-artifact integrity only; projected replies are not complete business-hash verification and this audit does not judge language meaning.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.review), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
