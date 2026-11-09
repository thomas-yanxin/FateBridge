"""Synthetic, offline checks for the post-review evidence auditor.

No model, production chart or language judge participates in these fixtures.
"""

import asyncio
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.validation.agent_capture import CaptureJournal
from fatebridge.validation.external_evaluation import freeze_external_selection
from scripts.evaluate_agent import grade_case
from scripts.evaluation.audit_mingli_evaluation import audit

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def mutate(path, operation):
    document = json.loads(path.read_text())
    operation(document)
    write_json(path, document)


def make_run(tmp_path, *, case_count=1, executed_count=None):
    """Seal valid synthetic cases, completed artifacts and attributed reviews."""
    run = tmp_path / "run"
    run.mkdir()
    review = tmp_path / "review.json"
    cases, executed, reviewed = [], [], []
    for number in range(1, case_count + 1):
        cases.append(
            {
                "id": f"synthetic-{number}-input",
                "source_case_id": f"synthetic-birth-{number}",
                "identity_key": f"birth:synthetic-{number}",
                "birth_fingerprint": hashlib.sha256(str(number).encode()).hexdigest(),
                "split": "development",
                "evaluation_layer": "input_quality",
                "source": {"repository": "synthetic fixture", "commit": "a" * 40},
                "prompt": "虚构资料，记载08:12，钟时口径不明且暂时查不到。",
                "manual_review": [
                    "保留明确时分，拒绝补造钟时。",
                    "说明缺项并停止重复追问。",
                ],
                "no_calculation": True,
                "allowed_tools": ["knowledge_read"],
            }
        )
    document = {
        "schema_version": 1,
        "suite_id": "mingli-bench-v2",
        "dataset_kind": "public_competition",
        "split": "development",
        "selection_kind": "frozen_single_split",
        "provenance": {"scope": "Entirely synthetic offline test; no source facts"},
        "cases": cases,
    }
    dataset = freeze_external_selection(document, run)
    (run / "case-dataset.json").write_bytes(dataset)
    for case in cases:
        target = run / case["id"]
        target.mkdir()
        answer = "原文记载08:12；时区未确认，不能排盘。\n资料暂时查不到，无须继续追问。"
        (target / "answer.txt").write_text(answer)
        actual_run_id = case["id"] + "-actual-tool-run"
        arguments = {"domain": "bazi", "category": "ten_gods", "key": "正官"}
        reply = {
            "structured_content": {
                "title": "正官",
                "run_metadata": {"run_id": actual_run_id},
            },
            "is_error": False,
        }
        capture = {
            "event": "tool_call",
            "tool": "knowledge_read",
            "arguments": arguments,
            "outcome": "returned",
            "result": reply,
        }
        journal = CaptureJournal(target / "mcp-calls.jsonl")
        try:
            asyncio.run(journal.append(capture))
        finally:
            journal.close()
        events = [
            {
                "type": "item.completed",
                "item": {
                    "type": "mcp_tool_call",
                    "server": "fatebridge",
                    "tool": "knowledge_read",
                    "arguments": arguments,
                    "status": "completed",
                    "result": reply,
                },
            }
        ]
        (target / "events.jsonl").write_text(json.dumps(events[0]) + "\n")
        grade = grade_case(case, events, answer, 0, [capture])
        assert grade["mechanical_checks_passed"]
        executed.append({"case": case["id"], "exit_code": 0, **grade})
        checks = []
        for index, quote in enumerate(
            ("原文记载08:12；时区未确认，不能排盘。", "资料暂时查不到，无须继续追问。"),
            1,
        ):
            start = answer.index(quote)
            checks.append(
                {
                    "criterion_index": index,
                    "criterion": case["manual_review"][index - 1],
                    "status": "pass",
                    "answer_quote": quote,
                    "quote_start": start,
                    "quote_end": start + len(quote),
                    "rationale": "Coding-assistant decision on synthetic quoted text.",
                    "actual_evidence_paths": [str(target / "mcp-calls.jsonl")],
                    "actual_run_ids": [actual_run_id],
                }
            )
        reviewed.append(
            {
                "case_id": case["id"],
                "evaluation_layer": case["evaluation_layer"],
                "overall_status": "pass",
                "answer_sha256": digest(target / "answer.txt"),
                "events_sha256": digest(target / "events.jsonl"),
                "capture_sha256": digest(target / "mcp-calls.jsonl"),
                "checks": checks,
            }
        )
    write_json(
        run / "report.json",
        {
            "split": "development",
            "dataset_sha256": digest(run / "case-dataset.json"),
            "cases": (
                executed[:executed_count] if executed_count is not None else executed
            ),
        },
    )
    write_json(
        review,
        {
            "schema_version": 1,
            "reviewer_role": "coding_assistant_semantic_review",
            "cases": reviewed,
        },
    )
    return run, review


def test_synthetic_sealed_run_replays_and_audits_without_models(tmp_path):
    run, review = make_run(tmp_path)
    result = audit(run, [review])
    assert result["complete"]
    assert result["accepted_in_this_batch"]
    assert result["mechanical_grade_replay"] == "matched"
    assert result["model_invocations_by_auditor"] == 0
    assert result["real_world_prediction"] == "not_tested"
    assert result["layer_denominators"]["input_quality"] == {
        "selected": 1,
        "executed": 1,
        "mechanical_passed": 1,
        "semantic_reviewed": 1,
        "semantic_passed": 1,
        "semantic_failed": 0,
        "semantic_unverified": 0,
    }


@pytest.mark.parametrize(
    "change",
    [{"answer_quote": "未出现的引文"}, {"quote_start": 1}, {"quote_end": True}],
)
def test_changed_quote_or_offsets_are_rejected(tmp_path, change):
    run, review = make_run(tmp_path)
    mutate(review, lambda d: d["cases"][0]["checks"][0].update(change))
    with pytest.raises(ValueError, match="quote or offsets mismatch"):
        audit(run, [review])


@pytest.mark.parametrize("key", ["answer_sha256", "events_sha256", "capture_sha256"])
def test_review_hashes_must_match_the_actual_artifacts(tmp_path, key):
    run, review = make_run(tmp_path)
    mutate(review, lambda d: d["cases"][0].update({key: "0" * 64}))
    with pytest.raises(ValueError, match="evidence hash mismatch"):
        audit(run, [review])


def test_edited_artifact_cannot_reuse_an_old_review(tmp_path):
    run, review = make_run(tmp_path)
    answer = run / "synthetic-1-input/answer.txt"
    answer.write_text(answer.read_text() + "\n新增断言。")
    with pytest.raises(ValueError, match="evidence hash mismatch"):
        audit(run, [review])


@pytest.mark.parametrize("change", ["text", "missing", "reordered"])
def test_criteria_cannot_be_mutated_omitted_or_reordered(tmp_path, change):
    run, review = make_run(tmp_path)

    def modify(document):
        checks = document["cases"][0]["checks"]
        if change == "text":
            checks[0]["criterion"] = "事后改写判据"
        elif change == "missing":
            checks.pop()
        else:
            checks.reverse()

    mutate(review, modify)
    with pytest.raises(ValueError, match="criterion changed|semantic criteria"):
        audit(run, [review])


def test_preparation_or_other_run_ids_cannot_replace_actual_model_evidence(tmp_path):
    run, review = make_run(tmp_path)
    mutate(
        review,
        lambda d: d["cases"][0]["checks"][0].update(
            actual_run_ids=["separate-preparation-reference-run"]
        ),
    )
    with pytest.raises(ValueError, match="non-actual run"):
        audit(run, [review])


@pytest.mark.parametrize("change", ["unknown", "duplicate", "unexecuted"])
def test_reviews_must_match_unique_executed_cases(tmp_path, change):
    run, review = make_run(
        tmp_path, case_count=2 if change == "unexecuted" else 1, executed_count=1
    )
    if change == "unknown":
        mutate(review, lambda d: d["cases"][0].update(case_id="unknown-case"))
    elif change == "duplicate":
        mutate(review, lambda d: d["cases"].append(copy.deepcopy(d["cases"][0])))
    with pytest.raises(ValueError, match="Unknown, duplicate or unexecuted review"):
        audit(run, [review])


@pytest.mark.parametrize("missing", ["execution", "review"])
def test_incomplete_evidence_never_becomes_an_accepted_batch(tmp_path, missing):
    run, review = make_run(
        tmp_path, case_count=2, executed_count=1 if missing == "execution" else 2
    )
    mutate(review, lambda d: d["cases"].pop())
    with pytest.raises(
        ValueError, match="Incomplete model execution or semantic review"
    ):
        audit(run, [review])
    partial = audit(run, [review], require_complete=False)
    assert not partial["complete"]
    assert not partial["accepted_in_this_batch"]
    assert partial["unreviewed_case_ids"] == ["synthetic-2-input"]
    assert partial["unexecuted_case_ids"] == (
        ["synthetic-2-input"] if missing == "execution" else []
    )


@pytest.mark.parametrize("change", ["passed", "failures", "exit_code"])
def test_stored_mechanical_grades_must_replay_from_actual_events(tmp_path, change):
    run, review = make_run(tmp_path)
    updates = {
        "passed": {"mechanical_checks_passed": False},
        "failures": {"failures": ["invented_failure"]},
        "exit_code": {"exit_code": 1},
    }
    mutate(run / "report.json", lambda d: d["cases"][0].update(updates[change]))
    with pytest.raises(ValueError, match="mechanical grade replay mismatch"):
        audit(run, [review])


def test_archived_payload_must_match_actual_delivery_even_after_file_hash_is_updated(
    tmp_path,
):
    run, review = make_run(tmp_path)
    target = run / "synthetic-1-input"
    capture_path = target / "mcp-calls.jsonl"
    row = json.loads(capture_path.read_text())
    original_payload = copy.deepcopy(row["result"]["structured_content"])
    payload_text = json.dumps(
        original_payload, ensure_ascii=False, separators=(",", ":")
    )
    original_path = tmp_path / "original-delivery.json"
    delivery = {
        "mode": "paged",
        "file_path": str(original_path),
        "file_payload_path": "payload",
        "total_bytes": len(payload_text.encode()),
        "total_chars": len(payload_text),
    }
    row["result"]["structured_content"]["result_delivery"] = delivery
    # All records here are synthetic. Regenerate their valid local chain so the
    # payload assertion is exercised independently of capture/file-byte hashes.
    capture_path.unlink()
    journal = CaptureJournal(capture_path)
    try:
        asyncio.run(
            journal.append(
                {
                    key: value
                    for key, value in row.items()
                    if key
                    not in {"sequence", "recorded_at", "previous_sha256", "sha256"}
                }
            )
        )
    finally:
        journal.close()
    events_path = target / "events.jsonl"
    event = json.loads(events_path.read_text())
    event["item"]["result"] = row["result"]
    events_path.write_text(json.dumps(event) + "\n")
    archive = target / "delivered-files/1.json"
    archive.parent.mkdir()
    write_json(archive, {"payload": original_payload})
    manifest = target / "delivery-archive.json"
    write_json(
        manifest,
        {
            "entries": [
                {
                    "original_path": str(original_path),
                    "archived_file": "delivered-files/1.json",
                    "run_id": original_payload["run_metadata"]["run_id"],
                    "file_sha256": digest(archive),
                    "file_payload_path": "payload",
                }
            ]
        },
    )
    mutate(
        review,
        lambda document: document["cases"][0].update(
            events_sha256=digest(events_path), capture_sha256=digest(capture_path)
        ),
    )
    assert audit(run, [review])["accepted_in_this_batch"]
    mutate(archive, lambda document: document["payload"].update(title="篡改后内容"))
    mutate(
        manifest,
        lambda document: document["entries"][0].update(file_sha256=digest(archive)),
    )
    with pytest.raises(ValueError, match="Archive payload differs"):
        audit(run, [review])


def test_script_cli_audits_only_synthetic_saved_artifacts(tmp_path):
    run, review = make_run(tmp_path)
    output = tmp_path / "audit.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.evaluation.audit_mingli_evaluation",
            "--run",
            str(run),
            "--review",
            str(review),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["accepted_in_this_batch"]
    audited = json.loads(output.read_text())
    assert audited["complete"]
    assert audited["model_invocations_by_auditor"] == 0
