"""Protect complete-cohort custody and retention of failures in the new audit."""

import importlib.util
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "full_profile_audit", ROOT / "scripts/audit_human_design_profile_full_coverage.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PROFILE = json.loads(
    (ROOT / "tests/data/human_design/profile_cohort/cohort.json").read_text()
)


def test_all_original_cohorts_are_required_without_expanding_the_shared_verifier():
    prepared = MODULE.prepare(deepcopy(PROFILE))
    assert [(name, len(ref["cases"])) for name, ref in prepared["cohorts"]] == [
        ("original19", 19),
        ("original193", 193),
        ("profile768", 192),
    ]
    assert len(prepared["combined"]["cases"]) == 404
    assert len(prepared["missing"]) == 576
    assert prepared["combined"]["cohorts"] == [
        {
            "chart_count": len(ref["cases"]),
            "scope": ref["scope"],
            "source": ref["source"],
        }
        for _, ref in prepared["cohorts"]
    ]


@pytest.mark.parametrize(
    "changed",
    [
        MODULE.PLAN,
        "tests/fixtures/human-design-official-charts.json",
        "tests/fixtures/human-design-official-cross-charts.json",
        "tests/fixtures/human-design-cross-coverage-plan.json",
        "tests/fixtures/human-design-cross-coverage-observations.json",
        *MODULE.EXTRA_PRESERVED,
    ],
)
def test_original_plan_and_every_preserved_source_cannot_be_rewritten(
    tmp_path, changed
):
    plan = json.loads((ROOT / MODULE.PLAN).read_text())
    for name in [
        MODULE.PLAN,
        *plan["preserved_cohorts_sha256"],
        *MODULE.EXTRA_PRESERVED,
    ]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    target = tmp_path / changed
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed"):
        MODULE.prepare(deepcopy(PROFILE), tmp_path)


@pytest.mark.parametrize("tamper", ["drop_middle", "reorder", "birth", "complete"])
def test_profile_subset_reordering_changed_input_and_false_completion_are_rejected(
    tamper,
):
    profile = deepcopy(PROFILE)
    if tamper == "drop_middle":
        profile["cases"].pop(12)
    elif tamper == "reorder":
        profile["cases"][0], profile["cases"][1] = (
            profile["cases"][1],
            profile["cases"][0],
        )
    elif tamper == "birth":
        profile["cases"][0]["birth_input"]["birth_hour"] ^= 1
    else:
        profile["collection_status"] = "complete"
        profile["missing_planned_ids"] = []
    with pytest.raises(ValueError, match="prefix|birth input|completeness metadata"):
        MODULE.prepare(profile)


def test_all_failed_rows_stay_in_each_denominator_and_no_report_row_can_disappear():
    prepared = MODULE.prepare(deepcopy(PROFILE))
    # Synthetic report only: this deliberately failing input is not a chart oracle.
    rows = [
        {
            "id": case["id"],
            "status": "failed",
            "gate_lines_checked": 26,
            "gate_lines_matched": 26,
            "gate_line_mismatches": [],
            "structure_checks": {"profile": True, "cross_name": False},
        }
        for case in prepared["combined"]["cases"]
    ]
    groups = MODULE.split_official_checks(prepared, {"cases": rows})
    assert [r["literal_name_failures"] for r in groups] == [19, 193, 192]
    assert all(r["complete_chart_matches"] == 0 for r in groups)
    assert sum(r["gate_lines_expected"] for r in groups) == 26 * 404
    rows.pop(0)
    with pytest.raises(ValueError, match="dropped"):
        MODULE.split_official_checks(prepared, {"cases": rows})
