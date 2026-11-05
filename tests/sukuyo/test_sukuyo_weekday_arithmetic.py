"""Selected manuscript arithmetic, never a hidden modern-calendar policy."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_weekday import (
    civil_weekday,
    classical_weekday_arithmetic,
)

FIXTURE = json.loads(
    (
        Path(__file__).parents[1] / "data/sukuyo-weekday-arithmetic-primary.json"
    ).read_bytes()
)


def test_entered_months_are_added_before_intercalation_not_after_it():
    # Literal order: multiply years by 12, ADD entered months, multiply by 7.
    # A zero-month worked example cannot catch this 30-day error.
    result = classical_weekday_arithmetic(2, 9, 1)
    trace = result["trace"]
    assert trace["intercalation_numerator"] == 231
    assert trace["intercalary_months"] == 1
    assert trace["accumulated_months"] == 34
    assert trace["accumulated_days"] == 1005
    assert result["luminary"] == "木"


def test_printed_2603_year_example_only_controls_its_shared_integer_prefix():
    example = FIXTURE["printed_recalculation"]
    trace = classical_weekday_arithmetic(example["elapsed_years"], 0, 0)["trace"]
    assert {key: trace[key] for key in example["printed_integer_steps"]} == example[
        "printed_integer_steps"
    ]
    assert trace["omission_numerator"] == example["printed_unbiased_numerator"] + 500
    assert not example["same_as_general_integer_formula"]
    # These are different numerical objects and must not be silently merged.
    printed_mean = Fraction(trace["nominal_days"] * (703 - 11), 703)
    assert int(printed_mean) == 950737
    assert printed_mean.denominator == 703
    assert trace["omission_remainder"] == 411
    assert trace["omitted_days"] == 15113


@pytest.mark.parametrize(
    "years,months,days",
    [(0, 0, 0), (1, 0, 1), (2, 9, 1), (1501, 4, 5), (2**60 + 13, 12, 30)],
)
def test_exact_division_order_and_remainders_without_floating_point(
    years, months, days
):
    # Independent rational formulation of the transcribed formula, not a
    # production-output fixture or an independent historical observation.
    count = years * 12 + months
    leaps = Fraction(count * 7, 228).__floor__()
    nominal = (count + leaps) * 30 + days
    omissions = Fraction(nominal * 11 + 500, 703).__floor__()
    result = classical_weekday_arithmetic(years, months, days)
    trace = result["trace"]
    assert trace["accumulated_days"] == nominal - omissions
    assert (
        trace["intercalary_months"] * 228 + trace["intercalation_remainder"]
        == count * 7
    )
    assert (
        trace["omitted_days"] * 703 + trace["omission_remainder"] == nominal * 11 + 500
    )
    assert not result["applied_to_primary_calendar"]
    assert not result["civil_date_conversion_evaluated"]
    assert not result["later_fractional_recalculation_applied"]


def test_count_one_and_zero_remainder_are_not_zero_based_moon_counts():
    outputs = [classical_weekday_arithmetic(0, 0, day) for day in range(1, 8)]
    assert [row["luminary"] for row in outputs] == list("月火水木金土日")
    assert outputs[0]["sexagenary_label"] == "甲辰"
    assert classical_weekday_arithmetic(0, 2, 1)["trace"]["accumulated_days"] == 60
    assert classical_weekday_arithmetic(0, 2, 1)["sexagenary_label"] == "癸卯"


@pytest.mark.parametrize(
    "position,value",
    [
        (0, -1),
        (0, True),
        (0, 1501.0),
        (1, 13),
        (1, "4"),
        (2, 31),
        (2, False),
        (2, None),
    ],
)
def test_elapsed_count_inputs_cannot_imply_a_civil_date_or_invent_missing_counts(
    position, value
):
    counts = [1501, 4, 5]
    counts[position] = value
    with pytest.raises(ValueError):
        classical_weekday_arithmetic(*counts)


def test_returned_trace_does_not_mutate_the_next_source_calculation():
    result = classical_weekday_arithmetic(1501, 4, 5)
    expected = result["trace"].copy()
    result["trace"]["accumulated_days"] = -999
    assert classical_weekday_arithmetic(1501, 4, 5)["trace"] == expected


@pytest.mark.parametrize("zone", ["UTC+08:00", "UTC+09:00"])
def test_primary_civil_weekday_stays_separate_from_manuscript_counts(zone):
    result = civil_weekday("0840-02-11", zone)
    assert result["luminary"] == "土"
    assert not result["classical_daybreak_boundary_acceptance"]
    context = calendar_mansion("2025-02-07", "12:00:00", "+08:00")
    assert day_evidence(context)["weekday"] == civil_weekday("2025-02-07", "UTC+08:00")


def test_unknown_host_boundary_cannot_silently_claim_utc08():
    with pytest.raises(ValueError):
        civil_weekday("2025-02-07", "UTC+10:00")
    context = calendar_mansion("2025-02-07", "12:00:00", "+08:00")
    context["calendar_timezone"] = "UTC+10:00"
    with pytest.raises(ValueError):
        day_evidence(context)


def test_primary_source_control_does_not_count_a_later_formula_as_the_general_rule():
    from scripts.sukuyo.check_sukuyo_weekday_arithmetic import verify_arithmetic

    report = verify_arithmetic()
    assert not report["printed_prefix_errors"]
    assert not report["rational_algebra_errors"]
    assert report["rational_algebra_cases"] == 741
    assert report["post_intercalation_month_addition_counterexamples"]
    assert not report["separate_recalculation"]["same_full_algorithm_claimed"]


def test_manuscript_capture_must_match_its_fingerprint(tmp_path):
    from scripts.sukuyo.check_sukuyo_weekday_arithmetic import verify_arithmetic

    (tmp_path / FIXTURE["captured_pages"][0]["file"]).write_bytes(b"altered image")
    with pytest.raises(ValueError, match="fingerprint"):
        verify_arithmetic(tmp_path)
