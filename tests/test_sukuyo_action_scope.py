"""Literal actors, purpose and social actions cannot substitute for each other."""

import json
from pathlib import Path

import pytest

from fatebridge.core.requests.divination import SuZhanRequest
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_activities import source_bundle as upper_bundle
from fatebridge.core.sukuyo_calendar_text import source_bundle as named_bundle
from fatebridge.core.sukuyo_lower import activity_detail_closure
from fatebridge.core.sukuyo_lower import source_bundle as mansion_bundle
from fatebridge.core.sukuyo_lower_methods import source_bundle as method_bundle

PRIMARY = json.loads(
    (Path(__file__).parent / "fixtures/sukuyo-action-scope-primary.json").read_bytes()
)


def evidence(civil, activity, details=(), natal=None):
    return day_evidence(
        calendar_mansion(civil),
        natal_mansion=natal,
        activity=activity,
        activity_details=details,
    )


def ids(result, bucket="matched_rules"):
    return {r["rule_id"] for r in result["activity_assessment"][bucket]}


@pytest.mark.parametrize(
    "details,lower_applies",
    [
        ([], False),
        (["long_distance_journey"], False),
        (["royal_or_official_traveler"], False),
        (["long_distance_journey", "diplomatic_mission"], False),
        (["long_distance_journey", "private_journey"], False),
        (["long_distance_journey", "royal_or_official_traveler"], True),
    ],
)
def test_lower_sunday_requires_actor_and_distance_but_upper_keeps_its_own_scope(
    details, lower_applies
):
    result = evidence("2025-03-02", "travel", details)
    assert ("t1299_lower_method_weekday_01" in ids(result)) is lower_applies
    assert ("t1299_activity_20" in ids(result)) is ("long_distance_journey" in details)
    bucket = "matched_rules" if lower_applies else "conditional_rules"
    rule = next(
        r
        for r in result["activity_assessment"][bucket]
        if r["rule_id"] == "t1299_lower_method_weekday_01"
    )
    assert rule["detail_match"]["required_all_of"] == [
        "long_distance_journey",
        "royal_or_official_traveler",
    ]
    assert rule["detail_match"]["applied_to_aggregate"] is lower_applies
    passage = next(
        p["text"] for p in PRIMARY["selected_primary"] if p["id"] == "lower_sun"
    )
    assert "王公百官等東西南北遠行" in passage
    assert "王公百官等東西南北遠行" in rule["source_excerpts"]
    if lower_applies:
        assert (
            "本次适用条件：下卷本条同时限定王公百官等行旅者及远行"
            in result["reading_text"]
        )


@pytest.mark.parametrize(
    "details,applies",
    [
        ([], False),
        (["personal_departure"], False),
        (["personal_departure", "long_distance_journey"], False),
        (["personal_departure", "diplomatic_mission"], False),
        (["private_journey"], True),
        (["private_journey", "long_distance_journey"], True),
    ],
)
def test_private_purpose_is_not_inferred_from_departure_or_distance(details, applies):
    result = evidence("2025-03-03", "travel", details)
    assert ("t1299_lower_method_weekday_03" in ids(result)) is applies
    # Upper main text has 私精; it is not silently amended from lower 私情.
    assert "t1299_activity_22" not in ids(result)
    assert "上卷月曜主文私精与下卷私情字面不同" in result["reading_text"]
    assert any("私精" in note for note in result["textual_variants"])


@pytest.mark.parametrize(
    "details,expected",
    [
        ([], set()),
        (["social_gathering"], {"t1299_lower_method_weekday_04"}),
        (
            ["forming_friendship"],
            {"t1299_activity_22", "t1299_lower_method_weekday_03"},
        ),
        (
            ["social_gathering", "forming_friendship"],
            {
                "t1299_activity_22",
                "t1299_lower_method_weekday_03",
                "t1299_lower_method_weekday_04",
            },
        ),
    ],
)
def test_monday_existing_friends_gathering_is_not_a_new_friendship(details, expected):
    result = evidence("2025-03-03", "social", details)
    assert ids(result) == expected
    if details == ["social_gathering"]:
        assert result["activity_assessment"]["evidence_status"] == "favorable"
        assert "t1299_activity_22" in ids(result, "conditional_rules")
        assert "所问社交" in result["reading_text"]
    if len(details) == 2:
        assert result["activity_assessment"]["evidence_status"] == "conflicted"
        assert "须核对动作和卷别" in result["reading_text"]


def test_friendship_scope_is_consistent_across_all_eighteen_selected_clauses():
    rules = [
        *upper_bundle()["rules"],
        *named_bundle()["activity_rules"],
        *mansion_bundle()["rules"],
        *method_bundle()["rules"],
    ]
    by_id = {r["rule_id"]: r for r in rules}
    for key, expected in [
        ("friendship_clauses", ["forming_friendship"]),
        ("friendship_or_gathering_clauses", ["forming_friendship", "social_gathering"]),
    ]:
        for rule_id in PRIMARY[key]:
            assert by_id[rule_id]["activity_conditions"]["social"]["any_of"] == expected
            assert (
                "结" in by_id[rule_id]["meaning"] or "交" in by_id[rule_id]["meaning"]
            )
    assert (
        len(PRIMARY["friendship_clauses"] + PRIMARY["friendship_or_gathering_clauses"])
        == 18
    )


def test_new_facts_do_not_imply_each_other_or_departure():
    for detail in [
        "forming_friendship",
        "social_gathering",
        "private_journey",
        "royal_or_official_traveler",
        "personal_departure",
        "diplomatic_mission",
    ]:
        assert activity_detail_closure([detail]) == ([detail], [])
    for detail, activity in [
        ("forming_friendship", "social"),
        ("private_journey", "travel"),
        ("royal_or_official_traveler", "travel"),
    ]:
        request = SuZhanRequest.model_validate(
            {
                "date": "2025-03-03",
                "time": "12:00:00",
                "activity": activity,
                "activity_details": [detail],
            }
        )
        assert request.activity_details == [detail]
        with pytest.raises(ValueError):
            SuZhanRequest.model_validate(
                {
                    "date": "2025-03-03",
                    "time": "12:00:00",
                    "activity": "commerce",
                    "activity_details": [detail],
                }
            )


def test_generic_hundred_affairs_clauses_and_real_marriage_conflicts_are_preserved():
    # A blanket source clause still covers each narrower action; the fix is
    # not a blanket removal of unfavorable evidence.
    for details in [["social_gathering"], ["forming_friendship"]]:
        result = evidence("2025-03-04", "social", details, natal="毕")
        assert {"t1299_activity_01", "t1299_activity_09"} <= ids(result)
    marriage = evidence("2025-03-04", "marriage", natal="奎")
    assert {"t1299_activity_11", "t1299_activity_12"} <= ids(marriage)
    assert marriage["personal_day"]["textual_conflict"]
    assert marriage["activity_assessment"]["evidence_status"] == "conflicted"


def test_action_facts_do_not_change_calendar_chart_or_physical_sky():
    from fatebridge.services.divination import calculate_suzhan_analysis

    results = [
        calculate_suzhan_analysis(
            date="2025-03-03",
            time="12:00:00",
            zone="+08:00",
            szchart=1,
            activity="social",
            activity_details=[detail],
        )
        for detail in ["social_gathering", "forming_friendship"]
    ]
    assert all("error" not in r for r in results), results
    assert results[0]["astronomy"] == results[1]["astronomy"]
    assert results[0]["chart"] == results[1]["chart"]
    assert results[0]["sukuyo"]["calendar"] == results[1]["sukuyo"]["calendar"]
    assert [r["sukuyo"]["activity_assessment"]["evidence_status"] for r in results] == [
        "favorable",
        "caution",
    ]
