"""Separate printed mean-day products, units, rounding and retained differences."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_weekday import (
    classical_mean_cycle_arithmetic,
    classical_solar_recalculation,
    classical_weekday_arithmetic,
)
from scripts.sukuyo.check_sukuyo_weekday_recalculation import verify_recalculation

FIXTURE = json.loads(
    (
        Path(__file__).parents[1] / "data/sukuyo-weekday-recalculation-primary.json"
    ).read_bytes()
)


def fraction(row):
    return Fraction(row["numerator"], row["denominator"])


def test_omission_printed_decimal_is_rounded_not_uniformly_truncated():
    result = classical_mean_cycle_arithmetic(137)
    omitted = result["omission_days"]
    assert omitted["rounded_decimal_12"] == "15112.873399715505"
    assert omitted["truncated_decimal_12"] == "15112.873399715504"
    # Exact conservation must hold before rendering either printed decimal.
    assert fraction(omitted) + fraction(result["mean_accumulated_days"]) == 965850


def test_general_bias_integer_and_later_fractional_methods_remain_distinct():
    general = classical_weekday_arithmetic(2603, 0, 0)
    later = classical_mean_cycle_arithmetic(137)
    assert general["trace"]["omission_numerator"] == 10624850
    assert fraction(later["omission_days"]) == Fraction(10624350, 703)
    assert later["omission_bias"] == 0
    assert not later["later_secular_correction_applied"]
    assert not later["general_integer_algorithm_applied"]
    assert not later["applied_to_primary_calendar"]
    assert general["trace"]["accumulated_days"] != fraction(
        later["mean_accumulated_days"]
    )


def test_printed_scaled_year_is_divided_by_10000_before_multiplication():
    result = classical_solar_recalculation(2603)
    assert fraction(result["baseline_year_days"]) == Fraction("365.242349669203")
    assert fraction(result["recalibrated_year_days"]) == Fraction("365.244342041162105")
    assert (
        result["baseline_accumulated_days"]["truncated_decimal_12"]
        == FIXTURE["solar_example"]["baseline_product_printed"]
    )
    assert (
        result["recalibrated_accumulated_days"]["truncated_decimal_12"]
        == FIXTURE["solar_example"]["recalibrated_product_printed"]
    )
    assert result["is_source_calibration_example"]
    assert not result["lunar_calibration_derivation_accepted"]
    assert not result["modern_tropical_year_accuracy_accepted"]


def test_printed_year_products_never_round_through_binary_float():
    result = classical_solar_recalculation(2603)
    expected = Fraction("950731.022333144959315")
    assert fraction(result["recalibrated_accumulated_days"]) == expected
    assert Fraction(float(expected)) != expected
    large = classical_mean_cycle_arithmetic(2**60 + 137)
    assert fraction(large["mean_accumulated_days"]) == Fraction(
        (2**60 + 137) * 235 * 30 * 692, 703
    )
    assert not classical_solar_recalculation(2604)["is_source_calibration_example"]


@pytest.mark.parametrize("bad", [True, -1, 137.0, "137", None])
def test_no_civil_year_inference_or_noninteger_cycle_counts(bad):
    for method in (classical_mean_cycle_arithmetic, classical_solar_recalculation):
        with pytest.raises(ValueError):
            method(bad)


@pytest.mark.parametrize(
    "basis,civil,expected",
    [
        ("chinese_hko_utc08", "2025-03-04", "火"),
        ("japanese_naoj_historical_utc09", "1816-02-28", "水"),
    ],
)
def test_missing_host_boundary_cannot_be_reported_as_verified_utc08(
    basis, civil, expected
):
    context = calendar_mansion(civil, "12:00:00", "+09:00", calendar_basis=basis)
    assert day_evidence(context)["weekday"]["luminary"] == expected
    del context["calendar_timezone"]
    with pytest.raises(ValueError, match="须明确"):
        day_evidence(context)


def test_source_discrepancy_is_retained_and_one_weekday_is_not_epoch_acceptance():
    result = verify_recalculation()
    assert not result["errors"]
    assert len(result["decimal_product_controls"]) == 4
    candidate = result["final_quotient_candidate"]
    assert candidate["candidate_value"] == 235815
    assert candidate["exact_floor_quotient_from_printed_accumulated_days"] == 135815
    assert candidate["candidate_minus_exact_quotient"] == 100000
    assert candidate["status"] == "retained_transcription_or_source_discrepancy"
    assert not candidate["source_text_rewritten"]
    assert not candidate["independent_collation_complete"]
    control = result["one_lunar_label_weekday_control"]
    assert control["naoj_reference_date"] == "1816-02-28"
    assert control["printed_luminary"] == control["civil_weekday"]["luminary"] == "水"
    assert not result["original_tang_epoch_or_civil_conversion_accepted"]
    assert not result["full_secular_correction_implemented"]


def test_captures_fail_closed_when_image_bytes_change(tmp_path):
    (tmp_path / FIXTURE["captured_pages"][0]["file"]).write_bytes(b"wrong image")
    with pytest.raises(ValueError, match="fingerprint"):
        verify_recalculation(tmp_path)
