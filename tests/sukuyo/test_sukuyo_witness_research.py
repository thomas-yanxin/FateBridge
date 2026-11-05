"""Source-backed research facts must not become accepted calendrical policies."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_hinoo_critical import critical_calendar_reference
from fatebridge.core.sukuyo_profiles import fullmoon_calculation, source_bundle

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = json.loads(
    (
        ROOT / "tests/data/sukuyo-witness-research-before-production-v84.json"
    ).read_bytes()
)
EXPECTED = REFERENCE["expected_bundle"]


def critical():
    return critical_calendar_reference(
        source_bundle()["hinoo_addendum"],
        [fullmoon_calculation(12, day, SU27_ORDER) for day in (1, 15, 30)],
    )


def test_hinoo_research_matches_the_complete_precode_source_reference():
    actual = critical()["image_witness_research"]
    fingerprint = actual.pop("source_bundle_sha256")
    assert len(fingerprint) == 64
    assert actual == EXPECTED
    assert all(value is False or value == 0 for value in actual["acceptance"].values())


def test_positive_shinpukuji_calendar_discovery_does_not_select_a_glyph_or_clock():
    witness = critical()["image_witness_research"]["shinpukuji"]
    assert witness["calendar_passages_located"]
    assert [r["frame_one_based"] for r in witness["selected_previews"]] == [34, 35]
    assert [r["literal_candidate"] for r in witness["day30_readings"]] == ["室", "室"]
    assert witness["day30_accepted_glyph"] is None
    assert witness["modern_half_clock"] is None
    assert not witness["overlap_priority_established"]
    assert not witness["identified_as_T2465_base_or_ko"]
    assert not witness["whole_manuscript_collated"]


def test_holder_catalogue_and_colophon_readings_remain_distinct():
    w = critical()["image_witness_research"]["nagoya_composite"]
    assert w["different_editions_composite_as_holder_statement"]
    assert (
        w["upper_lines_as_holder_statement"],
        w["lower_lines_as_holder_statement"],
    ) == (10, 8)
    assert "序によれば" in w["holder_catalogue_fields"]["内容注記"]
    assert w["volume_accepted_glyph"] is None and w["cost_accepted_glyph"] is None
    assert [r["volume_literal"] for r in w["colophon_first_readings"]] == [
        "下卷",
        "上下卷",
    ]
    assert [r["cost_literal"] for r in w["colophon_first_readings"]] == [
        "四兩九錢三分",
        "四兩九錢二分",
    ]
    assert not w["all_leaves_dated_by_catalogue1681"]
    assert not w["independent_lineage_accepted"]
    assert not w["metadata_license_is_image_license"]


def test_alternate_images_do_not_satisfy_missing_originals_or_item_identity():
    research = critical()["image_witness_research"]
    capture, w = research["capture_summary"], research["naoj_legacy"]
    assert (capture["NIJL_previews_saved"], capture["NIJL_previews_planned"]) == (
        196,
        197,
    )
    assert (
        capture["original_resolution_acquired"],
        capture["original_resolution_requirements"],
    ) == (0, 17)
    assert not capture["original_resolution_gate_met"]
    assert len(w["selected_images"]) == 11
    assert all(r["pixels"] == [2500, 1872] for r in w["selected_images"])
    assert len(w["visually_supported_content_pairs"]) == 9
    assert w["holder_catalogue_row"] == 143 and w["holder_row315_title"] == "談天"
    assert not w["missing_NIJL069_replaced_by_legacy070"]
    assert not w["constant_all80_page_offset_accepted"]
    assert (
        not w["same_physical_copy_accepted"] and not w["independent_lineage_accepted"]
    )


def test_own_first_error_and_new_source_disagreements_are_not_erased():
    w = critical()["image_witness_research"]["naoj_legacy"]
    count = w["legacy78_character_count_readings"]
    assert count["parent_first"] == "八千四百二十字"
    assert count["working_selected_image_reading"] == "八千四百一十字"
    assert count["parent_first_error_preserved"] and not count["applies_to_NAGO075"]
    timing = w["timing_passage"]
    assert timing["next_day_glyph_readings"] == {
        "parent": "曉",
        "reviewer": "曜",
        "accepted": None,
    }
    assert timing["evening_glyph_readings"]["accepted"] is None
    assert timing["modern_civil_clock"] is None and timing["solar_altitude"] is None
    assert timing["complete_intradaily_luminary_order"] is None
    assert not timing["Hinoo_half_equated_to_day_night"]
    conjunction = w["upper_conjunction_layers"]
    assert (
        "牛" in conjunction["prose_literal"] and "十宿" in conjunction["prose_literal"]
    )
    assert "九宿" in conjunction["verse_literal"]
    assert not conjunction["merged_with_selected_lower27_rule"]


@pytest.mark.parametrize(
    "field", ["publisher_html_response_sha256", "downloaded_calendar_windows"]
)
def test_new_research_cannot_be_reused_with_a_different_taisho_context(field):
    from fatebridge.core.sukuyo_witness_research import research_reference

    source = copy.deepcopy(
        source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    )
    source[field] = "changed"
    with pytest.raises(ValueError, match="原文不一致"):
        research_reference(source)


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("capture_summary", "original_resolution_acquired", 17),
        ("shinpukuji", "day30_accepted_glyph", "室"),
        ("shinpukuji", "modern_half_clock", "12:00"),
        ("nagoya_composite", "independent_lineage_accepted", True),
        ("naoj_legacy", "missing_NIJL069_replaced_by_legacy070", True),
        ("acceptance", "intercalary_short_month_priority_established", True),
    ],
)
def test_false_source_upgrades_require_requalification(section, key, value):
    from fatebridge.core.sukuyo_witness_research import validate_bundle

    altered = copy.deepcopy(EXPECTED)
    altered[section][key] = value
    with pytest.raises(ValueError, match="须重新核验"):
        validate_bundle(altered)


def test_research_fingerprint_and_returned_data_are_from_one_detached_load():
    from fatebridge.core.sukuyo_witness_research import SOURCE, research_reference

    source = source_bundle()["hinoo_addendum"]["downloaded_primary_edition"]
    first = research_reference(source)
    assert (
        first["source_bundle_sha256"] == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    )
    first["shinpukuji"]["day30_accepted_glyph"] = "星"
    second = research_reference(source)
    assert second["shinpukuji"]["day30_accepted_glyph"] is None
    first.pop("source_bundle_sha256")
    assert (
        second.pop("source_bundle_sha256")
        == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    )
    assert second == EXPECTED


@pytest.mark.parametrize(
    "date,candidates", [("1903-06-25", ["鬼", "参"]), ("1957-09-24", ["角", "轸"])]
)
def test_unresolved_calculations_and_conditional_delivery_keep_their_original_scope(
    date, candidates
):
    result = calendar_mansion(
        date, calendar_profile="hinoo_t1299_host27", calendar_day_part="first_half"
    )
    assert result["status"] == "partial" and result["natal_su27"] is None
    assert result["candidate_su27s"] == candidates
    profile = result["profile_calculation"]
    assert not profile["historical_calendar_reconstruction"]
    assert not profile["classical_full_profile_acceptance"]
    assert not profile["short_month_assignment"]["leap_short_month_precedence"][
        "source_rule_priority_established"
    ]
    text = day_evidence(result, "室", "travel")["reading_text"]
    for fragment in [
        "真福寺",
        "034",
        "035",
        "名古屋",
        "不同版本",
        "2500",
        "0／17",
        "八千四百一十字",
        "八千四百二十字",
    ]:
        assert fragment in text
    assert "未确定" in text


def test_ordinary_profile_does_not_silently_acquire_a_hinoo_reconstruction():
    result = calendar_mansion("1903-06-25")
    assert result["profile_calculation"]["hinoo_source"] is None
    assert result["status"] == "partial" and result["leap_month_policy"] == "unresolved"
