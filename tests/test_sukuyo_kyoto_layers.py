"""Preserve image layers, historical records and unresolved calculation support."""

import copy
import hashlib

import pytest

from fatebridge.core import sukuyo_kyoto_layers as layers
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_hinoo_critical import SOURCE as LEGACY_SOURCE
from fatebridge.core.sukuyo_sources import LoadedSource, load_source
from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


def legacy():
    loaded = load_source(LEGACY_SOURCE)
    return (
        loaded.data["selected_primary"],
        loaded.data["apparatus_span_reference"],
        loaded.sha256,
    )


def reference():
    return layers.qualify_kyoto_reference(*legacy())


def reviewed_fact_mutation(monkeypatch, change):
    """Exercise guards even if a later review changed the facts digest."""
    loaded = load_source(layers.SOURCE)
    data = loaded.data
    change(data)
    monkeypatch.setattr(layers, "FACTS_SHA256", layers._digest(data))
    monkeypatch.setattr(
        layers, "load_source", lambda _: LoadedSource(data, loaded.sha256)
    )


def test_current_scope_is_qualified_without_rewriting_the_historical_record():
    primary, original_span, identity = legacy()
    selected, active_span = reference()
    followup = selected.pop("later_layered_reading")
    assert selected == primary
    assert active_span["legacy_scope_before_layer_followup"] == original_span["scope"]
    assert "清楚保留这段" in original_span["scope"]
    assert "不能把整串声称为清楚同层黑正文" in active_span["scope"]
    assert (
        active_span["normalized_candidate_span"]
        == original_span["normalized_candidate_span"]
    )
    assert len(active_span["normalized_candidate_span"]) == 16
    assert not active_span["unconditional_ko_deletion_accepted"]
    assert (
        active_span["current_scope_qualification"]["followup_source_bundle_sha256"]
        == followup["source_bundle_sha256"]
    )
    assert followup["expected_legacy"]["source_bundle_sha256"] == identity
    assert hashlib.sha256(LEGACY_SOURCE.read_bytes()).hexdigest() == identity


def test_distinct_date_positions_do_not_inherit_other_positions_corrections():
    primary, _ = reference()
    data = primary["later_layered_reading"]
    assert [r["lunar_day"] for r in data["clear_date_example_positions"]] == [1, 15, 30]
    assert [r["legacy_mansion"] for r in data["clear_date_example_positions"]] == [
        "虚",
        "星",
        "室",
    ]
    assert len(data["corrected_number_positions"]) == 4
    assert all(
        r["black_accepted_literal"] is None for r in data["corrected_number_positions"]
    )
    assert all(
        r["red_working_reading"] == "三十" for r in data["corrected_number_positions"]
    )
    assert {r["legacy_observation_id"] for r in data["mapped_legacy_observations"]} == {
        r["id"] for r in primary["observations"]
    }


@pytest.mark.parametrize("part", ["primary", "span", "source_identity"])
def test_mismatched_legacy_objects_are_rejected(part):
    primary, span, identity = legacy()
    if part == "primary":
        primary["observations"][1]["normalized_transcription"] = "changed"
    elif part == "span":
        span["scope"] = "changed"
    else:
        identity = "0" * 64
    with pytest.raises(ValueError, match="身份不一致"):
        layers.qualify_kyoto_reference(primary, span, identity)


def test_undeclared_fact_edit_rejected_before_source_acceptance(monkeypatch):
    loaded = load_source(layers.SOURCE)
    changed = loaded.data
    changed["scope"] = "changed"
    monkeypatch.setattr(
        layers, "load_source", lambda _: LoadedSource(changed, loaded.sha256)
    )
    with pytest.raises(ValueError, match="事实或读录阶段改变"):
        reference()


@pytest.mark.parametrize("value", [True, None, 0])
def test_even_a_reviewed_new_digest_cannot_promote_acceptance(monkeypatch, value):
    reviewed_fact_mutation(
        monkeypatch,
        lambda d: d["acceptance_flags"].__setitem__(
            "modern_clock_mapping_established", value
        ),
    )
    with pytest.raises(ValueError, match="不能自动提升"):
        reference()


def test_missing_acceptance_flag_is_unknown_not_false(monkeypatch):
    reviewed_fact_mutation(
        monkeypatch, lambda d: d["acceptance_flags"].pop("algorithm_override_applied")
    )
    with pytest.raises(ValueError, match="不能自动提升"):
        reference()


@pytest.mark.parametrize(
    "section", ["number", "glyph", "span", "quote", "overwrite", "side", "insertion"]
)
def test_unresolved_readings_cannot_be_promoted_silently(monkeypatch, section):
    def change(data):
        if section == "number":
            data["corrected_number_positions"][0]["black_accepted_literal"] = "三十"
        elif section == "glyph":
            data["unresolved_readings"][0]["accepted_literal"] = "重"
        elif section == "span":
            data["span_scope_qualification"]["black_accepted_literal"] = "傍"
        elif section == "quote":
            data["quotation_context"]["prefixed_glyph"]["accepted_literal"] = "勘"
        elif section == "overwrite":
            data["middle_black_overwrite_and_side_writing"][
                "black_undertext_accepted_literal"
            ] = "失"
        elif section == "side":
            data["middle_black_overwrite_and_side_writing"][
                "small_black_side_characters"
            ][0]["accepted_literal"] = "雖"
        else:
            data["middle_black_overwrite_and_side_writing"][
                "insertion_order_accepted"
            ] = ["雖", "失"]

    reviewed_fact_mutation(monkeypatch, change)
    with pytest.raises(ValueError, match="不能未经复核"):
        reference()


@pytest.mark.parametrize(
    "change",
    ["missing_mapping", "changed_control", "overlapping_position", "outside_image"],
)
def test_reviewed_mapping_cannot_drop_old_context_or_mix_distinct_positions(
    monkeypatch, change
):
    def mutate(data):
        if change == "missing_mapping":
            data["mapped_legacy_observations"].pop()
        elif change == "changed_control":
            data["clear_date_example_positions"][2]["legacy_mansion"] = "婁"
        elif change == "overlapping_position":
            data["corrected_number_positions"][0]["region_xyxy"] = data[
                "clear_date_example_positions"
            ][2]["region_xyxy"]
        else:
            data["corrected_number_positions"][0]["region_xyxy"] = [0, 0, 6000, 8000]

    reviewed_fact_mutation(monkeypatch, mutate)
    with pytest.raises(ValueError, match="不能|超出"):
        reference()


def test_new_working_conflicts_and_small_notes_remain_attributed():
    primary, _ = reference()
    data = primary["later_layered_reading"]
    disputes = {r["id"]: r for r in data["unresolved_readings"]}
    assert disputes["first-day-verb"]["legacy_root_selected"] == "重"
    assert disputes["first-day-verb"]["reviewer_v104_working"] == "直"
    assert primary["supplemental_model_collation"]["conflicts"][1]["generator"] == "婁"
    assert all(r["accepted_literal"] is None for r in disputes.values())
    assert data["quotation_context"]["inline_note"]["right_small_column"] == [
        "依",
        "口",
    ]
    assert data["quotation_context"]["inline_note"]["left_small_column"] == ["決", "記"]
    assert data["quotation_context"]["red_bracket_function_accepted"] is None
    assert all(value is False for value in data["acceptance_flags"].values())


def test_returned_followup_is_detached_from_source_cache_and_next_call():
    selected, span = reference()
    original = copy.deepcopy((selected, span))
    selected["later_layered_reading"]["corrected_number_positions"][0][
        "black_candidates"
    ].clear()
    span["scope"] = "changed"
    assert reference() == original


@pytest.mark.parametrize("half,expected", [("first_half", None), ("second_half", "参")])
def test_actual_reading_delivers_qualifications_without_changing_slots(half, expected):
    result = calendar_mansion(
        "1903-06-25", calendar_profile="hinoo_t1299_host27", calendar_day_part=half
    )
    assert result["natal_su27"] == expected
    branches = result["profile_calculation"]["short_month_assignment"][
        "leap_short_month_precedence"
    ]
    assert branches["adjacent_month_first_half"] == "鬼"
    assert branches["repeat_true_month_first_half"] == "参"
    assert not branches["source_rule_priority_established"]
    text = day_evidence(result)["reading_text"]
    assert "不能把整串声称为清楚同层黑正文" in text
    assert "所绑定历史补充模型首读" in text
    assert "该历史记录中根任务当时选读" in text
    assert "本次根任务选读" not in text
    assert "后续直／重分歧仍存" in text
    assert "双小行工作读依口決記" in text
    assert "未改变配宿算法" in text
    assert "上旁字工作候选雖／雜，下旁字工作读失" in text
    assert "与半后覆黑是不同字位" in text


@pytest.mark.parametrize("half", ["first_half", "second_half"])
@pytest.mark.parametrize("key", ["suzhan", "sukuyo_compatibility"])
def test_source_layer_fields_survive_all_real_local_adapters(
    monkeypatch, capsys, half, key
):
    if key == "suzhan":
        payload = {
            "date": "1903-06-25",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": half,
        }
        roots = ["sukuyo.calendar"]
        fields = ["sukuyo.reading_text", "rulesets"]
    else:
        payload = {
            "person1_date": "1903-06-25",
            "person2_date": "1957-09-24",
            "calendar_profile": "hinoo_t1299_host27",
            "person1_calendar_day_part": half,
            "person2_calendar_day_part": half,
        }
        roots = ["person1.calendar", "person2.calendar"]
        fields = ["candidate_relation_analysis", "summary", "rulesets"]
    for root in roots:
        prefix = root + ".profile_calculation.hinoo_source.critical_calendar_reference."
        fields += [
            prefix + "selected_primary.later_layered_reading",
            prefix + "apparatus_span_reference.scope",
            prefix + "apparatus_span_reference.legacy_scope_before_layer_followup",
        ]
    run_transport_check(monkeypatch, capsys, key, payload, fields)
