"""Explicit accumulation hypotheses, not an ancient calendar provider.

Offsets are inputs to an exploratory calculation. Matching a residue cannot
select an epoch, resolve a historical lunar date, or change a production board.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def accumulation_hypothesis(
    *,
    year_accumulation: int,
    chapter_years: int,
    chapter_months: int,
    month_numerator: int,
    day_denominator: int,
    month_offset: int,
    day_offset: int,
) -> dict[str, int | str]:
    parameters = locals().copy()
    for name, value in parameters.items():
        if type(value) is not int or value < (0 if name.endswith("offset") else 1):
            raise ValueError(
                f"Explicit integral accumulation hypothesis required: {name}"
            )
    completed_months, chapter_remainder = divmod(
        year_accumulation * chapter_months, chapter_years
    )
    counted_months = completed_months + month_offset
    completed_days, day_remainder = divmod(
        counted_months * month_numerator, day_denominator
    )
    return {
        **parameters,
        "completed_months": completed_months,
        "chapter_remainder": chapter_remainder,
        "counted_months": counted_months,
        "completed_days": completed_days,
        "day_remainder": day_remainder,
        "candidate_accumulation": completed_days + day_offset,
        "rounding": "floor at each division; offsets supplied, not adjudicated",
    }


def sexagenary_hypothesis(accumulation: int, *, jiazi_origin: int) -> str:
    """Compare both explicit 0/1 conventions without adjudicating 算外."""
    if (
        type(accumulation) is not int
        or accumulation < 1
        or type(jiazi_origin) is not int
        or jiazi_origin not in (0, 1)
    ):
        raise ValueError(
            "Positive accumulation and explicit Jiazi origin0 or1 required"
        )
    offset = (accumulation - jiazi_origin) % 60
    return "甲乙丙丁戊己庚辛壬癸"[offset % 10] + "子丑寅卯辰巳午未申酉戌亥"[offset % 12]


def mean_origin_hypothesis(
    *,
    year_accumulation: int,
    chapter_years: int,
    chapter_months: int,
    month_numerator: int,
    day_denominator: int,
    qi_denominator: int,
    annual_residue_numerator: int,
    month_year_shift: int,
    solstice_year_shift: int,
    whole_cycle_days_per_year: int,
) -> dict[str, Any]:
    """Trace exact remainder units and a conditional absolute-day lift.

    The solstice rule supplies a reduced day phase. Adding whole cycles per
    year is an explicit hypothesis, not proof of its original absolute epoch.
    A compatible interval therefore never selects a production year reading.
    """
    parameters = locals().copy()
    for name, value in parameters.items():
        if name.endswith("year_shift"):
            valid = type(value) is int and value in (-1, 0)
        else:
            valid = type(value) is int and value > 0
        if not valid:
            raise ValueError(f"Explicit exact mean-origin parameter required: {name}")
    if whole_cycle_days_per_year % 60:
        raise ValueError(
            "Explicit exact mean-origin lift must contain whole60-day cycles"
        )

    def ratio(value: Fraction) -> dict[str, int]:
        return {"numerator": value.numerator, "denominator": value.denominator}

    month_year = year_accumulation + month_year_shift
    winter_year = year_accumulation + solstice_year_shift
    months, chapter_remainder = divmod(month_year * chapter_months, chapter_years)
    days, day_remainder = divmod(months * month_numerator, day_denominator)
    month_length = Fraction(month_numerator, day_denominator)
    newmoon = Fraction(months * month_numerator, day_denominator)
    reduced_winter = Fraction(winter_year * annual_residue_numerator, qi_denominator)
    lifted_winter = winter_year * whole_cycle_days_per_year + reduced_winter
    interval = lifted_winter - newmoon
    modulo_interval = interval % 60
    annual = Fraction(chapter_months * month_numerator, chapter_years * day_denominator)
    lifted_annual = whole_cycle_days_per_year + Fraction(
        annual_residue_numerator, qi_denominator
    )
    identity = annual == lifted_annual
    return {
        **parameters,
        "month_counted_years": month_year,
        "solstice_counted_years": winter_year,
        "initial_mean_lunations": months,
        "chapter_remainder": chapter_remainder,
        "chapter_remainder_denominator": chapter_years,
        "chapter_remainder_unit": "fraction of a mean lunation after division by chapter_years; not days",
        "initial_day_accumulation_floor": days,
        "initial_day_small_remainder": day_remainder,
        "initial_day_small_remainder_denominator": day_denominator,
        "exact_initial_newmoon": ratio(newmoon),
        "same_year_annual_minus_newmoon": ratio(
            Fraction(chapter_remainder, chapter_years) * month_length
        ),
        "source_reduced_solstice": ratio(reduced_winter),
        "lifted_solstice": ratio(lifted_winter),
        "source_annual_identity_holds": identity,
        "unwrapped_solstice_minus_newmoon": ratio(interval),
        "modulo60_solstice_minus_newmoon": ratio(modulo_interval),
        "mean_lunation_days": ratio(month_length),
        "conditional_solstice_in_mean_month": identity and 0 <= interval < month_length,
        "modulo60_interval_within_one_mean_month": 0 <= modulo_interval < month_length,
        "unwrapped_epoch_adjudicated": False,
        "production_year_reading_selected": False,
        "scope": "Exact source-constant diagnostic. Modulo60 agreement cannot identify a year. Unwrapped containment is conditional on the explicit annual whole-cycle lift; neither restores intercalation or a civil date.",
    }


def decode_day_counter(
    value: int, *, encoding: str, epoch_ganzhi: str
) -> dict[str, Any]:
    """Decode an explicitly typed count; do not infer a source's encoding.

    The epoch name supplies only its sexagenary phase. Two epochs with the
    same name need not denote the same actual day or absolute accumulation.
    """
    if encoding not in ("completed_days", "one_based_day_number"):
        raise ValueError("Explicit day-counter encoding required")
    minimum = 0 if encoding == "completed_days" else 1
    if type(value) is not int or value < minimum:
        raise ValueError("Explicit integral day-counter value outside encoding domain")
    cycle = [
        "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
        for i in range(60)
    ]
    if type(epoch_ganzhi) is not str or epoch_ganzhi not in cycle:
        raise ValueError("Explicit valid sexagenary epoch name required")
    completed = value if encoding == "completed_days" else value - 1
    return {
        "value": value,
        "encoding": encoding,
        "epoch_ganzhi": epoch_ganzhi,
        "completed_days": completed,
        "one_based_day_number": completed + 1,
        "day_ganzhi": cycle[(cycle.index(epoch_ganzhi) + completed) % 60],
        "source_encoding_adjudicated": False,
        "absolute_epoch_identity_adjudicated": False,
        "scope": "Representation identity only; does not infer source 算外 semantics, a calendar date or equality of absolute epochs.",
    }


def lunar_day_counter_views(
    month_start_value: int,
    lunar_day: int,
    *,
    month_start_encoding: str,
    epoch_ganzhi: str,
) -> dict[str, Any]:
    """Keep lunar ordinal, elapsed offset and both equivalent counter views.

    The caller declares the initial quotient's interpretation. Month legality,
    intercalation and binding to any historical source are not inferred here.
    """
    if type(lunar_day) is not int or not 1 <= lunar_day <= 30:
        raise ValueError("Explicit lunar day ordinal1 through30 required")
    start = decode_day_counter(
        month_start_value, encoding=month_start_encoding, epoch_ganzhi=epoch_ganzhi
    )
    elapsed = lunar_day - 1
    completed = start["completed_days"] + elapsed
    views = {
        encoding: decode_day_counter(
            value, encoding=encoding, epoch_ganzhi=epoch_ganzhi
        )
        for encoding, value in (
            ("completed_days", completed),
            ("one_based_day_number", completed + 1),
        )
    }
    return {
        "month_start": start,
        "lunar_day_ordinal": lunar_day,
        "elapsed_days_from_month_start": elapsed,
        "completed_days": completed,
        "one_based_day_number": completed + 1,
        "day_ganzhi": views["completed_days"]["day_ganzhi"],
        "views": views,
        "both_views_preserve_same_day": views["completed_days"]["day_ganzhi"]
        == views["one_based_day_number"]["day_ganzhi"],
        "lunar_date_legality_adjudicated": False,
        "source_month_quotient_encoding_adjudicated": False,
        "scope": "ordinal d supplies elapsed d-1; elapsed e and numbered day e+1 are coupled encodings. No fixed date correction, source epoch choice or historical calendar restoration.",
    }
