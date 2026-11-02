"""Literal lower-volume clauses, detail matching and observation boundaries."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.divination import SuZhanRequest
from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_lower import (
    conjunction_doctrine,
    lower_mansion_evidence,
    source_bundle,
)

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/sukuyo-lower-primary.json").read_text()
)
ALIASES = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")


def evidence(name, activity=None, details=None):
    return day_evidence(
        {
            "natal_su27": name,
            "calendar_date": "2025-03-04",
            "calendar_timezone": "UTC+08:00",
            "lunar_day": 5,
        },
        activity=activity,
        activity_details=details,
    )


def lower_layer(result):
    return next(
        r
        for r in result["activity_assessment"]["layers"]
        if r["layer"] == "lower_mansion"
    )


def test_all_named_entries_are_indexed_and_each_rule_quotes_its_own_source():
    bundle = source_bundle()
    assert bundle["source_sha256"] == REFERENCE["source_sha256"]
    refs = {r["mansion"]: r for r in REFERENCE["paragraphs"]}
    assert set(refs) == set(SU27_ORDER)
    assert {r["mansion"] for r in bundle["records"]} == set(SU27_ORDER)
    rules = bundle["rules"]
    assert len({r["rule_id"] for r in rules}) == len(rules) == 40
    assert sum(r["applicability"] == "activity_detail_required" for r in rules) == 23
    for rule in rules:
        assert rule["source_excerpt"] in refs[rule["selectors"][0]]["text"]
    for case in REFERENCE["cases"]:
        assert case["excerpt"] in refs[case["mansion"]]["text"]
        matched = [
            r
            for r in rules
            if r["selectors"] == [case["mansion"]]
            and case["activity"] in r["activities"]
            and r["assessment"] == case["assessment"]
            and r["applicability"] == case["applicability"]
        ]
        assert bool(matched) == (case["assessment"] is not None), case


def test_borrowing_does_not_become_a_prohibition_on_all_trade():
    generic = evidence("毕", "commerce")
    borrowing = evidence("毕", "commerce", ["borrowing"])
    sale = evidence("毕", "commerce", ["sale"])
    assert lower_layer(generic)["status"] == "conditional_only"
    assert lower_layer(sale)["status"] == "conditional_only"
    assert lower_layer(borrowing)["status"] == "caution"
    pending = [
        r
        for r in generic["activity_assessment"]["conditional_rules"]
        if r["layer"] == "lower_mansion"
    ]
    assert len(pending) == 1 and not pending[0]["applied_to_aggregate"]
    rule = next(
        r
        for r in borrowing["activity_assessment"]["matched_rules"]
        if r["layer"] == "lower_mansion"
    )
    assert rule["matched_activity_details"] == ["borrowing"]
    assert rule["applied_to_aggregate"]
    assert "未计入上述宜忌状态" in generic["reading_text"]


def test_southbound_restriction_requires_direction_and_does_not_replace_nature():
    generic = evidence("壁", "travel")
    south = evidence("壁", "travel", ["southbound_journey"])
    assert lower_layer(generic)["status"] == "conditional_only"
    assert lower_layer(south)["status"] == "caution"
    assert generic["nature"] == south["nature"] == "安重"
    assert "不宜南行" in south["reading_text"]


def test_ambiguous_reading_and_unattributed_paragraph_are_not_silently_applied():
    uncertain = evidence("女", "study", ["skill_learning"])
    pending = uncertain["activity_assessment"]["conditional_rules"]
    assert any(
        r["applicability_status"] == "not_evaluated_textual_reading_unresolved"
        for r in pending
    )
    assert not any(
        r["layer"] == "lower_mansion"
        for r in uncertain["activity_assessment"]["matched_rules"]
    )
    issue = lower_mansion_evidence("氐")["textual_issues"][0]
    assert issue["literal"] == REFERENCE["unattributed_paragraph"]["text"]
    assert not issue["applied_to_activity"]
    assert lower_layer(evidence("氐", "study"))["status"] == "uncovered"
    assert "未再次署宿" in evidence("氐", "study")["reading_text"]
    # Repairing a dwelling or moving grain indoors is not relocating a person.
    assert not lower_mansion_evidence("星")["topic_rules"]


def test_commerce_incoming_outgoing_and_general_trade_are_distinguished():
    generic = evidence("危", "commerce")
    spending = evidence("危", "commerce", ["spending_property"])
    assert lower_layer(generic)["status"] == "conditional_only"
    assert lower_layer(spending)["status"] == "caution"
    sale_and_spending = evidence("危", "commerce", ["sale", "spending_property"])
    assert lower_layer(sale_and_spending)["status"] == "conflicted"
    assert any(
        r.get("source_excerpt") == "不宜出財"
        for r in generic["activity_assessment"]["conditional_rules"]
    )
    assert all(
        r["source_excerpt"] != "不宜出財"
        for r in generic["activity_assessment"]["matched_rules"]
        if r["layer"] == "lower_mansion"
    )


def test_all_conjunction_memberships_and_inference_are_explicit():
    expected = REFERENCE["groups"]
    for key, names in expected.items():
        for name in names.translate(ALIASES):
            r = conjunction_doctrine(name)
            assert r["selected_group"]["id"] == key
            assert not r["applied_to_physical_moon"]
            assert r["angular_offset_degrees"] is None
            assert r["physical_evaluation_status"].startswith("not_computed")
    groups = source_bundle()["conjunction_doctrine"]["groups"]
    assert [len(g["members"]) for g in groups] == [6, 12, 9]
    assert set().union(*(set(g["members"]) for g in groups)) == set(SU27_ORDER)
    assert groups[-1]["membership_basis"].startswith("inferred_")
    with pytest.raises(ValueError):
        conjunction_doctrine("牛")


def test_unresolved_mansion_does_not_apply_lower_rules_or_choose_a_group():
    r = day_evidence(
        calendar_mansion("2024-08-04", calendar_profile="hinoo_t1299_host27"),
        activity="commerce",
        activity_details=["sale"],
    )
    assert r["lower_mansion_day"]["status"] == "not_evaluated"
    assert lower_layer(r)["status"] == "not_evaluated"
    doctrine = r["conjunction_doctrine"]
    assert doctrine["selected_group"] is None
    assert [r["mansion"] for r in doctrine["candidate_groups"]] == ["星", "张"]
    assert all(not r["applied_to_primary"] for r in doctrine["candidate_groups"])


def test_existing_school_and_far_journey_rules_are_not_applied_to_all_study_or_travel():
    generic = evidence("毕", "study")
    founding = evidence("毕", "study", ["founding_school"])
    assert any(
        r["rule_id"] == "t1299_activity_15"
        for r in generic["activity_assessment"]["conditional_rules"]
    )
    assert not any(
        r["rule_id"] == "t1299_activity_15"
        for r in generic["activity_assessment"]["matched_rules"]
    )
    assert any(
        r["rule_id"] == "t1299_activity_15"
        for r in founding["activity_assessment"]["matched_rules"]
    )
    generic = evidence("毕", "travel")
    far = evidence("毕", "travel", ["long_distance_journey"])
    assert any(
        r["rule_id"] == "t1299_activity_16"
        for r in generic["activity_assessment"]["conditional_rules"]
    )
    assert any(
        r["rule_id"] == "t1299_activity_16"
        for r in far["activity_assessment"]["matched_rules"]
    )


@pytest.mark.parametrize(
    "activity,details",
    [
        (None, ["borrowing"]),
        ("marriage", ["sale"]),
        ("study", ["southbound_journey"]),
        ("commerce", ["invented"]),
    ],
)
def test_invalid_detail_context_rejected_by_both_public_and_domain_models(
    activity, details
):
    with pytest.raises(ValidationError):
        SuZhanRequest(
            date="2025-03-04",
            time="12:00:00",
            activity=activity,
            activity_details=details,
        )
    with pytest.raises(ValueError):
        evidence("毕", activity, details)
