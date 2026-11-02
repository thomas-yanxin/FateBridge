"""Quotation identity is stronger evidence without becoming clock calibration."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo_quotation_comparison import (
    quotation_lines,
    quotation_reference,
    validate_quotation,
)
from fatebridge.core.sukuyo_t2217_collation import collation_lines, collation_reference

FIXTURE = Path(__file__).parent / "fixtures/sukuyo-quotation-before-code-v88.json"


def test_entire_before_code_reference_and_legacy_snapshot_are_retained():
    expected = json.loads(FIXTURE.read_bytes())
    reference = collation_reference()
    assert reference["subsequent_quotation_comparison"]["source_data"] == expected
    assert reference["source_data_snapshot_round"] == 87
    assert reference["subsequent_research_round"] == 88
    assert reference["source_data"]["quote_chain"]["intermediate_work_identity"] is None
    assert expected["identification"]["status"] == (
        "strong_work_level_identification_specific_exemplar_unestablished"
    )
    assert expected["target_passages"][0]["volume"] == 2
    assert expected["target_passages"][3]["volume"] == 3


@pytest.mark.parametrize(
    "key,value",
    [
        ("exact_quoted_exemplar_identified", True),
        ("every_sho_is_same_work", True),
        ("T2216_is_X0439", True),
        ("target_readings_unified", True),
        ("NTU_PDF_is_old_print_image", True),
        ("AI_punctuation_is_original_glyph", True),
        ("D_metadata_overrides_T2217_colophon", True),
        ("independent_ancient_witness_count", 847),
        ("modern_seconds_per_time", 2880),
        ("T1299_pingming_mapping_established", True),
        ("hinoo_half_mapping_established", True),
        ("leap_short_month_priority_established", True),
    ],
)
def test_unreviewed_scope_upgrades_fail_closed(key, value):
    data = copy.deepcopy(json.loads(FIXTURE.read_bytes()))
    data["scope"][key] = value
    with pytest.raises(ValueError):
        validate_quotation(data)


def test_wrong_volume_or_silent_punctuation_revision_requires_review():
    for fault in ["volume", "punctuation"]:
        data = copy.deepcopy(json.loads(FIXTURE.read_bytes()))
        if fault == "volume":
            data["target_passages"][3]["volume"] = 2
        else:
            data["target_passages"][0][
                "literal_with_current_electronic_punctuation"
            ] = data["target_passages"][0][
                "literal_with_current_electronic_punctuation"
            ].replace(
                "三、十", "三十"
            )
        with pytest.raises(ValueError):
            validate_quotation(data)


def test_native_text_distinguishes_work_inference_copy_punctuation_and_author_roles():
    text = "\n".join(collation_lines(collation_reference()))
    for literal in (
        "第87轮",
        "演密",
        "强",
        "卷四",
        "卷二",
        "卷三",
        "具体引本",
        "电子排版",
        "AI",
        "一行",
        "頼瑜",
        "闰小月",
    ):
        assert literal in text
    assert "三、十" in text
    assert "夕" in text and "且" in text and "旦" in text


def test_references_are_isolated_and_rendering_validates_actual_data():
    reference = quotation_reference()
    reference["source_data"]["scope"]["every_sho_is_same_work"] = True
    with pytest.raises(ValueError):
        quotation_lines(reference)
    assert not quotation_reference()["source_data"]["scope"]["every_sho_is_same_work"]


def test_current_research_marker_cannot_silently_lose_its_evidence():
    reference = collation_reference()
    reference.pop("subsequent_quotation_comparison")
    with pytest.raises(KeyError):
        collation_lines(reference)
