"""Clothing actions, textual witnesses, and complete day-branch evidence."""

import json
from pathlib import Path

import pytest

from fatebridge.core.requests.divination import SuZhanRequest
from fatebridge.core.sukuyo import calendar_mansion, day_evidence, rulesets
from fatebridge.core.sukuyo_clothing import clothing_reference
from fatebridge.validation.sukuyo import (
    required_quote_paths,
    verify_sukuyo_context_claims,
)
from scripts.sukuyo.audit_sukuyo_clothing_primary import verify_primary
from tests.sukuyo.test_sukuyo_calendar_text import payload, quotes

FACTS = json.loads(
    (Path(__file__).parents[1] / "data/sukuyo-clothing-primary.json").read_bytes()
)


@pytest.mark.parametrize("row", FACTS["verse_rows"], ids=lambda row: row["mansion"])
def test_all_27_literal_verse_cells_are_read_without_invented_outcome_scores(row):
    reference = clothing_reference({"natal_su27": row["mansion"]})
    candidate = reference["candidate_references"][0]
    assert candidate["verse"] == row
    assert candidate["primary_assessment"] == (
        "favorable"
        if row["mansion"] in FACTS["primary_positive_mansions"]
        else "caution"
    )
    assert not reference["verse_and_literal_forecasts_applied_to_aggregate"]
    assert not reference["real_world_event_prediction_evaluated"]


def test_ming_并_is_not_repaired_to_井_or_assigned_a_negative_complement():
    reference = clothing_reference({"natal_su27": "井"})
    primary, ming = reference["candidate_references"][0]["comparisons"]
    assert primary["assessment"] == "favorable"
    assert ming["assessment"] is None and not ming["applied_to_primary"]
    assert (
        "并" in reference["ming_literal_list"]
        and "井" not in reference["ming_literal_list"]
    )
    unlisted = clothing_reference({"natal_su27": "昴"})["candidate_references"][0]
    assert unlisted["primary_assessment"] == "caution"
    assert unlisted["comparisons"][1]["unlisted_complement_assessment"] is None
    assert not reference["independent_ming_edition_collated"]


def test_upper_heading_and_different_literal_forecasts_are_not_normalized_away():
    wall = clothing_reference({"natal_su27": "壁"})["candidate_references"][0]
    assert wall["upper_literal_cutting_statement"]["literal_heading_mansion"] == "璧"
    corner = clothing_reference({"natal_su27": "角"})["candidate_references"][0]
    assert "逃亡" in corner["upper_literal_cutting_statement"]["source_excerpt"]
    assert corner["verse"]["taisho_text"] == "角必安隱"


@pytest.mark.parametrize("name", ["牛", "并", "璧", "井宿", True])
def test_invalid_or_unresolved_mansion_characters_are_not_guessed(name):
    with pytest.raises(ValueError):
        clothing_reference({"natal_su27": name})


def clothing(value, details, **kwargs):
    return day_evidence(
        calendar_mansion(value, "12:00:00", "+08:00", **kwargs),
        activity="clothing",
        activity_details=details,
    )


def ids(result, key="matched_rules"):
    return {row["rule_id"] for row in result["activity_assessment"][key]}


def test_tailoring_closure_preserves_opposing_chapter_and_explicit_making_clauses():
    result = clothing("2025-02-11", ["tailoring_garments"])
    assert result["day_mansion"] == "张"
    assert {"t1299_clothing_02", "t1299_clothing_03", "t1299_clothing_18"} <= ids(
        result
    )
    assert result["activity_assessment"]["evidence_status"] == "conflicted"
    assert result["activity_assessment"]["effective_activity_details"] == [
        "tailoring_garments",
        "making_garments",
    ]
    assert (
        "wearing_garments"
        not in result["activity_assessment"]["effective_activity_details"]
    )
    assert "王者" in result["reading_text"]
    for rule in result["activity_assessment"]["matched_rules"]:
        assert (
            rule["rule_id"] in result["reading_text"]
            and rule["locator"] in result["reading_text"]
        )


def test_mere_making_repair_and_missing_details_do_not_trigger_the_cutting_wearing_list():
    for details in ([], ["making_garments"], ["repairing_garments"]):
        result = clothing("2025-02-07", details)
        assert "t1299_clothing_01" not in ids(result)
        assert "t1299_clothing_01" in ids(result, "conditional_rules")
    actual = clothing("2025-02-07", ["tailoring_garments"])
    assert "t1299_clothing_01" in ids(actual)


def test_royal_identity_and_new_wearing_are_both_required():
    ordinary = clothing("2025-02-04", ["wearing_new_garments"])
    royal_only = clothing("2025-02-04", ["royal_wearer"])
    royal = clothing("2025-02-04", ["wearing_new_garments", "royal_wearer"])
    assert "t1299_clothing_14" not in ids(ordinary) | ids(royal_only)
    assert "t1299_clothing_14" in ids(royal)
    assert (
        "royal_wearer"
        not in ordinary["activity_assessment"]["effective_activity_details"]
    )
    assert ordinary["activity_assessment"]["evidence_status"] == "conflicted"


def test_complete_hinoo_candidates_can_share_a_chapter_fact_without_a_unique_mansion():
    result = clothing(
        "2024-08-04", ["tailoring_garments"], calendar_profile="hinoo_t1299_host27"
    )
    ref = result["clothing_reference"]
    assert ref["mansion"] is None and ref["candidate_mansions"] == ["星", "张"]
    assert ref["candidate_set_complete_under_declared_profile"]
    assert (
        ref["status"] == "candidate_common_membership"
        and ref["primary_assessment"] == "caution"
    )
    assert "t1299_clothing_02" in ids(result)


def test_an_incomplete_single_leap_candidate_does_not_establish_favorable_membership():
    result = clothing("2020-05-23", ["tailoring_garments"])
    ref = result["clothing_reference"]
    assert ref["candidate_mansions"] == ["毕"]
    assert not ref["candidate_set_complete_under_declared_profile"]
    assert ref["primary_assessment"] is None
    assert not {"t1299_clothing_01", "t1299_clothing_02"} & ids(result)


def test_clothing_details_do_not_become_commerce_or_invented_purchase_evidence():
    with pytest.raises(ValueError):
        SuZhanRequest(
            date="2025-02-07",
            activity="commerce",
            activity_details=["wearing_new_garments"],
        )
    with pytest.raises(ValueError):
        SuZhanRequest(
            date="2025-02-07", activity="clothing", activity_details=["purchase"]
        )


def test_complete_context_rejects_the_previous_missing_candidate_day_loophole():
    # Domain/verifier fixture, explicitly synthetic. The public sky-chart tool
    # requires a clock; this does not claim an accepted clockless tool request.
    result = {
        "sukuyo": day_evidence(
            calendar_mansion("1969-09-30", zone="Pacific/Kwajalein"), activity="travel"
        ),
        "rulesets": rulesets(),
    }
    result["run_metadata"] = {
        "tool_name": "suzhan",
        "run_id": "synthetic-domain-branch-context",
    }
    assert len(result["sukuyo"]["candidate_days"]) == 3
    claims = quotes(result, "activity")
    assert (
        verify_sukuyo_context_claims(result, claims, focus="activity")["status"]
        == "verified_context_complete_quotes"
    )
    previous = [claim for claim in claims if claim.path != "sukuyo.candidate_days"]
    rejected = verify_sukuyo_context_claims(result, previous, focus="activity")
    assert {
        "code": "missing_interpretation_context",
        "path": "sukuyo.candidate_days",
    } in rejected["errors"]
    changed = [
        (
            claim.model_copy(update={"value": claim.value[:1]})
            if claim.path == "sukuyo.candidate_days"
            else claim
        )
        for claim in claims
    ]
    assert (
        verify_sukuyo_context_claims(result, changed, focus="activity")["status"]
        == "rejected"
    )


def test_clothing_reference_is_required_even_under_generic_activity_focus():
    result = payload(
        date="2025-02-07",
        natal_mansion=None,
        activity="clothing",
        activity_details=["tailoring_garments"],
    )
    complete = quotes(result, "clothing")
    assert (
        verify_sukuyo_context_claims(result, complete, focus="clothing")["status"]
        == "verified_context_complete_quotes"
    )
    generic = quotes(result, "activity")
    assert (
        verify_sukuyo_context_claims(result, generic, focus="activity")["status"]
        == "rejected"
    )
    assert "sukuyo.candidate_days" in required_quote_paths("day")


def test_primary_source_quotes_and_all_apparatus_are_preserved():
    report = verify_primary()
    assert report["verse_clauses"] == 27 and report["apparatus_records"] == 3
    assert report["action_rules_with_literal_source_quotes"] == 38
    assert report["ming_unlisted_complement_assessment"] is None
    assert not report["manual_action_annotation_independently_accepted"]


def test_quoted_historical_weekday_sequence_does_not_supply_an_hourly_order():
    from scripts.sukuyo.check_sukuyo_historical_weekday import verify_weekday

    report = verify_weekday()
    assert report["printed_weekday_labels_checked"] == 8
    assert not report["mismatches"]
    assert report["rows"][0]["reference_civil_date"] == "0840-02-11"
    assert not report["historical_daybreak_or_hourly_order_accepted"]
