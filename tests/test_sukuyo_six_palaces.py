"""Six natal positions use explicit primary counts, never calendar-day triggers."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_six_palaces import SOURCE, six_palace_reference
from fatebridge.services.tool_catalog import CATALOG

PRIMARY = json.loads(
    (Path(__file__).parent / "data/sukuyo-six-palaces-primary.json").read_bytes()
)


def test_primary_counting_and_annotation_examples_are_not_generated_oracles():
    reference = six_palace_reference("娄")
    assert reference["counting_excerpt"] in PRIMARY["paragraph"]
    assert (
        reference["joint_reading_requirement"]["source_excerpt"] in PRIMARY["paragraph"]
    )
    assert reference["source_sha256"] == PRIMARY["source_sha256"]
    assert (
        reference["source_bundle_sha256"]
        == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    )
    members = {r["name"]: r for r in reference["members"]}
    for example in PRIMARY["explicit_primary_examples"]:
        row = members[example["position"]]
        assert (row["inclusive_ordinal"], row["mansion"]) == (
            example["inclusive_ordinal"],
            example["mansion"],
        )
    assert {k: v["mansion"] for k, v in members.items()} == PRIMARY[
        "selected_manual_lou_members"
    ]
    assert list(members) == ["命", "事", "意", "聚", "同", "克"]


@pytest.mark.parametrize("natal", SU27_ORDER)
def test_each_natal_reference_keeps_six_distinct_positions_without_event_claim(natal):
    result = six_palace_reference(natal)
    assert result["status"] == "natal_reference"
    assert result["members"][0]["mansion"] == natal
    assert len({r["mansion"] for r in result["members"]}) == 6
    assert not result["seven_luminary_transits_evaluated"]
    assert not result["applied_to_day_assessment"]
    assert not result["joint_reading_requirement"]["evaluated"]


@pytest.mark.parametrize("natal", ["牛", "", "角亢", "命", 0, True])
def test_unverified_or_non_single_mansion_inputs_are_rejected(natal):
    with pytest.raises(ValueError):
        six_palace_reference(natal)


def test_no_natal_input_is_not_replaced_by_target_mansion_and_aliases_work():
    plain = day_evidence(calendar_mansion("2025-03-04"))
    assert plain["day_mansion"] == "毕"
    assert plain["six_palace_reference"]["status"] == "natal_mansion_required"
    assert plain["six_palace_reference"]["members"] == []
    assert plain["six_palace_reference"]["natal_mansion"] is None
    assert six_palace_reference("婁") == six_palace_reference("娄")
    assert (
        day_evidence(calendar_mansion("2025-03-04"), "婁")["six_palace_reference"][
            "natal_mansion"
        ]
        == "娄"
    )


def test_reference_does_not_depend_on_target_date_or_raise_negative_day_trigger():
    days = [
        day_evidence(calendar_mansion(value), "娄", "social")
        for value in ["2025-02-20", "2025-03-04", "2025-03-24"]
    ]
    assert all(
        day["six_palace_reference"] == days[0]["six_palace_reference"] for day in days
    )
    for day in days:
        assert (
            "六宫宿为命宿娄、事宿星、意宿毕、聚宿氐、同宿箕、克宿轸"
            in day["reading_text"]
        )
        assert "七曜运行犯宿及原文要求的三九参断均未计算" in day["reading_text"]
        assert not any(
            row["layer"] == "six_palace"
            for row in day["activity_assessment"]["matched_rules"]
        )


def test_natal_positions_survive_unresolved_or_incomplete_target_calendar():
    leap = day_evidence(
        calendar_mansion(
            "2017-06-24", zone="+09:00", calendar_basis="japanese_hutime_1002_1_utc09"
        ),
        "娄",
    )
    assert leap["day_mansion"] is None and leap["personal_day"] is None
    assert leap["six_palace_reference"]["status"] == "natal_reference"
    unknown = calendar_mansion(
        "2031-01-22", zone="UTC", calendar_basis="japanese_hutime_1002_1_utc09"
    )
    assert unknown["out_of_range_calendar_dates"]
    result = day_evidence(unknown, "娄")
    assert result["six_palace_reference"] == six_palace_reference("娄")
    assert result["personal_day"] is None


def test_returned_nested_data_is_detached_and_public_projection_schema_is_typed():
    first = six_palace_reference("娄")
    first["members"][0]["mansion"] = "牛"
    first["joint_reading_requirement"]["evaluated"] = True
    second = six_palace_reference("娄")
    assert second["members"][0]["mansion"] == "娄"
    assert not second["joint_reading_requirement"]["evaluated"]
    spec = next(spec for spec in CATALOG if spec.key == "suzhan")
    schema = spec.output_model.model_json_schema()
    assert schema["$defs"]["SukuyoDay"]["properties"]["six_palace_reference"]
    assert schema["$defs"]["SukuyoSixPalaceReference"]["properties"]["members"]
