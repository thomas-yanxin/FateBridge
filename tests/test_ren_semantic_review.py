"""Review indexing must retain first failures, actual runs and exact quotations."""

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from fatebridge.services.replay_metadata import digest
from fatebridge.validation.agent_capture import CaptureJournal

SPEC = importlib.util.spec_from_file_location(
    "audit_ren_semantic_review",
    Path(__file__).resolve().parents[1] / "scripts/audit_ren_semantic_review.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


@pytest.fixture
def cohort(tmp_path):
    body = {"jinkou": {"rows": [{"content": "申"}]}}
    full = {
        **body,
        "run_metadata": {
            "run_id": "actual-run",
            "business_output_sha256": digest(body),
        },
    }
    raw = json.dumps(full, ensure_ascii=False, separators=(",", ":"))
    delivery = {
        "sha256": MODULE.sha256(raw.encode()).hexdigest(),
        "total_chars": len(raw),
        "total_bytes": len(raw.encode()),
    }
    folder = tmp_path / "first"
    folder.mkdir()
    write_json(folder / "delivery-1.json", {"payload": full})
    journal = CaptureJournal(folder / "mcp-calls.jsonl")
    asyncio.run(journal.append({"event": "tool_list", "tool_names": ["jinkou"]}))
    asyncio.run(
        journal.append(
            {
                "event": "tool_call",
                "tool": "jinkou",
                "arguments": {"fields": None},
                "outcome": "returned",
                "result": {"structured_content": {**full, "result_delivery": delivery}},
            }
        )
    )
    journal.close()
    (folder / "answer.txt").write_text("将神为申。\n")
    write_json(
        tmp_path / "case-dataset.json",
        {"cases": [{"id": "first", "manual_review": ["解释实际结果"]}]},
    )
    write_json(
        tmp_path / "report.json",
        {
            "cases": [
                {
                    "case": "first",
                    "mechanical_checks_passed": False,
                    "failures": ["skill_not_observed:onda-zhanbu"],
                }
            ],
            "unrun_case_ids": [],
        },
    )
    review = {
        "dataset_sha256": MODULE.file_digest(tmp_path / "case-dataset.json"),
        "original_run_report_sha256": MODULE.file_digest(tmp_path / "report.json"),
        "cases": [
            {
                "id": "first",
                "status": "reviewed",
                "mechanical_checks_passed": False,
                "original_mechanical_failures": ["skill_not_observed:onda-zhanbu"],
                "answer_sha256": MODULE.file_digest(folder / "answer.txt"),
                "capture_sha256": MODULE.file_digest(folder / "mcp-calls.jsonl"),
                "preserved_deliveries": [
                    {
                        "journal_index": 1,
                        "file": "delivery-1.json",
                        "file_sha256": MODULE.file_digest(folder / "delivery-1.json"),
                        "complete_business_hash_verified": True,
                    }
                ],
                "units": [
                    {
                        "start": 0,
                        "end": 5,
                        "quote": "将神为申。",
                        "evidence": [
                            {
                                "journal_index": 1,
                                "run_id": "actual-run",
                                "path": "jinkou.rows.0.content",
                            }
                        ],
                    }
                ],
                "manual_criteria": [
                    {"criterion": "解释实际结果", "status": "pass", "unit_indices": [0]}
                ],
            }
        ],
    }
    write_json(tmp_path / "review.json", review)
    return tmp_path, review


def test_integrity_pass_does_not_promote_manual_review_or_erase_first_failure(cohort):
    root, _ = cohort
    result = MODULE.audit(root, root / "review.json")
    assert result["complete_business_hashes_verified"] == 1
    assert result["automatic_semantic_acceptance"] is False
    assert result["independent_external_review"] == "not_completed"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda c: c.update(mechanical_checks_passed=True), "mechanical"),
        (lambda c: c.update(original_mechanical_failures=[]), "mechanical"),
        (lambda c: c["units"][0].update(quote="将神为酉。"), "quotation"),
        (lambda c: c["units"][0].update(start=1, quote="神为申。"), "quotation"),
        (
            lambda c: c["units"][0]["evidence"][0].update(run_id="reference-run"),
            "another run",
        ),
        (
            lambda c: c["units"][0]["evidence"][0].update(path="jinkou.rows.2.content"),
            "path absent",
        ),
        (lambda c: c["manual_criteria"][0].update(criterion="换标准"), "criteria"),
        (lambda c: c["manual_criteria"][0].update(unit_indices=[1]), "outside"),
        (
            lambda c: c["preserved_deliveries"][0].update(
                complete_business_hash_verified=False
            ),
            "Projected delivery",
        ),
    ],
)
def test_review_substitution_fails(cohort, mutation, message):
    root, review = cohort
    mutation(review["cases"][0])
    write_json(root / "review.json", review)
    with pytest.raises(ValueError, match=message):
        MODULE.audit(root, root / "review.json")


def test_omitting_first_answer_end_fails(cohort):
    root, review = cohort
    unit = review["cases"][0]["units"][0]
    unit.update(end=3, quote="将神为")
    write_json(root / "review.json", review)
    with pytest.raises(ValueError, match="End of first answer"):
        MODULE.audit(root, root / "review.json")


def test_changed_delivery_with_recomputed_file_hash_still_fails_same_run(cohort):
    root, review = cohort
    path = root / "first/delivery-1.json"
    data = json.loads(path.read_text())
    data["payload"]["run_metadata"]["run_id"] = "separate-reference-run"
    write_json(path, data)
    review["cases"][0]["preserved_deliveries"][0]["file_sha256"] = MODULE.file_digest(
        path
    )
    write_json(root / "review.json", review)
    with pytest.raises(ValueError, match="actual same-run"):
        MODULE.audit(root, root / "review.json")
