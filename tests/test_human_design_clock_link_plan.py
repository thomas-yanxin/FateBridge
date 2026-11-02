"""Plan identity and failed/missing rows survive forged complete metadata."""

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "clock_link_audit", ROOT / "scripts/audit_human_design_clock_links.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PLAN = (ROOT / "tests/fixtures/human-design-disc-clock-plan.json").read_bytes()
COHORT = json.loads(
    (ROOT / "tests/fixtures/human-design-disc-clock-observations.json").read_text()
)
PLAN_SHA = "2ad8f1dd94abba5540b881369c61fe8df7937a6ed103139fca5f4d882997daf0"


def test_real_missing9remain_required_when_partial_metadata_is_consistent():
    assert hashlib.sha256(PLAN).hexdigest() == PLAN_SHA
    result = MODULE.source_plan_links(PLAN, COHORT, PLAN_SHA)
    assert result["required_plan_case_count"] == 22
    assert result["observed_case_count"] == 13
    assert len(result["missing_planned_ids"]) == 9
    assert result["collection_metadata_consistent"]
    assert not result["complete_source_plan_links"]


def test_editing_counts_and_deleting_failed_rows_cannot_make_a_complete_plan():
    changed = deepcopy(COHORT)
    changed["cases"] = [changed["cases"][0]]
    changed["planned_case_count"] = changed["observed_case_count"] = 1
    changed["missing_planned_ids"] = []
    changed["collection_status"] = "complete"
    result = MODULE.source_plan_links(PLAN, changed, PLAN_SHA)
    assert result["required_plan_case_count"] == 22
    assert len(result["missing_planned_ids"]) == 21
    assert not result["collection_metadata_consistent"]
    assert not result["complete_source_plan_links"]
    assert result["all_supplied_rows_retained"]


def test_changed_birth_input_stays_visible_and_never_restores_completeness():
    changed = deepcopy(COHORT)
    changed["cases"][0]["birth_input"]["birth_timezone"] = "UTC"
    result = MODULE.source_plan_links(PLAN, changed, PLAN_SHA)
    assert not result["input_link_cases"][0]["original_input_matched"]
    assert len(result["input_link_cases"]) == 13
    assert not result["complete_source_plan_links"]


def test_changed_plan_bytes_are_rejected_against_the_original_digest():
    with pytest.raises(ValueError, match="required digest"):
        MODULE.source_plan_links(PLAN + b" ", COHORT, PLAN_SHA)
