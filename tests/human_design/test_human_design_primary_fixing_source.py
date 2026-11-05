"""Retain failed source rows and distinguish positive examples from full lists."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation import human_design_primary_fixing as checks

ROOT = Path(__file__).resolve().parents[2]


def test_bounded_written_facts_and_disclosed_examples_match():
    result = checks.primary_fixing_checks(ROOT)
    assert result["source_fact_count"] == result["source_facts_matched"] == 2
    assert result["case_count"] == result["cases_matched"] == 14
    assert result["status"] == "bounded_written_examples_match"
    assert result["failures"] == []
    assert result["audio_asr_used_as_acceptance_oracle"] is False
    assert result["complete_fixing_statuses_certified"] is False
    assert result["full_384_line_meaning_acceptance"] is False
    assert result["authority_certified"] is False


def test_written_moon_example_does_not_delete_original_additional_venus():
    result = checks.primary_fixing_checks(ROOT)
    fact = next(r for r in result["source_facts"] if r["role"] == "exaltation")
    assert fact["computed_planet_set"] == ["Moon", "Venus"]
    guards = [
        r for r in result["cases"] if r["evidence_class"] == "existing_2001_prose_guard"
    ]
    assert len(guards) == 2
    for row in guards:
        assert (
            row["computed_recipient"]["additional_polarity_basis"][0][
                "additional_planet"
            ]
            == "Venus"
        )


def test_wrong_derived_state_keeps_the_failed_case_and_all_other_rows(monkeypatch):
    original = checks.line_fixings

    def corrupt(activations):
        rows = original(activations)
        for row in rows:
            if row["body"] == "Moon" and row["gate"] == 11 and row["line"] == 4:
                row["fixing_state"] = "unfixed"
        return rows

    monkeypatch.setattr(checks, "line_fixings", corrupt)
    result = checks.primary_fixing_checks(ROOT)
    assert result["status"] == "failed"
    assert result["case_count"] == 14
    assert result["cases_matched"] == 13
    assert len(result["failures"]) == 1
    assert result["failures"][0]["id"] == "lynda_moon_11_4"
    assert result["full_384_line_meaning_acceptance"] is False


@pytest.mark.parametrize("mutation", ["delete_failed_row", "change_expected_state"])
def test_frozen_reference_cannot_be_narrowed_or_relabelled(tmp_path, mutation):
    value = deepcopy(json.loads((ROOT / checks.FIXTURE).read_text()))
    if mutation == "delete_failed_row":
        value["cases"].pop(0)
    else:
        value["cases"][0]["expected_state"] = "unfixed"
    path = tmp_path / checks.FIXTURE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="reference changed"):
        checks.primary_fixing_checks(tmp_path)
