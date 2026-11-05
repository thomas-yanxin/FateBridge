"""Full source-quote coverage, applicability counterexamples and frozen data."""

import hashlib
import json
import re
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_activities
from fatebridge.core.sukuyo import calendar_mansion, day_evidence, rulesets
from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence
from fatebridge.core.sukuyo_calendar_text import source_bundle as day_bundle
from fatebridge.core.sukuyo_lower import source_bundle as lower_bundle

FIXTURE = json.loads(
    (Path(__file__).parent / "data/sukuyo-rule-scope-primary.json").read_text()
)


def all_rules():
    return [
        *sukuyo_activities.source_bundle()["rules"],
        *day_bundle()["activity_rules"],
        *lower_bundle()["rules"],
    ]


def assessment(date, activity, details=()):
    return day_evidence(
        calendar_mansion(date), activity=activity, activity_details=details
    )["activity_assessment"]


def ids(rows, layer=None):
    return {r["rule_id"] for r in rows if layer is None or r["layer"] == layer}


def test_all_91_rules_have_literal_selected_quotes_from_their_own_primary_window():
    rules = all_rules()
    refs = {r["rule_id"]: r for r in FIXTURE["rule_passages"]}
    assert len(rules) == len(refs) == 91
    assert {r["rule_id"] for r in rules} == set(refs)
    for rule in rules:
        ref = refs[rule["rule_id"]]
        assert ref["locator"] == rule["locator"]
        assert rule["source_excerpts"]
        assert all(q in ref["text"] for q in rule["source_excerpts"])
        condition = rule.get("activity_conditions", {}).get("travel", {})
        details = [
            *condition.get("any_of", []),
            *condition.get("all_of", []),
            *rule.get("activity_detail_any_of", []),
            *rule.get("activity_detail_all_of", []),
        ]
        if "long_distance_journey" in details:
            # A literal-support guard, not a semantic-acceptance score.
            assert re.search("遠(?:出)?行", ref["text"]), rule["rule_id"]


def test_upper_broad_travel_and_lower_far_travel_are_not_forced_into_one_scope():
    generic = assessment("2025-03-05", "travel")  # lunar2/6
    far = assessment("2025-03-05", "travel", ["long_distance_journey"])
    assert "t1299_named_day_05" in ids(generic["matched_rules"])
    assert "t1299_named_day_15" in ids(generic["conditional_rules"])
    assert {"t1299_named_day_05", "t1299_named_day_15"} <= ids(far["matched_rules"])
    generic = assessment("2025-03-01", "travel")  # lunar2/2
    assert "t1299_named_day_03" in ids(generic["matched_rules"])
    assert "t1299_named_day_13" in ids(generic["conditional_rules"])


@pytest.mark.parametrize(
    "details,expected",
    [
        ([], False),
        (["journey_abroad"], False),
        (["long_distance_journey"], False),
        (["journey_abroad", "long_distance_journey"], True),
    ],
)
def test_far_journey_abroad_requires_both_source_conditions(details, expected):
    assert calendar_mansion("2025-03-13")["natal_su27"] == "轸"
    result = assessment("2025-03-13", "travel", details)
    rows = result["matched_rules"] if expected else result["conditional_rules"]
    rule = next(r for r in rows if r["rule_id"] == "t1299_lower_mansion_18")
    evaluation = rule["detail_match"]
    assert evaluation["applied_to_aggregate"] is expected
    assert set(evaluation["required_all_of"]) == {
        "journey_abroad",
        "long_distance_journey",
    }
    assert set(evaluation["missing_all_of"]) == {
        "journey_abroad",
        "long_distance_journey",
    } - set(details)


def test_studying_with_teacher_is_not_arbitrarily_limited_to_first_enrolment():
    result = assessment("2025-03-13", "study", ["learning_with_teacher"])
    assert "t1299_activity_18" in ids(result["matched_rules"])


def test_lunar_day_debt_restrictions_retain_upper_lower_direction_difference():
    borrowing = assessment("2025-03-11", "commerce", ["borrowing"])
    lending = assessment("2025-03-11", "commerce", ["lending"])
    assert ids(borrowing["matched_rules"], "named_day") == {"t1299_named_day_21"}
    assert ids(lending["matched_rules"], "named_day") == {
        "t1299_named_day_20",
        "t1299_named_day_21",
    }
    rapid_borrow = assessment("2025-03-13", "commerce", ["borrowing"])
    rapid_lend = assessment("2025-03-13", "commerce", ["lending"])
    assert "t1299_activity_18" not in ids(rapid_borrow["matched_rules"])
    assert "t1299_activity_18" in ids(rapid_lend["matched_rules"])
    purchase = assessment("2025-03-13", "commerce", ["purchase"])
    assert "t1299_activity_18" in ids(purchase["matched_rules"])
    assert not ids(purchase["matched_rules"], "named_day")


def test_new_debt_rules_match_collection_spending_and_borrowing_separately():
    collect = assessment("2025-03-04", "commerce", ["collecting_debt"])
    assert {"t1299_activity_29", "t1299_activity_30"} <= ids(collect["matched_rules"])
    spending = assessment("2025-03-04", "commerce", ["spending_property"])
    assert "t1299_activity_29" in ids(spending["matched_rules"])
    assert "t1299_activity_30" not in ids(spending["matched_rules"])
    borrow = assessment("2025-03-05", "commerce", ["borrowing"])
    assert "t1299_activity_31" in ids(borrow["matched_rules"])


def test_individual_day_time_witnesses_and_eight_part_doctrine_are_literal_references():
    for ref in FIXTURE["time_witnesses"]:
        evidence = calendar_day_evidence(ref["lunar_day"])
        row = next(
            r
            for r in evidence["time_restrictions"]
            if r["witness"] == "lower_named_day"
        )
        assert (
            row["source_excerpt"] == ref["excerpt"]
            and row["source_excerpt"] in ref["text"]
        )
        assert row["phase"] == ref["phase"] and row["locator"] == ref["locator"]
        assert evidence["clock_evaluation_status"] == "not_computed"
    clock = calendar_day_evidence(8)["clock_doctrine"]
    assert clock["source_excerpt"] == FIXTURE["clock_clause"]["text"]
    assert clock["day_parts"] == clock["night_parts"] == 8
    assert clock["intradaily_luminary_order"] is None
    assert (
        not clock["western_24_hora_applied"]
        and not clock["source_claim_is_empirical_validation"]
    )


def test_all_30_lunar_days_render_every_published_time_witness_without_dropping_one():
    first = date(2025, 1, 29)
    for offset in range(30):
        context = calendar_mansion((first + timedelta(days=offset)).isoformat())
        assert context["lunar_day"] == offset + 1
        result = day_evidence(context)
        for row in result["calendar_day"]["time_restrictions"]:
            assert row["locator"] in result["reading_text"]
            if row["witness"] == "lower_named_day":
                assert "下卷日名逐日条文" in result["reading_text"]


def test_loaded_old_table_cannot_report_new_disk_bytes_as_its_fingerprint(
    monkeypatch, tmp_path
):
    original = sukuyo_activities.SOURCE.read_bytes()
    path = tmp_path / "rules.json"
    path.write_bytes(original)
    monkeypatch.setattr(sukuyo_activities, "SOURCE", path)
    first = assessment("2025-03-04", "commerce", ["purchase"])
    edited = json.loads(original)
    edited["id"] = "not_the_loaded_table"
    path.write_text(json.dumps(edited))
    second = assessment("2025-03-04", "commerce", ["purchase"])
    assert first == second
    assert second["source_bundle_sha256"] == hashlib.sha256(original).hexdigest()
    assert (
        second["source_bundle_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()
    )


def test_mutating_returned_facts_cannot_change_later_source_calculation():
    c = calendar_mansion("2025-03-04", calendar_profile="hinoo_t1299_host27")
    first = day_evidence(
        c, natal_mansion="毕", activity="commerce", activity_details=["purchase"]
    )
    expected = deepcopy(first)
    first["activity_assessment"]["matched_rules"][0]["selectors"].clear()
    first["lower_mansion_day"]["topic_rules"][0]["activities"].clear()
    first["conjunction_doctrine"]["selected_group"]["members"].clear()
    first["calendar_day"]["clock_doctrine"]["day_parts"] = 99
    first["calendar"]["profile_calculation"]["hinoo_source"]["id"] = "tampered"
    second = day_evidence(
        calendar_mansion("2025-03-04", calendar_profile="hinoo_t1299_host27"),
        natal_mansion="毕",
        activity="commerce",
        activity_details=["purchase"],
    )
    assert second == expected
    prior = deepcopy(rulesets("hinoo_t1299_host27"))
    returned = rulesets("hinoo_t1299_host27")
    returned["calendar"]["hinoo_addendum"]["id"] = "tampered"
    assert rulesets("hinoo_t1299_host27") == prior
