"""Primary passage scopes: distance, departure and residence_entry are distinct."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_activities import source_bundle as legacy_activity_source
from fatebridge.core.sukuyo_sanjiu_days import (
    SOURCE,
    personal_day_witnesses,
    source_bundle,
)
from fatebridge.services.tool_catalog import CATALOG

PRIMARY = json.loads(
    (Path(__file__).parents[1] / "data/sukuyo-sanjiu-days-primary.json").read_text()
)


def result(offset, activity, details=()):
    context = calendar_mansion("2025-03-04")
    natal = SU27_ORDER[(SU27_ORDER.index(context["natal_su27"]) - offset) % 27]
    return day_evidence(context, natal, activity, details)


def ids(rows):
    return {row["rule_id"] for row in rows if row["layer"] == "sanjiu"}


def test_selected_witness_excerpts_match_primary_paragraphs_not_runtime_answers():
    paragraphs = {p["id"]: p["text"] for p in PRIMARY["paragraphs"]}
    bundle = source_bundle()
    assert {r["relation"] for r in bundle["relation_witnesses"]} == set(
        PRIMARY["expected_relations"]
    )
    for relation in PRIMARY["expected_relations"]:
        evidence = personal_day_witnesses(relation)
        assert evidence["source_sha256"] == PRIMARY["source_sha256"]
        assert (
            evidence["source_bundle_sha256"]
            == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        )
        for row in [*evidence["witnesses"], evidence["priority_clause"]]:
            assert all(
                q in paragraphs[row["primary_paragraph_id"]]
                for q in row["source_excerpts"]
            )
        assert not evidence["priority_clause_applied_to_aggregate"]
    for rule in bundle["activity_rules"]:
        assert any(
            all(q in p for q in rule["source_excerpts"]) for p in paragraphs.values()
        )
    rules = {
        r["rule_id"]: r
        for r in [*legacy_activity_source()["rules"], *bundle["activity_rules"]]
    }
    for rule_id, topics in PRIMARY["expected_rule_conditions"].items():
        for topic, expected in topics.items():
            rule = rules[rule_id]
            actual = (
                rule.get("activity_conditions", {})
                .get(topic, {})
                .get("any_of", rule.get("activity_detail_any_of", []))
            )
            assert actual == expected


@pytest.mark.parametrize("offset", [4, 6, 13, 15, 22, 24])
def test_generic_danger_or_destruction_travel_cannot_satisfy_far_or_departure(offset):
    assessment = result(offset, "travel")["activity_assessment"]
    assert not ids(assessment["matched_rules"])
    assert {"t1299_activity_03", "t1299_activity_12", "t1299_sanjiu_lower_18"} <= ids(
        assessment["conditional_rules"]
    )


@pytest.mark.parametrize(
    "details,matched",
    [
        (["long_distance_journey"], {"t1299_activity_03", "t1299_activity_12"}),
        (["personal_departure"], {"t1299_sanjiu_lower_18"}),
        (["long_distance_traveler_entering_residence"], set()),
    ],
)
def test_far_journey_another_saying_departure_and_residence_entry_use_different_clauses(
    details, matched
):
    assessment = result(4, "travel", details)["activity_assessment"]
    assert ids(assessment["matched_rules"]) == matched
    assert {
        "t1299_activity_03",
        "t1299_activity_12",
        "t1299_sanjiu_lower_18",
    } - matched <= ids(assessment["conditional_rules"])


def test_lower_peaceful_residence_entry_does_not_turn_all_departures_favorable():
    for details in [[], ["personal_departure"], ["long_distance_journey"]]:
        assessment = result(3, "travel", details)["activity_assessment"]
        assert "t1299_sanjiu_lower_16" not in ids(assessment["matched_rules"])
        assert "t1299_sanjiu_lower_16" in ids(assessment["conditional_rules"])
    arrival = result(3, "travel", ["long_distance_traveler_entering_residence"])
    assert ids(arrival["activity_assessment"]["matched_rules"]) == {
        "t1299_sanjiu_lower_16"
    }
    assert arrival["activity_assessment"]["detail_inferences"] == []
    assert "不把出发" in arrival["reading_text"]
    move = result(3, "relocation")["activity_assessment"]
    assert {"t1299_activity_04", "t1299_sanjiu_lower_15"} <= ids(move["matched_rules"])


def test_lower_glory_monastic_clause_cannot_impute_participant_identity():
    for details in [
        [],
        ["learning_with_teacher"],
        ["skill_learning"],
        ["religious_learning"],
    ]:
        assessment = result(1, "study", details)["activity_assessment"]
        assert "t1299_sanjiu_lower_17" not in ids(assessment["matched_rules"])
        assert "t1299_sanjiu_lower_17" in ids(assessment["conditional_rules"])
    day = result(1, "study", ["monastic_dharma_request"])
    assert "t1299_sanjiu_lower_17" in ids(day["activity_assessment"]["matched_rules"])
    assert not day["personal_day"]["source_day_evidence"][
        "upper_day_entry_individually_listed"
    ]
    assert day["activity_assessment"]["detail_inferences"] == [
        {
            "from_detail": "monastic_dharma_request",
            "implied_detail": "religious_learning",
        }
    ]


def test_priority_reference_never_deletes_same_volume_opposing_marriage_clause():
    assessment = result(4, "marriage")["activity_assessment"]
    assert {"t1299_activity_05", "t1299_activity_11", "t1299_activity_12"} <= ids(
        assessment["matched_rules"]
    )
    assert (
        next(row for row in assessment["layers"] if row["layer"] == "sanjiu")["status"]
        == "conflicted"
    )
    assert (
        "己身三九若吉"
        in personal_day_witnesses("危")["priority_clause"]["source_excerpts"][0]
    )


def test_no_natal_or_unresolved_target_does_not_apply_personal_day_clauses():
    context = calendar_mansion("2025-03-04")
    day = day_evidence(
        context,
        activity="travel",
        activity_details=["long_distance_traveler_entering_residence"],
    )
    assert day["personal_day"] is None
    assert not ids(day["activity_assessment"]["matched_rules"])
    context = calendar_mansion("2024-08-04", calendar_profile="hinoo_t1299_host27")
    assert day_evidence(context, "奎", "travel")["personal_day"] is None
    with pytest.raises(ValueError):
        day_evidence(
            calendar_mansion("2025-03-04"),
            activity="study",
            activity_details=["long_distance_traveler_entering_residence"],
        )


def test_delivered_witnesses_are_detached_and_exposed_in_public_schema():
    first = personal_day_witnesses("安")
    first["witnesses"].clear()
    assert personal_day_witnesses("安")["witnesses"]
    for spec in CATALOG:
        if spec.key == "suzhan":
            schema = spec.output_model.model_json_schema()
            assert "SukuyoPersonalDay" in schema["$defs"]
            assert (
                "source_day_evidence"
                in schema["$defs"]["SukuyoPersonalDay"]["properties"]
            )
