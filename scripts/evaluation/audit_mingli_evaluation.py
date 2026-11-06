"""Audit external model records and quote-backed semantic review; never call a model.

This validates evidence integrity and completeness, not natural-language truth.
Review decisions remain attributable to the declared reviewer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from fatebridge.utils.json_values import same_value
from fatebridge.validation.agent_capture import read_capture
from fatebridge.validation.external_evaluation import load_frozen_selection
from scripts.evaluate_agent import grade_case, observations


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_delivery_archive(target: Path, captured: list[dict[str, Any]]) -> None:
    """Bind optional durable file copies to the actual server's delivery receipt."""
    manifest = target / "delivery-archive.json"
    if not manifest.exists():
        return
    deliveries = {}
    for row in captured:
        result = row.get("result", {}).get("structured_content") or {}
        delivery = result.get("result_delivery") or {}
        if delivery.get("file_path"):
            deliveries[str(Path(delivery["file_path"]).resolve())] = (
                result,
                delivery,
            )
    for entry in json.loads(manifest.read_text())["entries"]:
        original = str(Path(entry["original_path"]).resolve())
        if original not in deliveries:
            raise ValueError("Archive was not delivered by this actual run")
        inline, delivery = deliveries[original]
        run_id = inline.get("run_metadata", {}).get("run_id")
        path = (target / entry["archived_file"]).resolve()
        if not path.is_relative_to(target) or not path.is_file():
            raise ValueError("Archive file escapes this actual case")
        if (
            entry["run_id"] != run_id
            or entry["file_payload_path"] != delivery["file_payload_path"]
            or entry["file_sha256"] != digest(path)
        ):
            raise ValueError("Archive delivery identity or file hash mismatch")
        body = json.loads(path.read_text())
        payload = body[delivery["file_payload_path"]]
        encoded = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode()
        if (
            len(encoded) != delivery["total_bytes"]
            or len(encoded.decode()) != delivery["total_chars"]
            or payload.get("run_metadata", {}).get("run_id") != run_id
            or any(
                not same_value(payload.get(key), value)
                for key, value in inline.items()
                if key not in {"run_metadata", "result_delivery"}
            )
        ):
            raise ValueError("Archive payload differs from observed delivery")


def audit(
    run: Path, reviews: list[Path], *, require_complete: bool = True
) -> dict[str, Any]:
    run = run.resolve()
    report = json.loads((run / "report.json").read_text())
    split = report["split"]
    document = load_frozen_selection(run / "case-dataset.json", split)
    if report["dataset_sha256"] != digest(run / "case-dataset.json"):
        raise ValueError("Run dataset hash mismatch")
    cases = {case["id"]: case for case in document["cases"]}
    executed: dict[str, Any] = {}
    observed_ids: dict[str, set[str]] = {}
    for record in report["cases"]:
        name = record["case"]
        if name not in cases or name in executed:
            raise ValueError("Unknown or duplicate executed case")
        target = run / name
        answer = (target / "answer.txt").read_text()
        events = [
            json.loads(line)
            for line in (target / "events.jsonl").read_text().splitlines()
            if line.strip()
        ]
        captured = read_capture(target / "mcp-calls.jsonl")
        validate_delivery_archive(target, captured)
        calls = [row for row in captured if row["event"] == "tool_call"]
        visible, _ = observations(events)
        visible = [row for row in visible if row["server"] == "fatebridge"]
        normalize = lambda rows: sorted(
            json.dumps([row["tool"], row["arguments"]], sort_keys=True) for row in rows
        )
        if normalize(calls) != normalize(visible):
            raise ValueError("Capture and observed tool calls disagree: " + name)
        replay = grade_case(cases[name], events, answer, record["exit_code"], calls)
        if any(
            record[key] != replay[key]
            for key in ("mechanical_checks_passed", "failures")
        ):
            raise ValueError("Original mechanical grade replay mismatch: " + name)
        observed_ids[name] = {
            result["run_metadata"]["run_id"]
            for row in calls
            if isinstance(
                result := row.get("result", {}).get("structured_content"), dict
            )
            and isinstance(result.get("run_metadata"), dict)
            and result["run_metadata"].get("run_id")
        }
        executed[name] = record
    reviewed: dict[str, Any] = {}
    review_sources = []
    for path in reviews:
        data = json.loads(path.read_text())
        if data.get("schema_version") != 1 or not data.get("reviewer_role"):
            raise ValueError("Semantic review needs schema version and reviewer")
        review_sources.append({"path": str(path.resolve()), "sha256": digest(path)})
        for row in data["cases"]:
            name = row["case_id"]
            if name not in executed or name in reviewed:
                raise ValueError("Unknown, duplicate or unexecuted review case")
            case = cases[name]
            if row["evaluation_layer"] != case["evaluation_layer"]:
                raise ValueError("Semantic layer mismatch")
            target = run / name
            for key, filename in (
                ("answer_sha256", "answer.txt"),
                ("events_sha256", "events.jsonl"),
                ("capture_sha256", "mcp-calls.jsonl"),
            ):
                if row.get(key) != digest(target / filename):
                    raise ValueError("Semantic evidence hash mismatch: " + name)
            answer = (target / "answer.txt").read_text()
            checks = row["checks"]
            expected = case["manual_review"]
            if len(checks) != len(expected) or [
                check["criterion_index"] for check in checks
            ] != list(range(1, len(expected) + 1)):
                raise ValueError("Incomplete or reordered semantic criteria")
            for check, criterion in zip(checks, expected):
                if check["criterion"] != criterion:
                    raise ValueError("Semantic criterion changed")
                if check["status"] not in {"pass", "fail", "unverified"}:
                    raise ValueError("Unknown semantic status")
                start, end = check["quote_start"], check["quote_end"]
                quote = check["answer_quote"]
                if (
                    type(start) is not int
                    or type(end) is not int
                    or not isinstance(quote, str)
                    or not quote
                    or not 0 <= start < end <= len(answer)
                    or answer[start:end] != quote
                ):
                    raise ValueError("Semantic answer quote or offsets mismatch")
                if not check.get("rationale") or not check.get("actual_evidence_paths"):
                    raise ValueError(
                        "Semantic review lacks rationale or actual evidence"
                    )
                for reference in check["actual_evidence_paths"]:
                    filename = re.split(r":L\d+|#", reference, maxsplit=1)[0]
                    evidence = Path(filename).resolve()
                    if not evidence.is_relative_to(target) or not evidence.is_file():
                        raise ValueError(
                            "Semantic evidence is outside this actual case"
                        )
                ids = set(check.get("actual_run_ids", []))
                if not ids <= observed_ids[name]:
                    raise ValueError("Semantic review cites a non-actual run")
                if case["evaluation_layer"] == "interpretation_fidelity" and not ids:
                    raise ValueError("Fidelity review needs actual model run evidence")
            statuses = {check["status"] for check in checks}
            expected_overall = (
                "fail"
                if "fail" in statuses
                else "unverified" if "unverified" in statuses else "pass"
            )
            if row["overall_status"] != expected_overall:
                raise ValueError("Semantic overall status contradicts its checks")
            reviewed[name] = row
    complete = set(executed) == set(cases) == set(reviewed)
    if require_complete and not complete:
        raise ValueError("Incomplete model execution or semantic review")
    layers = {}
    for layer in ("input_quality", "interpretation_fidelity", "consultation_boundary"):
        names = {
            name for name, case in cases.items() if case["evaluation_layer"] == layer
        }
        layer_statuses = Counter(
            reviewed[name]["overall_status"] for name in names & reviewed.keys()
        )
        layers[layer] = {
            "selected": len(names),
            "executed": len(names & executed.keys()),
            "mechanical_passed": sum(
                executed[name]["mechanical_checks_passed"]
                for name in names & executed.keys()
            ),
            "semantic_reviewed": len(names & reviewed.keys()),
            "semantic_passed": layer_statuses["pass"],
            "semantic_failed": layer_statuses["fail"],
            "semantic_unverified": layer_statuses["unverified"],
        }
    accepted = (
        complete
        and all(row["mechanical_checks_passed"] for row in executed.values())
        and all(row["overall_status"] == "pass" for row in reviewed.values())
    )
    return {
        "schema_version": 1,
        "suite_id": document["suite_id"],
        "split": split,
        "complete": complete,
        "accepted_in_this_batch": accepted,
        "mechanical_grade_replay": "matched",
        "selected_case_count": len(cases),
        "reviewed_case_count": len(reviewed),
        "unexecuted_case_ids": sorted(cases.keys() - executed.keys()),
        "unreviewed_case_ids": sorted(cases.keys() - reviewed.keys()),
        "layer_denominators": layers,
        "run_dir": str(run),
        "run_report_sha256": digest(run / "report.json"),
        "case_dataset_sha256": digest(run / "case-dataset.json"),
        "review_sources": review_sources,
        "reviewer_roles": sorted(
            {json.loads(path.read_text())["reviewer_role"] for path in reviews}
        ),
        "scope": "Evidence/quote/completeness audit of declared semantic decisions; not automatic language correctness, external human expert acceptance or predictive validity.",
        "model_invocations_by_auditor": 0,
        "archive_original_content_independently_authenticated": False,
        "real_world_prediction": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    try:
        result = audit(
            args.run, args.review, require_complete=not args.allow_incomplete
        )
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "complete": result["complete"],
                "accepted_in_this_batch": result["accepted_in_this_batch"],
                "reviewed_case_count": result["reviewed_case_count"],
            }
        )
    )
    return 0 if result["accepted_in_this_batch"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
