"""Primary literals, nominal rational arithmetic and source-layer limits."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo_quotation_comparison import (
    quotation_lines,
    quotation_reference,
)
from fatebridge.core.sukuyo_zhidu_calendar import (
    validate_zhidu,
    zhidu_lines,
    zhidu_reference,
)

FIXTURE = Path(__file__).parent / "fixtures/sukuyo-zhidu-before-code-v89.json"


def frozen():
    return json.loads(FIXTURE.read_bytes())


def test_complete_reference_and_separate_before_code_numerical_oracle():
    expected = frozen()
    actual = zhidu_reference()
    assert actual["source_data"] == expected["source_data"]
    assert actual["nominal_arithmetic"] == expected["numerical_oracle"]
    assert actual["before_code_reference_sha256"] == actual["source_bundle_sha256"]


def test_four_stable_slots_survive_the_reported_repeated_month_term():
    data = zhidu_reference()["source_data"]
    rows = data["month_definitions"]["T1509"]
    assert [r["slot_id"] for r in rows] == [f"month_{i}" for i in range(1, 5)]
    reported = [
        (
            r["reported_term_alternatives"][0]["term"]
            if r["reported_term_alternatives"]
            else r["main_term"]
        )
        for r in rows
    ]
    assert reported == ["日月", "世間月", "日月", "星宿月"]
    assert len(rows) == 4
    assert data["month_definitions"]["T2122"][2]["reported_term_alternatives"] == []


def test_enumeration_and_detailed_definition_remain_separate():
    reference = zhidu_reference()
    data = reference["source_data"]
    enum = data["month_enumerations"]["T1509"]
    assert "二十九日、或二十七日半" in enum["main_literal"]
    assert enum["fourth_item_reported_variant"]["reported"] == "二十九日半"
    assert enum["fourth_item_reported_variant"][
        "does_not_modify_month4_detailed_definition"
    ]
    assert reference["nominal_arithmetic"]["models"]["T1509"][3] == {
        "slot_id": "month_4",
        "numerator": 1830,
        "denominator": 67,
    }


def test_day_end_variant_is_not_moved_to_month_names_or_other_books():
    sources = zhidu_reference()["source_data"]["sources"]
    note = sources["T2122"]["selected_apparatus"][0]
    assert note["app"]["lem"] == "旦"
    assert note["app"]["rdg"] == "日"
    assert note["app"]["rdg_witnesses"] == ["【宋】", "【明】", "【宮】"]
    assert sources["T1509"]["sigla"]["wit1"] == "【宋】"
    assert sources["T2122"]["sigla"]["wit1"] == "【元】"
    assert sources["T1509"]["apparatus_counts"]["selected_records"] == 13
    assert sources["T2122"]["apparatus_counts"]["selected_records"] == 6


def test_volume_layers_and_unresolved_printed_character_are_not_unified():
    data = zhidu_reference()["source_data"]
    page = data["printed_pages"]["T1509"]
    assert page["page_and_volume_layers"]["margin_header_literal"].endswith("四十九")
    assert page["page_and_volume_layers"][
        "target_following_volume_end_literal"
    ].endswith("四十八")
    assert page["note29"]["accepted_printed_working_reading"] == "四十八＝十五【石】"
    assert page["note29"]["root_first_misread_retained"] == "四十八＝三十五【石】"
    target = data["printed_pages"]["T2122"]["after_twenty_ninth_day"]
    assert target["unique_printed_character"] is None
    assert target["printed_candidates"] == ["滅", "減"]
    assert target["XML_main_character"] == "減"
    assert not target["established_print_XML_character_discrepancy"]


def test_year_branches_and_extra_arithmetic_assumptions_are_explicit():
    reference = zhidu_reference()
    data = reference["source_data"]
    assert data["intercalation_and_year"]["T1509"][
        "explicit_selected_year_alternatives"
    ] == ["十二月", "十三月"]
    assert data["intercalation_and_year"]["T2122"][
        "explicit_selected_year_alternatives"
    ] == ["十三月"]
    assert len(data["conditional_arithmetic_assumptions"]) == 4
    assert reference["nominal_arithmetic"]["conditional5_cycle_gap_days"] == {
        "numerator": 30,
        "denominator": 1,
    }
    assert not reference["nominal_arithmetic"][
        "historical_intercalation_schedule_established"
    ]
    assert data["sources"]["T2122"]["source_previously_bound_in_existing_data"] is None
    assert data["source_match_scope"][
        "not_found_is_not_global_project_novelty_or_no_prior_capture"
    ]


@pytest.mark.parametrize(
    "key",
    [
        "source_nominal_day_is_modern_86400_seconds",
        "source_term_matches_modern_astronomical_period_certified",
        "enumeration_aligned_to_definitions_by_position",
        "repeated_terms_merged",
        "complete_alternate_witness_text_reconstructed",
        "daily_half_chosen_from_month_length_half",
        "T1299_pingming_modern_clock_established",
        "T2465_half_clock_established",
        "leap_short_priority_established",
        "calendar_or_mansion_override_applied",
        "five_uniform_cycles_are_historical_intercalation_rule",
        "real_prediction_efficacy_established",
    ],
)
def test_unestablished_scope_upgrades_require_a_new_source_review(key):
    data = copy.deepcopy(frozen()["source_data"])
    data["scope"][key] = True
    with pytest.raises(ValueError):
        validate_zhidu(data)


def test_source_mutation_does_not_affect_later_calls_and_native_rejects_it():
    reference = zhidu_reference()
    reference["source_data"]["printed_pages"]["T2122"]["after_twenty_ninth_day"][
        "unique_printed_character"
    ] = "滅"
    with pytest.raises(ValueError):
        zhidu_lines(reference)
    assert (
        zhidu_reference()["source_data"]["printed_pages"]["T2122"][
            "after_twenty_ninth_day"
        ]["unique_printed_character"]
        is None
    )


def test_native_rejects_arithmetic_not_supported_by_its_bound_literals():
    reference = zhidu_reference()
    reference["nominal_arithmetic"]["month4_written_T2122_minus_T1509"]["numerator"] = 0
    with pytest.raises(ValueError):
        zhidu_lines(reference)


@pytest.mark.parametrize("change", ["boolean_integer", "float_integer", "zero_flag"])
def test_native_rejects_nominal_values_with_different_json_types(change):
    reference = zhidu_reference()
    arithmetic = reference["nominal_arithmetic"]
    if change == "boolean_integer":
        arithmetic["models"]["T1509"][1]["denominator"] = True
    elif change == "float_integer":
        arithmetic["models"]["T1509"][1]["numerator"] = 30.0
    else:
        arithmetic["historical_intercalation_schedule_established"] = 0
    with pytest.raises(ValueError, match="名义月长诊断"):
        zhidu_lines(reference)


@pytest.mark.parametrize(
    "field", ["source_bundle_sha256", "before_code_reference_sha256"]
)
def test_parent_native_rejects_wrong_upstream_source_identity(field):
    reference = quotation_reference()
    reference["upstream_calendar_context"][field] = "0" * 64
    with pytest.raises(ValueError, match="来源身份"):
        quotation_lines(reference)


def test_current_quotation_requires_its_actual_upstream_context():
    reference = quotation_reference()
    assert reference["upstream_context_round"] == 89
    assert (
        reference["upstream_calendar_context"]["source_data"] == frozen()["source_data"]
    )
    text = "\n".join(quotation_lines(reference))
    for phrase in [
        "四种月",
        "914/31",
        "1830/67",
        "547/20",
        "49/1340",
        "滅／減",
        "十五",
        "未",
    ]:
        assert phrase in text
    reference.pop("upstream_calendar_context")
    with pytest.raises(KeyError):
        quotation_lines(reference)


def test_archived_quotation_without_current_marker_keeps_its_historical_scope():
    reference = quotation_reference()
    reference.pop("upstream_context_round")
    reference.pop("upstream_calendar_context")
    assert "49/1340" not in "\n".join(quotation_lines(reference))
