"""Water subset and expanded witnesses keep separate frozen denominators."""

import copy

import pytest

from scripts import audit_numerology as audit


def test_water_literal_controls_and_expanded_witness_statistics_are_distinct():
    report = audit.canping_text_checks()
    assert report["checks_passed"] and report["failures"] == []
    assert (
        report["comparison_cells_examined"],
        report["comparison_clear_readings"],
        report["comparison_uncertain_readings"],
    ) == (72, 70, 2)
    assert (
        report["comparison_water_cells_examined"],
        report["comparison_water_clear_readings"],
        report["comparison_water_uncertain_readings"],
    ) == (36, 34, 2)
    assert (
        report["comparison_registered_counterpart_cells"],
        report["comparison_registered_counterpart_keys"],
        report["comparison_ambiguous_counterpart_keys"],
        report["comparison_unmatched_observed_cells"],
    ) == (69, 66, 3, 3)
    assert report["collated_cells"] == 1123 and report["unresolved_reading_cells"] == 47
    assert report["comparison_primary_count_increase"] == 0


@pytest.mark.parametrize(
    "field,bad",
    [("cells_examined", 35), ("clear_readings", 35), ("uncertain_readings", 0)],
)
def test_expanded_global_counts_cannot_hide_a_damaged_water_subset(
    field, bad, monkeypatch
):
    original = audit.canping_collation_summary

    def damaged():
        result = copy.deepcopy(original())
        result["comparison_witness"]["part_coverage"]["水"][field] = bad
        return result

    monkeypatch.setattr(audit, "canping_collation_summary", damaged)
    report = audit.canping_text_checks()
    assert report["checks_passed"] is False
    assert {"kind": "canping_witness_coverage"} in report["failures"]


def test_old_global34_false_positive_cannot_override_the_water_fixture(monkeypatch):
    original = audit.canping_collation_summary

    def damaged():
        result = copy.deepcopy(original())
        result["comparison_witness"]["clear_readings"] = 34
        result["comparison_witness"]["part_coverage"]["水"]["clear_readings"] = 33
        return result

    monkeypatch.setattr(audit, "canping_collation_summary", damaged)
    report = audit.canping_text_checks()
    assert report["checks_passed"] is False
    assert {"kind": "canping_witness_coverage"} in report["failures"]
