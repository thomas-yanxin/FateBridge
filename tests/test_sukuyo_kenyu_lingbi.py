"""A named period table is conditional evidence, not a planetary conjunction."""

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence


def test_sukuyo_lingbi_table_is_exposed_without_replacing_primary_results():
    result = day_evidence(calendar_mansion("2025-02-01", "12:00:00"), "室", "study")
    reference = result["kenyu_lingbi_reference"]
    assert reference["source_image"]["frame"] == 8
    assert len(reference["printed_rows"]) == 23
    assert reference["t1299_planetary_condition_evaluated"] is False
    assert reference["applied_to_primary_or_activities"] is False
    assert reference["ancient_day_boundary_established"] is False
    assert "若有急事欲作之者" in result["reading_text"]
    assert "月首曜条件" in result["reading_text"]


def test_sukuyo_lingbi_literal_endpoints_and_unlisted_conditions_are_preserved():
    from fatebridge.core.sukuyo_kenyu_lingbi import lookup_lingbi_interval

    assert lookup_lingbi_interval(7, "金", 3)["membership_in_printed_interval"] is True
    assert lookup_lingbi_interval(7, "金", 4)["membership_in_printed_interval"] is False
    assert (
        lookup_lingbi_interval(12, "金", 30)["membership_in_printed_interval"] is True
    )
    unlisted = lookup_lingbi_interval(8, "日", 28)
    assert unlisted["matching_intervals"] == []
    assert unlisted["membership_in_printed_interval"] is None
    assert lookup_lingbi_interval(8, "火", 27)["membership_in_printed_interval"] is True
    assert (
        lookup_lingbi_interval(8, "火", 28)["membership_in_printed_interval"] is False
    )


def test_sukuyo_period_lookup_uses_the_month_start_ruler_not_the_current_day_ruler():
    result = day_evidence(calendar_mansion("2024-02-11", "06:30:00"))
    reference = result["kenyu_lingbi_reference"]
    assert result["weekday"]["luminary"] == "日"
    assert reference["civil_month_start_reference"]["date"] == "2024-02-10"
    selected = reference["selected_civil_month_start_lookup"]
    assert selected["condition_month_start_luminary"] == "土"
    assert selected["condition_lunar_day"] == 2
    assert selected["membership_in_printed_interval"] is True
    assert not reference["applied_to_primary_or_activities"]


def test_sukuyo_lingbi_condition_and_urgent_clause_do_not_contaminate_cached_source():
    result = day_evidence(calendar_mansion("2024-02-11"), "室", "study")
    reference = result["kenyu_lingbi_reference"]
    assert reference["urgent_action_established"] is None
    assert next(r for r in reference["personal_conditions"] if "危" in r["relations"])[
        "urgent_action_required"
    ]
    reference["printed_rows"].clear()
    assert (
        len(
            day_evidence(calendar_mansion("2024-02-11"))["kenyu_lingbi_reference"][
                "printed_rows"
            ]
        )
        == 23
    )


def test_sukuyo_new_reference_keeps_independent_day_facts_when_month_is_unknown():
    minimal = {
        "natal_su27": "参",
        "calendar_date": "2025-03-04",
        "calendar_timezone": "UTC+08:00",
        "lunar_day": 7,
    }
    result = day_evidence(
        minimal, activity="travel", activity_details=["long_distance_journey"]
    )
    reference = result["kenyu_lingbi_reference"]
    assert result["day_mansion"] == "参"
    assert result["activity_assessment"] is not None
    assert reference["lookup_status"] == "not_evaluated_missing_calendar_context"
    assert reference["missing_context_fields"] == ["lunar_month", "is_leap_month"]
    assert reference["selected_civil_month_start_lookup"] is None
    assert len(reference["printed_rows"]) == 23
    assert minimal.get("lunar_month") is None


def test_sukuyo_lingbi_leap_clause_does_not_decide_hinoo_priority_or_daybreak():
    result = day_evidence(
        calendar_mansion(
            "1903-06-25",
            "06:00:00",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
    )
    reference = result["kenyu_lingbi_reference"]
    assert reference["leap_month_reference"]["literal"] == "潤月全如本月"
    assert reference["selected_civil_month_start_lookup"] is None
    assert (
        reference["leap_month_reference"]["month_start_ruler_inheritance_established"]
        is False
    )
    assert len(reference["conditional_month_start_lookups"]) == 7
    assert result["day_mansion"] is None
    assert set(result["calendar"]["candidate_su27s"]) == {"鬼", "参"}
    assert result["calendar_day"]["clock_evaluation_status"] == "not_computed"


@pytest.mark.parametrize(
    "args", [(True, "日", 1), (13, "日", 1), (1, "太阳", 1), (1, "日", 31)]
)
def test_sukuyo_lingbi_lookup_refuses_invalid_conditions(args):
    from fatebridge.core.sukuyo_kenyu_lingbi import lookup_lingbi_interval

    with pytest.raises(ValueError):
        lookup_lingbi_interval(*args)
