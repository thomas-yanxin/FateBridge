"""Reference preparation cannot earn interpretation credit or widen the exam."""

import copy
import json
from pathlib import Path

import pytest

from scripts.audit_numerology_semantics_preparation import (
    check_pending_worksheet,
    check_reference,
)

DATASET = (
    Path(__file__).parent / "fixtures/agent_behavior/numerology_semantic_cases_v1.json"
)
CASES = json.loads(DATASET.read_bytes())["cases"]


def reference():
    case = CASES[0]
    return (
        {
            "run_id": "reference-only",
            "reference_profile": {"scenarios": "onda-xingpan", "tool_scope": "topic"},
        },
        {
            "tool": "heluo",
            "arguments": {
                **case["reference_request"]["arguments"],
                "fields": None,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
            "is_error": False,
            "structured_content": {
                "run_metadata": {
                    "run_id": "reference-only",
                    "tool_name": "heluo",
                    "business_output_sha256": "0" * 64,
                }
            },
        },
        case,
    )


def worksheet():
    return {
        "model_invocations": 0,
        "cases": [
            {
                "case": case["id"],
                "model_status": "not_run",
                "semantic_status": "pending",
                "checks": [
                    {
                        "criterion": criterion,
                        "status": "pending",
                        "answer_quote": None,
                        "actual_model_run_id": None,
                        "reviewer": None,
                        "evidence_paths": [],
                    }
                    for criterion in case["manual_review"]
                ],
            }
            for case in CASES
        ],
    }


def test_reference_integrity_does_not_claim_original_business_digest_recomputed():
    record, artifact, case = reference()
    # A source digest is retained as an opaque identity. It is not the hash of
    # the snapshot-less structured reply, and this check grants no semantic pass.
    assert check_reference(record, artifact, case) == []
    assert check_pending_worksheet(worksheet(), CASES) == []


@pytest.mark.parametrize(
    "change,expected",
    [
        ("scope", "reference_scope_widened"),
        ("arguments", "reference_request_mismatch"),
        ("run", "reference_run_identity_mismatch"),
        ("tool", "reference_tool_identity_mismatch"),
        ("error", "reference_not_successful"),
        ("snapshot", "unexpected_snapshot_text"),
        ("digest", "missing_original_business_identity"),
    ],
)
def test_tampered_reference_cannot_pass(change, expected):
    record, artifact, case = reference()
    if change == "scope":
        record["reference_profile"]["tool_scope"] = "complete"
    elif change == "arguments":
        artifact["arguments"]["use_true_solar_time"] = True
    elif change == "run":
        artifact["structured_content"]["run_metadata"]["run_id"] = "other-run"
    elif change == "tool":
        artifact["structured_content"]["run_metadata"]["tool_name"] = "canping"
    elif change == "error":
        artifact["is_error"] = True
    elif change == "snapshot":
        artifact["structured_content"]["snapshot_text"] = "unexpected"
    else:
        artifact["structured_content"]["run_metadata"].pop("business_output_sha256")
    assert expected in check_reference(record, artifact, case)


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("model_invocations", False, "preparation_promoted_to_model_execution"),
        ("model_status", "completed", "preparation_promoted_to_semantic_acceptance"),
        ("semantic_status", "pass", "preparation_promoted_to_semantic_acceptance"),
        ("criterion", "easier replacement", "criterion_changed"),
        ("status", "pass", "unsupported_semantic_credit"),
        ("answer_quote", "invented answer", "unsupported_semantic_credit"),
        ("actual_model_run_id", "reference-only", "unsupported_semantic_credit"),
        ("reviewer", "unperformed review", "unsupported_semantic_credit"),
        ("evidence_paths", ["reference.json"], "unsupported_semantic_credit"),
    ],
)
def test_reference_or_fabricated_review_never_earns_model_credit(key, value, expected):
    value = copy.deepcopy(value)
    data = worksheet()
    if key == "model_invocations":
        data[key] = value
    elif key in {"model_status", "semantic_status"}:
        data["cases"][0][key] = value
    else:
        data["cases"][0]["checks"][0][key] = value
    assert any(f.startswith(expected) for f in check_pending_worksheet(data, CASES))


def test_dropping_a_failed_case_would_change_the_predeclared_cohort():
    data = worksheet()
    data["cases"].pop()
    assert "worksheet_case_set_changed" in check_pending_worksheet(data, CASES)
