"""Source-bound directional clauses, including contrary and missing evidence."""

import json
from pathlib import Path

import pytest

from fatebridge.core.requests.divination import SuZhanRequest
from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_directions import source_bundle, travel_direction_evidence
from fatebridge.core.sukuyo_padas import palace_reference
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.sukuyo import required_quote_paths

PRIMARY = json.loads(
    (Path(__file__).parent / "fixtures/sukuyo-directions-primary.json").read_text()
)


def evidence(mansion, details=(), activity="travel"):
    return day_evidence(
        {
            "natal_su27": mansion,
            "calendar_date": "2025-03-13",
            "calendar_timezone": "UTC+08:00",
            "lunar_day": 14,
        },
        activity=activity,
        activity_details=details,
    )


def direction_layer(result):
    return next(
        r
        for r in result["activity_assessment"]["layers"]
        if r["layer"] == "travel_direction"
    )


def test_entire_chapter_and_original_apparatus_windows_are_retained():
    bundle = source_bundle()
    assert bundle["source_sha256"] == PRIMARY["source_sha256"]
    assert len(bundle["rules"]) == len(PRIMARY["paragraphs"]) == 16
    text = "".join(p["text"] for p in PRIMARY["paragraphs"])
    apparatus = {r["id"]: r["text"] for r in PRIMARY["apparatus"]}
    for r in bundle["rules"]:
        assert all(e in text for e in r["source_excerpts"])
        for variant in r["textual_variants"]:
            assert variant["literal"] == apparatus[variant["apparatus_id"]]
            assert not variant["applied_to_selected_text"]
    assert PRIMARY["raw_inline_time_exception"] == (
        '<note place="inline">縱吉時亦不可行</note>'
    )


@pytest.mark.parametrize("direction", ["north", "east", "south", "west"])
def test_all_27_day_mansions_against_primary_direction_matrix(direction):
    # A manually transcribed primary-text matrix supplies expected values;
    # neither the rule bundle nor a prior production run supplies the oracle.
    for mansion in SU27_ORDER:
        result = evidence(mansion, [direction + "bound_journey"])
        actual = {
            r["assessment"]
            for r in result["activity_assessment"]["matched_rules"]
            if r["layer"] == "travel_direction"
        }
        expected = set()
        if mansion in PRIMARY["main_text_positive"][direction]:
            expected.add("favorable")
        if mansion in PRIMARY["main_text_negative"][direction]:
            expected.add("caution")
        assert actual == expected, (mansion, direction)
        assert not result["directional_travel"]["direction_inferred"]
        assert not result["directional_travel"]["physical_palace_computed"]


def test_missing_or_different_direction_cannot_apply_north_prohibition():
    generic = evidence("轸")
    wrong = evidence("轸", ["eastbound_journey"])
    north = evidence("轸", ["northbound_journey"])
    for result in (generic, wrong):
        assert not any(
            r["rule_id"] == "t1299_direction_01"
            for r in result["activity_assessment"]["matched_rules"]
        )
        assert any(
            r["rule_id"] == "t1299_direction_01"
            for r in result["activity_assessment"]["conditional_rules"]
        )
    assert direction_layer(north)["status"] == "caution"
    rule = next(
        r
        for r in north["activity_assessment"]["matched_rules"]
        if r["rule_id"] == "t1299_direction_01"
    )
    assert rule["auspicious_time_cannot_release"]
    assert "不能用吉时抵销" in north["reading_text"]


def test_wall_south_preserves_opposite_chapter_and_individual_mansion_clauses():
    result = evidence("壁", ["southbound_journey"])
    facts = result["activity_assessment"]["matched_rules"]
    assert {r["assessment"] for r in facts} == {"favorable", "caution"}
    assert any(
        r["layer"] == "lower_mansion" and r["assessment"] == "caution" for r in facts
    )
    assert any(
        r["layer"] == "travel_direction" and r["assessment"] == "favorable"
        for r in facts
    )
    assert result["activity_assessment"]["evidence_status"] == "conflicted"
    assert "向南出行列为宜条" in result["reading_text"]
    assert "不宜南行" in result["reading_text"]


def test_ming_opposite_assessment_and_membership_are_never_silently_merged():
    for mansion, direction in [("女", "south"), ("娄", "west"), ("毕", "north")]:
        result = evidence(mansion, [direction + "bound_journey"])
        rules = [
            r
            for r in result["activity_assessment"]["matched_rules"]
            if r["layer"] == "travel_direction"
        ]
        assert len(rules) == 1 and rules[0]["assessment"] == "caution"
        assert rules[0]["textual_assessment_variant"]
        assert any(
            v["literal"] == "凶＝吉【明】＊" for v in rules[0]["textual_variants"]
        )
        assert "明本校记作吉" in result["reading_text"]
    tail = travel_direction_evidence("尾")["selected_records"]
    assert len(tail) == 1 and tail[0]["literal_palace_name"] == "弓宮"
    assert tail[0]["direction"] == "west"
    assert "〔尾〕－【明】" in [v["literal"] for v in tail[0]["textual_variants"]]
    # 互 remains an unidentified token; it is not silently normalized to 氐.
    assert travel_direction_evidence("氐")["selected_records"] == []
    assert not any("氐" in r["selectors"] for r in source_bundle()["rules"])
    assert "互" in source_bundle()["textual_issues"][0]["literal"]


def test_palace_numbers_are_local_labels_not_upper_pada_or_natal_palaces():
    record = travel_direction_evidence("星")["selected_records"][0]
    assert (record["literal_palace_ordinal"], record["literal_palace_name"]) == (
        5,
        "獅子宮",
    )
    upper = palace_reference({"natal_su27": "星", "status": "computed"})
    assert upper["selected_palace"]["ordinal"] == 1
    assert not upper["birth_pada_established"]
    result = evidence(None)
    assert result["directional_travel"]["selected_records"] == []
    assert direction_layer(result)["status"] == "not_evaluated"


def test_unresolved_hinoo_candidates_are_reference_only_not_directional_facts():
    context = calendar_mansion("2024-08-04", calendar_profile="hinoo_t1299_host27")
    result = day_evidence(
        context, activity="travel", activity_details=["westbound_journey"]
    )
    assert result["day_mansion"] is None
    assert result["directional_travel"]["selected_records"] == []
    candidates = result["directional_travel"]["candidate_records"]
    assert [r["mansion"] for r in candidates] == ["星", "张"]
    assert all(not r["applied_to_primary"] for r in candidates)
    assert direction_layer(result)["status"] == "not_evaluated"
    assert not any(
        r["layer"] == "travel_direction"
        for r in result["activity_assessment"]["matched_rules"]
    )


def test_validation_schema_context_and_cache_do_not_lose_direction_conditions():
    for direction in ["north", "east", "south", "west"]:
        SuZhanRequest(
            date="2025-03-13",
            time="12:00:00",
            activity="travel",
            activity_details=[direction + "bound_journey"],
        )
    with pytest.raises(ValueError):
        SuZhanRequest(
            date="2025-03-13",
            time="12:00:00",
            activity="study",
            activity_details=["northbound_journey"],
        )
    with pytest.raises(ValueError):
        travel_direction_evidence("牛")
    result = travel_direction_evidence("轸")
    result["selected_records"][0]["textual_variants"].append({"tamper": True})
    assert (
        travel_direction_evidence("轸")["selected_records"][0]["textual_variants"] == []
    )
    assert "sukuyo.directional_travel" in required_quote_paths("activity")
    spec = next(s for s in CATALOG if s.key == "suzhan")
    defs = spec.output_model.model_json_schema()["$defs"]
    assert "directional_travel" in defs["SukuyoDay"]["properties"]
    assert "auspicious_time_cannot_release" in defs["SukuyoActivityRule"]["properties"]
