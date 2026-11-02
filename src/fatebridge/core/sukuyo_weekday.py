"""Civil weekdays and a separate, explicitly counted manuscript algorithm.

T30107's selected integer formula is not a conversion from a modern birth date.
In particular its later fractional/secular recalculation must not be spliced
into the general rule to make two different computations appear identical.
"""

from __future__ import annotations

from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_t30107_weekday_arithmetic.json"
)
RECALCULATION_SOURCE = SOURCE.with_name("sukuyo_t30107_recalculation.json")
PRINTED_CHAPTER_SOURCE = SOURCE.with_name("sukuyo_wakita_weekday.json")
CALIBRATION_SOURCE = SOURCE.with_name("sukuyo_t30107_calibration.json")


def _nonnegative_count(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name}须为明确的非负整数积算，不接受民用日期猜配")


def _fraction_record(value: Fraction) -> dict[str, int | str]:
    """Serialize exact values; printed decimals never feed another operation."""
    scale = 10**12
    magnitude = abs(value.numerator)
    truncated = magnitude * scale // value.denominator
    rounded = (2 * magnitude * scale + value.denominator) // (2 * value.denominator)

    def decimal(integer: int) -> str:
        whole, tail = divmod(integer, scale)
        sign = "-" if value < 0 and integer else ""
        return f"{sign}{whole}.{tail:012d}"

    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "truncated_decimal_12": decimal(truncated),
        "rounded_decimal_12": decimal(rounded),
    }


def classical_source_year_count(named_year_number: int) -> dict[str, Any]:
    """The printed add/subtract-year instruction, not a civil-date conversion.

    The argument is the CE number labelling the named Chinese/Japanese year,
    not a Gregorian instant or a claim that its first day is 1 January.
    """
    _nonnegative_count(named_year_number, "named_year_number")
    if not 1 <= named_year_number <= 9999:
        raise ValueError("具名年份仅接受1..9999的纪年标签，不外推历元前日期")
    source = load_source(PRINTED_CHAPTER_SOURCE)
    rule = source.data["year_count_rule"]
    delta = named_year_number - rule["anchor_year_number"]
    elapsed = rule["anchor_elapsed_years"] + delta
    return {
        "named_year_number": named_year_number,
        "anchor_named_year": rule["anchor_named_year"],
        "anchor_year_number": rule["anchor_year_number"],
        "anchor_elapsed_years": rule["anchor_elapsed_years"],
        "year_difference": delta,
        "elapsed_years": elapsed,
        "algebraic_zero_count_year_number": rule["anchor_year_number"]
        - rule["anchor_elapsed_years"],
        "ruleset_id": source.data["id"],
        "source_bundle_sha256": source.sha256,
        "source_url": source.data["catalogue_url"],
        "locator": source.data["locator"],
        "scope": source.data["scope"],
        "civil_epoch_date_accepted": False,
        "host_lunar_month_mapping_accepted": False,
        "applied_to_primary_calendar": False,
    }


def _selected_decimal_interval(value: str, scale: int = 1) -> tuple[Fraction, Fraction]:
    """One final decimal unit either side; no fitted tolerances."""
    precision = len(value.partition(".")[2])
    center = Fraction(value) / scale
    unit = Fraction(1, scale * 10**precision)
    return center - unit, center + unit


def classical_calibration_precision() -> dict[str, Any]:
    """Replay selected printed intermediates and retain incompatible precision.

    Each relation uses the precision stated by its own input. A low-precision
    earlier drift cannot be used to excuse over-precise later intermediates.
    """
    source = load_source(CALIBRATION_SOURCE)
    rule = source.data
    mean_record = classical_mean_cycle_arithmetic(rule["elapsed_cycles"])
    nominal = mean_record["nominal_days"]
    if (
        nominal != rule["nominal_days"]
        or mean_record["elapsed_years"] != rule["elapsed_years"]
    ):
        raise ValueError("Selected calibration nominal day/year counts changed")
    mean_value = mean_record["mean_accumulated_days"]
    mean = Fraction(mean_value["numerator"], mean_value["denominator"])
    drift = _selected_decimal_interval(rule["printed_drift_days"])
    correction = _selected_decimal_interval(rule["printed_per_nominal_day_correction"])
    omission = _selected_decimal_interval(
        rule["printed_scaled_omission_coefficient"], rule["day_scale"]
    )
    corrected_mean = _selected_decimal_interval(rule["printed_corrected_mean_days"])
    revised_year = _selected_decimal_interval(
        rule["printed_recalibrated_scaled_year"], rule["day_scale"]
    )
    mean_rule = load_source(RECALCULATION_SOURCE).data["mean_cycle"]
    base_omission = Fraction(
        mean_rule["omission_numerator"], mean_rule["omission_denominator"]
    )

    def relation(
        name: str,
        predicted: tuple[Fraction, Fraction],
        printed: tuple[Fraction, Fraction],
    ) -> dict[str, Any]:
        compatible = max(predicted[0], printed[0]) <= min(predicted[1], printed[1])
        return {
            "relation": name,
            "calculated_interval": [_fraction_record(v) for v in predicted],
            "printed_interval": [_fraction_record(v) for v in printed],
            "compatible_at_selected_decimal_precision": compatible,
        }

    relations = [
        relation(
            "drift_divided_by_nominal_days",
            (drift[0] / nominal, drift[1] / nominal),
            correction,
        ),
        relation(
            "base_omission_plus_printed_correction",
            (base_omission + correction[0], base_omission + correction[1]),
            omission,
        ),
        relation(
            "nominal_days_minus_printed_omissions",
            (nominal * (1 - omission[1]), nominal * (1 - omission[0])),
            corrected_mean,
        ),
        relation(
            "mean_days_minus_printed_drift",
            (mean - drift[1], mean - drift[0]),
            corrected_mean,
        ),
        relation(
            "corrected_mean_divided_by_elapsed_years",
            (
                corrected_mean[0] / rule["elapsed_years"],
                corrected_mean[1] / rule["elapsed_years"],
            ),
            revised_year,
        ),
    ]
    drift_center = Fraction(rule["printed_drift_days"])
    omission_from_correction = base_omission + Fraction(
        rule["printed_per_nominal_day_correction"]
    )
    printed_omission = (
        Fraction(rule["printed_scaled_omission_coefficient"]) / rule["day_scale"]
    )
    correct_denominator = drift_center / nominal
    incorrect_denominator = drift_center / mean
    return {
        "ruleset_id": rule["id"],
        "source_bundle_sha256": source.sha256,
        "source_url": rule["catalogue_url"],
        "locator": rule["locator"],
        "precision_policy": rule["precision_policy"],
        "relations": relations,
        "selected_precision_discrepancies": [
            r["relation"]
            for r in relations
            if not r["compatible_at_selected_decimal_precision"]
        ],
        "printed_omission_minus_calculated_rate": _fraction_record(
            printed_omission - omission_from_correction
        ),
        "accumulated_day_difference_between_printed_intermediates": _fraction_record(
            nominal * (omission_from_correction - printed_omission)
        ),
        "denominator_counterexample": {
            "source_nominal_days": nominal,
            "source_mean_days": _fraction_record(mean),
            "correction_from_source_nominal_days": _fraction_record(
                correct_denominator
            ),
            "wrong_correction_from_mean_days": _fraction_record(incorrect_denominator),
            "accumulated_day_error_if_mean_replaces_nominal": _fraction_record(
                nominal * (incorrect_denominator - correct_denominator)
            ),
            "is_historical_observation": False,
        },
        "independent_transcription_accepted": False,
        "complete_lunar_secular_derivation_accepted": False,
        "civil_date_conversion_accepted": False,
        "applied_to_primary_calendar": False,
        "scope": rule["scope"],
    }


def classical_mean_cycle_arithmetic(elapsed_cycles: int) -> dict[str, Any]:
    """Selected later fractional rule, restricted to complete 19-year cycles."""
    _nonnegative_count(elapsed_cycles, "elapsed_cycles")
    source = load_source(RECALCULATION_SOURCE)
    rule = source.data["mean_cycle"]
    months = elapsed_cycles * (
        rule["regular_months_per_cycle"] + rule["intercalary_months_per_cycle"]
    )
    nominal = months * rule["nominal_days_per_month"]
    omitted = Fraction(
        nominal * rule["omission_numerator"], rule["omission_denominator"]
    )
    mean = nominal - omitted
    return {
        "ruleset_id": source.data["id"],
        "elapsed_cycles": elapsed_cycles,
        "elapsed_years": elapsed_cycles * rule["elapsed_years_per_cycle"],
        "accumulated_months": months,
        "nominal_days": nominal,
        "omission_days": _fraction_record(omitted),
        "mean_accumulated_days": _fraction_record(mean),
        "omission_bias": rule["omission_bias"],
        "source_bundle_sha256": source.sha256,
        "locator": rule["locator"],
        "scope": rule["scope"],
        "later_secular_correction_applied": False,
        "general_integer_algorithm_applied": False,
        "civil_date_conversion_accepted": False,
        "applied_to_primary_calendar": False,
    }


def classical_solar_recalculation(elapsed_years: int) -> dict[str, Any]:
    """Multiply the two printed coefficients without adopting their calibration.

    The unit is the manuscript's 10,000 scaled units per day. In particular,
    this does not convert an astronomical year into a Gregorian date or import
    the printed decimals as modern measurements of the tropical year.
    """
    _nonnegative_count(elapsed_years, "elapsed_years")
    source = load_source(RECALCULATION_SOURCE)
    rule = source.data["solar_recalculation"]
    baseline = Fraction(rule["baseline_scaled_year"]) / rule["scaled_day_unit"]
    recalibrated = Fraction(rule["recalibrated_scaled_year"]) / rule["scaled_day_unit"]
    return {
        "ruleset_id": source.data["id"],
        "elapsed_years": elapsed_years,
        "baseline_year_days": _fraction_record(baseline),
        "recalibrated_year_days": _fraction_record(recalibrated),
        "baseline_accumulated_days": _fraction_record(baseline * elapsed_years),
        "recalibrated_accumulated_days": _fraction_record(recalibrated * elapsed_years),
        "coefficient_difference_days": _fraction_record(recalibrated - baseline),
        "accumulated_difference_days": _fraction_record(
            (recalibrated - baseline) * elapsed_years
        ),
        "is_source_calibration_example": elapsed_years
        == rule["calibration_elapsed_years"],
        "source_bundle_sha256": source.sha256,
        "locator": rule["locator"],
        "scope": rule["scope"],
        "lunar_calibration_derivation_accepted": False,
        "modern_tropical_year_accuracy_accepted": False,
        "civil_date_conversion_accepted": False,
        "applied_to_primary_calendar": False,
    }


def civil_weekday(calendar_date: str, calendar_timezone: str) -> dict[str, Any]:
    if calendar_timezone not in {"UTC+08:00", "UTC+09:00"}:
        raise ValueError("宿曜七曜须明确已支持的UTC+08或UTC+09宿主历日")
    weekday = (date.fromisoformat(calendar_date).weekday() + 1) % 7
    return {
        "index_sunday_zero": weekday,
        "luminary": "日月火水木金土"[weekday],
        "basis": (
            "modern_utc_plus09_civil_midnight"
            if calendar_timezone == "UTC+09:00"
            else "modern_utc_plus08_civil_midnight"
        ),
        "classical_daybreak_boundary_acceptance": False,
        "classical_boundary_locator": "T21n1299_p0399b25-27",
    }


def classical_weekday_arithmetic(
    elapsed_years: int, elapsed_months: int, elapsed_days: int
) -> dict[str, Any]:
    """Reproduce selected counted inputs, with every Euclidean remainder.

    Inputs are already elapsed counts in this source's convention, never a
    Gregorian year/month/day. No input defaults or implicit epoch conversion.
    Zero at the epoch is allowed; a negative computed day is not interpreted.
    """
    for name, value in (
        ("elapsed_years", elapsed_years),
        ("elapsed_months", elapsed_months),
        ("elapsed_days", elapsed_days),
    ):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name}须为已核定的非负整数积算，不接受民用日期猜配")
    if elapsed_months > 12 or elapsed_days > 30:
        raise ValueError("入年月数须为0..12，入月日数须为0..30的明确积算")
    source = load_source(SOURCE)
    constants = source.data["general_formula"]["constants"]
    regular_months = elapsed_years * constants["months_per_year"]
    entered_regular_months = regular_months + elapsed_months
    intercalation_numerator = (
        entered_regular_months * constants["intercalation_numerator"]
    )
    intercalary_months, intercalation_remainder = divmod(
        intercalation_numerator, constants["intercalation_denominator"]
    )
    accumulated_months = entered_regular_months + intercalary_months
    nominal_days = (
        accumulated_months * constants["nominal_days_per_month"] + elapsed_days
    )
    omission_numerator = (
        nominal_days * constants["omission_numerator"] + constants["omission_bias"]
    )
    omitted_days, omission_remainder = divmod(
        omission_numerator, constants["omission_denominator"]
    )
    accumulated_days = nominal_days - omitted_days
    if accumulated_days < 0:
        raise ValueError("所选原式积日为负，未裁定历元前的余数及计数规则")
    weekday_remainder = accumulated_days % 7
    sexagenary_remainder = accumulated_days % 60
    cycle_index = (40 + accumulated_days - 1) % 60  # 甲辰 counts as one.
    return {
        "ruleset_id": source.data["id"],
        "status": "computed_from_explicit_elapsed_counts",
        "inputs": {
            "elapsed_years": elapsed_years,
            "elapsed_months": elapsed_months,
            "elapsed_days": elapsed_days,
        },
        "trace": {
            "regular_months": regular_months,
            "entered_regular_months": entered_regular_months,
            "intercalation_numerator": intercalation_numerator,
            "intercalation_denominator": constants["intercalation_denominator"],
            "intercalary_months": intercalary_months,
            "intercalation_remainder": intercalation_remainder,
            "accumulated_months": accumulated_months,
            "nominal_days": nominal_days,
            "omission_numerator": omission_numerator,
            "omission_denominator": constants["omission_denominator"],
            "omitted_days": omitted_days,
            "omission_remainder": omission_remainder,
            "accumulated_days": accumulated_days,
            "weekday_remainder": weekday_remainder,
            "sexagenary_remainder": sexagenary_remainder,
        },
        "luminary": "日月火水木金土"[weekday_remainder],
        "sexagenary_label": "甲乙丙丁戊己庚辛壬癸"[cycle_index % 10]
        + "子丑寅卯辰巳午未申酉戌亥"[cycle_index % 12],
        "counting": {
            "weekday_first_count": "月",
            "weekday_zero_remainder": "日",
            "sexagenary_first_count": "甲辰",
            "sexagenary_zero_remainder": "癸卯",
            "rounding": "each_division_quotient_before_subtraction; retain_remainders",
        },
        "source_url": source.data["catalogue_url"],
        "locator": source.data["general_formula"]["locator"],
        "source_bundle_sha256": source.sha256,
        "source_manifest_sha256": source.data["manifest_sha256"],
        "civil_date_conversion_evaluated": False,
        "historical_epoch_identity_accepted": False,
        "later_fractional_recalculation_applied": False,
        "classical_daybreak_or_hourly_sequence_accepted": False,
        "applied_to_primary_calendar": False,
        "scope": source.data["scope"],
    }
