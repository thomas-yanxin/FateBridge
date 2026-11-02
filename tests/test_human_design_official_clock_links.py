"""Preserve real failed comparisons while explaining their clock confound."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from tests.ephemeris_case_runtime import native_ephemeris_files_module

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


from fatebridge.validation.human_design_official import official_chart_checks

FIXTURES = Path(__file__).with_name("fixtures")
COHORT = json.loads(
    (FIXTURES / "human-design-disc-clock-observations.json").read_text()
)
BEFORE = json.loads((FIXTURES / "human-design-disc-clock-before.json").read_text())


@pytest.fixture(scope="module")
def results():
    return (
        official_chart_checks(COHORT),
        official_chart_checks(COHORT, include_clock_link_evidence=True),
    )


def test_original_report_and_real_neptune_failure_are_unchanged(results):
    legacy, _ = results
    assert legacy == BEFORE
    assert legacy["gate_lines_checked"] == 338
    assert legacy["gate_lines_matched"] == 337
    assert legacy["charts_with_all_mechanics_matched"] == 8
    assert legacy["charts_matched"] == 2
    failed = next(
        r for r in legacy["cases"] if r["id"] == "disc-full-21-neptune-184002020325"
    )
    assert failed["status"] == "failed"
    assert failed["gate_line_mismatches"] == [
        {
            "side": "personality",
            "body": "Neptune",
            "expected": "19.6",
            "actual": "19.5",
        }
    ]


def test_enhanced_report_adds_context_without_regrading_or_dropping_rows(results):
    legacy, enhanced = results
    projected = deepcopy(enhanced)
    projected.pop("birth_clock_link_summary")
    for row in projected["cases"]:
        row.pop("birth_clock_link")
    assert projected == legacy
    assert [r["id"] for r in enhanced["cases"]] == [r["id"] for r in COHORT["cases"]]
    assert len(COHORT["missing_planned_ids"]) == 9
    assert COHORT["planned_case_count"] == 22
    assert COHORT["collection_status"] == "incomplete"


def test_historical_75second_disagreements_remain_explicit_and_uncertified(results):
    _, enhanced = results
    summary = enhanced["birth_clock_link_summary"]
    expected = [
        r["id"] for r in COHORT["source_clock_links"] if not r["exact_label_match"]
    ]
    assert len(expected) == 5
    assert summary["nominal_clock_disagreement_case_ids"] == expected
    assert summary["linked_gate_lines_checked"] == 208
    assert summary["linked_gate_lines_matched"] == 208
    assert summary["unlinked_gate_lines_checked"] == 130
    assert summary["unlinked_gate_lines_matched"] == 129
    assert not summary["unassessed_case_ids"]
    assert not summary["physical_clock_accuracy_certified"]
    for row in enhanced["cases"]:
        clock = row["birth_clock_link"]
        assert not clock["physical_clock_accuracy_certified"]
        assert not clock["ephemeris_cause_isolated"]
        if row["id"] in expected:
            assert clock["status"] == "nominal_clock_disagreement"
            assert clock["calculated_minus_displayed_seconds"] == 75
            assert not clock["same_nominal_instant"]
            assert row["structure_checks"]["birth_utc"] is False
            assert row["status"] == "failed"
