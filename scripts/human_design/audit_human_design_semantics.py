"""Bind a complete first-answer review to actual observed MCP evidence.

This validates quotations, inputs, provenance and review completeness. It does
not decide whether the reviewer's semantic judgments are correct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any

from fatebridge.services.replay_metadata import digest
from fatebridge.validation.agent_capture import read_capture
from fatebridge.validation.claims import _same_value
from fatebridge.validation.evaluation_environment import (
    load_selection,
    verify_stage_selection,
)
from scripts.evaluate_agent import model_prompt, observations

DATASET_SHA256 = "0e413de085cb892fffa222c05219ec438b0e62f9ee1d769b293c7e0f931dad9b"
COHORT_SHA256 = {
    "original-v1": DATASET_SHA256,
    "source-contract-v2": "af298d2f53fcb7f1437d5ed520cb94d413caf31edc83d6b4471ba02d0dd95d8c",
    "complete-answer-v3": "c2f5454a5be108312a77c28ad239ddfd36849e2f01e97465e5813269759062e8",
}
DECISIONS = {"pass", "fail", "indeterminate"}


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def response(record: dict[str, Any]) -> dict[str, Any]:
    result = record["result"]
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
        raise ValueError("Missing actual structured reply")
    return value


def lookup(value: Any, path: str) -> Any:
    if not isinstance(path, str) or not path:
        raise ValueError("Evidence requires a nonempty field path")
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def accept_delivery(
    packet: dict[str, Any], source: dict[str, Any], text: str, *, full_requested: bool
) -> None:
    delivery = packet["result_delivery"]
    if (
        hashlib.sha256(text.encode()).hexdigest() != delivery["sha256"]
        or len(text) != delivery["total_chars"]
        or len(text.encode()) != delivery["total_bytes"]
    ):
        raise ValueError("Observed delivery bytes changed")
    full = json.loads(text)
    for key in ("run_id", "business_output_sha256"):
        if not _same_value(full["run_metadata"][key], packet["run_metadata"][key]):
            raise ValueError("Delivery substituted another run")
    source["delivered"] = full
    if (
        digest({k: v for k, v in full.items() if k != "run_metadata"})
        == packet["run_metadata"]["business_output_sha256"]
    ):
        source["complete"] = full
    elif full_requested:
        raise ValueError("Unprojected delivery is not a complete business result")


def observed_sources(
    records: list[dict[str, Any]], events: list[dict[str, Any]] | None = None
) -> dict[int, dict[str, Any]]:
    """Only observed packets/pages; never read a fresh reference or recalculate."""
    sources: dict[int, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if record["event"] != "tool_call" or record.get("outcome") != "returned":
            continue
        packet = response(record)
        sources[index] = {"projected": packet, "pages": {}}
        delivery = packet.get("result_delivery")
        if not delivery:
            continue
        full_requested = record.get("arguments", {}).get("fields") is None
        # File reading is also observable through the original completed shell
        # event. Accept only its printed payload with the original transport
        # checksum, never a file opened now or a newly calculated reference.
        filename = delivery.get("file_path")
        for event in events or []:
            item = event.get("item", {})
            if not (
                event.get("type") == "item.completed"
                and item.get("type") == "command_execution"
                and item.get("exit_code") == 0
                and filename
                and filename in item.get("command", "")
            ):
                continue
            for line in item.get("aggregated_output", "").splitlines():
                try:
                    wrapper = json.loads(line)
                except ValueError:
                    continue
                if isinstance(wrapper, dict) and isinstance(
                    wrapper.get("payload"), dict
                ):
                    text = json.dumps(
                        wrapper["payload"], ensure_ascii=False, separators=(",", ":")
                    )
                    accept_delivery(
                        packet, sources[index], text, full_requested=full_requested
                    )
        prefix = f"fatebridge://results/{delivery['result_id']}/pages/"
        pages: dict[int, dict[str, Any]] = sources[index]["pages"]
        for page_index, page_record in enumerate(records[index + 1 :], index + 1):
            if (
                page_record["event"] != "resource_read"
                or page_record.get("outcome") != "returned"
                or not page_record.get("uri", "").startswith(prefix)
            ):
                continue
            blocks = page_record["result"].get("contents", [])
            if len(blocks) != 1 or not isinstance(blocks[0].get("text"), str):
                raise ValueError("Malformed observed delivery page")
            page = json.loads(blocks[0]["text"])
            offset = int(page_record["uri"][len(prefix) :])
            if (
                type(page.get("offset")) is not int
                or page["offset"] != offset
                or page.get("sha256") != delivery["sha256"]
                or not isinstance(page.get("text"), str)
            ):
                raise ValueError("Observed page identity changed")
            pages[page_index] = page
        by_offset: dict[int, dict[str, Any]] = {}
        for page in pages.values():
            offset = page["offset"]
            if offset in by_offset and not _same_value(by_offset[offset], page):
                raise ValueError("Different page bodies at the same observed offset")
            by_offset[offset] = page
        next_page_offset: int | None = 0
        parts: list[str] = []
        visited: set[int] = set()
        while (
            next_page_offset is not None
            and next_page_offset in by_offset
            and next_page_offset not in visited
        ):
            visited.add(next_page_offset)
            page = by_offset[next_page_offset]
            parts.append(page["text"])
            following = page.get("next_offset")
            if following is not None and (
                type(following) is not int
                or following != next_page_offset + len(page["text"])
                or following <= next_page_offset
            ):
                raise ValueError("Observed page chain changed")
            next_page_offset = following
        if next_page_offset is not None:
            continue  # Partial observation is retained, never promoted to a full run.
        text = "".join(parts)
        accept_delivery(packet, sources[index], text, full_requested=full_requested)
    return sources


def verify_evidence(item: dict[str, Any], sources: dict[int, dict[str, Any]]) -> None:
    index = item["journal_index"]
    if type(index) is not int or index not in sources:
        raise ValueError("Evidence is not an actual tool packet")
    source = sources[index]
    if item["run_id"] != source["projected"]["run_metadata"]["run_id"]:
        raise ValueError("Evidence substituted another run")
    if item["kind"] == "field":
        if item["source"] not in {"projected", "delivered", "complete", "advertised"}:
            raise ValueError("Unknown observed field source")
        selected = source[item["source"]]
        if not _same_value(lookup(selected, item["path"]), item["value"]):
            raise ValueError(
                "Evidence value/type differs from the actual observed field"
            )
    elif item["kind"] == "page_text":
        page = source["pages"][item["page_journal_index"]]
        start, end = item["start"], item["end"]
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(page["text"])
            or page["text"][start:end] != item["quote"]
        ):
            raise ValueError(
                "Evidence quote differs from the observed same-run fragment"
            )
    else:
        raise ValueError("Unknown evidence kind")


def audit_review(
    run_dir: Path,
    review_path: Path,
    *,
    source_archive: Path | None = None,
    cohort: str = "original-v1",
) -> dict[str, Any]:
    if cohort not in COHORT_SHA256:
        raise ValueError("Unknown preregistered semantic cohort")
    expected_dataset = COHORT_SHA256[cohort]
    review = json.loads(review_path.read_text())
    dataset_path, report_path = run_dir / "case-dataset.json", run_dir / "report.json"
    if (
        file_digest(dataset_path) != expected_dataset
        or review["dataset_sha256"] != expected_dataset
    ):
        raise ValueError("Original sealed development cohort changed")
    if file_digest(report_path) != review["original_report_sha256"]:
        raise ValueError("Original mechanical report changed")
    specs = json.loads(dataset_path.read_text())["cases"]
    report = json.loads(report_path.read_text())
    native_binding = None
    native_sha = report.get("native_environment_sha256")
    stage_binding = None
    if (run_dir.parent / "preparation.json").is_file():
        stage_binding = verify_stage_selection(run_dir.parent, run_dir)
    if native_sha is not None:
        if review.get("native_environment_sha256") != native_sha:
            raise ValueError("Review is detached from the recorded native selection")
        load_selection(run_dir / "native-environment.json", native_sha)
        if stage_binding is not None:
            native_binding = stage_binding
        else:
            native_binding = {
                "status": "verified_execution_selection_only",
                "native_environment_sha256": native_sha,
                "stage_equivalence_verified": False,
            }
    manifest = json.loads((run_dir / "source-manifest.json").read_text())
    if digest(manifest) != report["source_sha256"]:
        raise ValueError("Original model source manifest changed")
    for name in manifest:
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Model source path escapes the frozen snapshot")
    if source_archive is None:
        for name, expected in manifest.items():
            if file_digest(run_dir / "source" / name) != expected:
                raise ValueError("Original model runtime source changed")
    else:
        # Read regular members directly; never extract executable files or links.
        with tarfile.open(source_archive, "r:gz") as archive:
            members = archive.getmembers()
            if len(members) != len(manifest) or {m.name for m in members} != {
                "source/" + n for n in manifest
            }:
                raise ValueError("Archived model source members changed")
            for member in members:
                if not member.isfile():
                    raise ValueError("Archived model source is not a regular file")
                stream = archive.extractfile(member)
                if (
                    stream is None
                    or hashlib.sha256(stream.read()).hexdigest()
                    != manifest[member.name.removeprefix("source/")]
                ):
                    raise ValueError("Archived model runtime source changed")
    ids = [c["id"] for c in specs]
    completed = {c["case"]: c for c in report["cases"]}
    if (
        [c["case"] for c in report["cases"]] != ids[: len(completed)]
        or report["unrun_case_ids"] != ids[len(completed) :]
        or [c["id"] for c in review["cases"]] != ids
    ):
        raise ValueError("Original cases, execution queue or order changed")
    unit_count, field_count, fragment_count, complete_count = 0, 0, 0, 0
    reviewed_answers, failed_without_answer = 0, 0
    advertised_files, advertised_field_count = 0, 0
    decisions: Counter[str] = Counter()
    for spec, case in zip(specs, review["cases"], strict=True):
        if case["id"] not in completed:
            if case["status"] != "not_run" or case.get("units") or case.get("criteria"):
                raise ValueError("Unrun case promoted to a reviewed answer")
            continue
        original = completed[case["id"]]
        if (
            case["original_mechanical_failures"] != original["failures"]
            or case["mechanical_checks_passed"]
            is not original["mechanical_checks_passed"]
        ):
            raise ValueError("Original mechanical outcome changed")
        folder = run_dir / case["id"]
        answer_path, capture_path = folder / "answer.txt", folder / "mcp-calls.jsonl"
        events_path = folder / "events.jsonl"
        if file_digest(events_path) != case["events_sha256"]:
            raise ValueError("Original model events changed")
        prompt_path = folder / "model-prompt.txt"
        if file_digest(prompt_path) != original[
            "prompt_sha256"
        ] or prompt_path.read_text() != model_prompt(spec):
            raise ValueError(
                "Original actual model prompt or sealed case contract changed"
            )
        if (
            "capture" in original
            and file_digest(capture_path) != original["capture"]["journal_sha256"]
        ):
            raise ValueError(
                "Actual capture differs from the original mechanical report"
            )
        events = [
            json.loads(line)
            for line in events_path.read_text().splitlines()
            if line.strip()
        ]
        calls, commands = observations(events)
        if (
            not _same_value(
                [c for c in calls if c["server"] == "fatebridge"],
                original["tool_calls"],
            )
            or commands != original["commands"]
        ):
            raise ValueError(
                "Original observed calls/commands differ from mechanical report"
            )
        if case["status"] == "execution_failed_without_answer":
            if (
                type(original.get("exit_code")) is not int
                or original["exit_code"] == 0
                or (answer_path.is_file() and answer_path.read_text().strip())
                or any(
                    e.get("type") == "item.completed"
                    and e.get("item", {}).get("type") == "agent_message"
                    and e["item"].get("text", "").strip()
                    for e in events
                )
                or case.get("units")
                or case.get("criteria")
            ):
                raise ValueError(
                    "Executed answer relabeled as an infrastructure failure"
                )
            expected_answer = file_digest(answer_path) if answer_path.exists() else None
            if (
                case["answer_sha256"] != expected_answer
                or file_digest(capture_path) != case["capture_sha256"]
            ):
                raise ValueError("Original empty answer or failure capture changed")
            read_capture(capture_path)
            failed_without_answer += 1
            continue
        if case["status"] != "reviewed":
            raise ValueError("Executed case has no original answer review")
        if (
            file_digest(answer_path) != case["answer_sha256"]
            or file_digest(capture_path) != case["capture_sha256"]
        ):
            raise ValueError("Original answer or actual captured reply changed")
        answer = answer_path.read_text()
        messages = [
            e["item"]["text"]
            for e in events
            if e.get("type") == "item.completed"
            and e.get("item", {}).get("type") == "agent_message"
        ]
        if not messages or messages[-1] != answer:
            raise ValueError(
                "Answer file differs from the original final agent message"
            )
        reviewed_answers += 1
        events = [
            json.loads(line)
            for line in events_path.read_text().splitlines()
            if line.strip()
        ]
        records = read_capture(capture_path)
        sources = observed_sources(records, events)
        preserved = case.get("preserved_deliveries", [])
        expected = {
            i for i, s in sources.items() if s["projected"].get("result_delivery")
        }
        if {item["journal_index"] for item in preserved} != expected or len(
            preserved
        ) != len(expected):
            raise ValueError("Original advertised deliveries omitted or duplicated")
        for item in preserved:
            name = Path(item["file"])
            if (
                name.name != item["file"]
                or file_digest(folder / name) != item["file_sha256"]
            ):
                raise ValueError("Preserved original delivery path or bytes changed")
            index = item["journal_index"]
            payload = json.loads((folder / name).read_text())["payload"]
            text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            bound: dict[str, Any] = {}
            accept_delivery(
                sources[index]["projected"],
                bound,
                text,
                full_requested=records[index].get("arguments", {}).get("fields")
                is None,
            )
            if item["full_business_hash_verified"] is not ("complete" in bound):
                raise ValueError(
                    "Projected delivery promoted to full business verification"
                )
            # Original advertised file, not necessarily a field the model
            # printed/read: keep its distinct source type and evidence counts.
            sources[index]["advertised"] = payload
            advertised_files += 1
        complete_count += sum("complete" in s for s in sources.values())
        previous = 0
        for unit in case["units"]:
            start, end = unit["start"], unit["end"]
            if (
                type(start) is not int
                or type(end) is not int
                or not previous <= start < end <= len(answer)
                or answer[previous:start].strip()
                or answer[start:end] != unit["quote"]
            ):
                raise ValueError(
                    "Original answer quotation changed or nonempty text omitted"
                )
            previous = end
            if unit["assessment"] not in {
                "supported",
                "contradicted",
                "unverified",
                "non_factual",
            }:
                raise ValueError("Unknown reviewer unit assessment")
            if sources and unit["assessment"] == "supported" and not unit["evidence"]:
                raise ValueError(
                    "Supported answer unit has no actual same-run evidence"
                )
            for item in unit["evidence"]:
                verify_evidence(item, sources)
                field_count += item["kind"] == "field"
                advertised_field_count += (
                    item["kind"] == "field" and item.get("source") == "advertised"
                )
                fragment_count += item["kind"] == "page_text"
            unit_count += 1
        if answer[previous:].strip():
            raise ValueError("Original answer ending omitted")
        if [c["criterion"] for c in case["criteria"]] != spec["manual_review"]:
            raise ValueError("Original manual criterion changed or omitted")
        for criterion in case["criteria"]:
            if (
                criterion["status"] not in DECISIONS
                or not criterion["rationale"].strip()
            ):
                raise ValueError("Missing reviewer decision/rationale")
            if not criterion["unit_indices"] or any(
                type(i) is not int or not 0 <= i < len(case["units"])
                for i in criterion["unit_indices"]
            ):
                raise ValueError("Criterion has no bound first-answer quotation")
            decisions[criterion["status"]] += 1
    result = {
        "status": "verified_first_answer_review_binding",
        "cohort_cases": len(specs),
        "executed_cases": len(completed),
        "reviewed_answers": reviewed_answers,
        "execution_failed_without_answer": failed_without_answer,
        "quotation_units": unit_count,
        "typed_actual_field_bindings": field_count,
        "observed_same_run_fragment_bindings": fragment_count,
        "complete_observed_business_deliveries": complete_count,
        "original_advertised_delivery_files_preserved": advertised_files,
        "advertised_file_field_bindings_visibility_not_certified": advertised_field_count,
        "reviewer_criterion_decisions": dict(decisions),
        "semantic_judgment_independently_certified": False,
        "all_live_model_answers_certified": False,
        "real_world_prediction_observations": 0,
        "scope": "Original complete answers, failed mechanical outcomes, sealed criteria and actual observed MCP fields/fragments bound without recalculation. Local journal hashes require trusted capture custody. A partial page is not full-business verification; this integrity check does not grade semantic truth or certify arbitrary future model text.",
    }
    if native_binding is not None:
        result["native_environment_binding"] = native_binding
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path)
    parser.add_argument("--cohort", choices=tuple(COHORT_SHA256), default="original-v1")
    args = parser.parse_args()
    result = audit_review(
        args.run, args.review, source_archive=args.source_archive, cohort=args.cohort
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
