"""A shared target reading cannot erase other glyph disagreements or identity gaps."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo_quotation_comparison import (
    kanbun_lines,
    kanbun_reference,
    quotation_lines,
    quotation_reference,
    validate_kanbun,
)

FIXTURE = Path(__file__).parent / "data/sukuyo-kanbun-before-code-v88.json"


def test_entire_print_reference_keeps_all_first_readings_and_source_layers():
    reference = quotation_reference()
    assert reference["kanbun_printed_witness"]["source_data"] == json.loads(
        FIXTURE.read_bytes()
    )
    readings = reference["kanbun_printed_witness"]["source_data"]["accepted_readings"]
    assert readings["glyph_after_至"] == "夕"
    assert readings["glyph_after_從"] is None
    assert readings["glyph_after_從_candidates"] == ["旦", "且"]
    assert readings["some_晝_畫_forms"] is None
    assert readings["complete_literal_uniquely_accepted"] is None


@pytest.mark.parametrize("glyph", ["旦", "且"])
def test_no_reader_majority_silently_adjudicates_disputed_glyph(glyph):
    data = copy.deepcopy(json.loads(FIXTURE.read_bytes()))
    data["accepted_readings"]["glyph_after_從"] = glyph
    with pytest.raises(ValueError):
        validate_kanbun(data)


@pytest.mark.parametrize(
    "key,value",
    [
        ("Taisho_base_physical_copy_identified", True),
        ("reported_甲_target_image_seen", True),
        ("complete_target_transcription_agreed", True),
        ("independent_ancient_witness_count", 3),
        ("old17_image_queue_completed", 1),
        ("T1299_pingming_mapping_established", True),
        ("hinoo_half_mapping_established", True),
        ("leap_short_priority_established", True),
    ],
)
def test_unestablished_identity_and_clock_claims_require_new_evidence(key, value):
    data = copy.deepcopy(json.loads(FIXTURE.read_bytes()))
    data["scope"][key] = value
    with pytest.raises(ValueError):
        validate_kanbun(data)


def test_native_delivers_target_agreement_disputed_from_glyph_and_unknown_identity():
    text = "\n".join(quotation_lines(quotation_reference()))
    for phrase in (
        "京都",
        "十九",
        "夕",
        "旦／且",
        "晝／畫",
        "未定",
        "朱笔",
        "大正",
        "同一",
        "甲本",
    ):
        assert phrase in text
    reference = kanbun_reference()
    reference["source_data"]["accepted_readings"]["glyph_after_至"] = "旦"
    with pytest.raises(ValueError):
        kanbun_lines(reference)
    assert (
        kanbun_reference()["source_data"]["accepted_readings"]["glyph_after_至"] == "夕"
    )


def test_current_witness_marker_cannot_lose_its_actual_reference():
    reference = quotation_reference()
    reference.pop("kanbun_printed_witness")
    with pytest.raises(KeyError):
        quotation_lines(reference)
