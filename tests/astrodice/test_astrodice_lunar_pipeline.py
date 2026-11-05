"""Current fixed-frame samples retain the complete original lunar cohort."""

from pathlib import Path

import pytest

from scripts.astrodice.audit_astrodice_lunar_pipeline import audit

RUN = (
    Path(__file__).parents[2]
    / "tests/data/astrodice/reference_sets/study-lunar-pipeline"
)


@pytest.mark.parametrize("split", ["development", "heldout"])
def test_current_lunar_source_population_is_graded_without_snapshot_replay(split):
    result = audit(RUN, split, RUN / f"{split}-reference-first.json")
    assert len(result["rows"]) == 6
    assert result["position_line_arcsec"] == "0.02"
    assert result["rate_line_arcsec_per_source_day"] == "0.002"
    assert result["original_overall_gate"] == 1
    assert result["original_production_gate"] == 2
    assert result["physical_TT_equivalence_certified"] is False
    assert result["complete_moving_frame_derivative_certified"] is False
    failures = {
        (row["label"], row["backend"]) for row in result["rows"] if not row["qualified"]
    }
    assert failures == (
        {("3000-12-07T04:07:32", "swieph")} if split == "development" else set()
    )
    for row in result["rows"]:
        if row["status"] == "ready":
            assert row["qualified"] == (
                row["context_ok"]
                and row["position_pass"]
                and row["longitude_rate_pass"]
                and row["auxiliary_full_direction_rate_pass"]
            )
        else:
            assert row["qualified"] is False
