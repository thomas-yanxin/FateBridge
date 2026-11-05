"""Documentary layers must not silently become calendar or action policy."""

from copy import deepcopy

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence
from fatebridge.core.sukuyo_directions import source_bundle, travel_direction_evidence
from fatebridge.core.sukuyo_documentary import with_text_layers
from fatebridge.core.sukuyo_lower import lower_mansion_evidence
from scripts.sukuyo.check_sukuyo_documentary_primary import verify_documentary_primary


def test_sukuyo_wall_opposition_preserves_main_and_inline_without_changing_activity():
    result = day_evidence(
        calendar_mansion("2025-04-22", "12:00:00"),
        activity="travel",
        activity_details=["southbound_journey"],
    )
    matches = {r["rule_id"]: r for r in result["activity_assessment"]["matched_rules"]}
    assert result["activity_assessment"]["evidence_status"] == "conflicted"
    main = matches["t1299_lower_mansion_37"]["source_passages"][0]
    note = matches["t1299_direction_10"]["source_passages"][0]
    assert "不宜南行" in main["main_text"] and main["inline_notes"] == []
    assert note["main_text"] == "第十二魚宮"
    assert "南行大吉" in note["inline_notes"][0]["text"]
    assert "取壁" not in note["main_text"]
    assert result["directional_travel"]["selected_records"][0]["source_passages"] == [
        note
    ]
    text = result["reading_text"]
    assert "取宿及行向说明在行内注" in text and "所选条文在主文" in text
    assert "同向出行证言相反" in text


def test_sukuyo_paired_already_above_clause_keeps_both_passages_and_detaches():
    original = next(
        r for r in source_bundle()["rules"] if r["rule_id"] == "t1299_direction_05"
    )
    before = deepcopy(original)
    attached = with_text_layers(original)
    assert [p["paragraph_xml_id"] for p in attached["source_passages"]] == [
        "pT21p0397b0201",
        "pT21p0397b0301",
    ]
    assert "東行大吉" not in attached["source_passages"][0]["inline_notes"][0]["text"]
    assert "已上東行大吉" in attached["source_passages"][1]["inline_notes"][0]["text"]
    attached["source_passages"][0]["inline_notes"][0]["text"] = "changed"
    assert original == before
    assert (
        with_text_layers(original)["source_passages"][0]["inline_notes"][0]["text"]
        == "取角、亢日"
    )


def test_sukuyo_prohibition_and_unreleasing_note_remain_separate():
    record = travel_direction_evidence("轸")["selected_records"][0]
    passage = record["source_passages"][0]
    assert "不得向北路行" in passage["main_text"]
    assert passage["inline_notes"] == [{"place": "inline", "text": "縱吉時亦不可行"}]
    assert record["auspicious_time_cannot_release"]
    assert lower_mansion_evidence("壁")["topic_rules"]


def test_sukuyo_japanese_body_comparison_preserves_all_thirty_primary_days():
    differences = []
    favorable = {1, 3, 5, 7, 10, 11, 13, 16, 18, 20, 22, 25, 26, 28}
    upper = {2, 6, 9, 12, 17, 21, 24, 27, 29}
    lower = {2, 6, 9, 12, 14, 17, 19, 21, 23, 24, 27, 30}
    for day in range(1, 31):
        result = calendar_day_evidence(day)
        assert [r["assessment"] for r in result["classifications"]] == [
            (
                "favorable"
                if day in favorable
                else "conditional" if day in selected else "unlisted"
            )
            for selected in (upper, lower)
        ]
        comparison = result["japanese_selected_reference"]
        if any(
            r["favorable_list_membership_differs"]
            for r in comparison["primary_general_day_comparison"]
        ):
            differences.append(day)
        assert comparison["current_body_list_membership"] == (
            "listed_favorable"
            if day in {1, 3, 5, 7, 9, 11, 13, 18, 20, 22, 24, 26, 28}
            else "unlisted"
        )
        assert not comparison["applied_to_primary"]
        assert not comparison["leap_short_month_priority_established"]
        assert result["clock_evaluation_status"] == "not_computed"
    assert differences == [9, 10, 16, 24, 25]


def test_sukuyo_unaccepted_margin_and_correlated_sequence_are_not_admitted():
    first = calendar_day_evidence(16)["japanese_selected_reference"]
    assert first["current_body_list_membership"] == "unlisted"
    assert first["unaccepted_marginal_annotation"]["normalized_transcription"] is None
    assert not first["selected_body_day_sequence"]["marginal_reconstruction_applied"]
    assert first["selected_body_weekday_sequence"]["luminaries"] == list(
        "土日月火水木金土"
    )
    assert not first["selected_body_weekday_sequence"]["intradaily_clock_order"]
    assert not first["source_reference"][
        "identified_as_T2465_or_its_base_or_ko_witness"
    ]
    first["selected_body_day_sequence"]["lunar_days"].append(16)
    assert (
        16
        not in calendar_day_evidence(16)["japanese_selected_reference"][
            "selected_body_day_sequence"
        ]["lunar_days"]
    )


def test_sukuyo_new_witness_does_not_resolve_leap_short_month_order():
    calendar = calendar_mansion(
        "1957-09-24",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    day = day_evidence(calendar)
    assert day["day_mansion"] is None
    assert not day["calendar_day"]["japanese_selected_reference"][
        "leap_short_month_priority_established"
    ]
    assert "闰月补配优先次序" in day["reading_text"]


def test_sukuyo_primary_placement_checker_and_changed_full_source(tmp_path):
    report = verify_documentary_primary()
    assert report["errors"] == [] and report["selected_paragraphs"] == 17
    assert not report["independent_image_transcription_or_human_collation"]
    path = tmp_path / "T21n1299.xml"
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="full source bytes changed"):
        verify_documentary_primary(path)


@pytest.mark.parametrize(
    "date,membership", [("2025-01-08", "listed_favorable"), ("2025-01-24", "unlisted")]
)
def test_sukuyo_new_manuscript_time_clause_is_not_lost_in_native_reading(
    date, membership
):
    day = day_evidence(
        calendar_mansion(date, "12:00:00"),
        activity="travel",
        activity_details=["southbound_journey"],
    )
    reference = day["calendar_day"]["japanese_selected_reference"]
    assert reference["current_body_list_membership"] == membership
    clause = reference["selected_body_time_restrictions"]["normalized_body_literal"]
    assert (
        clause in day["reading_text"]
    ), "New manuscript time clause present in structured result but missing from native answer"
    assert "善通寺109-5" in day["reading_text"]
    assert not reference["selected_body_time_restrictions"]["clock_conversion_computed"]


def test_sukuyo_own_direction_clause_does_not_claim_following_already_above():
    from fatebridge.core.sukuyo_documentary import text_placement_label

    own = travel_direction_evidence("毕")["selected_records"][0]
    paired = travel_direction_evidence("角")["selected_records"][0]
    assert own["direction_binding_basis"] == "explicit_in_own_clause"
    assert "已上" not in text_placement_label(own)
    assert "连属" in text_placement_label(paired)


def test_sukuyo_known_southbound_is_retained_when_north_clause_is_unmatched():
    day = day_evidence(
        calendar_mansion("2025-01-08", "12:00:00"),
        activity="travel",
        activity_details=["southbound_journey"],
    )
    assert day["activity_assessment"]["evidence_status"] == "favorable"
    assert "本次已明确行向：向南出行" in day["reading_text"]
    assert "不满足此条所需的向北出行" in day["reading_text"]
    assert "行向不自动代表远行" in day["reading_text"]


def test_sukuyo_native_candidate_directions_keep_complete_scope_and_actual_input():
    calendar = calendar_mansion(
        "1957-09-24",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    day = day_evidence(
        calendar, activity="travel", activity_details=["southbound_journey"]
    )
    assert day["day_mansion"] is None
    assert day["activity_assessment"]["matched_rules"] == []
    text = day["reading_text"]
    assert "本次声明的现代重建下完整" in text
    assert "候选角方向条文" in text and "候选轸方向条文" in text
    assert "该支本条方向相符" in text and "该支本条方向不符" in text
    assert "不能将一支方向相符提升为全案宜行" in text


@pytest.mark.parametrize(
    "date,basis,zone,time",
    [
        ("2025-01-07", "chinese_hko_utc08", "+08:00", "12:00:00"),
        ("0820-03-22", "japanese_naoj_historical_utc09", "+09:00", "00:30:00"),
    ],
)
def test_sukuyo_native_explains_confirmed_religious_learning_input(
    date, basis, zone, time
):
    day = day_evidence(
        calendar_mansion(date, time, zone=zone, calendar_basis=basis),
        activity="study",
        activity_details=["religious_learning"],
    )
    assert day["activity_assessment"]["activity_details"] == ["religious_learning"]
    text = day["reading_text"]
    assert "宗教学法" in text
    assert "本次已确认事项细节：宗教学法" in text


@pytest.mark.parametrize("details", [[], ["monastic_dharma_request"]])
def test_sukuyo_native_keeps_declared_input_separate_from_inferred_class(details):
    day = day_evidence(
        calendar_mansion("2025-01-07", "12:00:00"),
        activity="study",
        activity_details=details,
    )
    declared = [
        line
        for line in day["reading_text"].splitlines()
        if line.startswith("本次已确认事项细节：")
    ]
    if not details:
        assert declared == []
    else:
        assert len(declared) == 1 and "出家人求法" in declared[0]
        assert "宗教学法" not in declared[0]
        assert day["activity_assessment"]["activity_details"] == details
        assert (
            "religious_learning"
            in day["activity_assessment"]["effective_activity_details"]
        )
