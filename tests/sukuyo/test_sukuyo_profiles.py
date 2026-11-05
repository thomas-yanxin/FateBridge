"""Primary full-moon examples and independently dated small-month cases."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.compatibility import SukuyoCompatibilityRequest
from fatebridge.core.requests.divination import SuZhanRequest
from fatebridge.core.sukuyo import (
    MONTH_STARTS,
    SU27_ORDER,
    calendar_mansion,
    day_evidence,
    lunar_mansion,
)
from fatebridge.core.sukuyo_profiles import fullmoon_calculation
from fatebridge.services.divination import (
    calculate_sukuyo_compatibility,
    calculate_suzhan_analysis,
)
from scripts.sukuyo.fetch_sukuyo_reference import published_rows, read_sources

REFERENCE = json.loads(
    (Path(__file__).parents[1] / "data/sukuyo-fullmoon-primary.json").read_text()
)
NAOJ = json.loads(
    (Path(__file__).parents[1] / "data/sukuyo-t1299-reference.json").read_text()
)
ALIASES = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")


def test_fullmoon_source_examples_and_inclusive_counting():
    for example in REFERENCE["examples"]:
        r = fullmoon_calculation(example["month"], example["day"], SU27_ORDER)
        assert r["direct_mansion"] == example["mansion"].translate(ALIASES)
        assert r["shortcut_mansion"] == r["direct_mansion"]
    r = fullmoon_calculation(2, 17, SU27_ORDER)
    assert r["shortcut_inclusive_count"] == 30
    assert r["shortcut_one_based_remainder"] == 3
    assert r["fullmoon_mansion"] == "角" and r["direct_mansion"] == "氐"


def test_all_360_month_day_results_match_the_independent_naoj_start_table():
    # Expected table was frozen from NAOJ before this implementation existed.
    assert NAOJ["naoj_month_starts"] == MONTH_STARTS
    for month, anchor in enumerate(REFERENCE["anchors"], 1):
        assert fullmoon_calculation(month, 15, SU27_ORDER)[
            "direct_mansion"
        ] == anchor.translate(ALIASES)
        for day in range(1, 31):
            start = SU27_ORDER.index(NAOJ["naoj_month_starts"][month - 1])
            expected = SU27_ORDER[(start + day - 1) % 27]
            r = fullmoon_calculation(month, day, SU27_ORDER)
            assert r["direct_mansion"] == r["shortcut_mansion"] == expected
            assert lunar_mansion(month, day) == expected


def test_small_month_case_dates_come_from_official_hko_text_not_production():
    rows = {r[0]: r for r in published_rows(read_sources())}
    case = REFERENCE["hinoo_cases"][0]
    before = rows[case["previous_civil_date"]]
    after = rows[case["civil_date"]]
    assert before[2:4] == [case["previous_lunar_month"], 29]
    assert after[2:4] == [case["lunar_month"], 1]


def test_hinoo_unknown_part_does_not_guess_from_a_known_civil_clock():
    for time in [None, "00:00:00", "11:59:59", "12:00:00", "23:59:59"]:
        r = calendar_mansion("2024-08-04", time, calendar_profile="hinoo_t1299_host27")
        assert r["status"] == "partial" and r["natal_su27"] is None
        assert r["candidate_su27s"] == ["星", "张"]
        assert r["candidate_su27"] is None
        assert r["resolution_reason"] == "hinoo_short_month_day_part_unresolved"
        assert r["source_table_variant"]["reference_is_primary_result"] is False
        text = day_evidence(r)["reading_text"]
        assert "候选星、张未作为确定宿应用" in text and "None" not in text
    pair = calculate_sukuyo_compatibility(
        person1_date="2024-08-04",
        person2_date="2024-08-04",
        calendar_profile="hinoo_t1299_host27",
        person2_calendar_day_part="second_half",
    )
    assert pair["status"] == "partial" and pair["pair"] is None
    choices = pair["candidate_relation_analysis"]
    assert choices["candidate_set_complete_within_profile"]
    assert [
        (r["person1_su27"], r["person2_su27"], r["pair"]) for r in choices["rows"]
    ] == [("星", "张", "栄親"), ("张", "张", "命")]
    assert all(not r["applied_to_primary"] for r in choices["rows"])


def test_explicit_hinoo_halves_change_mansion_and_pair_without_changing_lunar_date():
    args = dict(date_text="2024-08-04", calendar_profile="hinoo_t1299_host27")
    first = calendar_mansion(**args, calendar_day_part="first_half")
    second = calendar_mansion(**args, calendar_day_part="second_half")
    assert first["natal_su27"] == "星" and second["natal_su27"] == "张"
    for key in [
        "calendar_date",
        "lunar_year",
        "lunar_month",
        "lunar_day",
        "is_leap_month",
    ]:
        assert first[key] == second[key]
    r = calculate_sukuyo_compatibility(
        person1_date="2024-08-04",
        person2_date="2024-08-04",
        calendar_profile="hinoo_t1299_host27",
        person1_calendar_day_part="first_half",
        person2_calendar_day_part="second_half",
    )
    assert r["status"] == "computed" and r["pair"] == "栄親"
    assert r["person1_to_person2"]["relation"] == "栄"
    assert r["person2_to_person1"]["relation"] == "親"
    base = calculate_sukuyo_compatibility(
        person1_date="2024-08-04", person2_date="2024-08-04"
    )
    assert base["pair"] == "命"


def test_hinoo_same_half_mansions_resolve_without_inventing_a_half():
    r = calendar_mansion("2024-03-10", calendar_profile="hinoo_t1299_host27")
    assert r["natal_su27"] == "奎" and r["calendar_day_part"] is None
    slots = r["profile_calculation"]["short_month_assignment"]["slots"]
    assert [s["mansion"] for s in slots] == ["奎", "奎"]
    assert "两个半日候选同宿" in day_evidence(r)["reading_text"]


def test_leap_repeat_and_short_month_precedence_remain_unresolved_when_needed():
    # Official HKO: ordinary month 5 ends on 1903-06-24 at day 29.
    r = calendar_mansion(
        "1903-06-25",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert r["is_leap_month"] and r["leap_month_policy"] == "repeat_month"
    assert r["status"] == "partial" and r["natal_su27"] is None
    assert r["candidate_su27s"] == ["鬼", "参"]
    assert r["resolution_reason"] == "hinoo_leap_short_month_precedence_unresolved"
    variants = r["profile_calculation"]["short_month_assignment"][
        "leap_short_month_precedence"
    ]
    assert variants["kind"].startswith("modern_reconstruction")
    r2 = calendar_mansion(
        "1903-06-25",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="second_half",
    )
    assert r2["status"] == "computed" and r2["natal_su27"] == "参"
    assert "未取唯一宿" in day_evidence(r)["reading_text"]
    # An ordinary 30-day month does not erase the earlier short-month
    # assignment if one reconstructs intercalation by repeating that month.
    long_month = calendar_mansion(
        "1957-09-24",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert long_month["status"] == "partial"
    assert long_month["candidate_su27s"] == ["角", "轸"]
    assert (
        long_month["profile_calculation"]["short_month_assignment"]["previous_lunar"][
            "lunar_day"
        ]
        == 30
    )


def test_no_hinoo_profile_means_no_hidden_leap_policy_change():
    base = calendar_mansion("2025-07-25")
    research = calendar_mansion("2025-07-25", calendar_profile="hinoo_t1299_host27")
    assert base["status"] == "partial" and base["candidate_su27s"] == ["鬼"]
    assert not base["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ]
    assert research["natal_su27"] == "鬼"
    assert (
        research["profile_calculation"]["requested_leap_month_policy"] == "unresolved"
    )
    assert research["leap_month_policy"] == "repeat_month"
    assert not research["profile_calculation"]["classical_full_profile_acceptance"]
    assert (
        research["profile_calculation"]["hinoo_source"]["textual_variant"]["literal"]
        == "十二月十五日星、三十日星"
    )


def test_calendrical_profile_cannot_move_the_physical_sky():
    args = dict(date="2024-08-04", time="09:00:00", zone="+08:00")
    base = calculate_suzhan_analysis(**args)
    first = calculate_suzhan_analysis(
        **args, calendar_profile="hinoo_t1299_host27", calendar_day_part="first_half"
    )
    assert base["astronomy"] == first["astronomy"]
    assert base["chart"] == first["chart"]
    assert base["sukuyo"]["day_mansion"] == "张"
    assert first["sukuyo"]["day_mansion"] == "星"


@pytest.mark.parametrize(
    "model,params",
    [
        (
            SuZhanRequest,
            {
                "date": "2024-08-04",
                "time": "09:00:00",
                "calendar_day_part": "first_half",
            },
        ),
        (
            SukuyoCompatibilityRequest,
            {
                "person1_date": "2024-08-04",
                "person2_date": "2024-08-04",
                "person1_calendar_day_part": "first_half",
            },
        ),
    ],
)
def test_day_part_cannot_silently_apply_to_another_calendar_profile(model, params):
    with pytest.raises(ValidationError):
        model.model_validate(params)
    with pytest.raises(ValueError):
        calendar_mansion("2024-08-04", calendar_day_part="first_half")
