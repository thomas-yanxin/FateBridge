"""Check complete-cohort preservation separately from failed strict acceptance."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "legacy_closure", ROOT / "scripts/compare_bazi_dayun_legacy_closure.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def bounds(**changes):
    return {
        "direction": "顺行",
        "period": 1,
        "pillar": "甲子",
        "earliest_start_at": "2020-11-01T01:00:00-04:00",
        "latest_start_at": "2020-11-01T01:00:00-05:00",
        "earliest_end_at": "2030-11-01T00:00:00+00:00",
        "latest_end_at": "2030-11-01T01:00:00+00:00",
        **changes,
    }


def test_fold_bounds_compared_in_utc():
    before = bounds()
    after = bounds(
        earliest_start_at="2020-11-01T05:00:00+00:00",
        latest_start_at="2020-11-01T06:00:00+00:00",
    )
    result = module.compare_boundaries([before], [after])
    assert not any(result.values())


@pytest.mark.parametrize(
    "field,value",
    [
        ("earliest_start_at", "2020-11-01T05:00:00.000001+00:00"),
        ("latest_start_at", "2020-11-01T05:59:59.999999+00:00"),
        ("earliest_end_at", "2030-11-01T00:00:00.000001+00:00"),
        ("latest_end_at", "2030-11-01T00:59:59.999999+00:00"),
    ],
)
def test_one_microsecond_shrink_is_retained(field, value):
    result = module.compare_boundaries([bounds()], [bounds(**{field: value})])
    assert len(result["shrunken_bounds"]) == 1
    assert result["shrunken_bounds"][0]["field"] == field
    assert not result["expanded_bounds"]


def test_removed_and_added_periods_do_not_cancel():
    result = module.compare_boundaries([bounds()], [bounds(period=2)])
    assert result["removed_periods"] == [["顺行", 1, "甲子"]]
    assert result["added_periods"] == [["顺行", 2, "甲子"]]


def test_duplicate_periods_rejected():
    with pytest.raises(AssertionError):
        module.compare_boundaries([bounds(), bounds()], [bounds()])


def test_original_failed_gate_is_not_replaced_by_preservation():
    folder = ROOT / "docs/validation/bazi-dayun-state-legacy-closure-v1"
    result = module.bound_json(folder / "paired-first.json")
    assessment = module.bound_json(folder / "strict-assessment-first.json")
    assert result["counts"]["rows"] == 116906
    assert result["counts"]["known"] == 116124
    assert result["counts"]["unknown"] == 782
    assert result["counts"]["before_strict_failures"] == 54818
    assert result["counts"]["after_strict_failures"] == 54818
    assert result["counts"]["before_point_probes"] == 812868
    assert result["counts"]["after_point_probes"] == 812868
    assert len(result["strict_transition_ids"]["retained"]) == 54818
    assert not result["strict_transition_ids"]["fixed"]
    assert not result["strict_transition_ids"]["introduced"]
    assert result["preservation_diagnostics_passed"]
    assert not result["registered_cohort_acceptance_passed"]
    assert result["failed_original_conditions"] == [
        "all_safe_source_witnesses_inside_probe_envelopes"
    ]
    assert not assessment["registered_cohort_acceptance_passed"]
    assert result["assessment_sha256"] == module.sha(
        folder / "strict-assessment-first.json"
    )
    assert result["records_sha256"] == module.sha(ROOT / result["records"])
    assert not result["authority_certified"]
    assert not result["full_goal_complete"]
    assert result["new_state_repair_credit"] == 0
