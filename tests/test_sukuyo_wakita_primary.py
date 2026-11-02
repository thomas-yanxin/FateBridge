"""Printed year-count instructions and a conservative decimal precision audit."""

from fractions import Fraction

import pytest

from fatebridge.core.sukuyo_weekday import (
    _fraction_record,
    classical_calibration_precision,
    classical_source_year_count,
    classical_weekday_arithmetic,
)
from scripts.check_sukuyo_wakita_primary import verify_printed_chapter


def fraction(record):
    return Fraction(record["numerator"], record["denominator"])


@pytest.mark.parametrize(
    "year,elapsed",
    [(1, 788), (713, 1500), (714, 1501), (715, 1502), (1816, 2603), (9999, 10786)],
)
def test_printed_year_add_subtract_counts_without_january_first_or_month_mapping(
    year, elapsed
):
    result = classical_source_year_count(year)
    assert result["elapsed_years"] == elapsed
    assert result["algebraic_zero_count_year_number"] == -787
    assert not result["civil_epoch_date_accepted"]
    assert not result["host_lunar_month_mapping_accepted"]
    assert not result["applied_to_primary_calendar"]


@pytest.mark.parametrize("bad", [0, -1, True, 714.0, "714", None, 10000])
def test_year_label_rejects_unstated_numbering_and_noninteger_inputs(bad):
    with pytest.raises(ValueError):
        classical_source_year_count(bad)


def test_year_count_and_entered_counts_remain_separate_from_a_civil_date():
    count = classical_source_year_count(714)
    result = classical_weekday_arithmetic(count["elapsed_years"], 4, 5)
    assert result["inputs"] == {
        "elapsed_years": 1501,
        "elapsed_months": 4,
        "elapsed_days": 5,
    }
    assert not result["civil_date_conversion_evaluated"]
    # Source-defined arithmetic, not a checked Gregorian date for May 5, 714.
    assert result["trace"]["accumulated_days"] == 548358


def test_nominal_and_mean_days_cannot_be_swapped_in_the_secular_denominator():
    trace = classical_calibration_precision()
    counter = trace["denominator_counterexample"]
    assert counter["source_nominal_days"] == 965850
    assert fraction(counter["source_mean_days"]) == Fraction(668368200, 703)
    correct = fraction(counter["correction_from_source_nominal_days"])
    wrong = fraction(counter["wrong_correction_from_mean_days"])
    assert correct == Fraction("6.1042671395") / 965850
    assert wrong > correct
    assert (
        Fraction("0.09")
        < fraction(counter["accumulated_day_error_if_mean_replaces_nominal"])
        < Fraction("0.1")
    )
    assert not counter["is_historical_observation"]


def test_precision_gap_is_not_hidden_by_borrowing_an_earlier_loose_precision():
    trace = classical_calibration_precision()
    assert trace["selected_precision_discrepancies"] == [
        "base_omission_plus_printed_correction",
        "nominal_days_minus_printed_omissions",
    ]
    assert (
        sum(r["compatible_at_selected_decimal_precision"] for r in trace["relations"])
        == 3
    )
    residual = fraction(
        trace["accumulated_day_difference_between_printed_intermediates"]
    )
    assert Fraction("0.000003") < abs(residual) * 86400 < Fraction("0.000004")
    assert not trace["complete_lunar_secular_derivation_accepted"]
    assert not trace["applied_to_primary_calendar"]


@pytest.mark.parametrize(
    "value,expected",
    [
        (Fraction(-5, 4), "-1.250000000000"),
        (Fraction(-1, 10**13), "0.000000000000"),
        (Fraction(-9, 10**13), "-0.000000000001"),
    ],
)
def test_signed_fraction_displays_do_not_turn_small_negative_residuals_into_minus_one(
    value, expected
):
    result = _fraction_record(value)
    assert result["rounded_decimal_12"] == expected
    assert fraction(result) == value
    if abs(value) < 1:
        assert not result["truncated_decimal_12"].startswith("-1.")


def test_printed_witness_comparison_does_not_certify_the_later_calibration():
    report = verify_printed_chapter()
    assert not report["implementation_or_selected_source_errors"]
    assert len(report["selected_formula_constant_comparison"]) == 9
    assert not report["source_arithmetic_consistent_at_selected_precision"]
    assert not report["independent_transcription_accepted"]
    assert not report["civil_epoch_or_host_calendar_mapping_accepted"]


def test_altered_primary_image_fails_before_accepting_any_selected_transcription(
    tmp_path,
):
    import json

    from scripts.check_sukuyo_wakita_primary import FIXTURE

    fixture = json.loads(FIXTURE.read_bytes())
    (tmp_path / fixture["captured_pages"][0]["file"]).write_bytes(b"altered")
    with pytest.raises(ValueError, match="fingerprint"):
        verify_printed_chapter(tmp_path)
