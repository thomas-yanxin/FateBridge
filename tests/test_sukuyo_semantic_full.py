"""Complete 宿占 review must retain the physical and adverse evidence."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.sukuyo_semantic import (
    complete_suzhan_calculation_view,
    semantic_calculation_view,
)

FIXTURE = (
    Path(__file__).parent / "fixtures/sukuyo-semantic-complete-before-code-v86.json"
)


def prepared():
    return json.loads(FIXTURE.read_bytes())


def test_complete_view_matches_entire_frozen_literal_without_hiding_the_sky():
    ref = prepared()
    assert complete_suzhan_calculation_view(ref["input"]) == ref["expected_complete"]


def test_existing_calendar_only_view_remains_explicitly_separate():
    ref = prepared()
    assert (
        semantic_calculation_view("suzhan", ref["input"])
        == ref["expected_legacy_calendar_only"]
    )
    full = complete_suzhan_calculation_view(ref["input"])
    assert full["chart"]["objects"][0]["su28"] != full["sukuyo"]["day_mansion"]


def test_future_adverse_science_and_nested_summary_are_retained():
    source = prepared()["input"]
    source["future_sky_evidence"] = {"rejected": [False, None], "summary": "unresolved"}
    result = complete_suzhan_calculation_view(source)
    assert result["future_sky_evidence"] == source["future_sky_evidence"]
    assert result["astronomy"]["source_failures"] == ["retained_failure"]
    assert result["chart"]["objects"][0]["diagnostic"]["summary"] == {"unresolved": 3}
    assert result["sukuyo"]["calendar"]["complete"] is False


def test_mutating_review_copy_cannot_modify_its_raw_evidence():
    source = prepared()["input"]
    before = deepcopy(source)
    result = complete_suzhan_calculation_view(source)
    result["chart"]["objects"].clear()
    result["sukuyo"]["calendar"]["candidate_su27s"].clear()
    result["astronomy"]["source_failures"].append("changed")
    assert source == before


@pytest.mark.parametrize("key", prepared()["required_actual_top_keys"])
def test_missing_complete_domain_branch_is_not_silently_accepted(key):
    source = prepared()["input"]
    del source[key]
    with pytest.raises(KeyError):
        complete_suzhan_calculation_view(source)


def test_declared_disabled_sky_keeps_null_and_available_planet_data():
    source = prepared()["input"]
    source["astronomy"] = None
    source["params"]["su28AstronomicalAccuracy"] = "not_computed"
    source["chart"]["objects"] = [{"id": "Moon", "longitude": 123.0}]
    result = complete_suzhan_calculation_view(source)
    assert result["astronomy"] is None
    assert result["params"]["su28AstronomicalAccuracy"] == "not_computed"
    assert result["chart"]["objects"] == [{"id": "Moon", "longitude": 123.0}]


def test_native_text_is_removed_recursively_without_removing_other_assertions():
    source = prepared()["input"]
    source["chart"]["objects"].append(
        {"id": "future", "reading_text": "NATIVE-DEEP", "claim": {"unresolved": True}}
    )
    result = complete_suzhan_calculation_view(source)
    assert "NATIVE" not in json.dumps(result)
    assert result["chart"]["objects"][-1] == {
        "id": "future",
        "claim": {"unresolved": True},
    }
