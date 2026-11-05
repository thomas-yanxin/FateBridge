"""A named Chinese facsimile is distinct from Taisho apparatus reconstruction."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_documentary import clock_position_reference
from fatebridge.core.sukuyo_printed_special import NTU_YONGLE_SOURCE
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.core.sukuyo_special_days import special_day_evidence

FIXTURE = Path(__file__).parent / "data/sukuyo-ntu-yongle130-selected-v1.json"
MANSIONS = "角亢氐房心尾箕斗女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸"


def evidence(name, weekday):
    return special_day_evidence(
        name, weekday, weekday_basis="modern_utc_plus08_civil_midnight"
    )


def test_frozen_visual_oracle_preserves_all_42_slots_before_runtime_comparison():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "5205a64930010b8232cdf1935936d8555010acf612b8ac6fa06f2cde66c219f3"
    )
    first = json.loads(raw)
    assert first["primary_first_sha256"] == (
        "be16c03a09d8671b6f6edc73a095f0a703eee1b66a3cb87c5624023461272549"
    )
    normalize = str.maketrans("軫畢張參", "轸毕张参")
    # All 27 x 7 lookups compare both complete selected volume tables, not just
    # a few matching dates or the already passing Taisho-apparatus cells.
    for name in MANSIONS:
        for weekday in range(7):
            result = evidence(name, weekday)
            for printed in result["direct_printed_comparisons"][2:]:
                selected = [
                    r
                    for r in first["source_only_selected_rows"]
                    if r["volume"] == printed["volume"]
                    and r["weekday_index"] == weekday
                ]
                assert len(selected) == 3
                assert printed["matched_labels"] == [
                    r["label"]
                    for r in selected
                    if r["literal_mansion"].translate(normalize) == name
                ]
                assert [r["source_clause"] for r in printed["rows_for_weekday"]] == [
                    r["source_clause"] for r in selected
                ]
                assert [r["ntu_pdf_page"] for r in printed["rows_for_weekday"]] == [
                    r["ntu_pdf_page"] for r in selected
                ]
                assert not printed["applied_to_primary"]


@pytest.mark.parametrize(
    "name,weekday,upper,lower,primary",
    [
        ("井", 2, ["甘露"], [], []),
        ("尾", 2, [], ["甘露"], ["甘露"]),
        ("昴", 2, ["金刚峰"], [], []),
        ("壁", 3, ["金刚峰"], [], []),
        ("女", 1, ["金刚峰"], ["金刚峰"], []),
        ("胃", 0, ["罗刹"], ["罗刹"], ["罗刹"]),
        ("氐", 4, ["罗刹"], ["罗刹"], ["罗刹"]),
    ],
)
def test_distinct_volume_cells_never_rewrite_primary_or_resolve_other_glyphs(
    name, weekday, upper, lower, primary
):
    result = evidence(name, weekday)
    direct = result["direct_printed_comparisons"]
    assert [r["witness"] for r in direct] == [
        "lower_wakita_1897_selected",
        "lower_kyoto_enpo_selected",
        "upper_ntu_yongle130_selected",
        "lower_ntu_yongle130_selected",
    ]
    assert direct[2]["matched_labels"] == upper
    assert direct[3]["matched_labels"] == lower
    assert result["primary"]["matched_labels"] == primary
    if weekday in (0, 4):
        other = next(r for r in result["comparisons"] if r["witness"] == "lower_taisho")
        assert other["unresolved_rows"][0]["literal_mansion"] in ("冒", "底")


def test_matching_downloads_and_apparatus_cells_cannot_authenticate_physical_witness():
    bundle = load_source(NTU_YONGLE_SOURCE).data
    ref = bundle["source_reference"]
    matches = ref["selected_page_image_matches"]
    assert len(matches) == 56
    assert [r["ntu_pdf_page"] for r in matches] == list(range(547, 603))
    assert not ref["image_identity_is_independent_witness_count"]
    assert not ref["identified_as_taisho_ming_witness"]
    assert not ref["exact_impression_date_authenticated"]
    assert not ref["independent_human_transcription_accepted"]
    assert not ref["whole_work_or_printed_apparatus_collated"]
    assert ref["html_catalogue_dynasty_literal"] == "宋"
    assert ref["attribution_literal_in_work"] == "宋內供奉三藏沙門不空奉詔譯"
    assert ref["volume_preliminary_catalogue_dynasty_literal"] == "唐"
    assert not ref["attribution_discrepancy_emended"]
    upper = bundle["witnesses"][0]
    assert not upper["source_reference"]["caption_diplomatic_reading_complete"]
    assert upper["source_reference"][
        "upper_third_group_caption_candidates_not_accepted"
    ]
    assert all(
        r["label_alignment_basis"] == "contextual_third_group_caption_glyph_unresolved"
        for r in upper["rows"]
        if r["label"] == "罗刹"
    )


def test_source_clock_is_not_civil_time_hinoo_priority_or_empirical_efficacy():
    clock = clock_position_reference()["direct_chinese_print_reference"]
    assert clock["day_parts"] == clock["night_parts"] == 8
    assert clock["accepted_selected_clauses"][1] == "平明即是所直之曜"
    assert clock["order_agrees_with_taisho_ming_position_operation"]
    for key in (
        "modern_clock_mapping_established",
        "hour_luminary_sequence_established",
        "leap_short_month_priority_established",
        "hinoo_half_mapping_established",
        "identified_as_taisho_ming_witness",
        "source_efficacy_claim_is_empirical_evidence",
        "applied_to_primary_or_activities",
    ):
        assert not clock[key]
    clock["accepted_selected_clauses"].clear()
    assert clock_position_reference()["direct_chinese_print_reference"][
        "accepted_selected_clauses"
    ]


@pytest.mark.parametrize("weekday", range(7))
def test_unknown_day_mansion_never_becomes_a_definitive_printed_label(weekday):
    result = evidence(None, weekday)
    for row in result["direct_printed_comparisons"][2:]:
        assert row["matched_labels"] == []
        assert not row["labels_complete_for_selected_day"]
        assert row["disagrees_with_primary"] is None


def test_product_explanation_names_both_volumes_and_retains_unaccepted_caption():
    result = day_evidence(calendar_mansion("2000-01-18"))
    text = result["reading_text"]
    assert "台大馆藏《永樂北藏》第一三〇册上卷所选影印段" in text
    assert "台大馆藏《永樂北藏》第一三〇册下卷所选影印段" in text
    assert "下卷分别为尾、壁、昴，上下卷互异没有合成一张表" in text
    assert "刹／利字形未唯一接纳" in text
    assert "两处下载只计同一影像来源" in text
    assert "‘萬不失一’是原典效力宣称" in text
    assert result["calendar_day"]["clock_evaluation_status"] == "not_computed"
