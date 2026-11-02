"""Observed stale contracts remain failures; schema checks never certify a run."""

import gzip
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.audit_bazi_connected_contract import compare, contract_record

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-connected-contract-drift-v1"


def inputs():
    observed = json.loads((STUDY / "connected-contract-first.json").read_text())
    expected = json.loads(
        gzip.decompress(
            (
                ROOT
                / "docs/validation/bazi-source-index-input-revision-v1/transport-expectations-first.json.gz"
            ).read_bytes()
        )
    )
    schema = json.loads((STUDY / "fresh-output-schema-first.json").read_text())[
        "output_schema"
    ]
    return observed, expected, schema


def test_actual_observed_contract_rejects_every_complete_current_output_only_method_enum_conflicts():
    observed, expected, schema = inputs()
    original = deepcopy((observed, expected, schema))
    result = compare(observed, expected, schema)
    assert result["case_count"] == 14
    assert result["declared_input_rejected_cases"] == 0
    assert result["connected_declared_output_rejected_cases"] == 14
    assert result["current_output_rejected_cases"] == 0
    for row, case in zip(result["cases"], expected["cases"], strict=True):
        assert row["case_id"] == case["case_id"]
        assert row["pillars"] == case["pillars"]
        constants = [
            leaf
            for error in row["connected_declared_output_errors"]
            for leaf in error["leaf_errors"]
            if leaf["validator"] == "const"
        ]
        assert constants
        assert all(
            c["path"] == ["source_comparison", "reference_index", "method_id"]
            and c["expected"] == "registered_literal_source_annotations_v3"
            for c in constants
        )
    assert result["declared_contract_compatible"] is False
    assert result["connected_service_exception_cause_conclusively_observed"] is False
    assert result["connected_deployment_accepted"] is False
    assert (observed, expected, schema) == original


def test_fresh_matching_schema_is_compatible_without_claiming_live_or_predictive_acceptance():
    observed, expected, schema = inputs()
    fresh = contract_record(observed)
    fresh["output_schema"] = schema
    result = compare(
        {"matched_count": 1, "detail": "full", "tools": [fresh]}, expected, schema
    )
    assert result["declared_contract_compatible"] is True
    assert result["connected_deployment_accepted"] is False
    assert result["authority_certified"] is False
    assert result["overall_score"] is None
    assert result["original_gates_superseded"] is False


@pytest.mark.parametrize(
    "fault", ["empty", "duplicate_id", "missing_pillar", "missing_result"]
)
def test_frozen_rows_cannot_be_omitted_or_made_incomparable(fault):
    observed, expected, schema = inputs()
    if fault == "empty":
        expected["cases"] = []
    elif fault == "duplicate_id":
        expected["cases"].append(expected["cases"][0])
    elif fault == "missing_pillar":
        expected["cases"][0]["pillars"].pop()
    else:
        expected["cases"][0].pop("result")
    with pytest.raises((ValueError, KeyError)):
        compare(observed, expected, schema)


@pytest.mark.parametrize("fault", ["server", "tool", "partial", "multiple"])
def test_unrelated_or_partial_observations_cannot_stand_in_for_connected_tool(fault):
    observed, expected, schema = inputs()
    if fault == "server":
        observed["server"] = "another_server"
    elif fault == "tool":
        observed["uri"] = "fatebridge://tools/another_tool"
    else:
        doc = json.loads(observed["contents"][0]["text"])
        if fault == "partial":
            doc["detail"] = "summary"
        else:
            doc["tools"].append(doc["tools"][0])
            doc["matched_count"] = 2
        observed["contents"][0]["text"] = json.dumps(doc)
    with pytest.raises(ValueError):
        compare(observed, expected, schema)


def test_command_retains_negative_exit_code_and_wont_overwrite_evidence(tmp_path):
    command = [
        sys.executable,
        str(ROOT / "scripts/audit_bazi_connected_contract.py"),
        "--connected-contract",
        str(STUDY / "connected-contract-first.json"),
        "--expected-results",
        str(
            ROOT
            / "docs/validation/bazi-source-index-input-revision-v1/transport-expectations-first.json.gz"
        ),
        "--current-schema",
        str(STUDY / "fresh-output-schema-first.json"),
        "--output",
        str(tmp_path / "negative.json"),
        "--require-compatible",
    ]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 1
    saved = (tmp_path / "negative.json").read_bytes()
    result = json.loads(saved)
    assert result["connected_declared_output_rejected_cases"] == 14
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode == 2
    assert (tmp_path / "negative.json").read_bytes() == saved
