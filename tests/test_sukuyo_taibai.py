"""Printed day triples, missing witness rows and nonphysical Taibai scope."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_taibai import SOURCE, taibai_direction_reference
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_sukuyo_taibai_primary import verify_primary

PRIMARY = json.loads(
    (Path(__file__).parent / "fixtures/sukuyo-taibai-primary.json").read_bytes()
)


@pytest.mark.parametrize("day,location,direction", PRIMARY["manual_day_locations"])
def test_all_30_days_against_independent_printed_triples(day, location, direction):
    result = taibai_direction_reference(day)
    assert result["lunar_day"] == day
    assert (result["location"], result["horizontal_direction"]) == (location, direction)
    assert len(result["witnesses"]) == 2
    first, ming = result["witnesses"]
    assert first["status"] == "listed" and first["applied_to_primary"]
    assert result["source_sha256"] == PRIMARY["source_sha256"]
    assert (
        result["source_bundle_sha256"]
        == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    )
    assert not result["physical_venus_position_evaluated"]
    assert not result["astronomical_retrograde_evaluated"]
    assert not result["movement_alignment_evaluated"]
    assert not result["applied_to_activity_assessment"]
    if day in PRIMARY["ming_missing_days"]:
        assert ming["status"] == "row_deleted_in_apparatus"
        assert ming["source_excerpt"] == ""
        assert ming["location"] is None and ming["realm"] is None
        assert not ming["reading_complete_for_selected_day"]
        assert not result["witnesses_agree_for_selected_day"]
        assert result["location"] == "天上" and result["realm"] == "above_sky"
    else:
        assert ming["status"] == "listed" and ming["reading_complete_for_selected_day"]
        assert result["witnesses_agree_for_selected_day"]
    assert not ming["applied_to_primary"]


def test_primary_table_and_apparatus_verifier_does_not_claim_private_full_bytes():
    report = verify_primary()
    assert report["selected_xml_paragraphs"] == 12
    assert report["selected_sat_quotation_lines"] == 19
    assert report["selected_apparatus_records"] == 13
    assert report["main_table_rows_agree_after_annotation_and_space_removal"]
    assert not report["full_source_xml_bytes_rechecked"]
    assert not report["full_publisher_response_bytes_rechecked"]
    assert not report["exact_cross_database_apparatus_identity"]
    assert len(report["retained_apparatus_literal_findings"]) == 2
    assert not report["independent_ming_edition_or_facsimile_collation"]


@pytest.mark.parametrize("day", [0, 31, -1, True, False, 1.0, "1", None])
def test_invalid_or_noninteger_day_is_not_coerced_into_source_table(day):
    with pytest.raises(ValueError):
        taibai_direction_reference(day)


def test_gregorian_day_and_hinoo_mansion_substitution_do_not_replace_lunar_day():
    day = day_evidence(calendar_mansion("2025-03-04"))
    assert day["calendar"]["lunar_day"] == 5
    assert day["taibai_direction_reference"]["location"] == "西方"
    halves = [
        day_evidence(
            calendar_mansion(
                "2024-08-04",
                calendar_profile="hinoo_t1299_host27",
                calendar_day_part=part,
            )
        )
        for part in ["first_half", "second_half"]
    ]
    assert halves[0]["day_mansion"] != halves[1]["day_mansion"]
    assert (
        halves[0]["taibai_direction_reference"]
        == halves[1]["taibai_direction_reference"]
    )
    assert halves[0]["taibai_direction_reference"]["lunar_day"] == 1


def test_known_lunar_day_survives_unresolved_leap_mansion():
    result = day_evidence(
        calendar_mansion(
            "2017-06-24", zone="+09:00", calendar_basis="japanese_hutime_1002_1_utc09"
        )
    )
    assert result["day_mansion"] is None
    assert result["taibai_direction_reference"]["location"] == "東方"


def test_unknown_and_incomplete_dates_keep_every_conditional_reference():
    complete = day_evidence(calendar_mansion("2025-02-07", zone="UTC"))
    assert complete["taibai_direction_reference"] is None
    assert [
        d["taibai_direction_reference"]["lunar_day"] for d in complete["candidate_days"]
    ] == [10, 11]
    assert "明本校记删去" in complete["reading_text"]
    incomplete = day_evidence(
        calendar_mansion(
            "1872-12-31", zone="UTC", calendar_basis="japanese_naoj_historical_utc09"
        )
    )
    assert incomplete["taibai_direction_reference"] is None
    assert incomplete["calendar"]["out_of_range_calendar_dates"] == ["1873-01-01"]
    assert (
        incomplete["candidate_days"][0]["taibai_direction_reference"]["lunar_day"] == 2
    )


def test_sky_and_below_ground_have_no_fabricated_horizontal_bearing_or_activity():
    for day, realm in [(9, "below_ground"), (10, "above_sky")]:
        reference = taibai_direction_reference(day)
        assert reference["realm"] == realm and reference["horizontal_direction"] is None
    result = day_evidence(
        calendar_mansion("2025-02-07"),
        activity="travel",
        activity_details=["eastbound_journey"],
    )
    assert result["taibai_direction_reference"]["location"] == "天上"
    assert "明本校记删去初十、二十、三十的天上行" in result["reading_text"]
    assert "不是实测金星方位或天文顺逆行" in result["reading_text"]
    assert not any(
        "taibai" in rule["rule_id"]
        for rule in result["activity_assessment"]["matched_rules"]
    )


def test_returned_edition_doctrine_and_apparatus_are_detached():
    first = taibai_direction_reference(10)
    first["witnesses"][1]["location"] = "天上"
    first["doctrine"]["movement_alignment_definition_established"] = True
    first["table_apparatus"].clear()
    later = taibai_direction_reference(10)
    assert later["witnesses"][1]["location"] is None
    assert not later["doctrine"]["movement_alignment_definition_established"]
    assert len(later["table_apparatus"]) == 13


def test_public_taibai_projection_has_typed_witnesses_and_uncomputed_flags():
    spec = next(s for s in CATALOG if s.key == "suzhan")
    defs = spec.output_model.model_json_schema()["$defs"]
    assert "taibai_direction_reference" in defs["SukuyoDay"]["properties"]
    assert "witnesses" in defs["SukuyoTaibaiReference"]["properties"]
    assert (
        "reading_complete_for_selected_day" in defs["SukuyoTaibaiWitness"]["properties"]
    )
