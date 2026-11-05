"""Unresolved halves retain conditional evidence without selecting a mansion."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "data/sukuyo-candidate-days-before-code-v98.json"
    ).read_bytes()
)
PROFILE = "hinoo_t1299_host27"


def test_conditional_candidates_are_declared_and_typed_in_shared_output_schema():
    from pydantic import ValidationError

    from fatebridge.core.output_reference import SukuyoDay

    assert "candidate_mansion_days" in SukuyoDay.model_json_schema()["properties"]
    SukuyoDay.model_validate(
        {"candidate_mansion_days": [{"applied_to_primary": False}]}
    )
    with pytest.raises(ValidationError):
        SukuyoDay.model_validate(
            {"candidate_mansion_days": "silently accepted extension"}
        )


def calendar(date="2024-08-04", part=None, **kwargs):
    return calendar_mansion(
        date,
        "09:00:00",
        "+08:00",
        calendar_profile=PROFILE,
        calendar_day_part=part,
        **kwargs,
    )


def test_unresolved_half_retains_both_personal_days_and_actual_source_witnesses():
    context = calendar()
    before = copy.deepcopy(context)
    day = day_evidence(context, "室", "travel")
    assert context == before
    assert day["day_mansion"] is None and day["personal_day"] is None
    assert day["candidate_days"] == []
    branches = day["candidate_mansion_days"]
    assert [
        (r["day_mansion"], r["personal_day"]["relation"]["relation"]) for r in branches
    ] == [("星", "安"), ("张", "危")]
    assert [
        len(r["personal_day"]["source_day_evidence"]["witnesses"]) for r in branches
    ] == [2, 5]
    assert not any(
        r["layer"] == "sanjiu" for r in day["activity_assessment"]["matched_rules"]
    )
    for row, half in zip(branches, ["first_half", "second_half"]):
        assert row["applied_to_primary"] is False
        assert row["conditions"] == [
            {
                "calendar_day_part": half,
                "reconstruction_id": None,
                "assignment_origin": (
                    "preceding_month_omitted_day_30"
                    if half == "first_half"
                    else "current_month_regular_day_1"
                ),
            }
        ]
        expected = next(
            r
            for r in REFERENCE["resolved_outputs"]
            if r["input"] == {"date": "2024-08-04", "part": half}
        )
        for field in [
            "personal_day",
            "nature",
            "activity_assessment",
            "lower_mansion_day",
            "lower_methods",
            "special_day_evidence",
            "directional_travel",
        ]:
            assert row[field] == expected[field], field
    text = day["reading_text"]
    assert "此支以本命室顺数至星为安" in text
    assert "此支以本命室顺数至张为危" in text
    for row in branches:
        for key in ["matched_rules", "conditional_rules"]:
            for rule in row["activity_assessment"][key]:
                assert rule["rule_id"] in text and rule["meaning"] in text
                assert rule["locator"] in text
                if rule.get("topic_condition"):
                    assert rule["topic_condition"] in text
    assert "未代入未定主宿或顶层事项" in text


@pytest.mark.parametrize(
    "activity",
    [
        "social",
        "marriage",
        "travel",
        "relocation",
        "commerce",
        "study",
        "clothing",
        None,
    ],
)
def test_every_activity_uses_the_existing_explicit_half_selectors(activity):
    day = day_evidence(calendar(), "室", activity)
    for row, half in zip(day["candidate_mansion_days"], ["first_half", "second_half"]):
        resolved = day_evidence(calendar(part=half), "室", activity)
        assert row["activity_assessment"] == resolved["activity_assessment"]
        if activity == "clothing":
            assert row["clothing_reference"] == resolved["clothing_reference"]
        assert resolved["candidate_mansion_days"] == []


def test_leap_overlap_retains_each_model_and_half_without_choosing_priority():
    for part in [None, "first_half"]:
        context = calendar("1957-09-24", part)
        day = day_evidence(context, "室", "travel", ["personal_departure"])
        assert day["day_mansion"] is None
        assert [r["day_mansion"] for r in day["candidate_mansion_days"]] == ["角", "轸"]
        supports = [c for r in day["candidate_mansion_days"] for c in r["conditions"]]
        assert len(supports) == (4 if part is None else 2)
        assert {c["reconstruction_id"] for c in supports} == {
            "adjacent_month_short_day_assignment",
            "repeat_regular_month_first_day_assignment",
        }
        for row in day["candidate_mansion_days"]:
            for condition in row["conditions"]:
                assert condition["calculation"]["direct_mansion"] == row["day_mansion"]
                if part:
                    assert condition["calendar_day_part"] == part
        assert not context["profile_calculation"]["short_month_assignment"][
            "leap_short_month_precedence"
        ]["source_rule_priority_established"]


def test_date_branches_keep_their_own_half_branches_and_unknown_clock():
    context = calendar_mansion(
        "2024-08-04", zone="Asia/Tokyo", calendar_profile=PROFILE
    )
    day = day_evidence(context, "室", "travel")
    assert context["birth_time_known"] is False
    assert [d["calendar"]["calendar_date"] for d in day["candidate_days"]] == [
        "2024-08-03",
        "2024-08-04",
    ]
    assert day["candidate_days"][0]["candidate_mansion_days"] == []
    assert [
        r["day_mansion"] for r in day["candidate_days"][1]["candidate_mansion_days"]
    ] == ["星", "张"]
    assert day["day_mansion"] is None and day["personal_day"] is None


def test_incomplete_default_leap_candidate_is_not_promoted_to_complete():
    context = calendar_mansion("2023-03-22", "09:00:00", "+08:00")
    day = day_evidence(context, "室", "study")
    assert day["day_mansion"] is None
    assert len(day["candidate_mansion_days"]) == 1
    branch = day["candidate_mansion_days"][0]
    assert branch["candidate_set_complete_under_declared_reconstructions"] is False
    assert branch["conditions"][0]["calendar_day_part"] is None
    assert branch["applied_to_primary"] is False


def test_candidate_mutation_cannot_leak_into_other_results_or_input():
    context = calendar()
    first = day_evidence(context, "室", "travel")
    first["candidate_mansion_days"][0]["personal_day"]["upper_volume"][
        "meaning"
    ] = "tampered"
    first["candidate_mansion_days"][0]["conditions"][0][
        "calendar_day_part"
    ] = "tampered"
    second = day_evidence(context, "室", "travel")
    assert (
        second["candidate_mansion_days"][0]["personal_day"]["upper_volume"]["meaning"]
        != "tampered"
    )
    assert context["calendar_day_part"] is None
    assert (
        second["candidate_mansion_days"][0]["conditions"][0]["calendar_day_part"]
        == "first_half"
    )
