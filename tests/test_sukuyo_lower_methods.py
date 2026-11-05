"""Lower-source tables, contrary witnesses and action-subtype implications."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_lower import (
    DETAIL_PARENTS,
    DETAIL_TOPICS,
    activity_detail_closure,
)
from fatebridge.core.sukuyo_lower_methods import lower_methods_evidence, source_bundle
from fatebridge.validation.sukuyo import required_quote_paths

PRIMARY = json.loads(
    (Path(__file__).parent / "data/sukuyo-lower-methods-primary.json").read_text()
)


def assessment(civil, topic, details=()):
    return day_evidence(
        calendar_mansion(civil), activity=topic, activity_details=details
    )["activity_assessment"]


def matched_ids(result):
    return {r["rule_id"] for r in result["matched_rules"]}


def test_seven_groups_against_individually_transcribed_member_lists():
    # Hand transcribed from the seven primary paragraphs, not service output.
    expected = {
        "安重": "毕翼斗壁",
        "和善": "觜角房奎",
        "毒害": "参柳心尾",
        "急速": "鬼轸牛娄",
        "猛恶": "胃星张箕室",
        "轻": "井亢女虚危",
        "刚柔": "昴氐",
    }
    groups = source_bundle()["nature_groups"]
    assert {g["name"]: "".join(g["members"]) for g in groups} == expected
    assert sum(len(g["members"]) for g in groups) == 28
    assert set("".join(expected.values())) == set(SU27_ORDER) | {"牛"}
    passages = {p["locator"]: p["text"] for p in PRIMARY["nature_passages"]}
    for group in groups:
        assert all(q in passages[group["locator"]] for q in group["source_excerpts"])
    for mansion in SU27_ORDER:
        result = lower_methods_evidence(mansion, "日", None)
        group = result["nature"]["selected_group"]
        assert mansion in expected[group["name"]]
    with pytest.raises(ValueError, match="牛"):
        lower_methods_evidence("牛", "日", None)


def test_light_heading_is_collated_without_turning_zhen_into_a_sixth_member():
    result = lower_methods_evidence("井", "日", "轻燥")
    group = result["nature"]["selected_group"]
    assert group["literal_heading"] == "軫" and group["name"] == "轻"
    assert group["members"] == list("井亢女虚危")
    assert result["nature"]["membership_differs_from_upper"] is False
    variant = group["textual_variants"][0]
    assert variant["apparatus_id"] == "0397004"
    xml = next(
        p["raw_xml"] for p in PRIMARY["apparatus"] if p["apparatus_id"] == "0397004"
    )
    assert ">軫</lem>" in xml and ">輕</rdg>" in xml
    assert (
        lower_methods_evidence("轸", "日", "急速")["nature"]["selected_group"]["name"]
        == "急速"
    )


@pytest.mark.parametrize(
    "luminary,title",
    tuple(
        zip(
            "日月火水木金土",
            [
                "太陽直日",
                "大陰直日",
                "熒惑直日",
                "辰星直日",
                "歲星直日",
                "太白直日",
                "鎮星直日",
            ],
        )
    ),
)
def test_all_seven_lower_weekday_records_retain_their_own_primary_title(
    luminary, title
):
    result = lower_methods_evidence(None, luminary, None)
    row = result["weekday"]
    assert row["literal_title"] == title
    text = next(
        p["text"] for p in PRIMARY["weekday_passages"] if p["locator"] == row["locator"]
    )
    assert title in text
    assert not row["classical_daybreak_boundary_acceptance"]
    assert result["nature"]["selected_group"] is None


def test_27_selected_lower_method_rules_have_primary_quotes_and_valid_conditions():
    rules = source_bundle()["rules"]
    refs = {p["rule_id"]: p for p in PRIMARY["rule_passages"]}
    assert len(rules) == len(refs) == 27
    assert sum(r["layer"] == "lower_nature" for r in rules) == 12
    assert sum(r["layer"] == "lower_weekday" for r in rules) == 15
    for rule in rules:
        ref = refs[rule["rule_id"]]
        assert rule["volume"] == "lower" and ref["locator"] == rule["locator"]
        assert all(q in ref["text"] for q in rule["source_excerpts"])
        for topic, condition in rule.get("activity_conditions", {}).items():
            assert all(DETAIL_TOPICS[d] == topic for d in condition["any_of"])


def test_fire_marriage_and_debt_keep_opposite_upper_lower_witnesses():
    marriage = assessment("2025-03-04", "marriage")
    ids = matched_ids(marriage)
    assert {"t1299_activity_23", "t1299_lower_method_weekday_06"} <= ids
    layers = {r["layer"]: r["status"] for r in marriage["layers"]}
    assert layers["weekday"] == "favorable" and layers["lower_weekday"] == "caution"
    assert marriage["evidence_status"] == "conflicted"
    debt = assessment("2025-03-04", "commerce", ["collecting_debt"])
    assert {"t1299_activity_29", "t1299_lower_method_weekday_08"} <= matched_ids(debt)
    assert debt["evidence_status"] == "conflicted"


def test_stomach_changes_membership_without_replacing_upper_nature_or_calendar():
    day = day_evidence(
        calendar_mansion("2025-03-02"),
        activity="study",
        activity_details=["learning_with_teacher"],
    )
    assert day["day_mansion"] == "胃" and day["nature"] == "急速"
    lower = day["lower_methods"]["nature"]
    assert lower["selected_group"]["name"] == "猛恶"
    assert lower["membership_differs_from_upper"]
    assert "t1299_activity_18" in matched_ids(day["activity_assessment"])
    assert not any(
        r["layer"] == "lower_nature"
        for r in day["activity_assessment"]["matched_rules"]
    )
    assert "下卷按明列成员归为猛恶宿" in day["reading_text"]


def test_lower_rapid_main_sale_does_not_silently_apply_ming_purchase_reading():
    bought = assessment("2025-03-13", "commerce", ["purchase"])
    sold = assessment("2025-03-13", "commerce", ["sale"])
    assert "t1299_lower_method_nature_06" not in matched_ids(bought)
    assert "t1299_lower_method_nature_06" in matched_ids(sold)
    assert "t1299_activity_18" in matched_ids(bought)  # upper has 買賣
    app = next(
        p["raw_xml"] for p in PRIMARY["apparatus"] if p["apparatus_id"] == "0396032"
    )
    assert ">賣</lem>" in app and ">買賣</rdg>" in app


def test_specific_purchase_and_sale_details_also_match_supported_parent_actions():
    specific = assessment("2025-03-04", "commerce", ["purchase_precious_goods"])
    generic = assessment("2025-03-04", "commerce", ["purchase"])
    assert "t1299_lower_method_weekday_05" in matched_ids(specific)
    assert "t1299_lower_method_weekday_05" not in matched_ids(generic)
    assert specific["activity_details"] == ["purchase_precious_goods"]
    assert specific["effective_activity_details"] == [
        "purchase_precious_goods",
        "purchase",
    ]
    assert matched_ids(generic) <= matched_ids(specific)
    assert "spending_property" not in specific["effective_activity_details"]
    upper_buy = assessment("2025-03-03", "commerce", ["purchase_precious_goods"])
    assert "t1299_activity_21" in matched_ids(upper_buy)
    upper_rule = next(
        r for r in upper_buy["matched_rules"] if r["rule_id"] == "t1299_activity_21"
    )
    assert upper_rule["detail_match"]["declared_satisfied_details"] == []
    assert upper_rule["detail_match"]["implied_satisfied_details"] == ["purchase"]
    for detail, parent in [("land_purchase", "purchase"), ("land_sale", "sale")]:
        result = assessment("2025-03-08", "commerce", [detail])
        assert "t1299_lower_method_weekday_13" in matched_ids(result)
        assert parent in result["effective_activity_details"]
    effective, inferred = activity_detail_closure(["sale_lactating_livestock"])
    assert effective == ["sale_lactating_livestock", "sale_livestock", "sale"]
    assert activity_detail_closure(effective)[0] == effective
    assert len(inferred) == 2
    assert all(
        DETAIL_TOPICS[child] == DETAIL_TOPICS[parent]
        for child, parents in DETAIL_PARENTS.items()
        for parent in parents
    )


def test_repaying_money_water_journeys_and_special_study_keep_their_specific_scope():
    assert "t1299_lower_method_nature_05" in matched_ids(
        assessment("2025-03-14", "commerce", ["repaying_debt"])
    )  # 角
    assert "t1299_lower_method_nature_05" not in matched_ids(
        assessment("2025-03-14", "commerce", ["returning_property"])
    )
    assert "t1299_lower_method_nature_10" in matched_ids(
        assessment("2025-03-07", "travel", ["water_journey"])
    )  # 井
    assert "t1299_lower_method_nature_10" not in matched_ids(
        assessment("2025-03-07", "travel", ["long_distance_journey"])
    )
    assert "t1299_lower_method_nature_08" not in matched_ids(
        assessment("2025-03-13", "study", ["beginning_study"])
    )
    assert "t1299_lower_method_nature_08" in matched_ids(
        assessment("2025-03-13", "study", ["classical_text_study"])
    )
    assert "t1299_lower_method_nature_11" in matched_ids(
        assessment("2025-03-07", "study", ["riding_training"])
    )


def test_private_journey_and_saturday_far_travel_do_not_expand_to_all_travel():
    rule = "t1299_lower_method_weekday_03"
    assert rule not in matched_ids(assessment("2025-03-03", "travel"))
    assert rule in matched_ids(assessment("2025-03-03", "travel", ["private_journey"]))
    rule = "t1299_lower_method_weekday_15"
    assert rule not in matched_ids(assessment("2025-03-08", "travel"))
    assert rule in matched_ids(
        assessment("2025-03-08", "travel", ["long_distance_journey"])
    )


def test_partial_calendar_does_not_choose_lower_nature_but_keeps_known_weekday():
    result = day_evidence(calendar_mansion("2025-07-25"), activity="marriage")
    assert result["lower_methods"]["nature"]["status"] == "not_evaluated"
    assert result["lower_methods"]["weekday"]["luminary"] == "金"
    assert "t1299_lower_method_weekday_12" in matched_ids(result["activity_assessment"])
    assert "sukuyo.lower_methods" in required_quote_paths("activity")


def test_lower_source_returns_copies_and_reading_preserves_both_fire_claims():
    c = calendar_mansion("2025-03-04")
    first = day_evidence(c, activity="commerce", activity_details=["collecting_debt"])
    expected = deepcopy(first)
    first["lower_methods"]["nature"]["selected_group"]["members"].clear()
    first["lower_methods"]["weekday"]["literal_title"] = "tampered"
    assert (
        day_evidence(c, activity="commerce", activity_details=["collecting_debt"])
        == expected
    )
    for rule in expected["activity_assessment"]["matched_rules"]:
        assert rule["rule_id"] in expected["reading_text"]
        assert rule["locator"] in expected["reading_text"]
