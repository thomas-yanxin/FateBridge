"""Printed variants retain their edition, quotation layer and work-local key."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo_t2217_collation import (
    collation_lines,
    collation_reference,
    validate_collation,
    witness_reference,
)
from fatebridge.core.sukuyo_waterclock import source_specific_time_reference

FIXTURE = Path(__file__).parent / "fixtures/sukuyo-t2217-before-production-v87.json"


def test_entire_preimplementation_print_reference_is_delivered():
    expected = json.loads(FIXTURE.read_bytes())
    result = source_specific_time_reference()["daybreak_source_comparison"]
    assert result["T2217_printed_collation"]["source_data"] == expected
    assert expected["printed_readings"]["body"]["target_glyph"] == "夕"
    assert expected["printed_readings"]["apparatus"]["target_glyph"] == "且"


@pytest.mark.parametrize("work", ["T2216", "T1299", "T1509", "", None])
def test_witness_siglum_cannot_be_borrowed_by_another_work(work):
    with pytest.raises(KeyError):
        witness_reference(work, "甲")


def test_printed_key_is_not_a_direct_observation_of_the_described_manuscript():
    witness = witness_reference("T2217", "甲")
    assert witness["description_literal"] == "室町時代寫高野山寶龜院藏本"
    assert witness["shelfmark"] is None
    assert not witness["target_original_image_seen"]
    assert not witness["physical_identity_verified"]
    witness["description_literal"] = "changed"
    assert witness_reference("T2217", "甲")["description_literal"] != "changed"
    with pytest.raises(KeyError):
        witness_reference("T2217", "乙")


@pytest.mark.parametrize(
    "branch,key,value",
    [
        ("quote_chain", "intermediate_work_identity", "T2216"),
        ("quote_chain", "is_direct_T1509_witness", True),
        ("quote_chain", "normalized_target_glyph", "旦"),
        ("scope", "birth_calendar_override_applied", True),
        ("scope", "hinoo_half_mapping_established", True),
        ("scope", "leap_short_month_priority_established", True),
        ("scope", "independent_ancient_witness_count", 3),
        ("acquisition", "highest_original_resolution_certified", True),
    ],
)
def test_unreviewed_claim_changes_require_new_source_review(branch, key, value):
    data = copy.deepcopy(json.loads(FIXTURE.read_bytes()))
    data[branch][key] = value
    with pytest.raises(ValueError):
        validate_collation(data)


def test_native_text_keeps_material_variants_and_the_remaining_rule_gap():
    reference = collation_reference()
    assert reference["source_data"]["acquisition"]["images"][0][
        "actual_dimensions"
    ] == [2000, 2867]
    text = "\n".join(collation_lines(reference))
    for literal in ("夕", "且", "鈔第二云", "室町", "原件", "闰小月"):
        assert literal in text
    reference["source_data"]["scope"]["modern_day_boundary"] = "06:00"
    assert collation_reference()["source_data"]["scope"]["modern_day_boundary"] is None
    with pytest.raises(ValueError):
        collation_lines(reference)
