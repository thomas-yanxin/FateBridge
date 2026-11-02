"""Actual recorded envelope failures cannot pass through an executor exit0."""

import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "audit_name,source_name,misses,resolved",
    [
        (
            "bazi-dayun-monrovia-future-clocks-before-v1.json",
            "monrovia-reference-summary.json",
            14,
            231,
        ),
        (
            "bazi-dayun-future-clocks-v2-before-v1.json",
            "reference-summary.json",
            2695,
            116124,
        ),
    ],
)
def test_complete_execution_does_not_hide_registered_envelope_misses(
    audit_name, source_name, misses, resolved
):
    assess = runpy.run_path(str(ROOT / "scripts/assess_bazi_future_clock_audit.py"))[
        "assess"
    ]
    audit = json.loads((ROOT / "docs/validation" / audit_name).read_text())
    source = json.loads(
        (ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2" / source_name).read_text()
    )
    result = assess(audit, source)
    assert result["registered_cohort_acceptance_passed"] is False
    assert result["failed_conditions"] == [
        "all_safe_source_witnesses_inside_probe_envelopes"
    ]
    assert (
        result["original_counts"]["probe_envelopes_not_covering_safe_source_witnesses"]
        == misses
    )
    assert result["source_grid_already_covered_rows"] == resolved
    assert result["new_state_repair_credit"] == 0
    assert result["full_goal_complete"] is False
