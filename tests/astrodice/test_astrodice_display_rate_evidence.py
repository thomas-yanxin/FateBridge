"""Current native comparisons use the original independent reference population."""

import json
from pathlib import Path

import pytest

from scripts.astrodice.audit_astrodice_display_rate import audit
from scripts.astrodice.verify_astrodice_display_reference import verify

RUN = (
    Path(__file__).parents[2] / "tests/data/astrodice/reference_sets/study-display-rate"
)


@pytest.mark.parametrize("split,expected", [("development", 22), ("heldout", 18)])
def test_current_complete_population_is_graded_at_original_lines(split, expected):
    reference = RUN / f"{split}-reference-first.json"
    result = audit(RUN, reference)
    assert len(result["rows"]) == expected
    assert result["position_line_arcsec"] == "0.02"
    assert result["rate_line_arcsec_per_day"] == "0.002"
    assert result["old_gates"] == {"production": 2, "overall": 1}
    assert result["physical_TT_equivalence_certified"] is False
    assert result["original_failure_records_regraded"] is False
    failures = {
        (row["label"], row["backend"]) for row in result["rows"] if not row["qualified"]
    }
    assert failures == (
        {("3000-12-07T04:07:32", "swieph")} if split == "development" else set()
    )
    for row in result["rows"]:
        assert row["status"] in {
            "passed_declared_source_lines",
            "failed_declared_source_lines",
            "unavailable_retained",
        }
        if row["status"] != "unavailable_retained":
            assert row["qualified"] == (
                row["position_pass"]
                and row["rate_pass"]
                and row["derivative_policy_applied"]
            )


@pytest.mark.parametrize("split", ["development", "heldout"])
def test_original_intervals_remain_independently_reproducible(split):
    result = verify(RUN, RUN / f"{split}-reference-first.json")
    assert all(r["status"] == "strict_containment_passed" for r in result["rows"])


def test_historical_negative_rows_remain_separate_from_current_execution():
    evidence = json.loads((RUN.parents[1] / "historical-failures.json").read_text())
    assert any(row["study"] == "lunar-pipeline" for row in evidence)
